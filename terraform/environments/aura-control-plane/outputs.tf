output "alb_dns_name" {
  value = module.compute.alb_dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.aura_api.repository_url
}
