resource "aws_instance" "attacker_machine" {
    ami = data.aws_ami.linux.id
    
    instance_type = "t3.micro"
    private_ip = "10.0.2.10"
    security_groups = [ aws_security_group.attacker_machine_sg.id ]
    key_name = aws_key_pair.user_attacker_key.key_name
    
    associate_public_ip_address = true
    subnet_id = aws_subnet.lab_public_subnet.id
    tags = {
        Name = "attacker_machine"
    }
}

resource "aws_instance" "logging_machine" {
    ami = data.aws_ami.linux.id

    instance_type = "t3.micro"
    private_ip = "10.0.1.10"
    security_groups = [ aws_security_group.logging_machine_sg.id ]
    key_name = aws_key_pair.internal_lab_key.key_name

    subnet_id = aws_subnet.lab_private_subnet.id
    tags = {
        Name = "logging_machine"
    }

}

resource "aws_instance" "target_machine" {
    ami = local.selected_ami

    instance_type = "t3.micro"
    private_ip = "10.0.0.10"
    security_groups = [ aws_security_group.target_machine_sg.id ]
    key_name = aws_key_pair.internal_lab_key.key_name

    subnet_id = aws_subnet.lab_private_subnet.id
    host_id   = local.selected_ami == data.aws_ami.macos.id ? aws_ec2_host.mac_host[0].id : null
    tags = {
        Name = "target_machine"
    }
}