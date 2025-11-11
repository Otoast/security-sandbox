resource "aws_vpc" "lab_vpc" {
    cidr_block = "10.0.0.0/16"   
}

// Subnets
resource "aws_subnet" "lab_public_subnet" {
    vpc_id = aws_vpc.lab_vpc.id
    cidr_block = "10.0.2.0/23"
}

resource "aws_subnet" "lab_private_subnet" {
    vpc_id = aws_vpc.lab_vpc.id
    cidr_block = "10.0.0.0/23"
}

// IGW
resource "aws_internet_gateway" "lab_public_igw" {
    vpc_id = aws_vpc.lab_vpc.id
}

// Route Tables
resource "aws_route_table" "lab_public_route_table" {
    vpc_id = aws_vpc.lab_vpc.id

    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.lab_public_igw.id
    }

    route {
        cidr_block = "10.0.0.0/16"
        gateway_id = "local"
    }
}

resource "aws_route_table" "lab_private_route_table" {
    vpc_id = aws_vpc.lab_vpc.id

    route {
        cidr_block = "10.0.0.0/16"
        gateway_id = "local"
    }
}

resource "aws_route_table_association" "lab_public_route_table_association" {
    route_table_id = aws_route_table.lab_public_route_table.id
    subnet_id = aws_subnet.lab_public_subnet.id
}

resource "aws_route_table_association" "lab_private_route_table_association" {
    route_table_id = aws_route_table.lab_private_route_table.id
    subnet_id = aws_subnet.lab_private_subnet.id
}

// Security Groups

# --- Security Groups ---
resource "aws_security_group" "attacker_machine_sg" {
  name   = "attacker_machine_sg"
  vpc_id = aws_vpc.lab_vpc.id
}

resource "aws_security_group" "target_machine_sg" {
  name   = "target_machine_sg"
  vpc_id = aws_vpc.lab_vpc.id
}

resource "aws_security_group" "logging_machine_sg" {
  name   = "logging_machine_sg"
  vpc_id = aws_vpc.lab_vpc.id
}

# --- Security Group Rules ---

# Attacker → Logging (Kibana)
resource "aws_security_group_rule" "attacker_to_logging_kibana" {
  type                     = "egress"
  from_port                = 5601
  to_port                  = 5601
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Kibana port"
}

# Attacker → Logging (Elasticsearch)
resource "aws_security_group_rule" "attacker_to_logging_elasticsearch" {
  type                     = "egress"
  from_port                = 9200
  to_port                  = 9200
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Elasticsearch port"
}

# Attacker → Target (SSH)
resource "aws_security_group_rule" "attacker_to_target_ssh" {
  type                     = "egress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.target_machine_sg.id
  description              = "SSH into target, Ansible setup"
}

# Attacker → Logging (SSH)
resource "aws_security_group_rule" "attacker_to_logging_ssh" {
  type                     = "egress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "SSH into logging machine"
}

# Attacker ← External (User SSH)
resource "aws_security_group_rule" "user_to_attacker_ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["165.91.13.66/32"] # TODO: change to your real IP
  security_group_id = aws_security_group.attacker_machine_sg.id
  description       = "Accept SSH connection from user"
}

# Target ← Attacker (SSH)
resource "aws_security_group_rule" "target_from_attacker_ssh" {
  type                     = "ingress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.target_machine_sg.id
  description              = "Accept SSH from attacker machine"
}

# Target → Logging (Fleet Server)
resource "aws_security_group_rule" "target_to_logging_fleet" {
  type                     = "egress"
  from_port                = 8220
  to_port                  = 8220
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.target_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Send logs to Fleet server"
}

# Logging ← Target (Fleet Server)
resource "aws_security_group_rule" "logging_from_target_fleet" {
  type                     = "ingress"
  from_port                = 8220
  to_port                  = 8220
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.target_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Fleet server port"
}

# Logging ← Attacker (Kibana)
resource "aws_security_group_rule" "logging_from_attacker_kibana" {
  type                     = "ingress"
  from_port                = 5601
  to_port                  = 5601
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Kibana port"
}

# Logging ← Attacker (Elasticsearch)
resource "aws_security_group_rule" "logging_from_attacker_elasticsearch" {
  type                     = "ingress"
  from_port                = 9200
  to_port                  = 9200
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Elasticsearch port"
}

# Logging ← Attacker (SSH)
resource "aws_security_group_rule" "logging_from_attacker_ssh" {
  type                     = "ingress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "Accept SSH from attacker machine"
}
