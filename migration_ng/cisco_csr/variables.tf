
variable "ipsec_endpoints" {}
variable "ssh_addresses" {}

variable "region" {}

variable "key_name" {}
variable "name" {}

variable "account_name" {}
variable "cidr" {}
variable "csr_ami" {}

variable "ami" {
  default = ""
}

variable "instance_type" {
  default = "t3.micro"
}

variable "fixed_private_ip" {}

variable "private_ip" {
  type        = string
  description = "the last octet, module replaces xxx/xx in the subnet with this number"
  default     = ""
}

