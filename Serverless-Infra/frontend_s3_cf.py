import pulumi
import pulumi_aws as aws

def create_frontend(backend_dns, stack="dev"):
    # Create S3 Bucket (Must be globally unique)
    bundle_name = f"weprint-frontend-{stack}"
    bucket = aws.s3.Bucket(bundle_name,
        tags={
            "Name": bundle_name,
            "Environment": stack
        })

    # Create Origin Access Control (OAC)
    oac = aws.cloudfront.OriginAccessControl(f"weprint-oac-{stack}",
        description=f"OAC for We-Print Frontend - {stack}",
        origin_access_control_origin_type="s3",
        signing_behavior="always",
        signing_protocol="sigv4")

    # CloudFront Distribution
    distribution = aws.cloudfront.Distribution(f"weprint-distribution-{stack}",
        enabled=True,
        origins=[
            # S3 Origin
            aws.cloudfront.DistributionOriginArgs(
                origin_id=bucket.arn,
                domain_name=bucket.bucket_regional_domain_name,
                origin_access_control_id=oac.id,
            ),
            # Backend EC2 Origin
            aws.cloudfront.DistributionOriginArgs(
                origin_id="backend-ec2",
                domain_name=backend_dns,
                custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                    http_port=80,
                    https_port=443,
                    origin_protocol_policy="http-only", # EC2 only has HTTP (80)
                    origin_ssl_protocols=["TLSv1.2"],
                ),
                # Optional: Add custom headers for Laravel
                custom_headers=[
                    aws.cloudfront.DistributionOriginCustomHeaderArgs(
                        name="X-Forwarded-Proto",
                        value="https",
                    ),
                ],
            )
        ],
        default_root_object="index.html",
        # Default Behavior (S3 Frontend)
        default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
            target_origin_id=bucket.arn,
            viewer_protocol_policy="redirect-to-https",
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            cached_methods=["GET", "HEAD"],
            forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
                query_string=False,
                cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                    forward="none",
                ),
            ),
            min_ttl=0,
            default_ttl=3600,
            max_ttl=86400,
        ),
        # Backend API Behavior
        ordered_cache_behaviors=[
            aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
                path_pattern="/api/*",
                target_origin_id="backend-ec2",
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                cached_methods=["GET", "HEAD", "OPTIONS"],
                forwarded_values=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesArgs(
                    query_string=True,
                    headers=["*"], # Forward all headers to backend
                    cookies=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesCookiesArgs(
                        forward="all",
                    ),
                ),
                min_ttl=0,
                default_ttl=0, # Do not cache API responses
                max_ttl=0,
                compress=True, # Enable compression for API responses
            ),
            # Optional: Add storage behavior if you serve files
            aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
                path_pattern="/user/*",
                target_origin_id="backend-ec2",
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                cached_methods=["GET", "HEAD"],
                forwarded_values=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesArgs(
                    query_string=True,
                    headers=[
                        "Authorization", 
                        "Origin", 
                        "Accept", 
                        "X-Requested-With",
                        "X-CSRF-Token"
                    ],
                    cookies=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesCookiesArgs(
                        forward="all",
                    ),
                ),
                min_ttl=0,
                default_ttl=0,
                max_ttl=0,
                compress=True,
            ),
            aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
                path_pattern="/orders_files/*",
                target_origin_id="backend-ec2",
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD", "OPTIONS"],
                cached_methods=["GET", "HEAD"],
                forwarded_values=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesArgs(
                    query_string=False,
                    cookies=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesCookiesArgs(
                        forward="none",
                    ),
                ),
                min_ttl=0,
                default_ttl=86400, # Cache files for 24 hours to save EC2 bandwidth
                max_ttl=31536000,
                compress=True,
            ),
            aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
                path_pattern="/images/*",
                target_origin_id="backend-ec2",
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD", "OPTIONS"],
                cached_methods=["GET", "HEAD"],
                forwarded_values=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesArgs(
                    query_string=False,
                    cookies=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesCookiesArgs(
                        forward="none",
                    ),
                ),
                min_ttl=0,
                default_ttl=86400, # Cache for 1 day
                max_ttl=31536000,
                compress=True,
            ),

        ],
        # SPA Routing: Redirect 403/404 to index.html
        custom_error_responses=[
            aws.cloudfront.DistributionCustomErrorResponseArgs(
                error_code=403,
                response_code=200,
                response_page_path="/index.html",
            ),
            aws.cloudfront.DistributionCustomErrorResponseArgs(
                error_code=404,
                response_code=200,
                response_page_path="/index.html",
            ),
        ],
        restrictions=aws.cloudfront.DistributionRestrictionsArgs(
            geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                restriction_type="none",
            ),
        ),
        viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
            cloudfront_default_certificate=True,
        ),
        tags={
            "Name": f"weprint-distribution-{stack}",
            "Environment": stack
        })

    # Allow CloudFront to access S3 Bucket (Bucket Policy)
    bucket_policy = aws.s3.BucketPolicy(f"weprint-bucket-policy-{stack}",
        bucket=bucket.id,
        policy=pulumi.Output.all(bucket.arn, distribution.arn).apply(
            lambda args: f"""{{
                "Version": "2012-10-17",
                "Statement": [{{
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {{
                        "Service": "cloudfront.amazonaws.com"
                    }},
                    "Action": "s3:GetObject",
                    "Resource": "{args[0]}/*",
                    "Condition": {{
                        "StringEquals": {{
                            "AWS:SourceArn": "{args[1]}"
                        }}
                    }}
                }}]
            }}"""
        ))

    # Export important values
    pulumi.export("bucket_name", bucket.id)
    pulumi.export("cloudfront_domain", distribution.domain_name)
    pulumi.export("cloudfront_distribution_id", distribution.id)

    return bucket, distribution