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

variable "tags" {
  type    = map(string)
  default = {}
}
