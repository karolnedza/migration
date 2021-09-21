module "avx_spoke_us_east_1_spoke1" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-east-1-spoke1"
  vpc_cidr      = "10.235.240.0/24"
  az_count      = 2    
  avtx_cidr     = "10.52.2.0/25"
  hpe           = true
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  region        = "us-east-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_east_1 }
}