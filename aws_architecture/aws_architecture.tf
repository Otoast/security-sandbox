// VPC
resource "aws_vpc" "lab_vpc" {
    cidr_block = "10.0.0.0/16"
    
    tags = merge(local.common_tags, {
        Name = "lab_vpc"
    })
}

// Subnets
resource "aws_subnet" "lab_public_subnet" {
    vpc_id = aws_vpc.lab_vpc.id
    cidr_block = "10.0.2.0/23"
    availability_zone = local.config.availability_zone
    tags = merge(local.common_tags, {
      Name = "lab_public_subnet"
    })
}

resource "aws_subnet" "lab_private_subnet" {
    vpc_id = aws_vpc.lab_vpc.id
    availability_zone = local.config.availability_zone
    cidr_block = "10.0.0.0/23"
    tags = merge(local.common_tags, {
      Name = "lab_private_subnet"
    })
}

// IGW
resource "aws_internet_gateway" "lab_public_igw" {
    vpc_id = aws_vpc.lab_vpc.id
    tags = merge(local.common_tags, {
        Name = "lab_public_igw"
    })
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
    tags = merge(local.common_tags, {
        Name = "lab_public_route_table"
    })
}

resource "aws_route_table" "lab_private_route_table" {
  vpc_id = aws_vpc.lab_vpc.id

  # Local route for the VPC
  route {
    cidr_block = "10.0.0.0/16"
    gateway_id = "local"
  }

  # Conditional default route via NAT (only when enable_provisioning = true)
  dynamic "route" {
    for_each = var.enable_provisioning ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.temp_nat_gateway[0].id
    }
  }

  tags = merge(local.common_tags, {
    Name = "lab_private_route_table"
  })
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
  
  tags = merge(local.common_tags, {
    Name = "attacker_machine_sg"
  })
}

resource "aws_security_group" "target_machine_sg" {
  name   = "target_machine_sg"
  vpc_id = aws_vpc.lab_vpc.id
  
  tags = merge(local.common_tags, {
    Name = "target_machine_sg"
  })
}

resource "aws_security_group" "logging_machine_sg" {
  name   = "logging_machine_sg"
  vpc_id = aws_vpc.lab_vpc.id
  
  tags = merge(local.common_tags, {
    Name = "logging_machine_sg"
  })
}

# --- Security Group Rules ---

# Attacker → Internet (for package updates, Atomic Red Team, tools)
resource "aws_security_group_rule" "attacker_to_internet" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.attacker_machine_sg.id
  description       = "Allow outbound internet for tools/packages"
}

# Attacker → Logging (Kibana)
resource "aws_security_group_rule" "attacker_to_logging_kibana" {
  type                     = "egress"
  from_port                = 5601
  to_port                  = 5601
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.logging_machine_sg.id
  security_group_id        = aws_security_group.attacker_machine_sg.id
  description              = "attacker access Kibana port"
}

# Attacker → Logging (Elasticsearch)
resource "aws_security_group_rule" "attacker_to_logging_elasticsearch" {
  type                     = "egress"
  from_port                = 9200
  to_port                  = 9200
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.logging_machine_sg.id
  security_group_id        = aws_security_group.attacker_machine_sg.id
  description              = "attacker access Elasticsearch port"
}

# Attacker → Target (SSH)
resource "aws_security_group_rule" "attacker_to_target_ssh" {
  type                     = "egress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.target_machine_sg.id
  security_group_id        = aws_security_group.attacker_machine_sg.id
  description              = "SSH into target, Ansible setup"
}

# Attacker → Logging (SSH)
resource "aws_security_group_rule" "attacker_to_logging_ssh" {
  type                     = "egress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.logging_machine_sg.id
  security_group_id        = aws_security_group.attacker_machine_sg.id
  description              = "SSH into logging machine"
}

# Attacker ← External (User SSH)
resource "aws_security_group_rule" "user_to_attacker_ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks = ["${local.config.user_ip}/32"]
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
  source_security_group_id = aws_security_group.logging_machine_sg.id
  security_group_id        = aws_security_group.target_machine_sg.id
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
  description              = "Accept logs sent by target to Fleet port"
}

# Logging ← Attacker (Kibana)
resource "aws_security_group_rule" "logging_from_attacker_kibana" {
  type                     = "ingress"
  from_port                = 5601
  to_port                  = 5601
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "attacker allow access to Kibana port"
}

# Logging ← Attacker (Elasticsearch)
resource "aws_security_group_rule" "logging_from_attacker_elasticsearch" {
  type                     = "ingress"
  from_port                = 9200
  to_port                  = 9200
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.attacker_machine_sg.id
  security_group_id        = aws_security_group.logging_machine_sg.id
  description              = "attacker allow access to Elasticsearch port"
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

// NAT Gateway provisioning (temporary, only if provisioning is enabled)

# Create EIP only if provisioning is enabled
resource "aws_eip" "nat" {
  count      = var.enable_provisioning ? 1 : 0
  domain    = "vpc"

  tags = merge(local.common_tags, {
    Name = "temp_nat_eip"
  })
}

# Create NAT Gateway
resource "aws_nat_gateway" "temp_nat_gateway" {
  count             = var.enable_provisioning ? 1 : 0
  allocation_id     = aws_eip.nat[0].id
  subnet_id         = aws_subnet.lab_public_subnet.id
  depends_on        = [aws_eip.nat]
  tags = merge(local.common_tags, {
    Name = "temp_nat_gateway"
  })
}


# Logging → Internet (for installing ELK Stack and APR)
resource "aws_security_group_rule" "logging_to_internet" {
  count             = var.enable_provisioning ? 1 : 0
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.logging_machine_sg.id
  description       = "Allow outbound internet to install Elastic Packages (only if NAT Gateway present)"
}
