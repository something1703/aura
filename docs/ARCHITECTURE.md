# AURA Technical Architecture

## Architectural style

AURA should use a modular monolith initially, not microservices.

This is intentional. AURA's challenge is architecture intelligence, not service decomposition. Splitting a young rule engine into multiple services creates operational overhead before the domain is stable.

## Layers

```text
CLI / API / UI
      ↓
Application Services
      ↓
Domain Engines
      ↓
Domain Models
      ↓
Adapters
      ↓
AWS / Terraform / Filesystem
```

## Domain engines

### Requirements

Owns validation and normalization.

### Architecture

Owns patterns, candidate generation, and graph construction.

### Evaluation

Owns rules, hard constraints, weights, and evidence.

### Failure

Owns failure scenarios, dependency traversal, and recovery paths.

### Cost

Owns price model abstractions and assumptions.

### Reporting

Owns reports and ADR rendering.

## Dependency rule

Domain engines cannot import AWS SDK clients directly.

Instead:

```text
Domain logic → provider interface → AWS adapter
```

This keeps local tests fast and deterministic.

## Suggested Python package

```text
src/aura/
├── domain/
│   ├── models.py
│   ├── enums.py
│   └── graph.py
├── requirements/
│   ├── loader.py
│   ├── validator.py
│   └── normalizer.py
├── architecture/
│   ├── catalog.py
│   ├── generator.py
│   └── patterns.py
├── evaluation/
│   ├── rules.py
│   ├── engine.py
│   └── scoring.py
├── failure/
│   ├── scenarios.py
│   ├── simulator.py
│   └── blast_radius.py
├── cost/
│   ├── model.py
│   └── estimates.py
├── providers/
│   ├── aws.py
│   └── terraform.py
├── reporting/
│   ├── markdown.py
│   └── adr.py
└── cli/
    └── main.py
```

## Data flow

```text
YAML
 ↓
Pydantic Workload
 ↓
Normalized Workload
 ↓
Architecture Candidates
 ↓
Evaluation Matrix
 ↓
Failure Simulation
 ↓
Decision
 ↓
Report + ADR + JSON
```
