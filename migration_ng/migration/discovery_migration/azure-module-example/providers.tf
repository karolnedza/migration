provider "azurerm" {
  features {}
}

provider "aviatrix" {
  username      = "terraform-guy"
  password      = var.controller_password
  controller_ip = var.controller_ip
}
