output "public_ip" {
  value = aws_eip.csr_eip.public_ip
}

output "vpc_id" {
  value = aviatrix_vpc.on_prem_sim.vpc_id

}
