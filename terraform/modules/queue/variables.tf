variable "name" {
  type = string
}

variable "visibility_timeout_seconds" {
  description = "Should exceed the consumer's expected processing time. AURA's topology tags this queue as durable, visibility_timeout_seconds=30 (src/aura/architecture/generator.py) — kept in sync here."
  type        = number
  default     = 30
}

variable "message_retention_seconds" {
  description = "How long an unprocessed message survives. 4 days: long enough to ride out an extended compute-tier outage (see the DEPENDENCY_FAILURE / AZ_FAILURE scenarios in the failure model) without losing work."
  type        = number
  default     = 345600
}

variable "tags" {
  type    = map(string)
  default = {}
}
