# AURA — Autonomous Unified Reliability Architecture

> **Design for success. Validate for failure.**

AURA is an architecture decision, validation, and reliability-analysis platform for AWS workloads. It converts business and non-functional requirements into explicit engineering constraints, evaluates multiple architecture patterns, models failure domains, estimates scalability and cost, and produces explainable architecture decisions and ADRs.

AURA is intentionally **not** an AWS service catalog or a generic Terraform wrapper. Its central problem is architectural judgment:

> Given a workload, its constraints, and its failure assumptions, **which architecture is the best trade-off and why?**

## Current starting point

The local environment already assumes:

- AWS CLI is configured and authenticated.
- Terraform is installed and available on `PATH`.
- The initial project does not assume an existing production VPC or application.
- Phase 1 focuses on architecture intelligence and validation before provisioning a real stack.

## Project goals

1. Convert human requirements into machine-readable constraints.
2. Generate or select candidate AWS architecture patterns.
3. Evaluate candidates against availability, RTO/RPO, scalability, security, cost, operations, and complexity.
4. Model explicit failure scenarios and blast radius.
5. Produce explainable architecture decisions and ADRs.
6. Evolve from static architecture analysis into infrastructure validation and deployment gates.
7. Provide a foundation for Units 1–5 rather than five disconnected assignments.

## Non-goals

AURA is not initially intended to:

- autonomously deploy arbitrary production workloads without approval;
- replace AWS documentation or professional architecture review;
- guarantee exact AWS bills or exact recovery times;
- make unsupported claims about service behavior without an evidence source.

## Three-phase implementation

### Phase 1 — Architecture Intelligence Lab

Build the core architecture model, requirements parser, candidate architecture catalog, scoring engine, failure model, trade-off engine, and report/ADR generator.

**Output:** a local CLI/web prototype that accepts a workload specification and produces an architecture recommendation with evidence, risks, failure analysis, and ADRs.

### Phase 2 — Infrastructure Reality Bridge

Connect AURA to Terraform and AWS read APIs. Generate bounded Terraform plans or validation inputs, inspect deployed resources, compare desired versus observed architecture, and validate environment parity.

**Output:** AURA can validate real AWS architecture and act as a pre-deployment architecture gate.

### Phase 3 — Continuous Reliability Platform

Integrate CI/CD, containerized workloads, progressive delivery, observability, security controls, and controlled failure experiments.

**Output:** architecture becomes a continuously evaluated production engineering artifact.

## High-level architecture

```text
                    +-----------------------+
                    |       AURA CLI/UI     |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |  Requirements Engine  |
                    +-----------+-----------+
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
     Architecture Engine   Failure Engine      Cost/Scale Engine
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                    +-----------------------+
                    | Architecture Validator|
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Decision / ADR Engine |
                    +-----------+-----------+
                                |
                 +--------------+--------------+
                 |                             |
                 v                             v
          Architecture Report             Machine Output
                                           (JSON/YAML)

Phase 2 adds:

        Terraform <----> AURA <----> AWS Read APIs

Phase 3 adds:

        Git -> CI -> AURA Gate -> Progressive Delivery -> Observability
                                      ^                     |
                                      |                     |
                                 Failure Lab <-------------+
```

## Example input

```yaml
application:
  name: flash-commerce
  type: ecommerce

traffic:
  average_rps: 5000
  peak_rps: 150000
  peak_duration_minutes: 20

availability:
  target: 99.99%

recovery:
  rto_minutes: 5
  rpo_minutes: 1

consistency:
  orders: strong
  catalog: eventual

geography:
  primary_regions:
    - ap-south-1
  user_regions:
    - IN
    - SG
    - AE

budget:
  monthly_usd: 15000

deployment:
  frequency_per_day: 10
  downtime_allowed: false

security:
  internet_facing: true
  data_classification: confidential
```

## Example output

```text
AURA ARCHITECTURE REPORT
========================
Recommendation: Multi-AZ primary + warm regional recovery

Reliability       94/100
Scalability       91/100
Security          96/100
Operations        89/100
Cost               81/100
Complexity         76/100
Overall            90/100

RTO target         5 min
Expected envelope  3–5 min
RPO target         1 min
Expected envelope  <1 min

Top risk:
Regional recovery depends on database promotion and traffic cutover.

Rejected alternative:
Multi-region active-active. Higher cost and data consistency complexity
without sufficient business benefit for the supplied constraints.
```

## Recommended stack

### Core

- Python 3.12+
- FastAPI for API boundaries
- Pydantic for typed configuration and validation
- Typer for CLI
- PyYAML for workload specifications
- Jinja2 for report/ADR generation
- pytest for tests

### AWS integration

- AWS CLI
- boto3
- Terraform
- Terraform JSON plan output for safe machine inspection

### Optional Phase 2/3

- SQLite/PostgreSQL for persisted architecture evaluations
- Docker
- GitHub Actions
- Amazon ECS
- Amazon CloudWatch
- Amazon S3
- Amazon DynamoDB or Aurora depending on the final workload

## Repository structure

