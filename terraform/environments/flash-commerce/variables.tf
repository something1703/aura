variable "primary_region" {
  description = "Matches config/flash-commerce.yaml geography.primary_regions[0]."
  type        = string
  default     = "ap-south-1"
}

variable "secondary_region" {
  description = "AURA's assumed DR pairing for ap-south-1 (see aura.architecture.generator.choose_secondary_region)."
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Distinguishes this from a real production deployment; used in resource names/tags."
  type        = string
  default     = "demo"
}

variable "container_image" {
  description = "Placeholder demo application image. Replace with the real application before this is anything more than a demo."
  type        = string
  default     = "public.ecr.aws/nginx/nginx:1.27"
}

variable "primary_desired_count" {
  description = "Fargate task count in the primary region."
  type        = number
  default     = 3
}

variable "secondary_desired_count" {
  description = "Fargate task count in the secondary region (smaller: warm standby, not full parity)."
  type        = number
  default     = 2
}

variable "database_instance_class" {
  description = "Small/cheap by default for a demo. db.t3.micro rather than db.t4g.micro: see modules/database/variables.tf for why. Size up for anything beyond a demo."
  type        = string
  default     = "db.t3.micro"
}

variable "database_multi_az_secondary" {
  description = "AURA models the warm-standby secondary database as Multi-AZ too (a live copy, not cold). Set false to cut replica cost in half for a cheaper demo."
  type        = bool
  default     = true
}
