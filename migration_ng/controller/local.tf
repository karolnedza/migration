data "aws_region" "current" {}

locals {
  vpc_subnets = [
    cidrsubnet(var.vpcCIDRblock, 2, 0),
    cidrsubnet(var.vpcCIDRblock, 2, 1),
    cidrsubnet(var.vpcCIDRblock, 2, 2),
    cidrsubnet(var.vpcCIDRblock, 2, 3),
  ]
}

# Define Common Tags
locals {
  common_tags = {
    nike-department  = var.tag_department
    nike-environment = var.tag_environment
    nike-domain      = var.tag_domain
    nike-application = var.tag_application
  }
}