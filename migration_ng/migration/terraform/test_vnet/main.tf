data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

data "aws_ssm_parameter" "avx-azure-client-secret" {
  name     = "avx-azure-client-secret"
  provider = aws.us_west_2
}

data "aws_ssm_parameter" "avx-vstsnetworkengsandbox-secret" {
  name     = "avx-vstsnetworkengsandbox-secret"
  provider = aws.us_west_2
}
