resource "aviatrix_account" "azure" {
  cloud_type          = 8  
  account_name        = var.account_name
  arm_subscription_id = var.ARM_SUBSCRIPTION_ID
  arm_directory_id    = var.ARM_TENANT_ID
  arm_application_id  = var.ARM_CLIENT_ID
  arm_application_key = var.ARM_CLIENT_SECRET
}

