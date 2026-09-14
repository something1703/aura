# Terraform

Five reusable modules, and environments built from them two ways: hand-wired
(the two checked-in ones below) or **generated directly from an AURA
candidate** (see "Generated environments" — this is what actually closes the
loop between "AURA recommends X" and "the infrastructure matches X").

```
terraform/
├── modules/
│   ├── networking/        # dedicated VPC, public+private subnets, 1 NAT GW
│   ├── compute/            # ALB (HTTP) + ECS Fargate cluster/service + CloudWatch alarms
│   ├── database/           # RDS Multi-AZ, or a (cross-region) read replica + alarms
│   ├── cache/               # single-node ElastiCache Redis
│   └── queue/                # durable SQS queue + DLQ (event-driven-buffered pattern)
└── environments/
    ├── flash-commerce/      # the workload AURA is analyzing — see below
    └── aura-control-plane/  # AURA's own API + web UI, deployed — see below
```

## Generated environments — closing the AURA → Terraform loop

`terraform/environments/flash-commerce/` (below) was originally hand-written
by reading one AURA recommendation once. That never updates: change the
workload and get a different recommendation, and that Terraform sits there
unchanged until a human rewrites it. `aura terraform generate` fixes that —
it renders real `.tf` files directly from a candidate's actual topology
(`candidate.topology`, `candidate.primary_region`, ...), the same data the
analysis already computed, via `src/aura/reporting/terraform_codegen.py`.

```bash
aura terraform generate config/flash-commerce.yaml \
  --output-dir terraform/environments/my-generated-env
# or a specific pattern instead of the recommendation:
aura terraform generate config/flash-commerce.yaml \
  --candidate single-region-multi-az --output-dir terraform/environments/my-single-region

cd terraform/environments/my-generated-env
terraform init && terraform validate && terraform plan
```

Generated environments always include exactly the modules that candidate's
topology has — no secondary region/KMS key for a single-region pattern, a
`queue` module (with the compute task wired for SQS access) only for
event-driven-buffered, `cache_secondary` only for active-active. `desired_count`
defaults to what the workload's peak RPS actually needs at the cost engine's
50-RPS/task assumption — which can be a very large, real, correct-but-not-
demo-sized number (`aura terraform generate` prints a warning when it is,
with the `-var` overrides to use instead). A `global-router`/`cdn` component
in the topology gets a comment, not generated code — both need a registered
domain this generator has no way to know about.

**Never overwrites an existing deployed environment's state** — always
targets a directory you name; regenerating a workload you've already applied
means diffing/moving the new files in yourself, not an automatic migration.

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

### Progressive delivery

Every `aws_ecs_service` deploys with a circuit breaker
(`deployment_circuit_breaker { enable = true, rollback = true }`) and
`deployment_minimum_healthy_percent = 100` / `deployment_maximum_percent = 200`:
new tasks must pass the ALB health check to count toward a rollout, full
capacity keeps serving throughout, and if the new tasks never stabilize ECS
automatically rolls the service back to the previous task definition —
matching docs/IMPLEMENTATION_PHASES.md's "Health Validation -> Canary/Blue-Green
-> Promote or Roll Back" without needing a separate CodeDeploy setup.

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
flash-commerce demo above. Deploys both AURA's own API (`Dockerfile` at the
repo root) and its web UI (`Dockerfile.web`), each behind its own ALB in a
single region, plus the two ECR repositories to push them to. No database:
the API is stateless, so this skips the HA treatment given to the workload
it analyzes.

The two services are wired together automatically: the web task's
`AURA_API_URL` env var is set to the API ALB's real DNS name, read at
request time by [`web/src/app/api/[...path]/route.ts`](../web/src/app/api/%5B...path%5D/route.ts)
— not baked into the image at build time, so the exact same Docker image
works unchanged in any other deployment too.

```bash
cd terraform/environments/aura-control-plane
terraform init
terraform validate
terraform plan
terraform apply            # creates 2 ECR repos, VPC, 2 ALBs, and 2 ECS
                            # services that will sit unhealthy until you
                            # push images:

aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin "$(terraform output -raw api_ecr_repository_url | cut -d/ -f1)"

# --platform matters, and the two images need different ones here:
#
# API -> linux/amd64 (module default cpu_architecture = "X86_64"). Explicit
# because a `docker build` on an Apple Silicon Mac produces arm64 by
# default — an image that looks like it pushed fine but that ECS then can't
# pull ("CannotPullContainerError: image Manifest does not contain
# descriptor matching platform 'linux/amd64'"), hit for real running
# through this exact guide. Cross-compiling amd64 on Apple Silicon works
# fine here (pip/Python has no native-binary segfault risk under QEMU).
#
# Web -> linux/arm64, matching main.tf's cpu_architecture = "ARM64" for
# this module call specifically. NOT amd64, even though that's what
# actually runs on Fargate by default elsewhere: web/'s Tailwind v4
# toolchain (lightningcss, a Rust-compiled native addon) segfaults under
# QEMU's x86_64 emulation when cross-built on an Apple Silicon machine
# (`Segmentation fault`, exit 139) — also hit for real. Building natively
# for the arch this Mac already is sidesteps emulation entirely; the ECS
# side is told to expect that via cpu_architecture.
#
# On an x86_64 build machine (CI's GitHub-hosted runners included), both
# of these flags are unnecessary but harmless to leave in — except the web
# one, which would need to become --platform linux/amd64 there to match,
# same as the API. If you're not on an Apple Silicon Mac, build both with
# --platform linux/amd64 and set cpu_architecture = "X86_64" for both
# module calls in main.tf instead.
docker build --platform linux/amd64 -t "$(terraform output -raw api_ecr_repository_url):latest" -f ../../../Dockerfile ../../..
docker push "$(terraform output -raw api_ecr_repository_url):latest"

docker build --platform linux/arm64 -t "$(terraform output -raw web_ecr_repository_url):latest" -f ../../../Dockerfile.web ../../..
docker push "$(terraform output -raw web_ecr_repository_url):latest"

# ECS picks up new images on its own within a few minutes, or force it:
aws ecs update-service --cluster aura-control-plane-demo-api-cluster \
  --service aura-control-plane-demo-api-service --force-new-deployment --region ap-south-1
aws ecs update-service --cluster aura-control-plane-demo-web-cluster \
  --service aura-control-plane-demo-web-service --force-new-deployment --region ap-south-1

curl "http://$(terraform output -raw api_alb_dns_name)/api/health"
open "http://$(terraform output -raw web_alb_dns_name)"   # the actual app
terraform destroy          # tear it down when finished
```

A later `docker build`/`push`/`update-service` for either image is a normal
rolling ECS deployment, not a break-the-world event: new tasks come up
alongside the running ones, only take traffic once they pass the ALB health
check, and old tasks drain after — see `deployment_circuit_breaker` in
`modules/compute/main.tf`, which automatically rolls back a deployment whose
new tasks never stabilize.

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
