
module "aviatrix-iam-roles" {
  source         = "./aviatrix-controller-iam-roles"
  account_number = var.controller_account_id
  app_role_name  = var.app_role_name
  ec2_role_name  = var.ec2_role_name
}


module "aviatrix-controller-build" {
  source            = "github.com/AviatrixSystems/terraform-modules.git//aviatrix-controller-build?ref=terraform_0.12"
  vpc               = aws_vpc.vpc.id
  subnet            = aws_subnet.public_subnet1.id
  keypair           = var.keypair_name
  ec2role           = module.aviatrix-iam-roles.aviatrix-role-ec2-name
  incoming_ssl_cidr = ["0.0.0.0/0"]
  type              = var.license_type
  instance_type     = var.instance_type
  root_volume_size  = var.root_volume_size
}

data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "avx-password" {
  name = "avx-admin-password"
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = module.aviatrix-controller-build.public_ip
}

module "aviatrix-controller-initialize" {
  source              = "github.com/AviatrixSystems/terraform-modules.git//aviatrix-controller-initialize?ref=terraform_0.12"
  admin_password      = data.aws_ssm_parameter.avx-password.value
  admin_email         = var.admin_email
  private_ip          = module.aviatrix-controller-build.private_ip
  public_ip           = module.aviatrix-controller-build.public_ip
  access_account_name = var.access_account_name
  aws_account_id      = data.aws_caller_identity.current.account_id
  vpc_id              = module.aviatrix-controller-build.vpc_id
  subnet_id           = module.aviatrix-controller-build.subnet_id
  customer_license_id = var.customer_license_id
  controller_version  = var.controller_version
}

