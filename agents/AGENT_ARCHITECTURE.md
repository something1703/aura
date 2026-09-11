# Architecture Agent

## Goal
Produce bounded candidate architectures from known patterns.

## Process

1. classify workload;
2. filter unsupported patterns;
3. generate candidate graphs;
4. attach AWS implementation choices;
5. declare trade-offs;
6. return candidates for deterministic scoring.

## Output requirement

Every candidate must include:

- topology;
- components;
- dependency relationships;
- availability model;
- scaling model;
- data strategy;
- failure strategy;
- costs assumptions;
- known limitations.
