# Cost Model

## Purpose

Compare architectures economically without creating false precision.

## Cost categories

- compute;
- storage;
- databases;
- data transfer;
- load balancing;
- observability;
- backup/replication;
- fixed platform cost;
- burst cost.

## Estimation model

Each estimate contains:

```text
service
unit
quantity
utilization
unit_price
assumption
confidence
```

## Example

```text
ECS compute
20 tasks
40% average utilization
estimated monthly compute = X
confidence = medium
```

## Scenario analysis

Every meaningful architecture should be estimated at:

- average load;
- peak load;
- sustained peak;
- failure-mode load.

## Cost decision rule

If a candidate exceeds the hard budget, mark it ineligible.
If it exceeds a preferred budget, keep it eligible but expose the variance.

## Important limitation

AURA should never claim that its cost estimate is an AWS invoice. Pricing varies by region, usage pattern, discounts, data transfer, and managed-service configuration.
