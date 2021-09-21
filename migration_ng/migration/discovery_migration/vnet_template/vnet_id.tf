$var_route_tables

module "${vnet_name}" {
  source              = "../module_azure_brownfield_spoke_vnet"
  vnet_name           = "$vnet_name"
  vnet_cidr           = $vnet_cidr
  avtx_cidr           = "$avtx_cidr"
  hpe                 = $hpe
  avtx_gw_size        = "$avtx_gw_size"
  region              = "$region"
  use_azs             = $use_azs # Set to false if region above doesn't support AZs
  resource_group_name = "$resource_group"
  account_name        = "$account_name"
  route_tables        = $route_tables
  switch_traffic      = false
  providers = {
    azurerm = azurerm.$provider
  }
}
