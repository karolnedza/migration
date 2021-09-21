

module "second-level-vnet" {
  source              = "../module_azure_brownfield_spoke_vnet"
  vnet_name           = "second-level-vnet"
  vnet_cidr           = ["192.168.3.0/24"]
  avtx_cidr           = "192.168.103.0/25"
  hpe                 = true
  avtx_gw_size        = "Standard_D8_v3"
  region              = "East US"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s5-aviatrix-rg-01"
  account_name        = "az-sandbox-01"
  route_tables        = {}
  switch_traffic      = false
  providers = {
    azurerm = azurerm.aviatrix
  }
}

resource "azurerm_virtual_network" "second-level-vnet" {
  location            = "East US"
  name                = "second-level-vnet"
  resource_group_name = "s5-aviatrix-rg-01"
  address_space       = ["192.168.3.0/24", "192.168.103.0/25"]
  tags                = {}
  provider            = azurerm.aviatrix
}

resource "azurerm_subnet" "second-level-vnet_s5-192_168_3_128_28-dmz" {
  name                 = "s5-192.168.3.128_28-dmz"
  resource_group_name  = "s5-aviatrix-rg-01"
  virtual_network_name = "second-level-vnet"
  address_prefixes     = ["192.168.3.128/28"]
  provider             = azurerm.aviatrix
}

resource "azurerm_subnet" "second-level-vnet_s5-192_168_3_0_25-internal" {
  name                 = "s5-192.168.3.0_25-internal"
  resource_group_name  = "s5-aviatrix-rg-01"
  virtual_network_name = "second-level-vnet"
  address_prefixes     = ["192.168.3.0/25"]
  provider             = azurerm.aviatrix
}

