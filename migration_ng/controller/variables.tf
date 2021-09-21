variable "region" {
}
variable "vpcCIDRblock" {
}

variable "instanceTenancy" {
  default = "default"
}
variable "dnsSupport" {
  default = true
}
variable "dnsHostNames" {
  default = true
}
# TagGuid
variable "tag_department" {
}
# Environment
variable "tag_environment" {
}
variable "tag_application" {
}
variable "tag_domain" {
}
variable "vpc_name" {
}

# 

variable "keypair_name" {}

variable "license_type" {}

variable "access_account_name" {}

variable "admin_email" {}

#variable "admin_password" {}

variable "customer_license_id" {
}

variable "ec2role" {
  default = ""
}

variable controller_version {
  type        = string
  default     = "latest"
  description = "The version in which you want launch Aviatrix controller"
}

variable "instance_type" {
}

variable "app_role_name" {}

variable "ec2_role_name" {}

variable "controller_account_id" {}

variable "root_volume_size" {}