```text
.
├── README.md
├── AGENTS.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
│
├── docs/
│   ├── PROJECT_VISION.md
│   ├── IMPLEMENTATION_PHASES.md
│   ├── ARCHITECTURE.md
│   ├── REQUIREMENTS_ENGINE.md
│   ├── SCORING_ENGINE.md
│   ├── FAILURE_MODEL.md
│   ├── COST_MODEL.md
│   ├── AWS_INTEGRATION.md
│   ├── TESTING.md
│   ├── DEMO_RUNBOOK.md
│   └── ROADMAP.md
│
├── agents/
│   ├── AGENT_ORCHESTRATOR.md
│   ├── AGENT_REQUIREMENTS.md
│   ├── AGENT_ARCHITECTURE.md
│   ├── AGENT_FAILURE.md
│   ├── AGENT_COST.md
│   ├── AGENT_AWS_VALIDATOR.md
│   └── AGENT_REPORTER.md
│
├── architecture/
│   ├── logical.md
│   ├── runtime.md
│   └── decision-framework.md
│
├── adr/
│   ├── ADR-0001-project-scope.md
│   ├── ADR-0002-rule-based-first.md
│   └── ADR-0003-read-only-aws-validation.md
│
├── config/
│   └── flash-commerce.yaml
│
├── schemas/
│   ├── workload.schema.json
│   └── architecture.schema.json
│
├── scripts/
│   ├── bootstrap.sh
│   ├── validate.sh
│   └── generate_schemas.py
│
├── tests/
│   ├── unit/
│   ├── golden/
│   └── integration/
│
├── web/                        # Next.js UI over the FastAPI JSON API
│   └── src/
│
└── src/aura/
    ├── domain/                 # enums, Workload/graph models, parsing
    ├── requirements/           # loader, validator, normalizer
    ├── architecture/           # pattern catalog, candidate generator
    ├── failure/                # scenarios, simulator, blast radius
    ├── cost/                   # scenario-based cost estimates
    ├── evaluation/             # rules, scoring, eligibility
    ├── providers/               # Terraform plan parser, read-only AWS inventory (Phase 2)
    ├── reporting/               # Markdown report + ADR generation
    ├── web/                     # FastAPI app backing the Next.js UI
    └── cli/
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,aws]"   # [aws] (boto3) is needed to run the full test suite —
                               # the Phase 2 provider tests mock the AWS calls but still
                               # import boto3 itself

aws sts get-caller-identity
terraform version

aura validate config/flash-commerce.yaml
aura analyze config/flash-commerce.yaml
aura failures config/flash-commerce.yaml
aura score config/flash-commerce.yaml
aura report config/flash-commerce.yaml --output artifacts/report
aura adr config/flash-commerce.yaml --output artifacts/adr

pytest -q
```

The exact package layout can be adjusted during Phase 1; the important contract is that configuration, domain logic, and provider integration remain separated.

## Web UI

A Next.js front end (`web/`) runs the same pipeline in the browser — a "how it works"
walkthrough plus a live demo you can point at any workload YAML. It talks to a small
FastAPI JSON API (`aura serve`); nothing in either process calls AWS.

```bash
# terminal 1 — API
pip install -e .
aura serve                 # http://127.0.0.1:8000

# terminal 2 — UI
cd web
npm install
npm run dev                # http://localhost:3000
```

Then open http://localhost:3000. If the API runs on a non-default host/port, point the UI
at it with `NEXT_PUBLIC_AURA_API_URL` and allow that UI origin on the API with
`AURA_WEB_ORIGIN`, e.g.:

```bash
AURA_WEB_ORIGIN=http://localhost:3100 aura serve --port 8100
NEXT_PUBLIC_AURA_API_URL=http://127.0.0.1:8100 npm run dev -- --port 3100
```

## Engineering principles

### 1. Requirements before services

Never start with “use ECS.” Start with the availability, capacity, data, security, and recovery constraints.

### 2. Explainability before cleverness

Every recommendation must have a reason, evidence, assumptions, and a confidence level.

### 3. Rule-based core before AI-generated decisions

The first decision engine is deterministic and testable. LLM or agent assistance can be added later for requirement extraction and narrative generation, but the final score and policy evaluation must remain auditable.

### 4. Read-only AWS integration first

AURA should inspect AWS before it is trusted to mutate AWS.

### 5. Failure is a first-class input

A design that only describes the healthy path is incomplete.

### 6. Cost is a constraint, not a report footnote

A technically excellent design that violates the business budget is not automatically the right design.

## What “done” means for Unit 1

The Unit 1 milestone is complete when a reviewer can:

1. provide a workload YAML;
2. run one AURA command;
3. receive at least three candidate architectures;
4. see why one candidate was selected;
5. inspect the failure scenarios and blast radius;
6. inspect the scoring breakdown;
7. inspect generated ADRs;
8. understand which assumptions are uncertain;
9. reproduce the same result locally.

## Future evolution

Unit 1 establishes architectural intelligence.

Unit 2 turns the chosen architecture into Terraform-managed infrastructure.

Unit 3 places AURA inside CI/CD as an architecture gate.

Unit 4 validates containerized service topology and scaling.

Unit 5 adds observability, security, drift, runtime reliability, and controlled chaos experiments.
