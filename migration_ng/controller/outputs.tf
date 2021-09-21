output "result" {
  value = module.aviatrix-controller-initialize.result
}

output "controller_private_ip" {
  value = module.aviatrix-controller-build.private_ip
}

output "controller_public_ip" {
  value = module.aviatrix-controller-build.public_ip
}

output "controller_vpc_id" {
  value = aws_vpc.vpc.id
}

output "controller_sg_id" {
  value = module.aviatrix-controller-build.security_group_id
}

