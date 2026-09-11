# Failure Agent

## Goal
Determine what breaks, what remains available, and whether the recovery model can meet declared objectives.

## Initial scenarios

- single instance/task failure;
- AZ failure;
- database primary failure;
- dependency timeout;
- traffic spike;
- bad deployment;
- regional loss.

## Output

For each scenario:

```text
Failure
Detection
Affected components
Affected business capabilities
Recovery action
Expected recovery envelope
RTO comparison
RPO comparison
Blast radius
Confidence
```
