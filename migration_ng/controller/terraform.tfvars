region              = "us-west-2"
vpc_name            = "Network-Service"
vpcCIDRblock        = "10.50.4.0/23"
keypair_name        = "network-key"
instance_type       = "c5.4xlarge"
root_volume_size    = "64"
license_type        = "BYOL"         # Valid values are "meteredplatinum" and "BYOL"
access_account_name = "AWS-GNS-TEST" # name will be shown in the controller
controller_version  = "latest"       # This will install 6.3, change to 6.2 if you prefer it
tag_department      = "infrastructure engineering"
tag_environment     = "sandbox"
tag_application     = "nike-application"
tag_domain          = "infrastructure"
app_role_name       = "aviatrix-role-app" # Don't change for now
ec2_role_name       = "aviatrix-role-ec2" # Don't change for now

