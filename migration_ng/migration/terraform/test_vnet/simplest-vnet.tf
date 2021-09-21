
variable "route_tables" {}

module "test_vnet" {
  source              = "../module_azure_brownfield_spoke_vnet"
  vnet_name           = "simplest-vnet"
  vnet_cidr           = azurerm_virtual_network.spoke.address_space
  avtx_cidr           = "192.168.100.0/25"
  hpe                 = false
  avtx_gw_size        = "Standard_D8_v3"
  region              = "East US"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s5-aviatrix-rg-01"
  account_name        = "az-sandbox-01"
  route_tables        = var.route_tables
  providers = {
    azurerm = azurerm.aviatrix
  }
}

# Below comes from the discovery and yaml (address), needs to be imported to TF state
resource "azurerm_virtual_network" "spoke" {
  location            = "eastus"
  name                = "simplest-vnet"
  resource_group_name = "s5-aviatrix-rg-01"
  address_space       = ["192.168.1.0/24", "192.168.100.0/25"]
  tags                = {}
  provider            = azurerm.aviatrix
}

