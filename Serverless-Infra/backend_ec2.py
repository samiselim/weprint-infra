import pulumi
import pulumi_aws as aws

def create_backend(public_subnet_id, security_group_ids, db_endpoint, db_username, db_password, db_name, instance_type="t3.micro", ebs_size=20, stack="dev"):
    # AMI for Amazon Linux 2023 (Free Tier eligible usually)
    ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["amazon"],
        filters=[{"name": "name", "values": ["al2023-ami-2023.*-x86_64"]}],
    )

    # Create EC2 Instance
    server = aws.ec2.Instance(f"weprint-backend-server-{stack}",
        instance_type=instance_type,
        vpc_security_group_ids=security_group_ids,
        ami=ami.id,
        subnet_id=public_subnet_id,
        key_name="weprint-key", # Attach specific key pair
        tags={
            "Name": f"weprint-backend-server-{stack}",
        })

    # Create Dedicated EBS Volume for Persistent Storage
    storage_volume = aws.ebs.Volume(f"weprint-storage-vol-{stack}",
        availability_zone=server.availability_zone,
        size=ebs_size,
        type="gp3",
        tags={
            "Name": f"weprint-storage-vol-{stack}",
        })

    # Attach the volume to the instance
    attachment = aws.ec2.VolumeAttachment(f"weprint-storage-attach-{stack}",
        device_name="/dev/xvdf",
        instance_id=server.id,
        volume_id=storage_volume.id)

    # Create Elastic IP
    eip = aws.ec2.Eip(f"weprint-backend-eip-{stack}",
        instance=server.id,
        domain="vpc",
        tags={
            "Name": f"weprint-backend-eip-{stack}",
        })

    return server, eip
