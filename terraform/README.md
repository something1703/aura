# Terraform: the architecture AURA recommended, for real

This directory implements **multi-region-warm-standby**, the architecture
`aura score config/flash-commerce.yaml` actually recommends for the
flash-commerce workload — not a generic reference architecture. Change the
workload, get a different AURA recommendation, and this Terraform would need
to change to match (see `architecture/runtime.md` for how the decision and
the infrastructure relate).

```
terraform/
├── modules/
│   ├── networking/   # dedicated VPC, public+private subnets, 1 NAT GW
│   ├── compute/       # ALB (HTTP) + ECS Fargate cluster/service
│   ├── database/      # RDS Multi-AZ, or a (cross-region) read replica
│   └── cache/          # single-node ElastiCache Redis
└── environments/
    └── flash-commerce/  # wires the modules into both regions
```

## What's deployed

| AURA topology component | Terraform | Primary (`ap-south-1`) | Secondary (`ap-southeast-1`) |
|---|---|---|---|
| `load-balancer` | `module.compute_*` (ALB) | 3-AZ VPC, internet-facing ALB | 2-AZ VPC, internet-facing ALB |
| `compute` | `module.compute_*` (ECS Fargate) | 3 tasks | 2 tasks (warm, not full parity) |
| `database` | `module.database_*` (RDS) | Multi-AZ primary | Multi-AZ cross-region read replica |
| `cache` | `module.cache_primary` (ElastiCache) | 1 node | *(none — AURA only places cache in the primary region for this pattern)* |

This mirrors `src/aura/architecture/generator.py` component-for-component —
see the comments in `environments/flash-commerce/main.tf`.

## Known limitations (deliberate, for a demo)

- **No `global-router`/`cdn`.** AURA's topology includes a Route53-style
  global router and a CDN for this workload, but both need a registered
  domain this demo doesn't have. The ALBs are reachable directly by DNS name
  in the meantime.
- **HTTP only**, no ACM certificate (same reason: no domain to issue one for).
- **Placeholder container image** (`public.ecr.aws/nginx/nginx`) — there is
  no real flash-commerce application to deploy yet.
- **Small instance classes** (`db.t4g.micro`, `cache.t4g.micro`, 0.25 vCPU
  Fargate tasks) — nowhere near the 150,000 RPS peak capacity AURA's cost
  model sized for. This proves the *architecture* (Multi-AZ, cross-region
  replication, warm standby), not production-scale capacity.

## Cost

Rough estimate at the default (small) sizing, **if left running continuously**:

| Item | Approx. |
|---|---|
| 2× NAT Gateway | ~$65/mo |
| 2× ALB | ~$32/mo |
| 5× Fargate task (0.25 vCPU / 0.5 GB) | ~$11/mo |
| RDS `db.t4g.micro` Multi-AZ ×2 (primary + replica) | ~$45/mo |
| ElastiCache `cache.t4g.micro` | ~$12/mo |
| **Total** | **~$165/mo (~$0.23/hr)** |

For a few hours of demo this is under a dollar. **Run `terraform destroy`
when you're done** — nothing here auto-expires.

## Compliance: never the default VPC

Every VPC here is purpose-built (`aws_vpc` with an explicit CIDR in
`modules/networking`) — nothing references or deploys into the account's
default VPC.

## Running it

```bash
cd terraform/environments/flash-commerce
terraform init
terraform validate
terraform plan            # read-only: shows what would be created, creates nothing
terraform apply           # creates real, billed AWS resources — review the plan first
terraform show -json > tfplan.json   # then, from the repo root:
aura terraform inspect terraform/environments/flash-commerce/tfplan.json
aura validate-deployed --workload config/flash-commerce.yaml --region ap-south-1
terraform destroy         # tear it down when finished
```
