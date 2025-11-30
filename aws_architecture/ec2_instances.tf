resource "aws_instance" "attacker_machine" {
    ami = local.final_attacker_ami
    
    instance_type = "m7i-flex.large"

    private_ip = local.config.attacker_private_ip
    vpc_security_group_ids = [ aws_security_group.attacker_machine_sg.id ]
    key_name = aws_key_pair.user_attacker_key.key_name
    availability_zone = local.config.availability_zone
    associate_public_ip_address = true
    subnet_id = aws_subnet.lab_public_subnet.id
    
    tags = {
        Name = "attacker_machine"
    }
    
    root_block_device {
      volume_size = 30
    }
}

resource "aws_instance" "logging_machine" {
    ami = local.final_logging_ami

    instance_type = "m7i-flex.large"

    private_ip = local.config.logging_private_ip
    vpc_security_group_ids = [ aws_security_group.logging_machine_sg.id ]
    key_name = aws_key_pair.internal_lab_key.key_name
    availability_zone = local.config.availability_zone
    subnet_id = aws_subnet.lab_private_subnet.id
    
    tags = {
        Name = "logging_machine"
    }
    
    root_block_device {
      volume_size = 30
    }

}

resource "aws_instance" "target_machine" {
    ami = local.final_target_ami

    instance_type = local.config.target_machine_os == "macos" ? "mac2-m2.metal" : "m7i-flex.large"
    private_ip = local.config.target_private_ip
    vpc_security_group_ids = [ aws_security_group.target_machine_sg.id ]
    key_name = aws_key_pair.internal_lab_key.key_name
    availability_zone = local.config.availability_zone
    subnet_id = aws_subnet.lab_private_subnet.id
    host_id   = local.config.target_machine_os == "macos" ? aws_ec2_host.mac_host[0].id : null
    user_data = local.config.target_machine_os == "windows" ? file("../target/windows/user_data_windows") : null 
    tags = {
        Name = "target_machine"
    }

    root_block_device {
      volume_size = 30
    }
}