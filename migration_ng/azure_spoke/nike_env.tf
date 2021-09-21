
terraform {
  backend "s3" {}
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
  version                    = "=2.46.0"
  subscription_id            = "c071ec82-59ab-4825-8340-005741c5ff4e"
  client_id                  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  client_secret              = data.aws_ssm_parameter.avx-azure-client-secret.value
  tenant_id                  = "e299a644-a20f-492e-8471-57a29cac90c5"
  alias                      = "az_sandbox_01"
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
  version                    = "=2.46.0"
  subscription_id            = "7228b108-0a36-4ce6-8ea5-97815024a09a"
  client_id                  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  client_secret              = data.aws_ssm_parameter.avx-azure-client-secret.value
  tenant_id                  = "e299a644-a20f-492e-8471-57a29cac90c5"
  alias                      = "s0_sub_core_01"
}

resource "aviatrix_account" "s0-sub-core-01" {
  account_name        = "s0-sub-core-01"
  cloud_type          = 8
  arm_subscription_id = "7228b108-0a36-4ce6-8ea5-97815024a09a"
  arm_directory_id    = "e299a644-a20f-492e-8471-57a29cac90c5"
  arm_application_id  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  arm_application_key = data.aws_ssm_parameter.avx-azure-client-secret.value
}
