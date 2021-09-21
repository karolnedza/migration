terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = "=2.19.5"
    }
  }
  required_version = ">= 0.14"
}
