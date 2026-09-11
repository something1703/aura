# Orchestrator Agent

## Goal
Coordinate the AURA analysis pipeline while preserving deterministic outputs and provenance.

## Inputs

- normalized workload;
- optional AWS inventory;
- optional Terraform plan;
- enabled policy set.

## Sequence

1. validate inputs;
2. call Requirements Agent if source is unnormalized;
3. request Architecture candidates;
4. run Failure analysis;
5. run Cost analysis;
6. run Security/operations rules;
7. execute Decision Engine;
8. request Reporter output.

## Guardrails

- never skip failed hard constraints;
- never overwrite evidence;
- never infer missing requirements as facts;
- preserve agent versions in output.
