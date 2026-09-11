# Scoring and Decision Engine

## Principle

The scoring engine is a decision aid, not the decision itself.

## Hard constraints

A candidate becomes **INELIGIBLE** when a mandatory requirement fails.

Examples:

- RTO target violated;
- required regional resilience absent;
- mandatory encryption absent;
- budget ceiling violated if budget is hard.

## Soft criteria

Soft criteria receive configurable weights.

Default:

| Criterion | Weight |
|---|---:|
| Reliability | 25 |
| Scalability | 20 |
| Security | 15 |
| Performance | 10 |
| Operations | 10 |
| Cost | 10 |
| Complexity | 5 |
| Sustainability | 5 |

## Rule result

```json
{
  "rule_id": "rto.max",
  "status": "FAIL",
  "severity": "critical",
  "observed": 900,
  "required": 300,
  "evidence": "Candidate recovery path requires manual regional promotion."
}
```

## Candidate score

For eligible candidates:

```text
weighted_score = Σ(normalized_dimension_score × weight)
```

The engine should keep the raw dimension values so a reviewer can reconstruct the result.

## Recommendation confidence

Confidence is a separate value from score.

A candidate can score 92/100 but have 0.55 confidence if key workload data is missing.

Confidence should decrease when:

- major requirements are assumptions;
- cost estimates are incomplete;
- recovery behavior is untested;
- AWS state is unavailable.
