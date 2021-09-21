
output "vpc_id" {
  value = aws_vpc.vpc.id
}

output "subnet_id_az1" {
  value = aws_subnet.public_subnet[0].id
}

output "subnet_id_az2" {
  value = aws_subnet.public_subnet[1].id
}

output "sg_id" {
  value = aws_security_group.sg.id
}
