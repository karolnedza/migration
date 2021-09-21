variable "region" {}

variable "account_name" {}


variable "vpc_name" {}

variable "vpc_cidr" {
  description = "CIDR used by the applications"
}

variable "subnet_offset" {
  type        = string
  description = "Difference between VPC and subnet prefix lenght"
}

variable "avtx_cidr" {
  default     = ""
  description = "CIDR used by the Aviatrix gateways"
}

variable "subnet_count" {
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

variable "security_domain_name" {
  default = ""
}

variable "az_names" {
  type        = list
  description = "AZs available in the region"
}
