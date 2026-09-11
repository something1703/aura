variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach this database (the application tier)."
  type        = list(string)
}

variable "engine" {
  type    = string
  default = "postgres"
}

variable "engine_version" {
  type    = string
  default = "16.4"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "multi_az" {
  description = "AURA's topology drives this: primary always true; the warm-standby replica is also true (it is a live, Multi-AZ copy, not a cold single instance)."
  type        = bool
  default     = true
}

variable "db_name" {
  type    = string
  default = "flashcommerce"
}

variable "username" {
  type    = string
  default = "aura_app"
}

variable "replicate_source_db" {
  description = "ARN of the source DB instance to create this as a (cross-region) read replica of. Most other settings are inherited from the source when set."
  type        = string
  default     = null
}

variable "kms_key_id" {
  description = "KMS key for this instance's encrypted storage in this region. Required when replicate_source_db is set (cross-region replicas need a key local to the destination region)."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
