data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

data "aws_ssm_parameter" "avx-azure-client-secret" {
  name     = "avx-azure-client-secret"
  provider = aws.us_west_2
}

data "aws_ssm_parameter" "avx-gcp-client-secret" {
  name     = "avx-gcp-client-secret"
  provider = aws.us_west_2
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

module "aws_transit_us_west_2" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-us-west-2-transit"
  vpc_cidr         = "10.50.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "us-west-2"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = true
  bgp_polling_time = 10
  local_as_number  = "4207216793"
  tgw_asn          = "4207216795"
  providers = {
    aws = aws.us_west_2
  }
}

module "aws_transit_us_east_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-us-east-1-transit"
  vpc_cidr         = "10.52.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "us-east-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = true
  bgp_polling_time = 10
  local_as_number  = "4207216893"
  tgw_asn          = "4207216896"
  providers = {
    aws = aws.us_east_1
  }
}

module "aws_transit_us_west_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-us-west-1-transit"
  vpc_cidr         = "10.51.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "us-west-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = false
  bgp_polling_time = 10
  local_as_number  = "4207216693"
  tgw_asn          = "4207216696"
  providers = {
    aws = aws.us_west_1
  }
}

module "aws_transit_eu_west_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-eu-west-1-transit"
  vpc_cidr         = "10.54.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "eu-west-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = false
  bgp_polling_time = 10
  local_as_number  = "4207216993"
  tgw_asn          = "4207216995"
  providers = {
    aws = aws.eu_west_1
  }
}

module "aws_transit_eu_central_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-eu-central-1-transit"
  vpc_cidr         = "10.55.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "eu-central-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = false
  bgp_polling_time = 10
  local_as_number  = "4207217093"
  tgw_asn          = "4207217095"
  providers = {
    aws = aws.eu_central_1
  }
}

module "aws_transit_ap_southeast_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-ap-southeast-1-transit"
  vpc_cidr         = "10.56.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "ap-southeast-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = false
  bgp_polling_time = 10
  local_as_number  = "4207217193"
  tgw_asn          = "4207217195"
  providers = {
    aws = aws.ap_southeast_1
  }
}

module "aws_transit_ap_northeast_1" {
  source           = "./aws_transit_vpc"
  vpc_name         = "aviatrix-aws-ap-northeast-1-transit"
  vpc_cidr         = "10.57.0.0/23"
  account_name     = "AWS-GNS-TEST"
  enable_firenet   = false
  region           = "ap-northeast-1"
  hpe              = true
  avtx_gw_size     = "c5n.large"
  attach_tgw       = false
  bgp_polling_time = 10
  local_as_number  = "4207217293"
  tgw_asn          = "4207217295"
  providers = {
    aws = aws.ap_northeast_1
  }
}


