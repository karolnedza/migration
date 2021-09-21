
output "transit_vpc_id" {
  value = aws_vpc.transit.id
}

output "ingress_egress_subnet_id_az1" {
  value = var.enable_firenet ? aws_subnet.public[0].id : ""
}

output "ingress_egress_subnet_id_az2" {
  value = var.enable_firenet ? aws_subnet.public[1].id : ""
}

output "gw_name" {
  value = aviatrix_transit_gateway.atgw.gw_name
}

output "atgw_public_ip" {
  value = aviatrix_transit_gateway.atgw.eip
}

output "atgw_ha_public_ip" {
  value = aviatrix_transit_gateway.atgw.ha_eip
}

output "asn" {
  value = aviatrix_transit_gateway.atgw.local_as_number
}
