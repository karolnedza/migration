terraform {
  required_providers {
    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = "~> 2.18.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 3.58.0"
    }
  }
  required_version = ">= 0.13"
}
