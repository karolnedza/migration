module "aviatrix-create-dc-area-2" {
  source = "./cisco_csr"

  region           = var.aws_region_2
  account_name     = var.aws_account_name
  name             = var.dc_data.dc2.name
  cidr             = var.dc_data.dc2.cidr
  csr_ami          = var.csr_ami_west_2
  key_name         = aws_key_pair.ec2_key_region_2.key_name
  ssh_addresses    = "IP allowed to access CSR"
  ipsec_endpoints  = ["${module.aws_transit_us_east_1.atgw_public_ip}/32", "${module.aws_transit_us_east_1.atgw_ha_public_ip}/32", "${module.azure_transit_east_us.atgw_public_ip}/32", "${module.azure_transit_east_us.atgw_ha_public_ip}/32"]
  fixed_private_ip = true # for the test instance
  private_ip       = "16" # for the test instance, the last octet, module replaces xxx/xx in subnet with this number

  providers = {
    aws = aws.region_2
  }
}
