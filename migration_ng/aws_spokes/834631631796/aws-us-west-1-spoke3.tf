module "us_west_1_spoke3" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-west-1-tgw-spoke3"
  vpc_cidr      = "10.4.223.0/24"
  az_count      = 2    
  avtx_cidr     = ""
  hpe           = false
  avtx_gw_size  = ""
  tgw_vpc       = true
  region        = "us-west-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_west_1 }
}