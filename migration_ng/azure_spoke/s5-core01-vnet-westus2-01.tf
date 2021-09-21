
module "azure_spokes_rg_2_vnet_1" {
  source              = "./azure_spoke_vnet"
  vnet_name           = "s5-core01-vnet-westus2-01"
  vnet_cidr           = ["10.5.62.0/24"]
  subnets             =  {  
                            internal = {
                              subnet_cidr = "10.5.62.0/25"
                              public  = true }
                            dmz =   {
                              subnet_cidr  = "10.5.62.128/26"
                              public  = false }
                          } 
  avtx_cidr      = "10.50.8.0/25"
  hpe            = false
  avtx_gw_size   = "Standard_B1ms"
  native_peering = false
  region              = "West US 2"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s0-core01-neti_usw2-rg-01"
  account_name        = "s0-sub-core-01"
  providers = {
  azurerm = azurerm.s0_sub_core_01
  }
}
