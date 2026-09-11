# ADR-0002 — Rule-Based Decision Core Before AI Assistance

## Status
Accepted

## Decision

The AURA decision engine will be deterministic and testable before adding any generative AI assistance.

## Rationale

Architecture decisions require auditability. AI can help extract requirements or produce explanations, but mandatory constraints, scoring, and eligibility must be reproducible.

## Consequence

The initial engine may appear less “magical,” but its recommendations can be tested, reviewed, and challenged.
