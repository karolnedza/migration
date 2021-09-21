data "aws_ssm_parameter" "avx-password" {
  name     = "avx-admin-password"
  provider = aws.us_west_2
}

provider "aviatrix" {
  username      = "admin"
  password      = data.aws_ssm_parameter.avx-password.value
  controller_ip = var.controller_ip
}

module "gcp_spoke_1" {
  source        = "./gcp_spoke_vpc"
  vpc_name      = "gcp-us-west1-spoke1"
  vpc_cidr      = "10.184.180.0/24"
  aviatrix_cidr = "10.51.10.0/24"
  hpe           = true
  detach_gw     = false
  avtx_gw_size  = "n1-highcpu-4"
  region        = "us-west1"
  account_name  = "nike-aviatrix-test"
  providers = {
    google = google.us_west1
  }
}