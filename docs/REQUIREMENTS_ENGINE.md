# Requirements Engine

## Purpose

Convert incomplete, human-friendly workload requirements into a canonical model that downstream engines can evaluate.

## Requirements categories

### Workload

- application type;
- statefulness;
- synchronous/asynchronous workload;
- external dependencies.

### Traffic

- average RPS;
- peak RPS;
- concurrency;
- burst duration;
- growth rate.

### Availability

- uptime target;
- maintenance expectations;
- acceptable single-AZ failure.

### Recovery

- RTO;
- RPO;
- backup requirements;
- regional disaster requirements.

### Data

- consistency;
- durability;
- retention;
- data classification.

### Geography

- users;
- data residency;
- region preferences.

### Economics

- monthly budget;
- acceptable cost variance;
- reserved/spot constraints.

### Delivery

- deployment frequency;
- downtime allowed;
- rollback objective.

## Requirement states

Every requirement is:

```text
VALUE
SOURCE
CONFIDENCE
MANDATORY / PREFERRED
```

Example:

```yaml
rto:
  value_seconds: 300
  source: user
  confidence: 1.0
  mandatory: true
```

## Contradiction detection

Examples:

```text
RTO = 60 seconds
AND
manual recovery only
```

or:

```text
10,000 RPS peak
AND
maximum 2 compute instances
```

AURA should report the conflict rather than silently choosing one requirement.
