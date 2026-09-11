output "primary_alb_dns_name" {
  value = module.compute_primary.alb_dns_name
}

output "secondary_alb_dns_name" {
  value = module.compute_secondary.alb_dns_name
}

output "primary_vpc_id" {
  value = module.network_primary.vpc_id
}

output "secondary_vpc_id" {
  value = module.network_secondary.vpc_id
}

output "primary_database_endpoint" {
  value     = module.database_primary.endpoint
  sensitive = true
}

output "secondary_database_endpoint" {
  value     = module.database_secondary.endpoint
  sensitive = true
}

output "cache_endpoint" {
  value = module.cache_primary.endpoint
}
