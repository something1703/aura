export const GLOSSARY = {
  eligibility:
    "Whether this candidate passes every mandatory rule. A candidate can score highly and still be INELIGIBLE if it violates one hard constraint (e.g. required availability, encryption, or regional resilience) — a high score never overrides a failed mandatory rule.",
  confidence:
    "How much to trust this result, from 0 (none) to 1 (full). Drops when the workload leans on stated assumptions, cost estimates carry more uncertainty, or the result is modelled rather than measured against real infrastructure.",
  weightedScore:
    "The 0–100 blend of all 8 scoring dimensions, each multiplied by its configured weight (see the Scoring breakdown table below). Only eligible candidates get a score — an ineligible one has none, no matter how well it would otherwise perform.",
  dimensionScore:
    "This dimension's own 0–100 value, before weighting. Multiply by Weight to see how much it actually contributes to the overall weighted score.",
  weight:
    "How much this dimension counts toward the overall weighted score, as a share of 100%. Configurable per workload — a banking system, for instance, might weight Security and Reliability higher than the defaults used here.",
  blastRadius:
    "How much of the business breaks if this failure happens. LOW = a single non-critical component. MEDIUM = one bounded feature. HIGH = multiple business capabilities. CRITICAL = the core business path (e.g. checkout, payments) becomes unreachable.",
  rto:
    "Recovery Time Objective — how long the business can tolerate being down. AURA compares this against the modelled recovery time for each failure scenario; PASS means the scenario recovers within it.",
  rpo:
    "Recovery Point Objective — how much data the business can tolerate losing. AURA compares this against the modelled data-loss window for each scenario, driven mainly by how the database replicates (sync vs. async).",
  mandatory:
    "If this rule FAILs and is marked mandatory, the candidate becomes INELIGIBLE outright — no amount of score elsewhere can override a violated hard constraint.",
  evidence:
    "Every failure result here is tagged MODELLED: graph/rule reasoning over the candidate's topology, not a real test. AURA's evidence policy has two stronger tiers it never claims without doing the work: SIMULATED (a controlled test was actually run) and MEASURED (observed from real production metrics — see the `aura observe` command).",
} as const;

export type GlossaryTerm = keyof typeof GLOSSARY;
