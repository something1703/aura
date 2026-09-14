variable "region" {
  description = "Single region — AURA's own control plane doesn't need the HA treatment the workload it's analyzing gets; it's stateless and cheap to redeploy."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "demo"
}

variable "desired_count" {
  description = "Fargate task count for the AURA API."
  type        = number
  default     = 2
}

variable "web_desired_count" {
  description = "Fargate task count for the web UI."
  type        = number
  default     = 2
}

variable "image_tag" {
  description = "Tag to deploy from the API's ECR repo this stack creates. Push an image with this tag before the first apply — see README.md."
  type        = string
  default     = "latest"
}

variable "web_image_tag" {
  description = "Tag to deploy from the web UI's ECR repo this stack creates. Push an image with this tag before the first apply — see README.md."
  type        = string
  default     = "latest"
}
