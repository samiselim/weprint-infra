import pulumi
import pulumi_aws as aws

def create_monitoring(instance_id, distribution_id, stack="dev", alert_email=None):
    # 1. Create SNS Topic for Alerts
    topic = aws.sns.Topic(f"weprint-alerts-{stack}",
        display_name=f"We-Print Infrastructure Alerts - {stack}")

    # 2. Add Email Subscription
    if alert_email:
        aws.sns.TopicSubscription(f"weprint-alerts-email-{stack}",
            topic=topic.arn,
            protocol="email",
            endpoint=alert_email)

    # 3. EC2 System Alarms (CPU, Memory, Disk)
    aws.cloudwatch.MetricAlarm(f"weprint-cpu-high-{stack}",
        comparison_operator="GreaterThanOrEqualToThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when CPU exceeds 80% for 10 minutes",
        alarm_actions=[topic.arn],
        dimensions={"InstanceId": instance_id})

    aws.cloudwatch.MetricAlarm(f"weprint-mem-high-{stack}",
        comparison_operator="GreaterThanOrEqualToThreshold",
        evaluation_periods=2,
        metric_name="mem_used_percent",
        namespace="CWAgent",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when Memory exceeds 80% for 10 minutes",
        alarm_actions=[topic.arn],
        dimensions={"InstanceId": instance_id})

    aws.cloudwatch.MetricAlarm(f"weprint-disk-high-{stack}",
        comparison_operator="GreaterThanOrEqualToThreshold",
        evaluation_periods=2,
        metric_name="disk_used_percent",
        namespace="CWAgent",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when Disk exceeds 80% for 10 minutes",
        alarm_actions=[topic.arn],
        dimensions={
            "InstanceId": instance_id,
            "path": "/",
            "device": "nvme0n1p1",
            "fstype": "xfs"
        })

    # 4. CloudFront Uptime Monitoring (Non-Intrusive)
    # Monitor 5xx Error Rate to detect if the domain/backend is down
    aws.cloudwatch.MetricAlarm(f"weprint-uptime-5xx-{stack}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=1,
        metric_name="TotalErrorRate",
        namespace="AWS/CloudFront",
        period=300,
        statistic="Average",
        threshold=5, # Trigger if >5% of requests are errors
        alarm_description="Alarm if frontend or backend returns high error rate (downtime detection)",
        alarm_actions=[topic.arn],
        dimensions={
            "DistributionId": distribution_id,
            "Region": "Global"
        })

    return topic
