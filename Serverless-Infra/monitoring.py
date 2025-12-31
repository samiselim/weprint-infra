import pulumi
import pulumi_aws as aws
import json

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

    # Allow EventBridge to publish to this SNS Topic
    aws.sns.TopicPolicy(f"weprint-sns-policy-{stack}",
        arn=topic.arn,
        policy=topic.arn.apply(lambda arn: json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sns:Publish",
                "Resource": arn
            }]
        })))

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
        
        # Policy for Global Topic
        aws.sns.TopicPolicy(f"weprint-global-sns-policy-{stack}",
            arn=global_topic.arn,
            policy=global_topic.arn.apply(lambda arn: json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sns:Publish",
                    "Resource": arn
                }]
            })),
            opts=pulumi.ResourceOptions(provider=cloudfront_provider))
        
        global_topic_arn = global_topic.arn

    # 4. EventBridge Rules for Readable Emails
    def create_readable_rule(name, sns_topic_arn, region_provider=None):
        rule = aws.cloudwatch.EventRule(f"weprint-rule-{name}-{stack}",
            description=f"Rule to format {name} alerts for {stack}",
            event_pattern=json.dumps({
                "source": ["aws.cloudwatch"],
                "detail-type": ["CloudWatch Alarm State Change"],
                "detail": {
                    "state": {"value": ["ALARM"]},
                    "alarmName": [{"prefix": "weprint-"}]
                }
            }),
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)

        aws.cloudwatch.EventTarget(f"weprint-target-{name}-{stack}",
            rule=rule.name,
            arn=sns_topic_arn,
            input_transformer=aws.cloudwatch.EventTargetInputTransformerArgs(
                input_paths={
                    "alarmName": "$.detail.alarmName",
                    "newState": "$.detail.state.value",
                    "reason": "$.detail.state.reason",
                    "time": "$.time"
                },
                input_template=json.dumps("[weprint-<newState>] Alert Triggered!\n\nAlarm: <alarmName>\nTime: <time>\n\nReason:\n<reason>\n\nAction: Please investigate the infrastructure in the AWS Console.")
            ),
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)

    # Register rules for both regions
    create_readable_rule("local", topic.arn) # Ireland
    if cloudfront_provider:
        create_readable_rule("global", global_topic_arn, cloudfront_provider) # US

    # 5. EC2 System Alarms (CPU, Memory, Disk) - in eu-west-1
    # Note: We NO LONGER put topic.arn in alarm_actions because EventBridge handles the email
    aws.cloudwatch.MetricAlarm(f"weprint-cpu-high-{stack}",
        comparison_operator="GreaterThanOrEqualToThreshold",
        evaluation_periods=2,
        metric_name="CPUUtilization",
        namespace="AWS/EC2",
        period=300,
        statistic="Average",
        threshold=80,
        alarm_description="Alarm when CPU exceeds 80% for 10 minutes",
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
        treat_missing_data="notBreaching",
        dimensions={
            "InstanceId": instance_id,
            "path": "/",
            "device": "nvme0n1p1",
            "fstype": "xfs"
        })

    # 6. CloudFront Uptime Monitoring (Non-Intrusive) - in us-east-1
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
        treat_missing_data="notBreaching", # This ensures the alarm stays "OK" when traffic is zero
        dimensions={
            "DistributionId": distribution_id,
            "Region": "Global"
        },
        opts=pulumi.ResourceOptions(provider=cloudfront_provider) if cloudfront_provider else None)

    return topic
