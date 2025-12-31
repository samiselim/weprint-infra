import pulumi
import pulumi_aws as aws
import vpc
import security
import database
import backend_ec2
import frontend_s3_cf
import monitoring

# Load Configuration
config = pulumi.Config()
stack = pulumi.get_stack()

# Environment-specific settings
instance_type = config.get("instance_type") or "t3.micro"
db_instance_class = config.get("db_instance_class") or "db.t3.micro"
ebs_size = config.get_int("ebs_size") or 20
alert_email = config.get("alert_email")

# 1. Create Networking
vpc_resource, public_subnet, private_subnet, private_subnet_2 = vpc.create_vpc(stack)

# 2. Create Security Groups
backend_sg, db_sg = security.create_security_groups(vpc_resource.id, stack)

# 3. Create Database
db_instance = database.create_database([private_subnet.id, private_subnet_2.id], [db_sg.id], db_instance_class, stack)

# 4. Create Backend (EC2)
backend_server, backend_eip = backend_ec2.create_backend(
    public_subnet.id, 
    [backend_sg.id], 
    db_instance.address, 
    db_instance.username, 
    db_instance.password, 
    db_instance.db_name,
    instance_type,
    ebs_size,
    stack
)

# 5. Create Frontend (S3 + CloudFront)
bucket, distribution = frontend_s3_cf.create_frontend(backend_eip.public_dns, stack)

# 6. Create Monitoring & Alarms
# CloudFront metrics are only in us-east-1
us_east_1 = aws.Provider("us-east-1", region="us-east-1")
monitoring_topic = monitoring.create_monitoring(backend_server.id, distribution.id, stack, alert_email, us_east_1)

# Exports
pulumi.export("backend_public_ip", backend_eip.public_ip)
pulumi.export("backend_public_dns", backend_eip.public_dns)
pulumi.export("database_endpoint", db_instance.address)
pulumi.export("frontend_bucket_name", bucket.id)
pulumi.export("cloudfront_url", distribution.domain_name)
