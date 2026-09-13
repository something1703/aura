# Terraform

Two independent environments, both built from the same four modules:

```
terraform/
├── modules/
│   ├── networking/        # dedicated VPC, public+private subnets, 1 NAT GW
│   ├── compute/            # ALB (HTTP) + ECS Fargate cluster/service + CloudWatch alarms
│   ├── database/           # RDS Multi-AZ, or a (cross-region) read replica + alarms
│   └── cache/               # single-node ElastiCache Redis
└── environments/
    ├── flash-commerce/      # the workload AURA is analyzing — see below
    └── aura-control-plane/  # AURA's own API, deployed — see below
```

## `environments/flash-commerce/`

This implements **multi-region-warm-standby**, the architecture
`aura score config/flash-commerce.yaml` actually recommends for the
flash-commerce workload — not a generic reference architecture. Change the
workload, get a different AURA recommendation, and this Terraform would need
to change to match (see `architecture/runtime.md` for how the decision and
the infrastructure relate).

## What's deployed

| AURA topology component | Terraform | Primary (`ap-south-1`) | Secondary (`ap-southeast-1`) |
|---|---|---|---|
| `load-balancer` | `module.compute_*` (ALB) | 3-AZ VPC, internet-facing ALB | 2-AZ VPC, internet-facing ALB |
| `compute` | `module.compute_*` (ECS Fargate) | 3 tasks | 2 tasks (warm, not full parity) |
| `database` | `module.database_*` (RDS) | Multi-AZ primary | Multi-AZ cross-region read replica |
| `cache` | `module.cache_primary` (ElastiCache) | 1 node | *(none — AURA only places cache in the primary region for this pattern)* |

This mirrors `src/aura/architecture/generator.py` component-for-component —
see the comments in `environments/flash-commerce/main.tf`.

Both the compute and database modules also create CloudWatch alarms (unhealthy
targets, 5xx rate, CPU, and — on the secondary database — replica lag): see
"Observability" below.

### Known limitations (deliberate, for a demo)

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

### Cost

Rough estimate at the default (small) sizing, **if left running continuously**
(CloudWatch alarms add well under $1/mo — ~10 alarms at $0.10/alarm/mo — and
aren't itemized separately below):

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

### Running it

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

## `environments/aura-control-plane/`

"ECS deployment for the AURA control plane, if desired"
(docs/IMPLEMENTATION_PHASES.md Phase 3) — optional, separate infra from the
flash-commerce demo above. Deploys AURA's own API (`Dockerfile` at the repo
root) behind an ALB in a single region, plus the ECR repository to push it
to. No database: the API is stateless, so this skips the HA treatment given
to the workload it analyzes.

```bash
cd terraform/environments/aura-control-plane
terraform init
terraform validate
terraform plan
terraform apply            # creates the ECR repo, VPC, ALB, and an ECS service
                            # that will sit unhealthy until you push an image:

aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin "$(terraform output -raw ecr_repository_url | cut -d/ -f1)"
docker build -t "$(terraform output -raw ecr_repository_url):latest" -f ../../../Dockerfile ../../..
docker push "$(terraform output -raw ecr_repository_url):latest"
# ECS picks up the new image on its own within a few minutes, or force it:
aws ecs update-service --cluster aura-control-plane-demo-cluster \
  --service aura-control-plane-demo-service --force-new-deployment --region ap-south-1

curl "http://$(terraform output -raw alb_dns_name)/api/health"
terraform destroy          # tear it down when finished
```

Point the web UI at it with `NEXT_PUBLIC_AURA_API_URL=http://<alb_dns_name>`,
and set `-var web_origin=https://<wherever-the-ui-ends-up>` so CORS allows it
(the UI itself isn't deployed by this stack).

## Compliance: never the default VPC

Every VPC in both environments is purpose-built (`aws_vpc` with an explicit
CIDR in `modules/networking`) — nothing references or deploys into the
account's default VPC.

## Observability

Both `compute` and `database` create CloudWatch alarms by default
(`enable_alarms = false` to skip, `alarm_actions = [<sns-topic-arn>]` to
actually page someone). One is worth calling out specifically: the secondary
database's `replica_lag_high` alarm fires if real cross-region replication
lag exceeds the RPO the warm-standby pattern assumed — the same check
`aura observe` can run on demand:

```bash
aura observe --namespace AWS/RDS --metric ReplicaLag --region ap-southeast-1 \
  --dimension DBInstanceIdentifier=aura-demo-secondary
```

## CI: enabling `terraform plan` in GitHub Actions (opt-in, not done by default)

`.github/workflows/ci.yml`'s `terraform-plan` job and
`.github/workflows/runtime-validation.yml` are written to run a real,
read-only `terraform plan` / `aura validate-deployed` in CI, but they're
**inert until you add `AWS_ROLE_ARN`** as a repository secret —
nobody did that as part of this build, deliberately: this is a public
student-project repo, and long-lived AWS access keys should never live in
GitHub Actions secrets regardless.

If you want this live, the standard-practice way (OIDC — no stored
credentials, no keys to rotate or leak) is:

1. In IAM, add `token.actions.githubusercontent.com` as an OIDC identity
   provider (if the account doesn't already have one).
2. Create an IAM role trusted only for this repo:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
       "Action": "sts:AssumeRoleWithWebIdentity",
       "Condition": {
         "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
         "StringLike": { "token.actions.githubusercontent.com:sub": "repo:something1703/aura:*" }
       }
     }]
   }
   ```
3. Attach a **read-only** permissions policy — `terraform plan` and
   `aura terraform inspect`/`validate-deployed` only ever read: EC2, RDS,
   ELB, ElastiCache, ECS, CloudWatch `Describe*`/`List*`/`Get*` actions
   (`arn:aws:iam::aws:policy/ReadOnlyAccess` is the blunt version; scope it
   down if you want less).
4. Add the role's ARN as a repository secret named `AWS_ROLE_ARN`
   (Settings -> Secrets and variables -> Actions -> Secrets).

Nothing in either workflow ever runs `terraform apply` or a mutating
`aura chaos` command — those stay manual on purpose (AGENTS.md "Human
approval boundary").
