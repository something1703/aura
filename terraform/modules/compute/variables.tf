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

variable "environment_variables" {
  description = "Container environment variables, e.g. { AURA_WEB_ORIGIN = \"https://aura.example.com\" }."
  type        = map(string)
  default     = {}
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
