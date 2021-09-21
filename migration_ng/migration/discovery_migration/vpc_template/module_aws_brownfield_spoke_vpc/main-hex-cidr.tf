resource "aws_vpc_ipv4_cidr_block_association" "aviatrix_cidr" {
  count      = var.tgw_vpc ? 0 : 1
  vpc_id     = var.vpc_id
  cidr_block = var.avtx_cidr
}

resource "aws_internet_gateway" "IGW" {
  count  = var.igw_id == "" && !var.tgw_vpc ? 1 : 0
  vpc_id = var.vpc_id
  tags = {
    Name = "aviatrix-${var.vpc_name}"
  }
}

resource "aws_subnet" "aviatrix_public" {
  count             = var.hpe || var.tgw_vpc ? 0 : 2
  vpc_id            = aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].vpc_id
  cidr_block        = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, count.index)
  availability_zone = var.gw_zones[count.index]
  tags = {
    Name = count.index == 0 ? "aviatrix-${var.vpc_name}-gw" : "aviatrix-${var.vpc_name}-gw-hagw"
  }
}

resource "aws_route_table" "aviatrix_public" {
  count  = var.hpe || var.tgw_vpc ? 0 : 1
  vpc_id = var.vpc_id
  tags = {
    Name = "aviatrix-${var.vpc_name}-gw"
  }
}

resource "aws_route" "aviatrix_default" {
  count                  = var.hpe || var.tgw_vpc ? 0 : 1
  route_table_id         = aws_route_table.aviatrix_public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = var.igw_id == "" ? aws_internet_gateway.IGW[0].id : var.igw_id
}

resource "aws_route_table_association" "aviatrix_public" {
  count          = var.hpe || var.tgw_vpc ? 0 : 2
  subnet_id      = aws_subnet.aviatrix_public[count.index].id
  route_table_id = aws_route_table.aviatrix_public[0].id
}

locals {
  region = {
    us-west-2      = "usw2"
    us-west-1      = "usw1"
    us-east-1      = "use1"
    eu-west-1      = "euw1"
    eu-central-1   = "euc1"
    ap-southeast-1 = "apse1"
    ap-northeast-1 = "apne1"
    cn-north-1     = "cnn1"
    cn-northwest-1 = "cnnw1"
  }
}

resource "aviatrix_spoke_gateway" "gw" {
  count                             = var.tgw_vpc ? 0 : 1
  cloud_type                        = 1
  account_name                      = var.account_name
  gw_name                           = "aws-${local.region[var.region]}-${join("", formatlist("%02x", split(".", split("/", var.avtx_cidr)[0])))}-gw"
  vpc_id                            = var.vpc_id
  vpc_reg                           = var.region
  insane_mode                       = var.hpe
  gw_size                           = var.avtx_gw_size
  ha_gw_size                        = var.avtx_gw_size
  subnet                            = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 0)
  ha_subnet                         = cidrsubnet(aws_vpc_ipv4_cidr_block_association.aviatrix_cidr[0].cidr_block, 1, 1)
  insane_mode_az                    = var.hpe ? var.gw_zones[0] : null
  ha_insane_mode_az                 = var.hpe ? var.gw_zones[1] : null
  included_advertised_spoke_routes  = var.switch_traffic ? join(",", concat(var.vpc_cidr, [var.avtx_cidr])) : var.avtx_cidr
  manage_transit_gateway_attachment = false
  enable_active_mesh                = true
  single_az_ha                      = true
  tags = {
    "cis.asm.vm.riskException" = "RK0026082"
  }
  depends_on = [aws_route.aviatrix_default, aws_route_table_association.aviatrix_public, aws_route.pre_migration]
}

resource "aviatrix_spoke_transit_attachment" "attachment" {
  count           = var.tgw_vpc ? 0 : 1
  spoke_gw_name   = aviatrix_spoke_gateway.gw[0].gw_name
  transit_gw_name = "aws-${local.region[var.region]}-transit-gw"
  route_tables    = [for k, v in var.route_tables : aws_route_table.aviatrix_managed[k].id]
}

resource "aviatrix_aws_tgw_vpc_attachment" "tgw_attach" {
  count                           = var.tgw_vpc ? 1 : 0
  tgw_name                        = "${var.region}-tgw"
  vpc_account_name                = var.account_name
  region                          = var.region
  security_domain_name            = "Default_Domain"
  vpc_id                          = var.vpc_id
  customized_route_advertisement  = var.switch_traffic ? join(",", var.vpc_cidr) : ""
  disable_local_route_propagation = true
}

resource "aws_route_table" "aviatrix_managed" {
  for_each = var.route_tables
  vpc_id   = var.vpc_id
  tags     = merge(each.value.tags, { Org_RT = each.key })
}


resource "aws_route" "pre_migration" {
  for_each = {
    for route in local.routes : "${route.destination}.${route.key}" => route
    if substr(route["target"], 0, 5) != "vpce-"
  }
  route_table_id            = aws_route_table.aviatrix_managed[each.value.key].id
  destination_cidr_block    = each.value.destination
  gateway_id                = split("-", each.value.target)[0] == "igw" ? each.value.target : null
  instance_id               = split("-", each.value.target)[0] == "i" ? each.value.target : null
  nat_gateway_id            = split("-", each.value.target)[0] == "nat" ? each.value.target : null
  local_gateway_id          = split("-", each.value.target)[0] == "Igw" ? each.value.target : null # outpost gateway
  network_interface_id      = split("-", each.value.target)[0] == "eni" ? each.value.target : null
  vpc_peering_connection_id = split("-", each.value.target)[0] == "pcx" ? each.value.target : null

  # VPC gateway endpoints routes can't be added here, endpoint manages RTs

}

resource "null_resource" "vpce_route" {
  for_each = {
    for route in local.routes : "${route.destination}.${route.key}" => route
    if substr(route["target"], 0, 5) == "vpce-"
  }
  provisioner "local-exec" {
    command = "python3 -m dm.add_vpce_route ${var.region} ${var.role_arn} ${each.value["target"]} ${aws_route_table.aviatrix_managed[each.value.key].id}"
  }
}

locals {
  routes = flatten([
    for rt_key, rt_val in var.route_tables : [
      for route in rt_val.routes : {
        key         = rt_key
        destination = route.destination
        target      = route.target
      }
    ]
  ])
}
