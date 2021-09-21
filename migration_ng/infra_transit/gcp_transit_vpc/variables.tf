variable "account_name" {}
variable "region" {}
variable "vpc_cidr" {}
variable "vpc_name" {}
variable "hpe" {
  type = bool
}
variable "avtx_gw_size" {}
variable "local_as_number" {}
variable "enable_firenet" {
  type = bool
}
variable "bgp_polling_time" {}

