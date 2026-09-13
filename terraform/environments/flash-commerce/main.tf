# Realizes the architecture AURA recommended for config/flash-commerce.yaml:
# multi-region-warm-standby (see `aura score config/flash-commerce.yaml`,
# or src/aura/architecture/catalog.py MULTI_REGION_WARM_STANDBY).
#
# Topology mirrors src/aura/architecture/generator.py exactly:
#   - compute + database in both regions (secondary smaller: warm, not cold)
#   - cache only in the primary region
#   - no global-router/CDN here — those need a registered domain, which
#     this demo doesn't have (see README.md "Known limitations").

data "aws_availability_zones" "primary" {
  provider = aws.primary
  state    = "available"
}

data "aws_availability_zones" "secondary" {
  provider = aws.secondary
  state    = "available"
}

locals {
  name_prefix = "aura-${var.environment}"

  # Matches PatternDefinition.primary_az_count / secondary_az_count for
  # multi-region-warm-standby in src/aura/architecture/catalog.py.
  primary_azs   = slice(data.aws_availability_zones.primary.names, 0, 3)
  secondary_azs = slice(data.aws_availability_zones.secondary.names, 0, 2)

  common_tags = {
    Project      = "AURA"
    Environment  = var.environment
    ManagedBy    = "terraform"
    Architecture = "multi-region-warm-standby"
  }
}

module "network_primary" {
  source = "../../modules/networking"
  providers = {
    aws = aws.primary
  }

  name               = "${local.name_prefix}-primary"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = local.primary_azs
  enable_nat_gateway = true
  tags               = local.common_tags
}

module "network_secondary" {
  source = "../../modules/networking"
  providers = {
    aws = aws.secondary
  }

  name               = "${local.name_prefix}-secondary"
  vpc_cidr           = "10.1.0.0/16"
  availability_zones = local.secondary_azs
  enable_nat_gateway = true
  tags               = local.common_tags
}

module "compute_primary" {
  source = "../../modules/compute"
  providers = {
    aws = aws.primary
  }

  name               = "${local.name_prefix}-primary"
  vpc_id             = module.network_primary.vpc_id
  public_subnet_ids  = module.network_primary.public_subnet_ids
  private_subnet_ids = module.network_primary.private_subnet_ids
  container_image    = var.container_image
  desired_count      = var.primary_desired_count
  tags               = local.common_tags
}

module "compute_secondary" {
  source = "../../modules/compute"
  providers = {
    aws = aws.secondary
  }

  name               = "${local.name_prefix}-secondary"
  vpc_id             = module.network_secondary.vpc_id
  public_subnet_ids  = module.network_secondary.public_subnet_ids
  private_subnet_ids = module.network_secondary.private_subnet_ids
  container_image    = var.container_image
  desired_count      = var.secondary_desired_count
  tags               = local.common_tags
}

module "cache_primary" {
  source = "../../modules/cache"
  providers = {
    aws = aws.primary
  }

  name                       = "${local.name_prefix}-primary"
  vpc_id                     = module.network_primary.vpc_id
  private_subnet_ids         = module.network_primary.private_subnet_ids
  allowed_security_group_ids = [module.compute_primary.service_security_group_id]
  tags                       = local.common_tags
}

# Cross-region RDS read replicas need a KMS key local to the destination
# region (a source region's key cannot be used to encrypt data at rest
# in another region).
resource "aws_kms_key" "database_replica" {
  provider    = aws.secondary
  description = "Encrypts the ${local.name_prefix} cross-region RDS read replica"
  tags        = local.common_tags
}

module "database_primary" {
  source = "../../modules/database"
  providers = {
    aws = aws.primary
  }

  name                       = "${local.name_prefix}-primary"
  vpc_id                     = module.network_primary.vpc_id
  private_subnet_ids         = module.network_primary.private_subnet_ids
  allowed_security_group_ids = [module.compute_primary.service_security_group_id]
  instance_class             = var.database_instance_class
  multi_az                   = true
  tags                       = local.common_tags
}

module "database_secondary" {
  source = "../../modules/database"
  providers = {
    aws = aws.secondary
  }

  name                       = "${local.name_prefix}-secondary"
  vpc_id                     = module.network_secondary.vpc_id
  private_subnet_ids         = module.network_secondary.private_subnet_ids
  allowed_security_group_ids = [module.compute_secondary.service_security_group_id]
  instance_class             = var.database_instance_class
  is_replica                 = true
  replicate_source_db        = module.database_primary.arn
  kms_key_id                 = aws_kms_key.database_replica.arn
  multi_az                   = var.database_multi_az_secondary
  tags                       = local.common_tags
}
