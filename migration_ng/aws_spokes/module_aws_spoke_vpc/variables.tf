variable "region" {}

variable "account_name" {}


variable "vpc_name" {}

variable "vpc_cidr" {
  description = "CIDR used by the applications"
}

variable "avtx_cidr" {
  default     = ""
  description = "CIDR used by the Aviatrix gateways"
}

variable "az_count" {
  default = ""
}

variable "tgw_vpc" {
  default     = false
  description = "Decides if VPC should be attached to a TGW"
}

variable "transit_gw" {
  default = ""
}

variable "avtx_gw_size" {
  default = ""
}

variable "hpe" {
  default = false
}

variable "tgw_name" {
  default = ""
}

variable "test_ec2" {
  default = false
}

variable "security_domain_name" {
  default = ""
}

variable "tag_department" {
  default = ""
}

variable "tag_environment" {
  default = ""
}

variable "tag_domain" {
  default = ""
}

variable "region_ami" {
  type = map
  default = {
    eu-central-1   = "ami-0767046d1677be5a0"
    eu-west-1      = "ami-0947873a35c4b08ea"
    us-east-1      = "ami-075a86d91e6db7f81"
    us-west-1      = "ami-0c594ceb405f762ee"
    us-west-2      = "ami-025102f49d03bec05"
    ap-northeast-1 = "ami-0caf5bea3d6dc4fee"
    ap-southeast-1 = "ami-04d4984813eb75ddb"
  }
}

variable "migrate_to_swan" {
  default     = false
  description = "Forces creation of dummy S2C to switch gateway to strongswan in 6.3. Not needed in 6.4 release"
}
