vpc_data_us_west_2 = {
  vpc1 = {
    vpc_name      = "aviatrix-aws-us-west-2-spoke-1"
    vpc_cidr      = "10.240.69.0/24"
    subnet_offset = 3  # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count  = "" # leave "" for one subnet per AZ or specify desired number
    avtx_cidr     = "10.50.2.0/25"
    account_name  = "AWS-GNS-TEST"
    hpe           = true
    avtx_gw_size  = "t3.large"
    tgw_vpc       = false
  }
  vpc2 = {
    vpc_name      = "aviatrix-aws-us-west-2-spoke-2"
    vpc_cidr      = "10.240.70.0/24"
    subnet_offset = 3 # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count  = 2 # leave "" for one subnet per AZ or specify desired number
    avtx_cidr     = "10.50.2.128/27"
    account_name  = "AWS-GNS-TEST"
    hpe           = false
    avtx_gw_size  = "t3.small"
    tgw_vpc       = false
  }

}

account_1_spokes = {
  spoke-1 = {
    vpc_cidr       = "10.240.72.0/24"
    subnet_offset  = 3 # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count   = 2 # leave "" for one subnet per AZ or specify desired number
    avtx_cidr      = "10.50.3.0/25"
    account_number = "834631631796"
    hpe            = true
    avtx_gw_size   = "t3.large"
    tgw_vpc        = false
  }
  tgw-spoke-1 = {
    vpc_cidr       = "10.240.73.0/24"
    subnet_offset  = 3 # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count   = 2 # leave "" for one subnet per AZ or specify desired number
    account_number = "834631631796"
    tgw_vpc        = true
  }
}

account_2_spokes = {
  spoke-1 = {
    vpc_cidr       = "10.240.75.0/24"
    subnet_offset  = 3 # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count   = 2 # leave "" for one subnet per AZ or specify desired number
    avtx_cidr      = "10.50.4.0/25"
    account_number = "111111111111"
    hpe            = false
    avtx_gw_size   = "t3.small"
    tgw_vpc        = false
  }
  tgw-spoke-1 = {
    vpc_cidr       = "10.240.74.0/24"
    subnet_offset  = 3 # /27 = /24 + 3  Difference between VPC and subnet prefix lenght
    subnet_count   = 2 # leave "" for one subnet per AZ or specify desired number
    account_number = "111111111111"
    tgw_vpc        = true
  }
}
