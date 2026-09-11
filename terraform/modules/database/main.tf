# RDS instance. When `replicate_source_db` is unset this is a standalone
# primary (Multi-AZ, encrypted, password managed by AWS Secrets Manager —
# never a plaintext password in state). When it is set, this becomes a
# (possibly cross-region) read replica; most settings are then inherited
# from the source and must be left null here.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-db-"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-db-sg" })

  ingress {
    description     = "From the application tier only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  instance_class = var.instance_class

  # Standalone-primary-only settings (must be null when replicating).
  engine                      = var.replicate_source_db == null ? var.engine : null
  engine_version               = var.replicate_source_db == null ? var.engine_version : null
  allocated_storage            = var.replicate_source_db == null ? var.allocated_storage : null
  storage_encrypted            = var.replicate_source_db == null ? true : null
  db_name                      = var.replicate_source_db == null ? var.db_name : null
  username                     = var.replicate_source_db == null ? var.username : null
  manage_master_user_password  = var.replicate_source_db == null ? true : null
  backup_retention_period      = var.replicate_source_db == null ? 7 : null

  # Replica-only settings.
  replicate_source_db = var.replicate_source_db
  kms_key_id          = var.replicate_source_db != null ? var.kms_key_id : null

  # Common to both.
  multi_az                = var.multi_az
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.this.id]
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = var.tags
}
