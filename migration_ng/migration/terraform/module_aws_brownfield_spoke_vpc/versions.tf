terraform {
  required_providers {
    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = "= 2.19.4"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.43.0"
    }
  }
  required_version = ">= 0.14"
}
