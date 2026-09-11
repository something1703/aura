# Failure Model and Chaos Framework

## Failure-domain hierarchy

```text
Application
  → Task / Instance
  → AZ
  → Region
  → Provider / External Dependency
```

## Failure event schema

```yaml
failure:
  id: AZ_FAILURE
  target: ap-south-1a
  severity: critical
  assumptions:
    duration_seconds: 300
```

## Simulation phases

1. Detect affected nodes.
2. Remove failed nodes from the topology.
3. Traverse dependencies.
4. Determine impacted capabilities.
5. Identify recovery mechanisms.
6. Estimate recovery envelope.
7. Compare to RTO/RPO.
8. Produce recommendation.

## Example

```text
Failure: AZ-A unavailable

ALB
├── AZ-A target group → unavailable
└── AZ-B target group → available

Database
└── Multi-AZ failover → expected

Result:
- user traffic continues;
- reduced redundancy during recovery;
- no RPO violation expected;
- RTO satisfied.
```

## Blast radius classification

### Low
Single non-critical component.

### Medium
One feature or bounded service.

### High
Multiple business capabilities.

### Critical
Core business path or broad platform availability.

## Evidence policy

Simulation results must be labelled:

- `MODELLED` — graph/rule model only;
- `SIMULATED` — controlled test executed;
- `MEASURED` — observed from real metrics.

Never label a modelled result as measured.
