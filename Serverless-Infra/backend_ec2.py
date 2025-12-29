import pulumi
import pulumi_aws as aws

def create_backend(public_subnet_id, security_group_ids, db_endpoint, db_username, db_password, db_name):
    # AMI for Amazon Linux 2023 (Free Tier eligible usually)
    # Finding the latest Amazon Linux 2023 AMI
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["amazon"],
        filters=[{"name": "name", "values": ["al2023-ami-2023.*-x86_64"]}],
    )

    # UserData script to install dependencies and setup Laravel
    # Note: git clone requires public repo or credentials. Assuming public for now as per user link.


    # Create EC2 Instance
    server = aws.ec2.Instance("weprint-backend-server",
        instance_type="t3.micro", # Free tier eligible
        vpc_security_group_ids=security_group_ids,
        ami=ami.id,
        subnet_id=public_subnet_id,
        key_name="weprint-key", # Attach specific key pair
        tags={
            "Name": "weprint-backend-server",
        })

    # Create Dedicated EBS Volume for Persistent Storage
    # We create it in the same AZ as the subnet/instance
    storage_volume = aws.ebs.Volume("weprint-storage-vol",
        availability_zone=server.availability_zone,
        size=10, # 10 GB for storage
        type="gp3",
        tags={
            "Name": "weprint-storage-vol",
        })

    # Attach the volume to the instance
    # Device name /dev/xvdf is common for additional volumes
    attachment = aws.ec2.VolumeAttachment("weprint-storage-attach",
        device_name="/dev/xvdf",
        instance_id=server.id,
        volume_id=storage_volume.id)

    # Create Elastic IP
    eip = aws.ec2.Eip("weprint-backend-eip",
        instance=server.id,
        domain="vpc",
        tags={
            "Name": "weprint-backend-eip",
        })

    return server, eip
