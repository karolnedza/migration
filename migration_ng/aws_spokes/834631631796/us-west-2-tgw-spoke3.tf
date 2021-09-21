
module "us-west-2-tgw-spoke3" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-west-2-tgw-spoke3"
  vpc_cidr      = "10.240.73.0/24"
  az_count      = 2    
  avtx_cidr     = ""
  hpe           = false
  avtx_gw_size  = ""
  tgw_vpc       = true
  region        = "us-west-2"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_west_2 }
}