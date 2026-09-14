output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "arn" {
  value = aws_db_instance.this.arn
}

output "id" {
  value = aws_db_instance.this.id
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "master_password_secret_arn" {
  description = "null on a replica (it has no credentials of its own — it inherits the primary's)."
  value       = var.replicate_source_db == null ? aws_secretsmanager_secret.master_password[0].arn : null
}
