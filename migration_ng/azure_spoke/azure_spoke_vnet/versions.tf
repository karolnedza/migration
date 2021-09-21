terraform {
  required_providers {
    azurerm = {
      source           = "hashicorp/azurerm"
      required_version = "~> 2.46.0"
    }
    aviatrix = {
      source           = "aviatrixsystems/aviatrix"
      required_version = "~> 2.18.0"
    }
  }
}
