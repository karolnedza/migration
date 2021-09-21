module "azure_spokes_rg_1" {
  source              = "./azure_spoke_vnet"
  vnet_name           = "s5-mt01-vnet-westus2-04"
  vnet_cidr           = ["10.5.60.0/24"]
  subnets             =  {  
                            internal = {
                              subnet_cidr = "10.5.60.0/25"
                              service_endpoints = ["Microsoft.Sql","Microsoft.Storage"]
                               }
                            dmz =   {
                              subnet_cidr  = "10.5.60.128/28"                       
                               }       
                            netapp =   {
                              subnet_cidr  = "10.5.60.144/28"
                              delegation   = ["Microsoft.Netapp/volumes"]
                            }
                           sql    =   {
                              subnet_cidr  = "10.5.60.160/28"
                              delegation   = ["Microsoft.Sql/managedInstances"]
                           }
                           webserverfarms  =  {
                              subnet_cidr  = "10.5.60.176/28"
                              delegation   = ["Microsoft.Web/serverFarms"]
                           }
                          }
  avtx_cidr      = "10.50.6.0/25"
  hpe            = false
  avtx_gw_size   = "Standard_B1ms"
  native_peering = false
  region              = "West US 2"
  use_azs             = true # Set to false if region above doesn't support AZs
  resource_group_name = "s5-neti_usw2-rg-01"
  account_name        = "az-sandbox-01"
  providers = {
    azurerm = azurerm.az_sandbox_01
  }
}
