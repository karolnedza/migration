
module "us_west_2_spoke2" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-us-west-2-spoke2"
  vpc_cidr      = "10.240.70.0/24"
  az_count      = 2    
  avtx_cidr     = "10.50.2.128/25"
  hpe           = false
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  test_ec2      = true
  region        = "us-west-2"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_us_west_2 }
}



