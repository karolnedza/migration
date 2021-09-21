terraform {
  required_providers {
    aviatrix = {
      source  = "aviatrixsystems/aviatrix"
      version = $aviatrix_provider
    }
    aws = {
      source  = "hashicorp/aws"
      version = $aws_provider
    }
  }
  required_version = $terraform_version
}
