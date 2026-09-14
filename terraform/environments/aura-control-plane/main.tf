# "ECS deployment for the AURA control plane, if desired"
# (docs/IMPLEMENTATION_PHASES.md Phase 3). Optional and separate from the
# flash-commerce demo infra in ../flash-commerce — this deploys both AURA's
# own API (Dockerfile at the repo root) and its web UI (Dockerfile.web) so
# the whole thing has a real, always-on URL instead of someone's laptop
# running `aura serve` + `npm run dev`.
#
# Single region, no cross-region replica, no database at all: the API is
# stateless (every request re-runs the same deterministic analysis), so
# this doesn't need the HA treatment the workload it analyzes gets.
#
# Two separate ALBs (one per service) rather than one shared ALB with
# path-based routing — simpler, at the cost of a second ALB's ~$16/mo.
# The web task's AURA_API_URL points at the API ALB's DNS name directly
# (see web/src/app/api/[...path]/route.ts): that's a plain HTTP call over
# the public internet between two AWS services in the same VPC, not routed
# privately — an acceptable simplification for a demo control plane, not
# something to copy for a workload actually holding sensitive data.

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
  name                 = "${local.name}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_repository" "aura_web" {
  name                 = "${local.name}-web"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

module "api" {
  source = "../../modules/compute"

  name               = "${local.name}-api"
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  container_image   = "${aws_ecr_repository.aura_api.repository_url}:${var.image_tag}"
  container_port    = 8000
  health_check_path = "/api/health"
  desired_count     = var.desired_count

  # Mostly moot now that the web UI proxies server-side (see module "web"
  # below) rather than calling this API from the browser — but harmless to
  # keep allow-listed for anyone hitting this API directly (e.g. its own
  # /docs) from that origin.
  environment_variables = {
    AURA_WEB_ORIGIN = "http://${module.web.alb_dns_name}"
  }

  tags = local.tags
}

module "web" {
  source = "../../modules/compute"

  name               = "${local.name}-web"
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  container_image   = "${aws_ecr_repository.aura_web.repository_url}:${var.web_image_tag}"
  container_port    = 3000
  health_check_path = "/"
  desired_count     = var.web_desired_count

  # Read at request time by web/src/app/api/[...path]/route.ts — not baked
  # in at image build time, so this same image would work unchanged against
  # any other AURA API deployment too.
  environment_variables = {
    AURA_API_URL = "http://${module.api.alb_dns_name}"
  }

  tags = local.tags
}
