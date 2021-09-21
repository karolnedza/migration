variable "aws_cidr_block" {}

variable "vpc_name" {}

variable "vpc_name_prefix" {
  type    = string
  default = ""
}

variable "azs" {
  type = list
}

variable "vpc_IP" {
  description = "VPC IP based on mask seelected. For /24 1=1,2=2,..."
  type        = number
}

variable "vpc_cidr_offset" {
  description = "VPC suffix = base suffix + offset - /16 + 8 = /24"
  type        = number
}

variable "subnet_cidr_offset" {
  description = "subnet suffix = VPC suffix + offset"
  type        = number
}

variable "public_subnet_IPs" {
  description = "Defines No of subnets created and their IP, for /27 1=32, 2=64"
  type        = list(number)
}

variable "private_subnet_IPs" {
  description = "Defines No of subnets created and their IP, for /27 4=128, 5=160"
  type        = list(number)
}

variable "ssh_addresses" {
  type    = list
  default = []
}

variable "all_in_addresses" {
  type = list
}

variable "all_out_addresses" {
  type = list
}
