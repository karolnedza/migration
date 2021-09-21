variable "$route_tables" {}

module "${vpc_id}" {
  source         = "../module_aws_brownfield_spoke_vpc"
  vpc_name       = "$vpc_name"
  vpc_id         = "$vpc_id"
  vpc_cidr       = $vpc_cidr
  igw_id         = "$igw_id"
  avtx_cidr      = "$avtx_cidr"
  hpe            = $hpe
  avtx_gw_size   = "$avtx_gw_size"
  region         = "$region"
  gw_zones       = $gw_zones
  account_name   = aviatrix_account.aws_customer.account_name
  route_tables   = var.$route_tables
  role_arn       = local.role_arn
  switch_traffic = false
  $gw_name_suffix
  providers = { aws = $providers }
}
