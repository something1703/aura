# "ECS deployment for the AURA control plane, if desired"
# (docs/IMPLEMENTATION_PHASES.md Phase 3). Optional and separate from the
# flash-commerce demo infra in ../flash-commerce — this deploys AURA's own
# API (Dockerfile at the repo root) so the web UI can point at a real,
# always-on endpoint instead of someone's laptop running `aura serve`.
#
# Single region, no cross-region replica, no database at all: the API is
# stateless (every request re-runs the same deterministic analysis), so
# this doesn't need the HA treatment the workload it analyzes gets.

data "aws_availability_zones" "this" {
  state = "available"
}

locals {
  name = "aura-control-plane-${var.environment}"
  tags = {
    Project     = "AURA"
    Component   = "control-plane"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "network" {
  source = "../../modules/networking"

  name               = local.name
  vpc_cidr           = "10.10.0.0/16"
  availability_zones = slice(data.aws_availability_zones.this.names, 0, 2)
  enable_nat_gateway = true
  tags               = local.tags
}

resource "aws_ecr_repository" "aura_api" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

module "compute" {
  source = "../../modules/compute"

  name               = local.name
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  container_image   = "${aws_ecr_repository.aura_api.repository_url}:${var.image_tag}"
  container_port    = 8000
  health_check_path = "/api/health"
  desired_count     = var.desired_count

  # Same-origin CORS note: the web UI isn't deployed by this stack (it's a
  # separate concern — Vercel, another ECS service, a static host, etc.).
  # Set this to wherever it actually ends up.
  environment_variables = {
    AURA_WEB_ORIGIN = var.web_origin
  }

  tags = local.tags
}
