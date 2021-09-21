variable "region" {}

variable "account_name" {}

variable "role_arn" {}

variable "vpc_name" {}

variable "vpc_cidr" {
  type = list(string)
}

variable "vpc_id" {}

variable "avtx_cidr" {
  default     = ""
  description = "CIDR used by the Aviatrix gateways"
}

variable "tgw_vpc" {
  default     = false
  description = "Decides if VPC should be attached to a TGW"
}

variable "avtx_gw_size" {
  default = ""
}

variable "hpe" {
  default = false
}

variable "igw_id" {}

variable "route_tables" {}

variable "gw_name_suffix" {
  default = ""
}

variable "gw_zones" {
  type = list
}

variable "switch_traffic" {
  type    = bool
  default = false
}
