variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "container_image" {
  description = "Placeholder demo application image. Replace with the real application image before this is anything more than a demo."
  type        = string
  default     = "public.ecr.aws/nginx/nginx:1.27"
}

variable "container_port" {
  type    = number
  default = 80
}

variable "health_check_path" {
  description = "ALB target group health check path. The nginx placeholder demo image serves 200 at \"/\"; a real service (e.g. AURA's own API, which only defines /api/*) must override this."
  type        = string
  default     = "/"
}

variable "desired_count" {
  description = "Number of Fargate tasks. AURA sizes this per candidate/region; see the root module."
  type        = number
  default     = 2
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "cpu_architecture" {
  description = "Fargate task CPU architecture: \"X86_64\" or \"ARM64\" (Graviton). Must match whatever platform the pushed container_image was actually built for."
  type        = string
  default     = "X86_64"

  validation {
    condition     = contains(["X86_64", "ARM64"], var.cpu_architecture)
    error_message = "cpu_architecture must be \"X86_64\" or \"ARM64\"."
  }
}

variable "enable_deployment_circuit_breaker" {
  description = "Automatically roll back a deployment whose new tasks never stabilize (fail health checks / crash loop)."
  type        = bool
  default     = true
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum percent of desired_count that must stay running/healthy during a deployment."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Maximum percent of desired_count ECS may run during a deployment (extra capacity for the new tasks before old ones are stopped)."
  type        = number
  default     = 200
}

variable "environment_variables" {
  description = "Container environment variables, e.g. { AURA_WEB_ORIGIN = \"https://aura.example.com\" }."
  type        = map(string)
  default     = {}
}

variable "has_sqs_queue" {
  description = "Set true alongside sqs_queue_arn. Kept as a separate literal (rather than inferring from `sqs_queue_arn != null`) because the caller usually passes a not-yet-created queue module's ARN — an unknown-until-apply value can't drive `count` — while whether a queue exists at all is always known at plan time. Same pattern as modules/database's is_replica."
  type        = bool
  default     = false
}

variable "sqs_queue_arn" {
  description = "When set (the event-driven-buffered pattern's queue component), grants the task role SendMessage/ReceiveMessage/DeleteMessage/GetQueueAttributes on this queue."
  type        = string
  default     = null
}

variable "sqs_queue_url" {
  description = "When set alongside sqs_queue_arn, injected as the QUEUE_URL environment variable."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "enable_alarms" {
  description = "Create CloudWatch alarms for this service (docs/IMPLEMENTATION_PHASES.md Phase 3 observability)."
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "SNS topic ARNs (or similar) to notify. Empty by default: alarms still exist and are visible in the console, they just don't page anyone until this is wired up."
  type        = list(string)
  default     = []
}
