# AURA Implementation Master Plan

This document is the execution checklist for building AURA from an empty repository.

## Week/Iteration 1 — Foundations

1. Initialize Python package.
2. Add formatter/linter/test runner.
3. Implement domain enums.
4. Implement workload models.
5. Implement YAML loading.
6. Implement schema validation.
7. Build CLI skeleton.

Definition of done:

```bash
aura validate config/flash-commerce.yaml
```

returns a stable normalized document.

## Iteration 2 — Architecture domain

1. Implement architecture graph.
2. Implement pattern catalog.
3. Add single-region multi-AZ.
4. Add active-passive.
5. Add active-active.
6. Add event-buffered pattern.
7. Write candidate generator tests.

Definition of done:

```bash
aura analyze config/flash-commerce.yaml
```

returns candidate graphs.

## Iteration 3 — Rules + scores

1. Implement rule interface.
2. Add hard constraints.
3. Add soft scoring.
4. Add configurable weights.
5. Add confidence.
6. Add deterministic JSON output.

Definition of done:

Each candidate is eligible/ineligible with evidence.

## Iteration 4 — Failure engine

1. Implement dependency graph traversal.
2. Add failure scenarios.
3. Add blast-radius classification.
4. Add RTO/RPO comparison.
5. Add modelled/simulated/measured evidence tags.

Definition of done:

AURA can demonstrate why an architecture survives or fails an AZ and Region failure.

## Iteration 5 — Reporting

1. Build Markdown report renderer.
2. Build ADR renderer.
3. Add architecture diagram data.
4. Add executive summary.
5. Add machine-readable output.

Definition of done:

A fresh clone can regenerate the entire case-study package from the YAML input.

## Iteration 6 — Cost engine

1. Define cost provider interface.
2. Implement scenario-based estimates.
3. Add cost assumptions.
4. Add budget rules.
5. Add uncertainty/confidence.

## Iteration 7 — Terraform bridge

1. Create Terraform root/module conventions.
2. Capture `terraform show -json`.
3. Parse plan resources.
4. Map resources into AURA graph.
5. Validate desired architecture.

## Iteration 8 — AWS observer

1. Implement read-only credentials.
2. Implement inventory readers.
3. Build observed-state graph.
4. Compare desired vs observed.
5. Add conformance/drift report.

## Iteration 9 — CI gate

1. Run tests on PR.
2. Run AURA validate.
3. Run AURA architecture diff.
4. Run Terraform plan.
5. Block merge on mandatory architecture failures.

## Iteration 10 — Runtime reliability

1. Containerize AURA.
2. Add application metrics.
3. Add CloudWatch integration.
4. Store validation history.
5. Add controlled failure experiments.

## First end-to-end milestone

The first serious milestone is not “AWS resources exist.” It is:

```text
requirements.yaml
      ↓
aura analyze
      ↓
3 candidate architectures
      ↓
hard constraints
      ↓
failure analysis
      ↓
cost comparison
      ↓
selected architecture
      ↓
ADR package
```

Only after this works should real AWS provisioning become part of the success criteria.

## Engineering quality bar

AURA should have:

- typed domain models;
- deterministic tests;
- reproducible output;
- versioned decision rules;
- explicit assumptions;
- no credential leakage;
- documented safety boundaries;
- architecture decisions represented as code and ADRs.
