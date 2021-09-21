
module "eu_central1_spoke1" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-eu-central-1-spoke1"
  vpc_cidr      = "10.37.51.0/24"
  az_count      = 2    
  avtx_cidr     = "10.55.2.0/25"
  hpe           = true
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  region        = "eu-central-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_eu_central_1 }
}



