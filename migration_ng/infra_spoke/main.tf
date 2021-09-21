data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

data "aws_availability_zones" "az" {
  state    = "available"
  provider = aws.us_west_2
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

resource "aviatrix_account" "aws_customer" {
  for_each           = toset(var.aws_accounts)
  account_name       = "aws-${each.key}"
  cloud_type         = 1
  aws_account_number = each.key
  aws_iam            = true
  aws_role_app       = "arn:aws:iam::${each.key}:role/aviatrix-role-app"
  aws_role_ec2       = "arn:aws:iam::${each.key}:role/aviatrix-role-ec2"
}

###################################
#  This module to be removed
##################################
module "aws_spokes_us_west_2" {
  source        = "./aws_spoke_vpc"
  for_each      = var.vpc_data_us_west_2
  vpc_name      = each.value.vpc_name
  vpc_cidr      = each.value.vpc_cidr
  subnet_offset = each.value.subnet_offset
  subnet_count  = each.value.subnet_count
  avtx_cidr     = each.value.avtx_cidr
  account_name  = each.value.account_name
  hpe           = each.value.hpe
  avtx_gw_size  = each.value.avtx_gw_size
  tgw_vpc       = each.value.tgw_vpc
  region        = "us-west-2"
  az_names      = data.aws_availability_zones.az.names
  transit_gw    = "aws-us-west-2-transit-gw"
  providers = {
    aws = aws.us_west_2
  }
}
##########################################

module "aws_spokes_account_1" {
  source        = "./aws_spoke_vpc"
  for_each      = var.account_1_spokes
  vpc_name      = "aviatrix-aws-us-west-2-${each.key}"
  vpc_cidr      = each.value.vpc_cidr
  subnet_offset = each.value.subnet_offset
  subnet_count  = each.value.subnet_count
  avtx_cidr     = contains(keys(each.value), "avtx_cidr") ? each.value.avtx_cidr : ""
  hpe           = contains(keys(each.value), "hpe") ? each.value.hpe : false
  avtx_gw_size  = contains(keys(each.value), "avtx_gw_size") ? each.value.avtx_gw_size : ""
  tgw_vpc       = each.value.tgw_vpc
  transit_gw    = "aws-us-west-2-transit-gw"
  tgw_name      = "us-west-2-tgw"
  region        = "us-west-2"
  az_names      = data.aws_availability_zones.az.names
  account_name  = "aws-${aviatrix_account.aws_customer[each.value.account_number].aws_account_number}"
  providers = {
    aws = aws.account_1
  }
}

module "aws_spokes_account_2" {
  source        = "./aws_spoke_vpc"
  for_each      = var.account_2_spokes
  vpc_name      = "aviatrix-aws-us-west-2-${each.key}"
  vpc_cidr      = each.value.vpc_cidr
  subnet_offset = each.value.subnet_offset
  subnet_count  = each.value.subnet_count
  avtx_cidr     = contains(keys(each.value), "avtx_cidr") ? each.value.avtx_cidr : ""
  hpe           = contains(keys(each.value), "hpe") ? each.value.hpe : false
  avtx_gw_size  = contains(keys(each.value), "avtx_gw_size") ? each.value.avtx_gw_size : ""
  tgw_vpc       = each.value.tgw_vpc
  transit_gw    = "aws-us-west-2-transit-gw"
  tgw_name      = "us-west-2-tgw"
  region        = "us-west-2"
  az_names      = data.aws_availability_zones.az.names
  account_name  = "aws-${aviatrix_account.aws_customer[each.value.account_number].aws_account_number}"
  providers = {
    aws = aws.account_2
  }
}
