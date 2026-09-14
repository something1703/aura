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
  description = "Major version only ('16', not '16.4'): AWS periodically retires specific RDS minor versions (16.4 through 16.8 are gone as of 2026-09), so pinning one goes stale on its own schedule. A bare major version lets RDS pick whichever minor is currently supported."
  type        = string
  default     = "16"
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

variable "is_replica" {
  description = "Set true alongside replicate_source_db. Kept as a separate literal (rather than inferring from `replicate_source_db != null`) because the caller passes a not-yet-created resource's ARN there — an unknown-until-apply value can't drive a `count` — while whether this instance *is* a replica is always known at plan time."
  type        = bool
  default     = false
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

variable "enable_alarms" {
  description = "Create CloudWatch alarms for this database (docs/IMPLEMENTATION_PHASES.md Phase 3 observability)."
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "SNS topic ARNs (or similar) to notify. Empty by default: alarms still exist and are visible in the console, they just don't page anyone until this is wired up."
  type        = list(string)
  default     = []
}

variable "replica_lag_alarm_threshold_seconds" {
  description = "Alarm when real cross-region replica lag exceeds this. Defaults to the warm-standby pattern's RPO envelope (see aura.architecture.catalog.MULTI_REGION_WARM_STANDBY) — this alarm directly checks, against real data, the RPO assumption the cost/failure engines already baked in."
  type        = number
  default     = 60
}
