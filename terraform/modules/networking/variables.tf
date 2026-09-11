variable "name" {
  description = "Name prefix for resources in this VPC (e.g. aura-demo-primary)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for this dedicated VPC. Never the account's default VPC (project requirement)."
  type        = string
}

variable "availability_zones" {
  description = "Availability Zones to spread public/private subnet pairs across."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Create a single NAT Gateway for private-subnet egress (cost-optimized: one, not one per AZ)."
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
