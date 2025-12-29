import pulumi
import pulumi_aws as aws

def create_database(subnet_ids, security_group_ids):
    # Create DB Subnet Group
    db_subnet_group = aws.rds.SubnetGroup("weprint-db-subnet-group",
        subnet_ids=subnet_ids,
        tags={
            "Name": "weprint-db-subnet-group",
        })

    # Create RDS Instance
    # Note: Using hardcoded credentials for demo simplicity. 
    # In production, use AWS Secrets Manager or Pulumi Config.
    db_instance = aws.rds.Instance("weprint-db",
        engine="mysql",
        engine_version="8.0",
        instance_class="db.t3.micro", # Free tier eligible
        allocated_storage=20,
        db_name="weprint",
        username="admin",
        password="password123", # CHANGE THIS!
        db_subnet_group_name=db_subnet_group.name,
        vpc_security_group_ids=security_group_ids,
        skip_final_snapshot=True,
        publicly_accessible=False,
        tags={
            "Name": "weprint-db",
        })

    return db_instance
