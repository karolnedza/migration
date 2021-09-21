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
variable "avtx_gw_size" {}
variable "hpe" {
  default = true
}
variable "use_azs" {
  type = bool
}
variable "route_tables" {}
variable "switch_traffic" {
  type    = bool
  default = false
}