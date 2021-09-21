variable "vpc_name" {}

variable "vpc_cidr" {}

variable "region" {}

variable "local_as_number" {}

variable "hpe" {
  type    = bool
  default = true
}

variable "avtx_gw_size" {}

variable "account_name" {}

variable "attach_tgw" {
  type = bool
}

variable "enable_firenet" {
  type = bool
}

variable "tgw_asn" {}

variable "bgp_polling_time" {}
