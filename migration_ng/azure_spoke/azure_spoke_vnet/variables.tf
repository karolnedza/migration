variable "region" {}

variable "account_name" {}

variable "resource_group_name" {}

variable "vnet_name" {}

variable "vnet_cidr" {
  description = "CIDR used by the applications"
}

variable "avtx_cidr" {
  default     = ""
  description = "CIDR used by the Aviatrix gateways"
}

variable "subnets" {
}

variable "service_subnets" {
  default = {}
}

variable "avtx_gw_size" {
  default = ""
}

variable "hpe" {
  default = false
}

variable "use_azs" {
  type = bool
}

variable "native_peering" {
  type = bool
}
