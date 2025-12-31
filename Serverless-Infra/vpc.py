import pulumi
import pulumi_aws as aws

def create_vpc(stack):
    # Create VPC
    vpc = aws.ec2.Vpc(f"weprint-vpc-{stack}",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={
            "Name": f"weprint-vpc-{stack}",
        })

    # Create Internet Gateway
    igw = aws.ec2.InternetGateway(f"weprint-igw-{stack}",
        vpc_id=vpc.id,
        tags={
            "Name": f"weprint-igw-{stack}",
        })

    # Create Public Subnet
    public_subnet = aws.ec2.Subnet(f"weprint-public-subnet-{stack}",
        vpc_id=vpc.id,
        cidr_block="10.0.1.0/24",
        map_public_ip_on_launch=True,
        availability_zone="eu-west-1a", # Adjust AZ as needed
        tags={
            "Name": f"weprint-public-subnet-{stack}",
        })

    # Create Private Subnet 1 (For RDS/Backend)
    private_subnet = aws.ec2.Subnet(f"weprint-private-subnet-{stack}",
        vpc_id=vpc.id,
        cidr_block="10.0.2.0/24",
        map_public_ip_on_launch=False,
        availability_zone="eu-west-1a",
        tags={
            "Name": f"weprint-private-subnet-{stack}",
        })
    
    # Create Private Subnet 2 (For RDS Multi-AZ capability if needed, usually required by DB Subnet Group)
    private_subnet_2 = aws.ec2.Subnet(f"weprint-private-subnet-2-{stack}",
        vpc_id=vpc.id,
        cidr_block="10.0.3.0/24",
        map_public_ip_on_launch=False,
        availability_zone="eu-west-1b",
        tags={
            "Name": f"weprint-private-subnet-2-{stack}",
        },
        opts=pulumi.ResourceOptions(delete_before_replace=True))

    # Create Route Table for Public Subnet
    public_rt = aws.ec2.RouteTable(f"weprint-public-rt-{stack}",
        vpc_id=vpc.id,
        routes=[
            aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=igw.id,
            )
        ],
        tags={
            "Name": f"weprint-public-rt-{stack}",
        })

    # Associate Public Subnet with Public Route Table
    aws.ec2.RouteTableAssociation(f"weprint-public-rt-assoc-{stack}",
        subnet_id=public_subnet.id,
        route_table_id=public_rt.id)

    return vpc, public_subnet, private_subnet, private_subnet_2
