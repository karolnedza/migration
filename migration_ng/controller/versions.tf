terraform {
  required_providers {
    aviatrix = {
      source           = "aviatrixsystems/aviatrix"
      required_version = "~> 2.18.0"
    }
    aws = {
      source           = "hashicorp/aws"
      required_version = "~> 3.15.0"
    }
  }
  required_version = ">= 0.13"
}
