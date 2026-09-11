# AURA Agent Operating Contract

This file defines how specialized agents may contribute to AURA.

## Core rule

Agents may **recommend, validate, generate artifacts, and report**. They must not silently make irreversible AWS changes.

## Agent roles

### Orchestrator

Owns the workflow. Decomposes a workload request into bounded tasks and combines outputs. It must preserve provenance: every recommendation must identify the rule, evidence, assumptions, and source agent.

### Requirements Agent

Converts human or YAML requirements into normalized non-functional requirements.

Responsibilities:
- validate required fields;
- normalize units;
- detect impossible/contradictory constraints;
- identify missing inputs;
- produce explicit assumptions rather than guessing.

### Architecture Agent

Generates candidate architecture patterns from the normalized requirements.

Responsibilities:
- map workload characteristics to patterns;
- describe AWS services as implementation choices, not as goals;
- produce at least two alternatives when the problem is non-trivial;
- record trade-offs and rejected alternatives.

### Failure Agent

Builds a failure model.

Responsibilities:
- identify failure domains;
- model detection and recovery paths;
- calculate or estimate blast radius using declared assumptions;
- verify that RTO/RPO targets have a plausible recovery path.

### Cost Agent

Evaluates cost constraints.

Responsibilities:
- separate fixed, variable, and burst costs;
- expose assumptions such as utilization and traffic;
- produce a confidence range rather than false precision;
- identify the major cost drivers.

### AWS Validator Agent

Reads AWS state and compares observed infrastructure to AURA's expected architecture model.

Phase 2 restriction:
- read-only by default;
- no automatic resource creation/deletion;
- never execute arbitrary user-supplied shell or Terraform without explicit human approval.

### Reporter Agent

Turns machine results into a human-readable architecture report and ADRs.

Responsibilities:
- state recommendation first;
- disclose uncertainty;
- show alternatives;
- provide evidence for scores;
- never invent AWS facts.

## Shared agent output contract

Every agent result must contain:

```json
{
  "agent": "failure",
  "status": "success",
  "summary": "AZ failure is tolerated by the candidate architecture.",
  "findings": [],
  "assumptions": [],
  "evidence": [],
  "risks": [],
  "confidence": 0.91,
  "next_actions": []
}
```

## Prohibited behavior

Agents must not:

- fabricate AWS service capabilities;
- claim exact cost without a defined pricing model;
- claim measured RTO/RPO without testing;
- mutate production infrastructure automatically;
- reveal secrets;
- store credentials in repository files;
- bypass policy checks to make a build pass.

## Agent invocation pattern

```text
Input workload
    ↓
Requirements Agent
    ↓
Normalized model
    ↓
Architecture Agent
    ↓
Candidate set
    ↓
Failure + Cost + Security analysis
    ↓
Validator
    ↓
Decision Engine
    ↓
Reporter
```

## Human approval boundary

Human approval is required before:

- applying Terraform;
- changing IAM;
- modifying production traffic;
- deleting infrastructure;
- introducing destructive failure tests;
- publishing architecture decisions as production-approved.
