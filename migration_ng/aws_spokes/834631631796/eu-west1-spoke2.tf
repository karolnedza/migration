
module "eu_west1_spoke2" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-eu-west-1-spoke2"
  vpc_cidr      = "10.35.139.0/24"
  az_count      = 2    
  avtx_cidr     = "10.54.3.0/27"
  hpe           = false
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  region        = "eu-west-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_eu_west_1 }
}



