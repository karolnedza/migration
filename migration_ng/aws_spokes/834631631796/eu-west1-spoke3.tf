module "eu_west1_spoke3" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-eu-west-1-tgw-spoke3"
  vpc_cidr      = "10.35.140.0/24"
  az_count      = 2    
  avtx_cidr     = ""
  hpe           = false
  avtx_gw_size  = ""
  tgw_vpc       = true
  region        = "eu-west-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_eu_west_1 }
}