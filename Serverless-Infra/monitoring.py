import pulumi
import pulumi_aws as aws

def create_monitoring(instance_id, distribution_id, stack="dev", alert_email=None, cloudfront_provider=None):
    # 1. Create SNS Topic for Alerts (Local Region - eu-west-1)
    topic = aws.sns.Topic(f"weprint-alerts-{stack}",
        display_name=f"We-Print Infrastructure Alerts - {stack}")

    # 2. Add Email Subscription (Local Region)
    if alert_email:
        aws.sns.TopicSubscription(f"weprint-alerts-email-{stack}",
            topic=topic.arn,
            protocol="email",
            endpoint=alert_email)

    # 3. Create SNS Topic & Subscription in us-east-1 (For CloudFront Alarms)
    # This is because Alarms in us-east-1 MUST trigger Topics in us-east-1
    global_topic_arn = topic.arn
    if cloudfront_provider and alert_email:
        global_topic = aws.sns.Topic(f"weprint-global-alerts-{stack}",
            display_name=f"We-Print Global Uptime Alerts - {stack}",
            opts=pulumi.ResourceOptions(provider=cloudfront_provider))
        
        aws.sns.TopicSubscription(f"weprint-global-email-{stack}",
            topic=global_topic.arn,
            protocol="email",
            endpoint=alert_email,
            opts=pulumi.ResourceOptions(provider=cloudfront_provider))
        global_topic_arn = global_topic.arn

    # 4. EC2 System Alarms (CPU, Memory, Disk) - in eu-west-1
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
        treat_missing_data="notBreaching",
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
        treat_missing_data="notBreaching",
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
        treat_missing_data="notBreaching",
        dimensions={
            "InstanceId": instance_id,
            "path": "/",
            "device": "nvme0n1p1",
            "fstype": "xfs"
        })

    # 5. CloudFront Uptime Monitoring (Non-Intrusive) - in us-east-1
    # Monitor 5xx Error Rate to detect if the domain/backend is down
    # NOTE: CloudFront metrics are ONLY available in us-east-1
    aws.cloudwatch.MetricAlarm(f"weprint-uptime-5xx-{stack}",
        comparison_operator="GreaterThanThreshold",
        evaluation_periods=1,
        metric_name="TotalErrorRate",
        namespace="AWS/CloudFront",
        period=300,
        statistic="Average",
        threshold=5, # Trigger if >5% of requests are errors
        alarm_description="Alarm if frontend or backend returns high error rate (downtime detection)",
        alarm_actions=[global_topic_arn], # Use the us-east-1 topic!
        treat_missing_data="notBreaching", # This ensures the alarm stays "OK" when traffic is zero
        dimensions={
            "DistributionId": distribution_id,
            "Region": "Global"
        },
        opts=pulumi.ResourceOptions(provider=cloudfront_provider) if cloudfront_provider else None)

    return topic
