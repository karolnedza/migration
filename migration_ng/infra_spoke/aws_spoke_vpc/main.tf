resource "aws_vpc" "spoke" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = "true"
  tags = {
    Name = var.vpc_name
  }
}

resource "aws_vpc_ipv4_cidr_block_association" "aviatrix_cidr" {
  count      = var.tgw_vpc ? 0 : 1
  vpc_id     = aws_vpc.spoke.id
  cidr_block = var.avtx_cidr
}

resource "aws_internet_gateway" "IGW" {
  vpc_id = aws_vpc.spoke.id
  tags = {
    Name = aws_vpc.spoke.tags["Name"]
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.spoke.id
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Public-rtb"
  }
}

resource "aws_route" "default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.IGW.id
}

resource "aws_subnet" "public" {
  count             = var.subnet_count != "" ? var.subnet_count : length(var.az_names)
  vpc_id            = aws_vpc.spoke.id
  cidr_block        = cidrsubnet(var.vpc_cidr, var.subnet_offset, count.index)
  availability_zone = var.az_names[count.index]
  # map_public_ip_on_launch = true
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Public-${element(split("-", var.az_names[count.index]), 2)}"
  }
}

resource "aws_route_table_association" "public" {
  count          = var.subnet_count != "" ? var.subnet_count : length(var.az_names)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.spoke.id
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Private-rtb"
  }
}

resource "aws_subnet" "private" {
  count             = var.subnet_count != "" ? var.subnet_count : length(var.az_names)
  vpc_id            = aws_vpc.spoke.id
  cidr_block        = var.subnet_count != "" ? cidrsubnet(var.vpc_cidr, var.subnet_offset, var.subnet_count + count.index) : cidrsubnet(var.vpc_cidr, var.subnet_offset, length(var.az_names) + count.index)
  availability_zone = var.az_names[count.index]
  # map_public_ip_on_launch = false
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Private-${element(split("-", var.az_names[count.index]), 2)}"
  }
}

resource "aws_route_table_association" "private" {
  count          = var.subnet_count != "" ? var.subnet_count : length(var.az_names)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_subnet" "aviatrix_public" {
  count             = var.hpe || var.tgw_vpc ? 0 : 2
  vpc_id            = aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].vpc_id
  cidr_block        = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, count.index)
  availability_zone = var.az_names[count.index]
  # map_public_ip_on_launch = true
  tags = {
    Name = count.index == 0 ? "${aws_vpc.spoke.tags["Name"]}-gw" : "${aws_vpc.spoke.tags["Name"]}-gw-hagw"
  }
}

resource "aws_route_table" "aviatrix_public" {
  count  = var.hpe || var.tgw_vpc ? 0 : 1
  vpc_id = aws_vpc.spoke.id
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-gw"
  }
}

resource "aws_route" "aviatrix_default" {
  count                  = var.hpe || var.tgw_vpc ? 0 : 1
  route_table_id         = aws_route_table.aviatrix_public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.IGW.id
}

resource "aws_route_table_association" "aviatrix_public" {
  count          = var.hpe || var.tgw_vpc ? 0 : 2
  subnet_id      = aws_subnet.aviatrix_public[count.index].id
  route_table_id = aws_route_table.aviatrix_public[0].id
}


resource "aviatrix_spoke_gateway" "gw" {
  count              = var.tgw_vpc ? 0 : 1
  cloud_type         = 1
  account_name       = var.account_name
  gw_name            = "${trimprefix(var.vpc_name, "aviatrix-")}-${trimprefix(var.account_name, "aws-")}-gw"
  vpc_id             = aws_vpc.spoke.id
  vpc_reg            = var.region
  insane_mode        = var.hpe
  gw_size            = var.avtx_gw_size
  ha_gw_size         = var.avtx_gw_size
  subnet             = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 0)
  ha_subnet          = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 1)
  insane_mode_az     = var.hpe ? var.az_names[0] : null
  ha_insane_mode_az  = var.hpe ? var.az_names[1] : null
  transit_gw         = var.transit_gw
  enable_active_mesh = true
  depends_on         = [aws_route.default, aws_route_table_association.aviatrix_public]
}

resource "aviatrix_aws_tgw_vpc_attachment" "tgw_attach" {
  count                = var.tgw_vpc ? 1 : 0
  tgw_name             = var.tgw_name
  vpc_account_name     = var.account_name
  region               = var.region
  security_domain_name = "Default_Domain"
  vpc_id               = aws_vpc.spoke.id
  depends_on           = [aws_subnet.private, aws_subnet.public]
}