module "azure_transit_west_us" {
  source              = "./azure_transit_vnet"
  vnet_name           = "s5-mt01-vnet-westus-14"
  resource_group_name = "s5-vnet-rg-01"
  address_space       = ["10.51.4.0/23"]
  account_name        = "az-sandbox-01"
  enable_firenet      = true
  hpe                 = true
  avtx_gw_size        = "Standard_D8_v3"
  region              = "West US"
  use_azs             = false
  local_as_number     = "4207216694"
  bgp_polling_time    = 10
}
/*
module "azure_transit_west_us_2" {
  source              = "./azure_transit_vnet"
  vnet_name           = "s5-mt01-vnet-westus2-03"
  resource_group_name = "s5-neti_usw2-rg-01"
  address_space       = ["10.50.4.0/23"]
  account_name        = "az-sandbox-01"
  enable_firenet      = false
  hpe                 = true
  avtx_gw_size        = "Standard_D8_v3"
  region              = "West US 2"
  use_azs             = true
  local_as_number     = "4207216794"
  bgp_polling_time   = 10
}

module "azure_transit_east_us" {
  source                = "./azure_transit_vnet"
  vnet_name             = "s5-mt01-vnet-eastus-12"
  resource_group_name   = "s5-vnet-rg-01"
  address_space         = ["10.52.4.0/23"]
  account_name          = "az-sandbox-01"
  enable_firenet        = false
  hpe                   = true
  avtx_gw_size          = "Standard_D8_v3"
  region                = "East US"
  use_azs             = true
  local_as_number       = "4207216894"
  bgp_polling_time   = 10
}

module "azure_transit_north_eu" {
  source                = "./azure_transit_vnet"
  vnet_name             = "s6-mt01-vnet-northeurope-03"
  resource_group_name   = "s6-mt01-rg-network-01"
  address_space         = ["10.54.4.0/23"]
  account_name          = "az-sandbox-01"
  enable_firenet        = false
  hpe                   = true
  avtx_gw_size          = "Standard_D8_v3"
  region                = "North Europe"
  use_azs             = true
  local_as_number       = "4207216994"
  bgp_polling_time   = 10
}

module "azure_transit_west_eu" {
  source                = "./azure_transit_vnet"
  vnet_name             = "s6-mt01-vnet-westeurope-03"
  resource_group_name   = "s6-vnet-rg-01"
  address_space         = ["10.55.4.0/23"]
  account_name          = "az-sandbox-01"
  enable_firenet        = false
  hpe                   = true
  avtx_gw_size          = "Standard_D8_v3"
  region                = "West Europe"
  use_azs             = true
  local_as_number       = "4207217094"
  bgp_polling_time   = 10
}

module "azure_transit_southeast_asia" {
  source                = "./azure_transit_vnet"
  vnet_name             = "s7-mt01-vnet-southeastasia-03"
  resource_group_name   = "s7-vnet-rg-01"
  address_space         = ["10.56.4.0/23"]
  account_name          = "az-sandbox-01"
  enable_firenet        = false
  hpe                   = true
  avtx_gw_size          = "Standard_D8_v3"
  region                = "South East Asia"
  use_azs             = true
  local_as_number       = "4207217194"
  bgp_polling_time   = 10

}


module "azure_transit_japan_east" {
  source                = "./azure_transit_vnet"
  vnet_name             = "s7-mt01-vnet-japaneast-02"
  resource_group_name   = "s7-mt01-rg-network-01"
  address_space         = ["10.57.4.0/23"]
  account_name          = "az-sandbox-01"
  enable_firenet        = false
  hpe                   = true
  avtx_gw_size          = "Standard_D8_v3"
  region                = "Japan East"
  use_azs             = true
  local_as_number       = "4207217294"
  bgp_polling_time   = 10
}
*/
module "gcp_transit_us_west_1" {
  source           = "./gcp_transit_vpc"
  vpc_name         = "aviatrix-gcp-us-west1-transit"
  vpc_cidr         = "10.51.8.0/23"
  account_name     = "nike-aviatrix-test"
  enable_firenet   = false
  region           = "us-west1"
  hpe              = true
  avtx_gw_size     = "n1-highcpu-4"
  local_as_number  = "4207216695"
  bgp_polling_time = 10
  providers = {
    google = google.us_west1
  }
}

module "transit_peering" {
  source         = "./transit_peering"
  excluded_cidrs = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
  transit_gateways = [
    {
      name = module.aws_transit_us_east_1.gw_name,
      asn  = module.aws_transit_us_east_1.asn
    },
    {
      name = module.aws_transit_us_west_1.gw_name,
      asn  = module.aws_transit_us_west_1.asn
    },
    {
      name = module.aws_transit_us_west_2.gw_name,
      asn  = module.aws_transit_us_west_2.asn
    },
    {
      name = module.aws_transit_eu_west_1.gw_name,
      asn  = module.aws_transit_eu_west_1.asn
    },
    {
      name = module.aws_transit_eu_central_1.gw_name,
      asn  = module.aws_transit_eu_central_1.asn
    },
    {
      name = module.aws_transit_ap_northeast_1.gw_name,
      asn  = module.aws_transit_ap_northeast_1.asn
    },
    {
      name = module.aws_transit_ap_southeast_1.gw_name,
      asn  = module.aws_transit_ap_southeast_1.asn
    },
    {
      name = module.azure_transit_west_us.gw_name,
      asn  = module.azure_transit_west_us.asn
    },
    /*
    {
      name = module.azure_transit_east_us.gw_name,
      asn  = module.azure_transit_east_us.asn
    },
    {
      name = module.azure_transit_west_us_2.gw_name,
      asn  = module.azure_transit_west_us_2.asn
    },
    {
      name = module.azure_transit_north_eu.gw_name,
      asn  = module.azure_transit_north_eu.asn
    },
    {
      name = module.azure_transit_west_eu.gw_name,
      asn  = module.azure_transit_west_eu.asn
    },
    {
      name = module.azure_transit_southeast_asia.gw_name,
      asn  = module.azure_transit_southeast_asia.asn
    },
    {
      name = module.azure_transit_japan_east.gw_name,
      asn  = module.azure_transit_japan_east.asn
    },

*/ {
      name = module.gcp_transit_us_west_1.gw_name,
      asn  = module.gcp_transit_us_west_1.asn
    }
  ]
}

