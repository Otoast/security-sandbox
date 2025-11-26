
output "attacker_instance_id" {
  value = aws_instance.attacker_machine.id
}

output "target_instance_id" {
  value = aws_instance.target_machine.id
}

output "logging_instance_id" {
  value = aws_instance.logging_machine.id
}