locals {
  config = jsondecode(file("${path.module}/../config.json"))
}

locals {
  pub_key_dir  = "../${local.config.ssh_keys_dir}"
  pub_key_info = local.config.user_to_attacker_ssh_key
  pub_key_path = "${local.pub_key_dir}/${local.pub_key_info.name}.pub"
  selected_ami = lookup({
    linux   = data.aws_ami.linux.id,
    windows = data.aws_ami.windows.id,
    macos   = data.aws_ami.macos.id
  }, local.config.target_machine_os, data.aws_ami.linux.id)
}

variable "availability_zone" {
  description = "Availability Zone to deploy resources in"
  type        = string
  default     = ""
}

// Key-pair for attacker machine
resource "aws_key_pair" "user_attacker_key" {
  key_name   = local.pub_key_info.name
  public_key = file(local.pub_key_path)
}

data "aws_ami" "linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

data "aws_ami" "windows" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Windows_Server-2019-English-Full-Base-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "macos" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn-ec2-macos-*"]
  }

  filter {
    name   = "architecture"
    values = ["arm64_mac"]
  }
}

resource "aws_ec2_host" "mac_host" {
  instance_type       = "mac2-m2.metal"
  availability_zone  = var.availability_zone
  host_recovery       = "on"
  count               = local.selected_ami == data.aws_ami.macos.id ? 1 : 0
}




