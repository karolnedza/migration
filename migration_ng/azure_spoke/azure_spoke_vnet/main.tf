resource azurerm_virtual_network "spoke" {
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
  dynamic delegation {
    for_each = contains(keys(each.value), "delegation") ? each.value.delegation : []
    content {
      name = each.value.delegation[0]
      service_delegation {
        name    = each.value.delegation[0]
        actions = local.actions[each.value.delegation[0]]
      }
    }
  }

}


resource "azurerm_route_table" "customer_public" {
  #name                = "${substr(var.vnet_name, 0, 7)}-rt-${lower(replace(var.region, " ", ""))}-public-01"
  name                = "${var.vnet_name}-rt-public-01"
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
    if ! contains(keys(subnet), "delegation")
  }
  subnet_id      = azurerm_subnet.subnets[each.key].id
  route_table_id = azurerm_route_table.customer_public.id
}

resource "aviatrix_spoke_gateway" "gw" {
  count                             = var.native_peering ? 0 : 1
  cloud_type                        = 8
  account_name                      = var.account_name
  gw_name                           = "azure-${lower(replace(var.region, " ", "-"))}-${var.vnet_name}-gw"
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
    ignore_changes = [tag_list]
  }
}


resource "aviatrix_spoke_transit_attachment" "attachment" {
  count           = var.native_peering ? 0 : 1
  spoke_gw_name   = aviatrix_spoke_gateway.gw[0].gw_name
  transit_gw_name = "azure-${lower(replace(var.region, " ", "-"))}-transit-gw"
  depends_on      = [aviatrix_site2cloud.dummy]
}

resource "aviatrix_azure_spoke_native_peering" "spoke_native_peering" {
  count                = var.native_peering ? 1 : 0
  transit_gateway_name = "azure-${lower(replace(var.region, " ", "-"))}-transit-gw"
  spoke_account_name   = var.account_name
  spoke_region         = var.region
  spoke_vpc_id         = join(":", [var.vnet_name, var.resource_group_name])
}

locals {
  actions = {
    "Microsoft.Netapp/volumes"  = ["Microsoft.Network/networkinterfaces/*", "Microsoft.Network/virtualNetworks/subnets/join/action"]
    "Microsoft.Web/serverFarms" = ["Microsoft.Network/virtualNetworks/subnets/action"]
    "Microsoft.Sql/managedInstances" = [
      "Microsoft.Network/virtualNetworks/subnets/join/action",
      "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
      "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action"
    ]

  }
}

resource "aviatrix_site2cloud" "dummy" {
  count                      = var.native_peering || ! var.migrate_to_swan ? 0 : 1
  vpc_id                     = join(":", [var.vnet_name, var.resource_group_name])
  connection_name            = "dummy-${var.vnet_name}"
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
