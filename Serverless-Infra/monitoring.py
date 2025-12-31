import pulumi
import pulumi_aws as aws
import json

def create_monitoring(instance_id, distribution_id, stack="dev", alert_email=None, cloudfront_provider=None):
    # --- 1. SNS Setup ---
    # Topic for local (Ireland) beauty-formatted alerts
    topic = aws.sns.Topic(f"weprint-alerts-{stack}",
        display_name=f"We-Print Alerts - {stack}")

    if alert_email:
        aws.sns.TopicSubscription(f"weprint-alerts-email-{stack}",
            topic=topic.arn,
            protocol="email",
            endpoint=alert_email)

    # Topic for global (US) beauty-formatted alerts
    global_topic_arn = None
    if cloudfront_provider and alert_email:
        global_topic = aws.sns.Topic(f"weprint-global-alerts-{stack}",
            display_name=f"We-Print Global Alerts - {stack}",
            opts=pulumi.ResourceOptions(provider=cloudfront_provider))
        
        aws.sns.TopicSubscription(f"weprint-global-email-{stack}",
            topic=global_topic.arn,
            protocol="email",
            endpoint=alert_email,
            opts=pulumi.ResourceOptions(provider=cloudfront_provider))
        global_topic_arn = global_topic.arn

    # --- 2. Lambda Role & Policy (Reusable) ---
    def create_lambda_role(name, region_provider=None):
        role = aws.iam.Role(f"weprint-lambda-role-{name}-{stack}",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Effect": "Allow",
                }]
            }),
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)

        aws.iam.RolePolicyAttachment(f"weprint-lambda-log-policy-{name}-{stack}",
            role=role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)
        
        aws.iam.RolePolicy(f"weprint-lambda-sns-policy-{name}-{stack}",
            role=role.name,
            policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sns:Publish",
                    "Resource": "*",
                    "Effect": "Allow",
                }]
            }),
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)
        return role

    # --- 3. Lambda Implementation ---
    def create_formatter_lambda(name, target_topic_arn, region_provider=None):
        role = create_lambda_role(name, region_provider)
        
        # Inline Lambda code for the formatter
        lambda_code = """
import boto3
import json
import os

def handler(event, context):
    sns = boto3.client('sns')
    detail = event.get('detail', {})
    alarm_name = detail.get('alarmName', 'Unknown Alarm')
    new_state = detail.get('state', {}).get('value', 'Unknown State')
    reason = detail.get('state', {}).get('reason', 'No details provided.')
    time = event.get('time', 'Unknown Time')
    
    emoji = "🔴" if new_state == "ALARM" else "🟢"
    status_label = "CRITICAL ALERT" if new_state == "ALARM" else "RECOVERY"
    
    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        f" {emoji}  WE-PRINT INFRASTRUCTURE: {status_label}\\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n"
        f"📍  ENVIRONMENT: {os.environ['STACK_NAME']}\\n"
        f"🚨  ALARM:       {alarm_name}\\n"
        f"📊  STATUS:      {new_state}\\n"
        f"⏰  TIME:        {time}\\n\\n"
        f"📝  DETAILS:\\n"
        f"----------------------------------------------------\\n"
        f"{reason}\\n"
        f"----------------------------------------------------\\n\\n"
        f"👉  ACTION: Please check your AWS Managed Console for more information.\\n\\n"
        f"We-Print DevOps 🚀"
    )
    
    subject = f"{emoji} [{status_label}] {alarm_name}"
    
    sns.publish(
        TopicArn=os.environ['SNS_TOPIC_ARN'],
        Message=message,
        Subject=subject
    )
"""
        
        fn = aws.lambda_.Function(f"weprint-formatter-{name}-{stack}",
            runtime="python3.11",
            handler="index.handler",
            role=role.arn,
            code=pulumi.AssetArchive({
                "index.py": pulumi.StringAsset(lambda_code)
            }),
            environment={
                "variables": {
                    "SNS_TOPIC_ARN": target_topic_arn,
                    "STACK_NAME": stack.upper()
                }
            },
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)
        
        # EventBridge Rule to trigger Lambda
        rule = aws.cloudwatch.EventRule(f"weprint-format-rule-{name}-{stack}",
            description="Format CloudWatch alarms into beautiful emails",
            event_pattern=json.dumps({
                "source": ["aws.cloudwatch"],
                "detail-type": ["CloudWatch Alarm State Change"],
                "detail": {
                    "alarmName": [{"prefix": "weprint-"}]
                }
            }),
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)
        
        aws.lambda_.Permission(f"weprint-lambda-prm-{name}-{stack}",
            action="lambda:InvokeFunction",
            function=fn.name,
            principal="events.amazonaws.com",
            source_arn=rule.arn,
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)
        
        aws.cloudwatch.EventTarget(f"weprint-format-target-{name}-{stack}",
            rule=rule.name,
            arn=fn.arn,
            opts=pulumi.ResourceOptions(provider=region_provider) if region_provider else None)

    # Instantiate formatters
    create_formatter_lambda("local", topic.arn)
    if cloudfront_provider:
        create_formatter_lambda("global", global_topic_arn, cloudfront_provider)

    # --- 4. EC2 System Alarms (CPU, Memory, Disk) ---
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

    # --- 5. CloudFront Uptime Monitoring ---
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
