
module "eu_central1_spoke2" {
  source        = "../module_aws_spoke_vpc"
  vpc_name      = "aws-eu-central-1-spoke2"
  vpc_cidr      = "10.37.52.0/24"
  az_count      = 2    
  avtx_cidr     = "10.55.3.0/27"
  hpe           = false
  avtx_gw_size  = "t3.small"
  tgw_vpc       = false
  test_ec2      = true
  region        = "eu-central-1"
  account_name  = aviatrix_account.aws_customer.account_name
  providers     =  { aws = aws.spoke_eu_central_1 }
}



