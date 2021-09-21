
terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "aws" {
  region = "us-west-1"
  alias  = "spoke_us_west_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "us-west-2"
  alias  = "spoke_us_west_2"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "us-east-1"
  alias  = "spoke_us_east_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "eu-west-1"
  alias  = "spoke_eu_west_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "eu-central-1"
  alias  = "spoke_eu_central_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "ap-northeast-1"
  alias  = "spoke_ap_northeast_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}

provider "aws" {
  region = "ap-southeast-1"
  alias  = "spoke_ap_southeast_1"
  allowed_account_ids = [var.aws_account]
  assume_role {role_arn = "arn:aws:iam::${var.aws_account}:role/networking.cicd.role" }
}




