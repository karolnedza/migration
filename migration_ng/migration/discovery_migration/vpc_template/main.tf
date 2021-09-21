data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

resource "aviatrix_account" "aws_customer" {
  account_name       = "aws-$${var.aws_account}"
  cloud_type         = 1
  aws_account_number = var.aws_account
  aws_iam            = true
  audit_account      = false
  aws_role_app       = "arn:aws:iam::$${var.aws_account}:role/$${var.ctrl_role_app}"
  aws_role_ec2       = "arn:aws:iam::$${var.aws_ctrl_account}:role/$${var.ctrl_role_ec2}"
  aws_gateway_role_app       = "arn:aws:iam::$${var.aws_account}:role/$${var.gateway_role_app}"
  aws_gateway_role_ec2       = "arn:aws:iam::$${var.aws_account}:role/$${var.gateway_role_ec2}"
}

$s3_backend