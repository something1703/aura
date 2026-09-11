# Runtime Architecture (Phase 1)

This describes the actual runtime call path for `src/aura`, as implemented —
see [logical.md](logical.md) for the intended shape and
[decision-framework.md](decision-framework.md) for the four evaluation
layers this runtime enforces.

```text
YAML file
  │  aura.requirements.loader.load_workload_document
  ▼
raw dict
  │  aura.requirements.validator.validate_workload (Pydantic)
  ▼
Workload
  │  aura.requirements.normalizer.normalize
  ▼
NormalizedRequirements  (value/raw/source/confidence/mandatory per field,
                          + detected conflicts, + overall confidence)
  │  aura.architecture.generator.generate_candidates
  ▼
Candidate[]  (one per catalog pattern, each with a concrete topology Graph)
  │
  │  per candidate, run in this order (aura.evaluation.engine.evaluate_candidate):
  │
  ├─▶ aura.failure.simulator.simulate_candidate
  │     8 scenarios × {evaluate_component_availability, impacted_capabilities,
  │     blast_radius.classify} → CandidateFailureReport
  │
  ├─▶ aura.cost.estimates.estimate_candidate_all_scenarios
  │     4 scenarios (average/peak/sustained-peak/failure-mode) → CostEstimate
  │
  ├─▶ aura.evaluation.rules.evaluate_rules
  │     9 rules, consuming the failure report + cost estimates → RuleResult[]
  │
  └─▶ aura.evaluation.scoring.compute_dimension_scores
        8 weighted dimensions → DimensionScore[] → weighted_score
  ▼
CandidateScore[]  (eligibility + rule evidence + dimensions + confidence)
  │  aura.evaluation.engine.select_recommendation
  ▼
recommendation (or none, if every candidate is INELIGIBLE)
  │  aura.reporting.context.build_context
  ▼
ReportContext
  │
  ├─▶ aura.reporting.markdown.render_report   → report.md (+ report.json)
  └─▶ aura.reporting.adr.generate_adrs        → ADR-0001..0006.md
```

## Enforced invariants

- A mandatory rule `FAIL` always makes a candidate `INELIGIBLE`, regardless
  of its weighted score (`aura.evaluation.engine.evaluate_candidate`).
- Every failure-simulation result is tagged `MODELLED`
  (`aura.domain.enums.EvidenceType`) — nothing here is `SIMULATED` (a
  controlled test was run) or `MEASURED` (observed from real metrics), since
  Phase 1 has no execution environment to produce either.
- Domain engines (`architecture`, `evaluation`, `failure`, `cost`) never
  import an AWS SDK client. Phase 2 will add `aura.providers.aws` and
  `aura.providers.terraform` behind an interface; nothing in this call path
  changes shape when that lands.

## Phase 2/3 extension points

Phase 2 inserts an observed-state graph and a Terraform desired-state graph
alongside the `Candidate.topology` graph already produced above, and compares
them (`docs/AWS_INTEGRATION.md`). Phase 3 wraps this whole pipeline in a CI
gate and adds a runtime observation loop (`docs/IMPLEMENTATION_PHASES.md`
Phase 3). Neither changes the Phase 1 call path itself.
