terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
    }

    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = "$aviatrix_provider"
    }
  }
  required_version = "$terraform_version"
}
