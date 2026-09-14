output "api_alb_dns_name" {
  value = module.api.alb_dns_name
}

output "web_alb_dns_name" {
  description = "Point a browser here — this is the whole deployed app, UI and API together."
  value       = module.web.alb_dns_name
}

output "api_ecr_repository_url" {
  value = aws_ecr_repository.aura_api.repository_url
}

output "web_ecr_repository_url" {
  value = aws_ecr_repository.aura_web.repository_url
}
