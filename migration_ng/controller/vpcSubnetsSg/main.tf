resource "aws_vpc" "vpc" {
  cidr_block           = cidrsubnet(var.aws_cidr_block, var.vpc_cidr_offset, var.vpc_IP)
  enable_dns_hostnames = "true"

  tags = {
    Name = var.vpc_name_prefix == "" ? var.vpc_name : "${var.vpc_name_prefix} - ${var.vpc_name}"
  }
}

resource "aws_internet_gateway" "IGW" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = aws_vpc.vpc.tags["Name"]
  }
}

resource "aws_route_table" "public_RT" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "${aws_vpc.vpc.tags["Name"]} - Public"
  }
}

resource "aws_route" "default" {
  route_table_id         = aws_route_table.public_RT.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.IGW.id
}

resource "aws_route_table" "private_RT" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "${aws_vpc.vpc.tags["Name"]} - Private"
  }
}

resource "aws_subnet" "public_subnet" {
  count = length(var.public_subnet_IPs)

  vpc_id                  = aws_vpc.vpc.id
  cidr_block              = cidrsubnet(aws_vpc.vpc.cidr_block, var.subnet_cidr_offset, var.public_subnet_IPs[count.index])
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = join(" - ", [aws_vpc.vpc.tags["Name"], "Public", element(split("-", var.azs[count.index]), 2)])
  }
}

resource "aws_route_table_association" "public_rt_association" {
  count = length(var.public_subnet_IPs)

  subnet_id      = aws_subnet.public_subnet[count.index].id
  route_table_id = aws_route_table.public_RT.id
}

resource "aws_subnet" "private_subnet" {
  count = length(var.private_subnet_IPs)

  vpc_id                  = aws_vpc.vpc.id
  cidr_block              = cidrsubnet(aws_vpc.vpc.cidr_block, var.subnet_cidr_offset, var.private_subnet_IPs[count.index])
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = join(" - ", [aws_vpc.vpc.tags["Name"], "Private", element(split("-", var.azs[count.index]), 2)])
  }
}

resource "aws_route_table_association" "private_rt_association" {
  count = length(var.private_subnet_IPs)

  subnet_id      = aws_subnet.private_subnet[count.index].id
  route_table_id = aws_route_table.private_RT.id
}

resource "aws_security_group" "sg" {
  name   = "${aws_vpc.vpc.tags["Name"]} - All int + ssh, https & netflow"
  vpc_id = aws_vpc.vpc.id
  tags = {
    Name = "${aws_vpc.vpc.tags["Name"]} - All int + ssh, https & netflow"
  }
}

resource "aws_security_group_rule" "egress_all" {
  count             = length(var.all_out_addresses) == 0 ? 0 : 1
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = var.all_out_addresses
  security_group_id = aws_security_group.sg.id
}

resource "aws_security_group_rule" "ingress_all" {
  count             = length(var.all_in_addresses) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = var.all_in_addresses
  security_group_id = aws_security_group.sg.id
}

resource "aws_security_group_rule" "ingress_ssh" {
  count             = length(var.ssh_addresses) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_addresses
  security_group_id = aws_security_group.sg.id
}

resource "aws_security_group_rule" "ingress_https" {
  count             = length(var.ssh_addresses) == 0 ? 0 : 1
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.ssh_addresses
  security_group_id = aws_security_group.sg.id
}

resource "aws_security_group_rule" "ingress_netflow" {
  type              = "ingress"
  from_port         = 31283
  to_port           = 31283
  protocol          = "udp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.sg.id
}
