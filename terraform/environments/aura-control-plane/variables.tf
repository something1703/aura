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

variable "image_tag" {
  description = "Tag to deploy from the ECR repo this stack creates. Push an image with this tag before the first apply — see README.md."
  type        = string
  default     = "latest"
}

variable "web_origin" {
  description = "Origin of the deployed web UI, for CORS (AURA_WEB_ORIGIN). The UI itself isn't deployed by this stack."
  type        = string
  default     = "http://localhost:3000"
}
