# AWS and Terraform Integration

## Preconditions

The developer machine should already have:

```bash
aws sts get-caller-identity
terraform version
```

Do not commit credentials.

## Integration order

### Step 1 — identity

AURA can execute read-only AWS calls through boto3 using the developer's existing AWS configuration.

### Step 2 — inventory

Implement:

```bash
aura aws inventory --region ap-south-1
```

Start with safe resource discovery only.

### Step 3 — Terraform plan inspection

Use:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json
```

AURA parses the JSON plan without executing Terraform.

### Step 4 — desired vs observed

Create an architecture graph from the Terraform plan and an observed graph from AWS inventory.

Compare:

```text
expected nodes
expected relationships
expected properties
observed nodes
observed relationships
observed properties
```

## Safety rules

Phase 2 AURA does not call `terraform apply` automatically.

Phase 3 may integrate a deployment gate, but the apply step remains outside the AURA decision engine unless explicitly designed and approved.

## IAM principle

Start with a read-only inspection role. Expand permissions only when a new feature has a documented use case.
