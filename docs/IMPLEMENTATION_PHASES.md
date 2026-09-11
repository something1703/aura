# Three-Phase Implementation Plan

## Phase 1 — Architecture Intelligence Lab

### Objective

Create a deterministic architecture-analysis engine that operates locally without requiring AURA to deploy resources.

### Deliverables

- typed workload model;
- YAML loader and validator;
- requirement normalization;
- architecture pattern catalog;
- candidate generator;
- rule engine;
- scoring engine;
- failure and blast-radius engine;
- cost-model abstraction;
- ADR generator;
- Markdown + JSON report output;
- CLI;
- unit/integration tests;
- example workload cases;
- architecture diagrams.

### Module implementation

#### 1. Requirements model

Create Pydantic models for:

```text
Workload
 ├── Application
 ├── Traffic
 ├── Availability
 ├── Recovery
 ├── Consistency
 ├── Geography
 ├── Budget
 ├── Deployment
 ├── Security
 └── Compliance
```

Validation should reject:

- negative RTO/RPO;
- invalid percentage targets;
- peak traffic below average traffic;
- impossible budget formats;
- unknown consistency modes;
- empty application names.

#### 2. Normalization

Convert user inputs into canonical values.

Examples:

- `5m` → 300 seconds;
- `99.99%` → four-nines target;
- `$15k` → 15000 USD/month.

The normalized model must retain the original value for reporting.

#### 3. Architecture catalog

Start with five patterns:

- single-region multi-AZ;
- multi-region active-passive;
- multi-region warm standby;
- multi-region active-active;
- event-driven buffered architecture.

Each pattern has:

```yaml
id: multi-region-active-passive
supports:
  availability_min: 99.95
  rto_max_seconds: 900
  rpo_max_seconds: 300
requires:
  - cross_region_replication
tradeoffs:
  - higher_cost
  - operational_complexity
failure_modes:
  - regional_loss
```

#### 4. Candidate generation

Do not generate arbitrary graph structures initially. Generate known patterns with typed components. This makes the engine deterministic and testable.

#### 5. Evaluation rules

Create small, composable rules:

```text
AvailabilityRule
CapacityRule
RTORule
RPORule
BudgetRule
RegionalResilienceRule
SecurityBoundaryRule
DeploymentRule
OperationalComplexityRule
```

Each rule returns:

```text
PASS | WARN | FAIL | NOT_EVALUATED
```

with evidence and severity.

#### 6. Scoring

Suggested initial weighting:

```text
Reliability         25%
Scalability         20%
Security            15%
Performance         10%
Operations          10%
Cost                10%
Complexity           5%
Sustainability       5%
```

The weighting must be configurable per workload. For example, a banking workload may give security and recovery a larger weight.

Never allow a weighted score to hide a hard constraint failure. A candidate that violates a mandatory RTO should be marked **ineligible**, even if its numerical score is high.

#### 7. Failure engine

Represent failures as typed events:

```text
INSTANCE_FAILURE
AZ_FAILURE
REGION_FAILURE
DATABASE_FAILURE
NETWORK_DEGRADATION
TRAFFIC_SPIKE
BAD_DEPLOYMENT
DEPENDENCY_FAILURE
```

For each event calculate a recovery path from graph edges. If no path exists, report a hard failure.

#### 8. Blast radius

AURA should traverse dependency relationships from the failed component and classify affected business capabilities:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

A component is not “critical” merely because it is important. Criticality must be based on declared business capabilities and dependency graph reachability.

#### 9. ADR generation

Generate ADRs only for meaningful decisions:

- compute model;
- data model;
- region strategy;
- deployment strategy;
- scaling strategy;
- recovery strategy.

#### 10. Phase 1 CLI

Commands:

```bash
aura validate <workload.yaml>
aura analyze <workload.yaml>
aura failures <workload.yaml>
aura score <workload.yaml>
aura report <workload.yaml> --output <dir>
aura adr <workload.yaml> --output <dir>
```

### Phase 1 acceptance test

Input a flash-sale workload.

Expected:

- at least 3 viable candidates;
- at least 1 rejected candidate with reasons;
- one selected architecture;
- failure report for AZ and Region failure;
- scoring breakdown;
- generated ADRs;
- deterministic JSON output.

---

## Phase 2 — Infrastructure Reality Bridge

### Objective

Connect the architecture model to Terraform and read-only AWS inspection.

### Deliverables

- Terraform architecture modules;
- environment conventions;
- Terraform plan parser;
- AWS inventory reader;
- desired-vs-observed graph comparison;
- drift detection report;
- architecture conformance gate.

### Important boundary

Phase 2 should **read infrastructure before it writes infrastructure**.

Start with:

```bash
aura aws inventory
```

and:

```bash
aura terraform inspect tfplan.json
```

Then:

```bash
aura validate-deployed --workload config/flash-commerce.yaml
```

The output should explain:

```text
Expected: 3 Availability Zones
Observed: 2
Status: FAIL

Expected: encrypted database storage
Observed: encrypted
Status: PASS
```

### Terraform integration

The recommended pattern is:

```text
AURA workload
    ↓
AURA architecture decision
    ↓
Terraform module inputs
    ↓
terraform plan -out=tfplan
    ↓
terraform show -json tfplan
    ↓
AURA policy/architecture validation
    ↓
Human approval
    ↓
terraform apply
```

AURA should not initially write `.tf` files directly. Prefer stable modules and generated variable values.

### Phase 2 acceptance test

Provision a non-production environment with Terraform.

Intentionally change one architecture attribute out of band.

Run AURA.

Expected result:

```text
Architecture Conformance: FAILED
Drifted attributes: 1

Required: 3 AZs
Observed: 2 AZs
```

---

## Phase 3 — Continuous Reliability Platform

### Objective

Make architecture validation part of the software delivery lifecycle.

### Deliverables

- GitHub Actions or equivalent CI;
- AURA architecture gate;
- Dockerized AURA service;
- ECS deployment for the AURA control plane, if desired;
- progressive delivery validation;
- CloudWatch/observability integration;
- security policy checks;
- runtime architecture validation;
- controlled failure experiments.

### CI/CD flow

```text
Pull Request
    ↓
Unit Tests
    ↓
Architecture Validation
    ↓
Terraform Plan
    ↓
AURA Plan Validation
    ↓
Human Approval
    ↓
Deploy
    ↓
Health Validation
    ↓
Canary / Blue-Green
    ↓
AURA Runtime Validation
    ↓
Promote or Roll Back
```

### Runtime reliability loop

```text
Deploy
  ↓
Observe
  ↓
Compare actual behavior to architecture assumptions
  ↓
Detect reliability/cost/security drift
  ↓
Create finding
  ↓
Recommend action
```

### Controlled chaos

The first chaos experiments should be non-destructive and isolated:

1. terminate a disposable task;
2. remove one healthy target in a test environment;
3. generate synthetic traffic;
4. simulate a dependency timeout.

Only later should multi-AZ or regional experiments be considered, and never in production without explicit authorization.

### Phase 3 acceptance test

Run a complete demonstration:

```text
Git push
→ architecture gate
→ Terraform plan
→ approval
→ deployment
→ synthetic traffic
→ metric validation
→ controlled failure
→ automatic detection
→ recovery evidence
```

The demonstration should produce an auditable timeline.
