

module "azure_spokes_rg_2_vnet_2" {
  source              = "./azure_spoke_vnet"
  vnet_name           = "s5-core01-vnet-westus2-02"
  vnet_cidr           = ["10.5.63.0/24"]
  subnets             =  {  
                            internal = {
                              subnet_cidr = "10.5.63.0/25"
                              public  = true }
                            dmz =   {
                              subnet_cidr  = "10.5.63.128/26"
                              public  = false }
                          } 
  avtx_cidr      = "10.50.9.0/25"
  hpe            = true
  avtx_gw_size   = "Standard_D8_v3"
  native_peering = false
  region              = "West US 2"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s0-core01-neti_usw2-rg-01"
  account_name        = "s0-sub-core-01"
  providers = {
  azurerm = azurerm.s0_sub_core_01
  }
}

