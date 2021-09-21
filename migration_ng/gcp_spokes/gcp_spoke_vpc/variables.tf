variable "aviatrix_cidr" {}
variable "account_name" {}
variable "region" {}
variable "vpc_cidr" {}
variable "vpc_name" {}
variable "hpe" {
  type = bool
}
variable "avtx_gw_size" {}
variable "detach_gw" {
  type = bool
  default = false
}
