# RDS instance. When `replicate_source_db` is unset this is a standalone
# primary (Multi-AZ, encrypted); when it is set, this becomes a (possibly
# cross-region) read replica, and most settings are inherited from the
# source and must be left null here.
#
# Password: NOT manage_master_user_password (AWS-managed, via Secrets
# Manager automatically) — AWS explicitly does not support creating a read
# replica from a source that has it enabled ("InvalidParameterValue:
# Creating read replicas for source instance with engine postgres where
# ManageMasterUserPassword is enabled is not supported", hit for real
# against this exact module). Explicit random_password + our own Secrets
# Manager secret gets the same "no plaintext password to hand-type" outcome
# without that restriction.

resource "random_password" "master" {
  count   = var.replicate_source_db == null ? 1 : 0
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "master_password" {
  count = var.replicate_source_db == null ? 1 : 0
  name  = "${var.name}-master-password"
  tags  = var.tags
}

resource "aws_secretsmanager_secret_version" "master_password" {
  count     = var.replicate_source_db == null ? 1 : 0
  secret_id = aws_secretsmanager_secret.master_password[0].id
  secret_string = jsonencode({
    username = var.username
    password = random_password.master[0].result
  })
}

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
  engine                  = var.replicate_source_db == null ? var.engine : null
  engine_version          = var.replicate_source_db == null ? var.engine_version : null
  allocated_storage       = var.replicate_source_db == null ? var.allocated_storage : null
  storage_encrypted       = var.replicate_source_db == null ? true : null
  db_name                 = var.replicate_source_db == null ? var.db_name : null
  username                = var.replicate_source_db == null ? var.username : null
  password                = var.replicate_source_db == null ? random_password.master[0].result : null
  backup_retention_period = var.replicate_source_db == null ? 7 : null

  # Replica-only settings.
  replicate_source_db = var.replicate_source_db
  kms_key_id          = var.replicate_source_db != null ? var.kms_key_id : null

  # Common to both.
  multi_az               = var.multi_az
  storage_type           = var.storage_type
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  skip_final_snapshot    = true
  deletion_protection    = false
  apply_immediately      = true

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "${var.name} RDS instance sustained CPU > 85%."
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.id
  }

  alarm_actions = var.alarm_actions
  tags          = var.tags
}

# Only meaningful on a replica; a standalone primary has no ReplicaLag metric.
resource "aws_cloudwatch_metric_alarm" "replica_lag_high" {
  count               = var.enable_alarms && var.is_replica ? 1 : 0
  alarm_name          = "${var.name}-rds-replica-lag-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = var.replica_lag_alarm_threshold_seconds
  alarm_description   = "${var.name} cross-region replica lag exceeds the ${var.replica_lag_alarm_threshold_seconds}s RPO this architecture assumed."
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.id
  }

  alarm_actions = var.alarm_actions
  tags          = var.tags
}
