# AWS Validator Agent

## Goal
Compare the expected architecture with real AWS state.

## Phase 2 scope

Read-only inventory and Terraform plan inspection.

## Example findings

```text
[FAIL] expected 3 AZs, observed 2
[PASS] encrypted EBS volumes
[PASS] RDS Multi-AZ enabled
[WARN] no regional recovery configuration detected
```

## Security

Credentials come from the standard AWS credential chain. Never store access keys in the repository.
