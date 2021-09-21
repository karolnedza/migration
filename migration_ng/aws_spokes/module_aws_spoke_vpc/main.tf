locals {
  common_tags = {
    nike-department  = var.tag_department
    nike-environment = var.tag_environment
    nike-domain      = var.tag_domain

  }
}

data "aws_availability_zones" "az" {
  state = "available"
}

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
  count             = var.az_count
  vpc_id            = aws_vpc.spoke.id
  cidr_block        = cidrsubnet(var.vpc_cidr, var.az_count == 2 ? 2 : 4, var.az_count == 2 ? count.index + 2 : count.index + 12)
  availability_zone = data.aws_availability_zones.az.names[count.index]
  # map_public_ip_on_launch = true
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Public-${element(split("-", data.aws_availability_zones.az.names[count.index]), 2)}"
  }
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
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
  count             = var.az_count
  vpc_id            = aws_vpc.spoke.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 2, count.index)
  availability_zone = data.aws_availability_zones.az.names[count.index]
  # map_public_ip_on_launch = false
  tags = {
    Name = "${aws_vpc.spoke.tags["Name"]}-Private-${element(split("-", data.aws_availability_zones.az.names[count.index]), 2)}"
  }
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_subnet" "aviatrix_public" {
  count             = var.hpe || var.tgw_vpc ? 0 : 2
  vpc_id            = aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].vpc_id
  cidr_block        = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, count.index)
  availability_zone = data.aws_availability_zones.az.names[count.index]
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
  count                             = var.tgw_vpc ? 0 : 1
  cloud_type                        = 1
  account_name                      = var.account_name
  gw_name                           = "${trimprefix(var.vpc_name, "aviatrix-")}-${trimprefix(var.account_name, "aws-")}-gw"
  vpc_id                            = aws_vpc.spoke.id
  vpc_reg                           = var.region
  insane_mode                       = var.hpe
  gw_size                           = var.avtx_gw_size
  ha_gw_size                        = var.avtx_gw_size
  subnet                            = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 0)
  ha_subnet                         = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 1)
  insane_mode_az                    = var.hpe ? data.aws_availability_zones.az.names[0] : null
  ha_insane_mode_az                 = var.hpe ? data.aws_availability_zones.az.names[1] : null
  manage_transit_gateway_attachment = false
  enable_active_mesh                = true
  depends_on                        = [aws_route.default, aws_route_table_association.aviatrix_public]
}

resource "aviatrix_spoke_transit_attachment" "attachment" {
  count           = var.tgw_vpc ? 0 : 1
  spoke_gw_name   = aviatrix_spoke_gateway.gw[0].gw_name
  transit_gw_name = "aws-${var.region}-transit-gw"
  depends_on      = [aviatrix_site2cloud.dummy]
}

resource "aviatrix_aws_tgw_vpc_attachment" "tgw_attach" {
  count                           = var.tgw_vpc ? 1 : 0
  tgw_name                        = "${var.region}-tgw"
  vpc_account_name                = var.account_name
  region                          = var.region
  security_domain_name            = "Default_Domain"
  vpc_id                          = aws_vpc.spoke.id
  customized_route_advertisement  = var.vpc_cidr
  disable_local_route_propagation = true
  depends_on                      = [aws_subnet.private, aws_subnet.public]
}

resource "aviatrix_site2cloud" "dummy" {
  count                      = var.tgw_vpc || ! var.migrate_to_swan ? 0 : 1
  vpc_id                     = aws_vpc.spoke.id
  connection_name            = "dummy-${var.vpc_name}"
  connection_type            = "unmapped"
  remote_gateway_type        = "generic"
  tunnel_type                = "policy"
  primary_cloud_gateway_name = aviatrix_spoke_gateway.gw[0].gw_name
  backup_gateway_name        = aviatrix_spoke_gateway.gw[0].ha_gw_name
  remote_gateway_ip          = "5.5.5.5"
  backup_remote_gateway_ip   = "5.5.5.5"
  remote_subnet_cidr         = "192.168.0.0/24"
  enable_ikev2               = true
  ha_enabled                 = true
}
