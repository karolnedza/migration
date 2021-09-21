provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

locals {
  role_arn = "arn:aws:iam::${var.aws_account}:role/${var.aws_account_role}"
}

provider "aws" {
  region              = "us-east-1"
  alias               = "spoke_us_east_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "us-east-2"
  alias               = "spoke_us_east_2"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "us-west-1"
  alias               = "spoke_us_west_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "us-west-2"
  alias               = "spoke_us_west_2"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "af-south-1"
  alias               = "spoke_af_south_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-east-1"
  alias               = "spoke_ap_east_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-south-1"
  alias               = "spoke_ap_south_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-northeast-1"
  alias               = "spoke_ap_northeast_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-northeast-2"
  alias               = "spoke_ap_northeast_2"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-northeast-3"
  alias               = "spoke_ap_northeast_3"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-southeast-1"
  alias               = "spoke_ap_southeast_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ap-southeast-2"
  alias               = "spoke_ap_southeast_2"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "ca-central-1"
  alias               = "spoke_ca_central_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-central-1"
  alias               = "spoke_eu_central_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-west-1"
  alias               = "spoke_eu_west_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-west-2"
  alias               = "spoke_eu_west_2"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-west-3"
  alias               = "spoke_eu_west_3"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-south-1"
  alias               = "spoke_eu_south_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "eu-north-1"
  alias               = "spoke_eu_north_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "me-south-1"
  alias               = "spoke_me_south_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}

provider "aws" {
  region              = "sa-east-1"
  alias               = "spoke_sa_east_1"
  allowed_account_ids = [var.aws_account]
  assume_role { role_arn = local.role_arn }
}