terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "aws" {
  region = "us-west-2"
  alias  = "aviatrix_pilot"
  allowed_account_ids = ["834631631796"]
  assume_role {role_arn = "arn:aws:iam::834631631796:role/aviatrix-role-app" }
}

