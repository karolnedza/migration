module "us_east_1_spoke3" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-east-1-tgw-spoke3"
  vpc_cidr      = "10.235.242.0/24"
  az_count      = 2    
  avtx_cidr     = ""
  hpe           = false
  avtx_gw_size  = ""
  tgw_vpc       = true
  region        = "us-east-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_east_1 }
}