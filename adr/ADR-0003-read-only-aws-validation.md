# ADR-0003 — Read-Only AWS Validation First

## Status
Accepted

## Decision

AURA will inspect AWS and Terraform state before acquiring any capability to mutate infrastructure automatically.

## Rationale

The platform is intended to become a trustworthy architecture gate. Read-only observation reduces accidental blast radius while the decision model matures.

## Consequence

Deployment remains outside AURA's autonomous control in early versions.
