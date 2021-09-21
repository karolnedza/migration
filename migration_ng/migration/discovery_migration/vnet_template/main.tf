
data "aws_ssm_parameter" "avx-azure-client-secret" {
  name     = "avx-azure-client-secret"
  provider = aws.us_west_2
}


