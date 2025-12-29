import pulumi
import pulumi_aws as aws

def create_vpc():
    # Create VPC
    vpc = aws.ec2.Vpc("weprint-vpc",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={
            "Name": "weprint-vpc",
        })

    # Create Internet Gateway
    igw = aws.ec2.InternetGateway("weprint-igw",
        vpc_id=vpc.id,
        tags={
            "Name": "weprint-igw",
        })

    # Create Public Subnet
    public_subnet = aws.ec2.Subnet("weprint-public-subnet",
        vpc_id=vpc.id,
        cidr_block="10.0.1.0/24",
        map_public_ip_on_launch=True,
        availability_zone="eu-west-1a", # Adjust AZ as needed
        tags={
            "Name": "weprint-public-subnet",
        })

    # Create Private Subnet 1 (For RDS/Backend)
    private_subnet = aws.ec2.Subnet("weprint-private-subnet",
        vpc_id=vpc.id,
        cidr_block="10.0.2.0/24",
        map_public_ip_on_launch=False,
        availability_zone="eu-west-1a",
        tags={
            "Name": "weprint-private-subnet",
        })
    
    # Create Private Subnet 2 (For RDS Multi-AZ capability if needed, usually required by DB Subnet Group)
    private_subnet_2 = aws.ec2.Subnet("weprint-private-subnet-2",
        vpc_id=vpc.id,
        cidr_block="10.0.3.0/24",
        map_public_ip_on_launch=False,
        availability_zone="eu-west-1b",
        tags={
            "Name": "weprint-private-subnet-2",
        },
        opts=pulumi.ResourceOptions(delete_before_replace=True))

    # Create Route Table for Public Subnet
    public_rt = aws.ec2.RouteTable("weprint-public-rt",
        vpc_id=vpc.id,
        routes=[
            aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=igw.id,
            )
        ],
        tags={
            "Name": "weprint-public-rt",
        })

    # Associate Public Subnet with Public Route Table
    aws.ec2.RouteTableAssociation("weprint-public-rt-assoc",
        subnet_id=public_subnet.id,
        route_table_id=public_rt.id)

    return vpc, public_subnet, private_subnet, private_subnet_2
