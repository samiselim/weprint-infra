import pulumi
import vpc
import security
import database
import backend_ec2
import frontend_s3_cf

# 1. Create Networking
vpc_resource, public_subnet, private_subnet, private_subnet_2 = vpc.create_vpc()

# 2. Create Security Groups
backend_sg, db_sg = security.create_security_groups(vpc_resource.id)

# 3. Create Database
# Using both private subnets for the Subnet Group (RDS requires at least 2 AZs usually)
db_instance = database.create_database([private_subnet.id, private_subnet_2.id], [db_sg.id])

# 4. Create Backend (EC2)
backend_server, backend_eip = backend_ec2.create_backend(
    public_subnet.id, 
    [backend_sg.id], 
    db_instance.address, 
    db_instance.username, 
    db_instance.password, 
    db_instance.db_name
)

# 5. Create Frontend (S3 + CloudFront)
# Pass the backend public DNS (from EIP) to configure CloudFront routing for /api
bucket, distribution = frontend_s3_cf.create_frontend(backend_eip.public_dns)

# Exports
pulumi.export("backend_public_ip", backend_eip.public_ip)
pulumi.export("backend_public_dns", backend_eip.public_dns)
pulumi.export("database_endpoint", db_instance.address)
pulumi.export("frontend_bucket_name", bucket.id)
pulumi.export("cloudfront_url", distribution.domain_name)
