import pulumi
import pulumi_aws as aws

def create_security_groups(vpc_id, stack):
    # Security Group for Backend (EC2)
    backend_sg = aws.ec2.SecurityGroup(f"weprint-backend-sg-{stack}",
        description="Allow HTTP and SSH access",
        vpc_id=vpc_id,
        ingress=[
            # Allow SSH from anywhere (For demo purposes. In prod, restrict to specific IP)
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=22,
                to_port=22,
                cidr_blocks=["0.0.0.0/0"], 
                description="Allow SSH",
            ),
            # Allow HTTP from anywhere
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=80,
                to_port=80,
                cidr_blocks=["0.0.0.0/0"],
                description="Allow HTTP",
            ),
             # Allow HTTPS from anywhere
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr_blocks=["0.0.0.0/0"],
                description="Allow HTTPS",
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
            )
        ],
        tags={
            "Name": f"weprint-backend-sg-{stack}",
        })

    # Security Group for Database (RDS)
    db_sg = aws.ec2.SecurityGroup(f"weprint-db-sg-{stack}",
        description="Allow MySQL access from Backend",
        vpc_id=vpc_id,
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=3306,
                to_port=3306,
                security_groups=[backend_sg.id],
                description="Allow MySQL from Backend",
            ),
        ],
        tags={
            "Name": f"weprint-db-sg-{stack}",
        })

    return backend_sg, db_sg
