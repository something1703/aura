# Durable ingestion queue for the event-driven-buffered pattern — decouples
# ingestion from processing so traffic bursts are absorbed instead of
# overwhelming compute/database directly (docs/IMPLEMENTATION_PHASES.md,
# TRAFFIC_SPIKE scenario in aura.failure.simulator).

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = var.message_retention_seconds
  # SSE-SQS (Amazon-managed key, free, no KMS key to provision/rotate) -
  # matches flash-commerce's encryption_at_rest requirement. Not a KMS CMK
  # like modules/database uses: that module needs one specifically for
  # cross-region replica key sharing, which doesn't apply here.
  sqs_managed_sse_enabled = true
  tags                    = var.tags
}

resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })

  tags = var.tags
}
