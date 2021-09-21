
module "azure_spokes_rg_1_vnet_2" {
  source              = "./azure_spoke_vnet"
  vnet_name           = "s5-mt01-vnet-westus2-05"
  vnet_cidr           = ["10.5.61.0/24"]
  subnets             =  {  
                            internal = {
                              subnet_cidr = "10.5.61.0/25"
                               }
                            dmz =   {
                              subnet_cidr  = "10.5.61.128/26"
                               }
                          } 
  avtx_cidr      = "10.50.6.128/25"
  hpe            = false
  avtx_gw_size   = "Standard_B1ms"
  native_peering = true
  region              = "West US 2"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s5-neti_usw2-rg-01"
  account_name        = "az-sandbox-01"
  providers = {
    azurerm = azurerm.az_sandbox_01
  }
}