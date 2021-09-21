

module "no-azs-region" {
  source              = "../module_azure_brownfield_spoke_vnet"
  vnet_name           = "no-azs-region"
  vnet_cidr           = ["192.168.2.0/24"]
  avtx_cidr           = "192.168.102.0/25"
  hpe                 = true
  avtx_gw_size        = "Standard_D8_v3"
  region              = "West US"
  use_azs             = false # Set to false if region above doesn't support AZs
  resource_group_name = "s5-aviatrix-rg-01"
  account_name        = "az-sandbox-01"
  route_tables        = {}
  switch_traffic      = false
  providers = {
    azurerm = azurerm.aviatrix
  }
}

resource "azurerm_virtual_network" "no-azs-region" {
  location            = "West US"
  name                = "no-azs-region"
  resource_group_name = "s5-aviatrix-rg-01"
  address_space       = ["192.168.2.0/24","192.168.102.0/25"]
  tags                = {}
  lifecycle {
    ignore_changes = [tags]
  }
  provider            = azurerm.aviatrix
}

resource "azurerm_subnet" "no-azs-region_s5-192_168_2_176_28-webserverfarms" {
  name = "s5-192.168.2.176_28-webserverfarms"
  resource_group_name = "s5-aviatrix-rg-01"
  virtual_network_name = "no-azs-region"
  address_prefixes = ["192.168.2.176/28"]
  delegation {
    name = "Microsoft.Web/serverFarms"
    service_delegation {
      name = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
  provider = azurerm.aviatrix
}

resource "azurerm_subnet" "no-azs-region_s5-192_168_2_144_28-netapp" {
  name = "s5-192.168.2.144_28-netapp"
  resource_group_name = "s5-aviatrix-rg-01"
  virtual_network_name = "no-azs-region"
  address_prefixes = ["192.168.2.144/28"]
  delegation {
    name = "Microsoft.Netapp/volumes"
    service_delegation {
      name = "Microsoft.Netapp/volumes"
      actions = ["Microsoft.Network/networkinterfaces/*", "Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
  provider = azurerm.aviatrix
}

resource "azurerm_subnet" "no-azs-region_s5-192_168_2_160_28-sql" {
  name = "s5-192.168.2.160_28-sql"
  resource_group_name = "s5-aviatrix-rg-01"
  virtual_network_name = "no-azs-region"
  address_prefixes = ["192.168.2.160/28"]
  delegation {
    name = "Microsoft.Sql/managedInstances"
    service_delegation {
      name = "Microsoft.Sql/managedInstances"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action", "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action", "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action"]
    }
  }
  provider = azurerm.aviatrix
}

resource "azurerm_subnet" "no-azs-region_s5-192_168_2_0_25-internal" {
  name = "s5-192.168.2.0_25-internal"
  resource_group_name = "s5-aviatrix-rg-01"
  virtual_network_name = "no-azs-region"
  address_prefixes = ["192.168.2.0/25"]
  service_endpoints = ["Microsoft.Sql", "Microsoft.Storage"]
  provider = azurerm.aviatrix
}

resource "azurerm_subnet" "no-azs-region_s5-192_168_2_128_28-dmz" {
  name = "s5-192.168.2.128_28-dmz"
  resource_group_name = "s5-aviatrix-rg-01"
  virtual_network_name = "no-azs-region"
  address_prefixes = ["192.168.2.128/28"]
  provider = azurerm.aviatrix
}

