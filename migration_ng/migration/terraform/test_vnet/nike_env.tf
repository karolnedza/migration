terraform {
  backend "s3" {
    bucket         = "nike-cicd-terraform-us-west-2-398538463346"
    key            = "aviatrix/azure-sandbox-spokes.tfstate"
    region         = "us-west-2"
    dynamodb_table = "nike-cicd-terraform-locktable"
    session_name   = "azure-sandbox-spokes"
  }
}

provider "aws" {
  region = "us-west-2"
  alias  = "us_west_2"
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
  subscription_id            = "c071ec82-59ab-4825-8340-005741c5ff4e"
  client_id                  = "f9ac510a-b663-46f1-8b82-05b4544fbe76"
  client_secret              = data.aws_ssm_parameter.avx-azure-client-secret.value
  tenant_id                  = "e299a644-a20f-492e-8471-57a29cac90c5"
  alias                      = "aviatrix"
}
