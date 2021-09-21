terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "$arm_provider"
    }

    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = "$aviatrix_provider"
    }
  }
  required_version = "$terraform_version"
}
