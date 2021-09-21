terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "aws" {
  region = "us-east-1"
  alias  = "us_east_1"
}

provider "aws" {
  region = "us-west-1"
  alias  = "us_west_1"
}

provider "aws" {
  region = "eu-west-1"
  alias  = "eu_west_1"
}

provider "aws" {
  region = "eu-central-1"
  alias  = "eu_central_1"
}

provider "aws" {
  region = "ap-southeast-1"
  alias  = "ap_southeast_1"
}

provider "aws" {
  region = "ap-northeast-1"
  alias  = "ap_northeast_1"
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
  version                    = "=2.46.0"
  subscription_id            = "c071ec82-59ab-4825-8340-005741c5ff4e"
  client_id                  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  client_secret              = data.aws_ssm_parameter.avx-azure-client-secret.value
  tenant_id                  = "e299a644-a20f-492e-8471-57a29cac90c5"
}

resource "aviatrix_account" "temp_acc_azure" {
  account_name        = "az-sandbox-01"
  cloud_type          = 8
  arm_subscription_id = "c071ec82-59ab-4825-8340-005741c5ff4e"
  arm_directory_id    = "e299a644-a20f-492e-8471-57a29cac90c5"
  arm_application_id  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  arm_application_key = data.aws_ssm_parameter.avx-azure-client-secret.value
}

provider "google" {
  credentials = data.aws_ssm_parameter.avx-gcp-client-secret.value
  project     = "nike-aviatrix-test"
  region      = "us-west1"
  alias       = "us_west1"
}