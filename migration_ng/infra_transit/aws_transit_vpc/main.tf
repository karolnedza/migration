resource "aws_vpc" "transit" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = "true"
  tags = {
    Name = var.vpc_name
  }
}

data "aws_availability_zones" "az" {
  state = "available"
}

resource "aws_internet_gateway" "IGW" {
  vpc_id = aws_vpc.transit.id
  tags = {
    Name = aws_vpc.transit.tags["Name"]
  }
}

resource "aws_route_table" "public" {
  count  = var.enable_firenet ? 1 : 0
  vpc_id = aws_vpc.transit.id
  tags = {
    Name = "${aws_vpc.transit.tags["Name"]}-Public-rtb"
  }
}

resource "aws_route" "default" {
  count                  = var.enable_firenet ? 1 : 0
  route_table_id         = aws_route_table.public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.IGW.id
}

resource "aws_subnet" "public" {
  count                   = var.enable_firenet ? 2 : 0
  vpc_id                  = aws_vpc.transit.id
  cidr_block              = cidrsubnet(aws_vpc.transit.cidr_block, 5, 8 + count.index)
  availability_zone       = data.aws_availability_zones.az.names[count.index]
  map_public_ip_on_launch = true
  tags = {
    Name = "${aws_vpc.transit.tags["Name"]}-Public-FW-ingress-egress-${element(split("-", data.aws_availability_zones.az.names[count.index]), 2)}"
  }
}

resource "aws_route_table_association" "public" {
  count          = var.enable_firenet ? 2 : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aviatrix_transit_gateway" "atgw" {
  cloud_type                    = 1
  vpc_reg                       = var.region
  vpc_id                        = aws_vpc.transit.id
  account_name                  = var.account_name
  gw_name                       = "${trimprefix(var.vpc_name, "aviatrix-")}-gw"
  insane_mode                   = var.hpe
  gw_size                       = var.avtx_gw_size
  ha_gw_size                    = var.avtx_gw_size
  subnet                        = cidrsubnet(aws_vpc.transit.cidr_block, 3, 0)
  ha_subnet                     = cidrsubnet(aws_vpc.transit.cidr_block, 3, 1)
  insane_mode_az                = data.aws_availability_zones.az.names[0]
  ha_insane_mode_az             = data.aws_availability_zones.az.names[1]
  enable_active_mesh            = true
  enable_hybrid_connection      = var.attach_tgw
  connected_transit             = true
  bgp_ecmp                      = true
  enable_advertise_transit_cidr = false
  enable_transit_firenet        = var.enable_firenet
  local_as_number               = var.local_as_number
  bgp_polling_time              = var.bgp_polling_time
  depends_on                    = [aws_internet_gateway.IGW]
}

resource "aviatrix_transit_external_device_conn" "dummy" {
  vpc_id            = aws_vpc.transit.id
  connection_name   = var.vpc_name
  gw_name           = aviatrix_transit_gateway.atgw.gw_name
  connection_type   = "bgp"
  enable_ikev2      = true
  bgp_local_as_num  = var.local_as_number
  bgp_remote_as_num = "65000"
  remote_gateway_ip = "1.1.1.1"
}

resource "aviatrix_aws_tgw" "tgw" {
  count                             = var.attach_tgw ? 1 : 0
  account_name                      = var.account_name
  aws_side_as_number                = var.tgw_asn
  manage_vpc_attachment             = false
  manage_transit_gateway_attachment = false
  region                            = var.region
  tgw_name                          = "${var.region}-tgw"

  security_domains {
    security_domain_name = "Aviatrix_Edge_Domain"
    connected_domains = [
      "Default_Domain",
      "Shared_Service_Domain"
    ]
  }

  security_domains {
    security_domain_name = "Default_Domain"
    connected_domains = [
      "Aviatrix_Edge_Domain",
      "Shared_Service_Domain"
    ]
  }

  security_domains {
    security_domain_name = "Shared_Service_Domain"
    connected_domains = [
      "Aviatrix_Edge_Domain",
      "Default_Domain"
    ]
  }
}

resource "aviatrix_aws_tgw_transit_gateway_attachment" "transit_vpc_attachment" {
  count                = var.attach_tgw ? 1 : 0
  tgw_name             = aviatrix_aws_tgw.tgw[0].tgw_name
  region               = var.region
  vpc_account_name     = var.account_name
  vpc_id               = aws_vpc.transit.id
  transit_gateway_name = aviatrix_transit_gateway.atgw.gw_name
}
