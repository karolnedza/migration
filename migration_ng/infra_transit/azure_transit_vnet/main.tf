resource azurerm_virtual_network "transit_vnet" {
  name                = var.vnet_name
  resource_group_name = var.resource_group_name
  location            = var.region
  address_space       = var.address_space
  #tags                = var.tags
}

resource "azurerm_subnet" "aviatrix_firenet_ingress" {
  count                = var.enable_firenet ? 2 : 0
  name                 = count.index == 0 ? "av-gw-azure-${lower(replace(var.region, " ", "-"))}-transit-Public-FW-ingress-egress-1" : "${var.vnet_name}-transit-Public-FW-ingress-egress-2"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.transit_vnet.name
  address_prefixes     = [cidrsubnet(azurerm_virtual_network.transit_vnet.address_space[0], 5, 20 + count.index)]
}

resource "aviatrix_transit_gateway" "atgw" {
  cloud_type                    = 8
  vpc_reg                       = var.region
  vpc_id                        = join(":", [var.vnet_name, var.resource_group_name])
  account_name                  = var.account_name
  gw_name                       = "azure-${lower(replace(var.region, " ", "-"))}-transit-2-gw"
  insane_mode                   = var.hpe
  gw_size                       = var.avtx_gw_size
  ha_gw_size                    = var.avtx_gw_size
  subnet                        = cidrsubnet(azurerm_virtual_network.transit_vnet.address_space[0], 3, 0)
  ha_subnet                     = cidrsubnet(azurerm_virtual_network.transit_vnet.address_space[0], 3, 4)
  zone                          = var.use_azs ? "az-1" : null
  ha_zone                       = var.use_azs ? "az-2" : null
  enable_active_mesh            = true
  connected_transit             = true
  bgp_ecmp                      = true
  enable_advertise_transit_cidr = false
  enable_transit_firenet        = var.enable_firenet
  local_as_number               = var.local_as_number
  bgp_polling_time              = var.bgp_polling_time
}

resource "aviatrix_transit_external_device_conn" "dummy" {
  vpc_id            = join(":", [var.vnet_name, var.resource_group_name])
  connection_name   = var.vnet_name
  gw_name           = aviatrix_transit_gateway.atgw.gw_name
  connection_type   = "bgp"
  enable_ikev2      = true
  bgp_local_as_num  = var.local_as_number
  bgp_remote_as_num = "65000"
  remote_gateway_ip = "1.1.1.1"
}