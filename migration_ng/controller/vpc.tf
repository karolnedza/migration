
# create the VPC
resource "aws_vpc" "vpc" {
  cidr_block           = var.vpcCIDRblock
  instance_tenancy     = var.instanceTenancy
  enable_dns_support   = var.dnsSupport
  enable_dns_hostnames = var.dnsHostNames
  tags = merge(
    local.common_tags,
    map(
    "Name", var.vpc_name
    )
  )
  
} # end resource


# create the public Subnet1

resource "aws_subnet" "public_subnet1" {
  vpc_id            = aws_vpc.vpc.id
  cidr_block        = local.vpc_subnets[0]
  availability_zone = format("%v%v",data.aws_region.current.name,"a")
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v Public Subnet 1", var.vpc_name),
      "Type", "Public",
    )
  )
}


# create the public Subnet2
resource "aws_subnet" "public_subnet2" {
  vpc_id            = aws_vpc.vpc.id
  cidr_block        = local.vpc_subnets[1]
  availability_zone = format("%v%v",data.aws_region.current.name,"b")
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v Public Subnet 2", var.vpc_name),
      "Type", "Public",
    )
  )
}

# create the private Subnet1
resource "aws_subnet" "private_subnet1" {
  vpc_id            = aws_vpc.vpc.id
  cidr_block        = local.vpc_subnets[2]
  availability_zone = format("%v%v",data.aws_region.current.name,"a")
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v Private Subnet 1", var.vpc_name),
      "Type", "Private",
    )
  )
}

# create the private Subnet2
resource "aws_subnet" "private_subnet2" {
  vpc_id            = aws_vpc.vpc.id
  cidr_block        = local.vpc_subnets[3]
  availability_zone = format("%v%v",data.aws_region.current.name,"b")
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v Private Subnet 2", var.vpc_name),
      "Type", "Private",
    )
  )
}

# Create the Internet Gateway
resource "aws_internet_gateway" "vpc_gw" {
  vpc_id = aws_vpc.vpc.id
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v Internet Gateway", var.vpc_name),
    )
  )
} # end resource
# Create the Route Table
resource "aws_route_table" "public_route_table" {
  vpc_id = aws_vpc.vpc.id
  tags = merge(
    local.common_tags,
    map(
      "Name", format("%v public Route Table", var.vpc_name),
    )
  )
} # end resource

# Create the Internet Access
resource "aws_route" "public_route" {
  route_table_id         = aws_route_table.public_route_table.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.vpc_gw.id
} # end resource
# Associate the Route Table with the Subnet
resource "aws_route_table_association" "vpc_association1" {
  subnet_id      = aws_subnet.public_subnet1.id
  route_table_id = aws_route_table.public_route_table.id
} # end resource

resource "aws_route_table_association" "vpc_association2" {
  subnet_id      = aws_subnet.public_subnet2.id
  route_table_id = aws_route_table.public_route_table.id
} # end resource






