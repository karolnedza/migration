

module "us_east_1_spoke2" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-east-1-spoke2"
  vpc_cidr      = "10.235.241.0/24"
  az_count      = 2    
  avtx_cidr     = "10.52.3.0/27"
  hpe           = false
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  region        = "us-east-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_east_1 }
}
