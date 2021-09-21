terraform {
  required_providers {
    azurerm = {
      source           = "hashicorp/azurerm"
      required_version = "~> 2.44.0"
    }
  }
  required_version = ">= 0.13"
}
