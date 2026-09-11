# AURA Demo Runbook

## Demo objective

Show that AURA can take a demanding workload and turn it into an explainable architecture decision.

## Demo 1 — Input

Use:

```text
config/flash-commerce.yaml
```

## Demo 2 — Validate

```bash
aura validate config/flash-commerce.yaml
```

Show:

- canonical requirements;
- detected assumptions;
- validation status.

## Demo 3 — Analyze

```bash
aura analyze config/flash-commerce.yaml
```

Show three or more candidate patterns.

## Demo 4 — Explain

Open the report and show:

- selected architecture;
- rejected alternatives;
- hard constraints;
- weighted scores;
- confidence;
- assumptions.

## Demo 5 — Failure

```bash
aura failures config/flash-commerce.yaml
```

Show AZ failure and Region failure.

## Demo 6 — ADRs

```bash
aura adr config/flash-commerce.yaml --output artifacts/adr
```

Open one ADR and explain the decision.

## Demo 7 — Phase 2 preview

Show the Terraform plan flow without applying.

```text
Terraform plan
    ↓
AURA validation
    ↓
PASS / FAIL
```

## Demo principle

Do not spend the demonstration reading code. Show the decision process, the evidence, the failure model, and the trade-offs.
