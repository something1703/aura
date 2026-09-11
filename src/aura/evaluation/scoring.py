"""Weighted scoring across the eight dimensions (docs/SCORING_ENGINE.md).

Default weights sum to 100. Callers may override any subset via
``weights=`` — the result is always renormalized to sum to 100 so a partial
override (e.g. only boosting Security for a banking workload) stays
well-defined.

A hard constraint failure must never be hidden by a high weighted score
(docs/IMPLEMENTATION_PHASES.md #6) — that is enforced in
:mod:`aura.evaluation.engine`, not here: this module only computes the
per-dimension 0-100 values and the weighted blend.
"""

from __future__ import annotations

from pydantic import BaseModel

from aura.architecture.generator import Candidate
from aura.cost.model import CostEstimate
from aura.domain.enums import CostScenario, RuleStatus, ScoringDimension
from aura.evaluation.rules import RuleResult
from aura.failure.simulator import CandidateFailureReport
from aura.requirements.normalizer import NormalizedRequirements

DEFAULT_WEIGHTS: dict[ScoringDimension, float] = {
    ScoringDimension.RELIABILITY: 25,
    ScoringDimension.SCALABILITY: 20,
    ScoringDimension.SECURITY: 15,
    ScoringDimension.PERFORMANCE: 10,
    ScoringDimension.OPERATIONS: 10,
    ScoringDimension.COST: 10,
    ScoringDimension.COMPLEXITY: 5,
    ScoringDimension.SUSTAINABILITY: 5,
}

_SCENARIO_PENALTY = {RuleStatus.PASS: 0, RuleStatus.WARN: 5, RuleStatus.FAIL: 15, RuleStatus.NOT_EVALUATED: 0}
_BLAST_RADIUS_PENALTY = {"LOW": 0, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 20}
_COMPLEXITY_TAGS = {"operational_complexity", "data_consistency_complexity"}
_MODERATE_COMPLEXITY_TAGS = {
    "eventual_consistency", "added_processing_latency", "secondary_region_underutilized",
    "moderate_idle_cost", "highest_cost", "higher_cost",
}


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _rule(rule_results: list[RuleResult], rule_id: str) -> RuleResult:
    return next(r for r in rule_results if r.rule_id == rule_id)


class DimensionScore(BaseModel):
    dimension: ScoringDimension
    value: float
    weight: float
    evidence: list[str]


def _reliability(failure_report: CandidateFailureReport, rule_results: list[RuleResult]) -> DimensionScore:
    score = 100.0
    for scenario in failure_report.scenarios:
        score -= _SCENARIO_PENALTY[scenario.rto_status]
        if scenario.rpo_status != RuleStatus.NOT_EVALUATED:
            score -= _SCENARIO_PENALTY[scenario.rpo_status] / 2
    score -= _BLAST_RADIUS_PENALTY[failure_report.worst_blast_radius.value]
    evidence = [
        f"worst blast radius: {failure_report.worst_blast_radius.value}",
        f"hard failures: {', '.join(failure_report.hard_failures) or 'none'}",
    ]
    return DimensionScore(dimension=ScoringDimension.RELIABILITY, value=_clamp(score), weight=0, evidence=evidence)


def _scalability(
    candidate: Candidate, failure_report: CandidateFailureReport, rule_results: list[RuleResult]
) -> DimensionScore:
    score = 100.0
    capacity = _rule(rule_results, "capacity.burst_ratio")
    score -= {"PASS": 0, "WARN": 15, "FAIL": 35, "NOT_EVALUATED": 0}[capacity.status.value]
    spike = next(s for s in failure_report.scenarios if s.event.type.value == "TRAFFIC_SPIKE")
    score -= _SCENARIO_PENALTY[spike.rto_status]
    evidence = [capacity.evidence, f"traffic-spike recovery: {spike.rto_status.value}"]
    return DimensionScore(dimension=ScoringDimension.SCALABILITY, value=_clamp(score), weight=0, evidence=evidence)


def _security(candidate: Candidate, normalized: NormalizedRequirements, rule_results: list[RuleResult]) -> DimensionScore:
    boundary = _rule(rule_results, "security.boundary")
    score = 100.0 if boundary.status == RuleStatus.PASS else 40.0
    score -= 3 * max(len(candidate.topology.regions) - 1, 0)
    if candidate.topology.component("cdn") is not None:
        score += 5
    evidence = [boundary.evidence]
    return DimensionScore(dimension=ScoringDimension.SECURITY, value=_clamp(score), weight=0, evidence=evidence)


