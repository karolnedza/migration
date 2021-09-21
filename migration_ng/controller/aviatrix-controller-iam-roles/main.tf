resource aws_iam_role aviatrix-role-ec2 {
  name               = var.ec2_role_name
  description        = "Aviatrix EC2 - Created by Terraform+Aviatrix"
  path               = "/"
  assume_role_policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
      {
         "Effect": "Allow",
         "Principal": {
           "Service": [
              "ec2.amazonaws.com"
           ]
         },
         "Action": [
           "sts:AssumeRole"
         ]
       }
    ]
}
EOF
}

resource aws_iam_role aviatrix-role-app {
  name               = var.app_role_name
  description        = "Aviatrix APP - Created by Terraform+Aviatrix"
  path               = "/"
  assume_role_policy = var.external_controller_account_id == "" ? local.policy_primary : local.policy_cross
}


resource aws_iam_policy aviatrix-assume-role-policy {
  name        = "Networking.Aviatrix.AssumeRolePolicy"
  path        = "/"
  description = "Policy for creating NIKE.Networking.Aviatrix.Ec2" 
  policy      = templatefile("${path.module}/iam_assume_role_policy.txt", { account_number = var.account_number, app_role_name = var.app_role_name })
}

resource aws_iam_policy aviatrix-app-policy {
  name        = "Networking.Aviatrix.AppPolicy"
  path        = "/"
  description = "Policy for creating NIKE.Networking.Aviatrix.App"
  policy      = templatefile("${path.module}/iam_access_policy.txt", { account_number = var.account_number, app_role_name = var.app_role_name })
}

resource aws_iam_role_policy_attachment aviatrix-role-ec2-attach {
  role       = aws_iam_role.aviatrix-role-ec2.name
  policy_arn = aws_iam_policy.aviatrix-assume-role-policy.arn
}

resource aws_iam_role_policy_attachment aviatrix-role-app-attach {
  role       = aws_iam_role.aviatrix-role-app.name
  policy_arn = aws_iam_policy.aviatrix-app-policy.arn
}

resource aws_iam_instance_profile aviatrix-role-ec2_profile {
  name = aws_iam_role.aviatrix-role-ec2.name
  role = aws_iam_role.aviatrix-role-ec2.name
}

