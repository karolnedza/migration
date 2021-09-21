module "avx_spoke_us_west_1_spoke2" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-west-1-spoke2"
  vpc_cidr      = "10.4.222.0/24"
  az_count      = 2    
  avtx_cidr     = "10.51.3.0/27"
  hpe           = false
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  region        = "us-west-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_west_1 }
}