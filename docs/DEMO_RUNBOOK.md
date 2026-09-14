# AURA Demo Runbook

## Demo objective

Show that AURA takes a demanding workload and turns it into an explainable, genuinely-computed architecture decision — then prove that decision is connected to real, live AWS infrastructure, not just a report.

Roughly 10–15 minutes. Do not spend it reading code — show the decision process, the evidence, the failure model, and the trade-offs. Everything below is a real, copy-pasteable command; none of it is illustrative.

## Before you start

- Have the two live AWS URLs ready (they change if the infra is ever recreated — re-fetch rather than trust old notes):
  ```bash
  cd terraform/environments/aura-control-plane && terraform output web_alb_dns_name
  cd ../flash-commerce && terraform output primary_alb_dns_name
  ```
- Activate the venv: `source .venv/bin/activate`.
- Have `config/flash-commerce.yaml` and `config/flash-commerce-relaxed.yaml` open side by side for Act 4.

## Act 1 — Open the live app

No command — just open `http://<web_alb_dns_name from above>` in a browser. This is a real ECS Fargate service behind a real ALB, not localhost. Point that out explicitly: nothing here is `npm run dev` on a laptop.

## Act 2 — Walk the web UI

In the browser: edit the pre-loaded workload (or use it as-is), click **Analyze**, then:

- **Candidate comparison table** — click between rows, including a rejected one, to show the topology diagram, strategy, scoring, failures, and cost all re-render for whichever candidate is selected.
- **Break everything** panel — start it, narrate a couple of the 8 scenarios as they animate.
- **Rejected candidates** panel — read out one candidate's exact rejection reason.
- **ADRs** — expand one, point out Status/Context/Decision/Consequences.

## Act 3 — The same engine from the CLI

Proves the UI isn't the "real" part — the engine is, and it's independently invokable:

```bash
aura validate config/flash-commerce.yaml
aura analyze config/flash-commerce.yaml
aura failures config/flash-commerce.yaml
aura score config/flash-commerce.yaml
aura report config/flash-commerce.yaml --output artifacts/report
aura adr config/flash-commerce.yaml --output artifacts/adr
```

Open `artifacts/report/report.md` and show: selected architecture, rejected alternatives, hard constraints, weighted scores, confidence, assumptions.

## Act 4 — Prove it's not hardcoded

The single best answer to "is the recommendation just fixed?" — run the identical pipeline against `config/flash-commerce-relaxed.yaml`, which changes exactly four values from the original (availability 99.99%→99.9%, RTO 5→60 min, RPO 1→30 min, regional disaster **not** required):

```bash
diff config/flash-commerce.yaml config/flash-commerce-relaxed.yaml

aura report config/flash-commerce.yaml --output /tmp/baseline
aura report config/flash-commerce-relaxed.yaml --output /tmp/relaxed
grep "Recommendation:" /tmp/baseline/report.md /tmp/relaxed/report.md
```

Verified output — a genuinely different *pattern*, not a score wobble:

```
/tmp/baseline/report.md:**Recommendation: Multi-region warm standby**
/tmp/relaxed/report.md:**Recommendation: Event-driven buffered (single region)**
```

## Act 5 — Tests and CI (the rigor story)

```bash
pytest -q                                    # 148 tests: unit, golden-file, property-based
ruff check src tests && ruff format --check src tests
gh run list --limit 5                        # or just show the green Actions tab in a browser
```

Worth naming specifically: the golden-file test pins flash-commerce's exact decision so a scoring change that silently flips it fails loudly; the property-based tests check invariants ("raising the required availability can never make a rule's status get better") across inputs, not one fixed example.

## Act 6 — Closing the loop: AURA → real Terraform

```bash
aura terraform generate config/flash-commerce.yaml --output-dir /tmp/demo-tf
ls /tmp/demo-tf
head -40 /tmp/demo-tf/main.tf

cd /tmp/demo-tf
terraform init -backend=false
terraform validate
```

This is real, applyable Terraform rendered directly from the candidate's computed topology — not a Terraform file someone hand-wrote once and hoped stays in sync.

## Act 7 — It's actually deployed, not just generated

```bash
cd terraform/environments/flash-commerce
terraform output
curl "http://$(terraform output -raw primary_alb_dns_name)"

aura aws inventory --region ap-south-1
```

`aws inventory` is real, read-only boto3 — the same read-only-first principle ([ADR-0003](../adr/ADR-0003-read-only-aws-validation.md)) that governs every AWS-touching command in this project.

## Act 8 — Optional, if time remains: real observability

The one command that produces MEASURED (not MODELLED) evidence — a real CloudWatch metric:

```bash
aura observe --namespace AWS/RDS --metric ReplicaLag --region ap-southeast-1 \
  --dimension DBInstanceIdentifier=aura-demo-secondary
```

And safe synthetic load (plain HTTP GETs, no AWS credentials, not gated by `--confirm`):

```bash
aura chaos synthetic-traffic "http://$(cd terraform/environments/flash-commerce && terraform output -raw primary_alb_dns_name)" --duration 15 --rps 3
```

`aura chaos terminate-task` / `remove-target` exist and are tested but are real, mutating, `--confirm`-gated AWS calls — mention them, don't run them live unless you actually intend to kill a real task.

## Anticipated questions

- **"Is the recommendation hardcoded?"** → Act 4.
- **"Is the frontend connected to anything real?"** → Act 1 + Act 7 (it's the same AWS account, same real resources).
- **"What stops a bad architecture from merging?"** → `aura gate` in CI, see [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).
- **"What if the recommended architecture changes later?"** → Act 6 — `aura terraform generate` regenerates real Terraform from whatever the current recommendation is.
- **"Could this actually deploy itself?"** → No, by design — see the README's [Non-goals](../README.md#non-goals). Every `terraform apply` in this project's history was run by a human on purpose.
