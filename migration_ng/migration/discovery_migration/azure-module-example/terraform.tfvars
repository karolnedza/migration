vnet_name = "brown-field-test-01"
vnet_cidr = ["10.13.80.0/24"]
subnets = {
  internal = {
    subnet_cidr = "10.13.80.0/25"
  }
  dmz = {
    subnet_cidr = "10.13.80.128/28"
  }
  netapp = {
    subnet_cidr = "10.13.80.144/28"
  }
  sql = {
    subnet_cidr = "10.13.80.160/28"
  }
  webserverfarms = {
    subnet_cidr = "10.13.80.176/28"
  }
}
avtx_cidr           = "10.52.6.0/25"
hpe                 = true
avtx_gw_size        = "Standard_D3_v2"
native_peering      = false
region              = "East US"
use_azs             = false # Set to false if region above doesn't support AZs
resource_group_name = "rg-av-spokes-in-here-129014" # Assumed as existing
account_name        = "Azure-Sky"
