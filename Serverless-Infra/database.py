import pulumi
import pulumi_aws as aws

def create_database(subnet_ids, security_group_ids, instance_class="db.t3.micro", stack="dev"):
    # Create DB Subnet Group
    db_subnet_group = aws.rds.SubnetGroup(f"weprint-db-subnet-group-{stack}",
        subnet_ids=subnet_ids,
        tags={
            "Name": f"weprint-db-subnet-group-{stack}",
        })

    # Create RDS Instance
    db_instance = aws.rds.Instance(f"weprint-db-{stack}",
        engine="mysql",
        engine_version="8.0",
        instance_class=instance_class,
        allocated_storage=20,
        db_name="weprint",
        username="admin",
        password="password123", # In prod, use secrets
        db_subnet_group_name=db_subnet_group.name,
        vpc_security_group_ids=security_group_ids,
        skip_final_snapshot=True,
        publicly_accessible=False,
        tags={
            "Name": f"weprint-db-{stack}",
        })

    return db_instance
