locals {
  region = {
    "East US"         = "use"
    "West US"         = "usw"
    "West US 2"       = "usw2"
    "North Europe"    = "eun"
    "West Europe"     = "euw"
    "South East Asia" = "asse"
    "Japan East"      = "jae"
    "China East 2"    = "che2"
    "China North 2"   = "chn2"
  }
}

resource "azurerm_virtual_network" "spoke" {
  name                = var.vnet_name
  resource_group_name = var.resource_group_name
  location            = var.region
  address_space       = var.native_peering ? var.vnet_cidr : concat(var.vnet_cidr, [var.avtx_cidr])
  lifecycle {
    ignore_changes = [tags]
  }
}

resource "azurerm_subnet" "aviatrix_public" {
  count                = var.hpe || var.native_peering ? 0 : 2
  name                 = count.index == 0 ? "aviatrix-spoke-gw" : "aviatrix-spoke-hagw"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = [cidrsubnet(azurerm_virtual_network.spoke.address_space[1], 1, count.index)]
}


resource "azurerm_subnet" "subnets" {
  for_each             = var.subnets
  name                 = join("-", [substr(var.resource_group_name, 0, 2), replace(each.value.subnet_cidr, "/", "_"), each.key])
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = [each.value.subnet_cidr]
  service_endpoints    = contains(keys(each.value), "service_endpoints") ? each.value.service_endpoints : []
}

resource "azurerm_route_table" "customer_private" {
  count               = length(var.subnets) > 1 ? 2 : 1 
  #name                = "${substr(var.vnet_name, 0, 7)}-rt-${lower(replace(var.region, " ", ""))}-public-01"
  name                = "${var.vnet_name}-rt-private-0${count.index}"
  location            = var.region
  resource_group_name = var.resource_group_name
  lifecycle {
    ignore_changes = [tags]
  }
}

resource "azurerm_route_table" "aviatrix_public" {
  count               = var.hpe || var.native_peering ? 0 : 1
  name                = "${substr(var.vnet_name, 0, 7)}-rt-${lower(replace(var.region, " ", ""))}-aviatrix-01"
  location            = var.region
  resource_group_name = var.resource_group_name
  lifecycle {
    ignore_changes = [tags]
  }
}

resource "azurerm_subnet_route_table_association" "aviatrix_public" {
  count          = var.hpe || var.native_peering ? 0 : 2
  subnet_id      = azurerm_subnet.aviatrix_public[count.index].id
  route_table_id = azurerm_route_table.aviatrix_public[0].id
}

resource "azurerm_subnet_route_table_association" "rta" {
  for_each = {
    for name, subnet in var.subnets : name => subnet
  }
  subnet_id      = azurerm_subnet.subnets[each.key].id
  route_table_id = azurerm_route_table.customer_private[0].id
}

resource "aviatrix_spoke_gateway" "gw" {
  count        = var.native_peering ? 0 : 1
  cloud_type   = 8
  account_name = var.account_name
  #gw_name                           = "azure-${lower(replace(var.region, " ", "-"))}-${var.vnet_name}-gw"
  #This gw_name function adds abbreviated region and converts avtx_cidr to hex e.g. "aws-usw1-0a330200-gw"
  gw_name                           = "azu-${local.region[var.region]}-${join("", formatlist("%02x", split(".", split("/", var.avtx_cidr)[0])))}-gw"
  vpc_id                            = join(":", [var.vnet_name, var.resource_group_name])
  vpc_reg                           = var.region
  insane_mode                       = var.hpe
  gw_size                           = var.avtx_gw_size
  ha_gw_size                        = var.avtx_gw_size
  subnet                            = cidrsubnet(azurerm_virtual_network.spoke.address_space[1], 1, 0)
  ha_subnet                         = cidrsubnet(azurerm_virtual_network.spoke.address_space[1], 1, 1)
  zone                              = var.use_azs ? "az-1" : null
  ha_zone                           = var.use_azs ? "az-2" : null
  manage_transit_gateway_attachment = false
  enable_active_mesh                = true
  depends_on                        = [azurerm_subnet_route_table_association.aviatrix_public, azurerm_subnet.aviatrix_public]
  lifecycle {
    ignore_changes = [tags]
  }
}

resource "aviatrix_spoke_transit_attachment" "attachment" {
  count           = var.native_peering ? 0 : 1
  spoke_gw_name   = aviatrix_spoke_gateway.gw[0].gw_name
  #transit_gw_name = "azu-${local.region[var.region]}-transit-gw"
  #my lab only:
  transit_gw_name = "transit-for-nk"
}

resource "aviatrix_azure_spoke_native_peering" "spoke_native_peering" {
  count                = var.native_peering ? 1 : 0
  transit_gateway_name = "azure-${lower(replace(var.region, " ", "-"))}-transit-gw"
  spoke_account_name   = var.account_name
  spoke_region         = var.region
  spoke_vpc_id         = join(":", [var.vnet_name, var.resource_group_name])
}
