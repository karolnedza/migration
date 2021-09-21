data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

resource "aviatrix_account" "aws_customer" {
  account_name       = "aws-${var.aws_account}"
  cloud_type         = 1
  aws_account_number = var.aws_account
  aws_iam            = true
  aws_role_app       = "arn:aws:iam::${var.aws_account}:role/aviatrix-role-app"
  aws_role_ec2       = "arn:aws:iam::${var.aws_account}:role/aviatrix-role-ec2"
}