def _performance(candidate: Candidate, normalized: NormalizedRequirements) -> DimensionScore:
    score = 80.0
    if candidate.multi_region and len(normalized.user_regions) > 1:
        score += 15
    if candidate.topology.component("cdn") is not None:
        score += 5
    evidence = [
        f"multi_region={candidate.multi_region}",
        f"declared user regions: {len(normalized.user_regions)}",
    ]
    return DimensionScore(dimension=ScoringDimension.PERFORMANCE, value=_clamp(score), weight=0, evidence=evidence)


def _operations(candidate: Candidate, rule_results: list[RuleResult]) -> DimensionScore:
    score = 100.0
    complexity_hits = [t for t in candidate.tradeoffs if t in _COMPLEXITY_TAGS]
    score -= 15 * len(complexity_hits)
    if candidate.multi_region:
        score -= 5
    deployment = _rule(rule_results, "deployment.rollback")
    score -= _SCENARIO_PENALTY[deployment.status]
    evidence = [f"complexity tradeoffs: {', '.join(complexity_hits) or 'none'}", deployment.evidence]
    return DimensionScore(dimension=ScoringDimension.OPERATIONS, value=_clamp(score), weight=0, evidence=evidence)


def _cost(cost_estimates: dict[str, CostEstimate], normalized: NormalizedRequirements) -> DimensionScore:
    observed = cost_estimates[CostScenario.PEAK_LOAD.value].total_monthly_usd
    budget = normalized.monthly_budget_usd.value
    ratio = observed / budget if budget else 1.0

    if ratio <= 0.5:
        score = 100.0
    elif ratio <= 1.0:
        score = 100.0 - (ratio - 0.5) * 80.0  # 100 -> 60
    elif ratio <= 1.5:
        score = 60.0 - (ratio - 1.0) * 80.0  # 60 -> 20
    else:
        score = max(0.0, 20.0 - (ratio - 1.5) * 40.0)

    evidence = [f"peak-load monthly cost ${observed:,.2f} is {ratio:.2f}x the ${budget:,.2f} budget"]
    return DimensionScore(dimension=ScoringDimension.COST, value=_clamp(score), weight=0, evidence=evidence)


def _complexity(candidate: Candidate) -> DimensionScore:
    score = 100.0
    hits = [t for t in candidate.tradeoffs if t in _COMPLEXITY_TAGS]
    moderate_hits = [t for t in candidate.tradeoffs if t in _MODERATE_COMPLEXITY_TAGS]
    score -= 15 * len(hits)
    score -= 5 * len(moderate_hits)
    if candidate.multi_region:
        score -= 10
    evidence = [f"tradeoffs: {', '.join(candidate.tradeoffs) or 'none'}"]
    return DimensionScore(dimension=ScoringDimension.COMPLEXITY, value=_clamp(score), weight=0, evidence=evidence)


def _sustainability(candidate: Candidate) -> DimensionScore:
    regions = len(candidate.topology.regions)
    score = 100.0 - 15 * max(regions - 1, 0)
    evidence = [f"footprint spans {regions} region(s)"]
    return DimensionScore(dimension=ScoringDimension.SUSTAINABILITY, value=_clamp(score), weight=0, evidence=evidence)


def compute_dimension_scores(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    rule_results: list[RuleResult],
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
    weights: dict[ScoringDimension, float] | None = None,
) -> list[DimensionScore]:
    resolved_weights = _normalize_weights(weights or DEFAULT_WEIGHTS)

    scores = {
        ScoringDimension.RELIABILITY: _reliability(failure_report, rule_results),
        ScoringDimension.SCALABILITY: _scalability(candidate, failure_report, rule_results),
        ScoringDimension.SECURITY: _security(candidate, normalized, rule_results),
        ScoringDimension.PERFORMANCE: _performance(candidate, normalized),
        ScoringDimension.OPERATIONS: _operations(candidate, rule_results),
        ScoringDimension.COST: _cost(cost_estimates, normalized),
        ScoringDimension.COMPLEXITY: _complexity(candidate),
        ScoringDimension.SUSTAINABILITY: _sustainability(candidate),
    }
    for dimension, score in scores.items():
        score.weight = resolved_weights[dimension]
    return [scores[d] for d in ScoringDimension]


def _normalize_weights(weights: dict[ScoringDimension, float]) -> dict[ScoringDimension, float]:
    merged = dict(DEFAULT_WEIGHTS)
    merged.update(weights)
    total = sum(merged.values())
    if total <= 0:
        raise ValueError("scoring weights must sum to a positive number")
    return {dimension: value / total * 100 for dimension, value in merged.items()}


def weighted_score(dimension_scores: list[DimensionScore]) -> float:
    return round(sum(s.value * s.weight / 100 for s in dimension_scores), 2)
