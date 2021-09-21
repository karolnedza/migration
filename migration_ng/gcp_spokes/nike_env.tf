terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

data "aws_ssm_parameter" "avx-gcp-client-secret" {
  name     = "avx-gcp-client-secret"
  provider = aws.us_west_2
}

provider "google" {
  credentials = data.aws_ssm_parameter.avx-gcp-client-secret.value
  project     = "nike-aviatrix-test"
  region      = "us-west1"
  alias       = "us_west1"
}
