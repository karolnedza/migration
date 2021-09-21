data "aws_availability_zones" "az_available" {}

resource "aviatrix_vpc" "on_prem_sim" {
  cloud_type           = 1
  account_name         = var.account_name
  region               = var.region
  name                 = var.name
  cidr                 = var.cidr
  aviatrix_transit_vpc = false
  aviatrix_firenet_vpc = false
}

resource aws_network_interface eni_0 {
  subnet_id         = aviatrix_vpc.on_prem_sim.subnets[length(data.aws_availability_zones.az_available.names)].subnet_id
  security_groups   = [aws_security_group.csr_public.id]
  source_dest_check = false
  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-CSR-Public"
  }
}

resource aws_network_interface eni_1 {
  subnet_id         = aviatrix_vpc.on_prem_sim.subnets[0].subnet_id
  security_groups   = [aws_security_group.csr_private.id]
  source_dest_check = false
  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-CSR-Private"
  }
}

resource aws_eip csr_eip {
  vpc = true
  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-CSR"
  }
}

resource aws_eip_association eip_assoc {
  network_interface_id = aws_network_interface.eni_0.id
  allocation_id        = aws_eip.csr_eip.id
}


resource "aws_instance" "csr" {
  key_name      = var.key_name
  ami           = var.csr_ami
  instance_type = "c5.large"

  network_interface {
    network_interface_id = aws_network_interface.eni_0.id
    device_index         = 0
  }

  network_interface {
    network_interface_id = aws_network_interface.eni_1.id
    device_index         = 1
  }

  root_block_device {
    volume_size = "8"
    volume_type = "gp2"
  }

  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-CSR"
  }
}

resource "aws_security_group" "csr_public" {
  name   = "${aviatrix_vpc.on_prem_sim.name} - All RFC1918, IPSec, ssh"
  vpc_id = aviatrix_vpc.on_prem_sim.vpc_id
  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name} - All RFC1918, IPSec, ssh"
  }
}

resource "aws_security_group_rule" "egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.csr_public.id
}

resource "aws_security_group_rule" "ingress_all" {
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
  security_group_id = aws_security_group.csr_public.id
}

resource "aws_security_group_rule" "ingress_ipsec_1" {
  count             = length(var.ipsec_endpoints) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 500
  to_port           = 500
  protocol          = "udp"
  cidr_blocks       = var.ipsec_endpoints
  security_group_id = aws_security_group.csr_public.id
}

resource "aws_security_group_rule" "ingress_ipsec_2" {
  count             = length(var.ipsec_endpoints) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 4500
  to_port           = 4500
  protocol          = "udp"
  cidr_blocks       = var.ipsec_endpoints
  security_group_id = aws_security_group.csr_public.id
}

resource "aws_security_group_rule" "ingress_ssh" {
  count             = length(var.ssh_addresses) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_addresses
  security_group_id = aws_security_group.csr_public.id
}


resource "aws_security_group" "csr_private" {
  name   = "${aviatrix_vpc.on_prem_sim.name} - All RFC1918"
  vpc_id = aviatrix_vpc.on_prem_sim.vpc_id
  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name} - All RFC1918"
  }
}

resource "aws_security_group_rule" "egress_all_private" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.csr_private.id
}

resource "aws_security_group_rule" "ingress_all_private" {
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
  security_group_id = aws_security_group.csr_private.id
}

data "aws_ami" "ubuntu_server" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-*"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "test_instance_public" {
  key_name                    = var.key_name
  ami                         = var.ami == "" ? data.aws_ami.ubuntu_server.id : var.ami
  instance_type               = var.instance_type
  subnet_id                   = aviatrix_vpc.on_prem_sim.subnets[length(data.aws_availability_zones.az_available.names)].subnet_id
  vpc_security_group_ids      = [aws_security_group.csr_public.id]
  associate_public_ip_address = true

  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-public-ubuntu"
  }
}

resource "aws_instance" "test_instance_private" {
  key_name                    = var.key_name
  ami                         = var.ami == "" ? data.aws_ami.ubuntu_server.id : var.ami
  instance_type               = var.instance_type
  subnet_id                   = aviatrix_vpc.on_prem_sim.subnets[0].subnet_id
  vpc_security_group_ids      = [aws_security_group.csr_private.id]
  associate_public_ip_address = false
  private_ip                  = var.fixed_private_ip ? join("", [regex("([\\d+\\.]+)(\\.\\d+/\\d+)", aviatrix_vpc.on_prem_sim.subnets[0].cidr)[0], ".", var.private_ip]) : null

  tags = {
    Name = "${aviatrix_vpc.on_prem_sim.name}-private-ubuntu"
  }
}

