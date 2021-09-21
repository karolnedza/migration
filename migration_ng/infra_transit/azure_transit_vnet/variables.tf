variable "vnet_name" {
  description = "Name of the vnet to create"
  type        = string
  default     = "acctvnet"
}
variable "resource_group_name" {
  description = "Name of the resource group to be imported."
  type        = string
}
variable "address_space" {
  type        = list(string)
  description = "The address space that is used by the virtual network."
  default     = ["10.0.0.0/16"]
}
#variable "tags" {}

variable "region" {}

variable "use_azs" {
  type = bool
}

variable "hpe" {
  type    = bool
  default = true
}

variable "avtx_gw_size" {}

variable "enable_firenet" {
  type = bool
}

variable "account_name" {}

variable "local_as_number" {}

variable "bgp_polling_time" {}