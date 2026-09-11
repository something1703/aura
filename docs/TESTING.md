# Testing Strategy

## Unit tests

Test each rule and model independently.

Examples:

```text
RTORule
AvailabilityRule
PeakTrafficRule
BudgetRule
RegionFailureRule
```

## Golden-file tests

Given a workload YAML, the selected candidate set and report JSON should be stable.

Store expected outputs under:

```text
tests/golden/
```

## Property tests

Useful properties:

- increasing required availability should not make a candidate more reliable;
- lowering budget should not improve cost score;
- removing a failure recovery edge cannot improve recoverability;
- a mandatory constraint failure always blocks eligibility.

## Integration tests

Phase 2 should include:

- Terraform plan parsing;
- mocked AWS inventory;
- desired/observed graph matching.

## Live AWS tests

Live tests should be explicitly tagged:

```bash
pytest -m aws
```

They should never run automatically on ordinary pull requests.
