"""Evaluation orchestration: rules + failure + cost -> eligibility + score.

Runs the AGENT_ORCHESTRATOR.md sequence per candidate (failure analysis,
then cost analysis, then rules) and enforces the one rule that must never be
bent: a mandatory rule FAIL makes the candidate INELIGIBLE regardless of how
high its weighted score would otherwise be (docs/SCORING_ENGINE.md).
"""

from __future__ import annotations

from pydantic import BaseModel

from aura.architecture.generator import Candidate
from aura.cost.estimates import estimate_candidate_all_scenarios
from aura.cost.model import CostEstimate
from aura.domain.enums import CostConfidence, CostScenario, EligibilityStatus, RuleStatus, ScoringDimension
from aura.evaluation.rules import RuleResult, evaluate_rules
from aura.evaluation.scoring import DimensionScore, compute_dimension_scores, weighted_score
from aura.failure.simulator import CandidateFailureReport, simulate_candidate
from aura.requirements.normalizer import NormalizedRequirements

_COST_CONFIDENCE_VALUE = {CostConfidence.LOW: 0.5, CostConfidence.MEDIUM: 0.75, CostConfidence.HIGH: 1.0}
_NO_LIVE_AWS_VALIDATION_VALUE = 0.7  # Phase 1 has no AWS/Terraform integration yet

# Weighted blend, not a product: docs/SCORING_ENGINE.md treats ~0.55 confidence as a normal,
# not alarming, outcome for an assumption-laden workload. Multiplying several independent
# 0.5-0.95 factors together collapses everything toward zero; a weighted average of the same
# signals stays legible while still moving when any one input is weak.
_REQUIREMENTS_CONFIDENCE_WEIGHT = 0.5
_COST_CONFIDENCE_WEIGHT = 0.2
_FAILURE_CONFIDENCE_WEIGHT = 0.2
_AWS_VALIDATION_WEIGHT = 0.1


class CandidateScore(BaseModel):
    candidate_id: str
    eligibility: EligibilityStatus
    ineligibility_reasons: list[str]
    rule_results: list[RuleResult]
    dimension_scores: list[DimensionScore]
    weighted_score: float | None
    confidence: float
    failure_report: CandidateFailureReport
    cost_estimates: dict[str, CostEstimate]


def _confidence(
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimate: CostEstimate,
) -> float:
    cost_confidence = _COST_CONFIDENCE_VALUE[cost_estimate.confidence]
    failure_confidence = (
        sum(s.confidence for s in failure_report.scenarios) / len(failure_report.scenarios)
        if failure_report.scenarios
        else 0.5
    )
    confidence = (
        _REQUIREMENTS_CONFIDENCE_WEIGHT * normalized.confidence
        + _COST_CONFIDENCE_WEIGHT * cost_confidence
        + _FAILURE_CONFIDENCE_WEIGHT * failure_confidence
        + _AWS_VALIDATION_WEIGHT * _NO_LIVE_AWS_VALIDATION_VALUE
    )
    return round(max(0.0, min(1.0, confidence)), 4)


def evaluate_candidate(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    weights: dict[ScoringDimension, float] | None = None,
) -> CandidateScore:
    failure_report = simulate_candidate(candidate, normalized)
    cost_estimates = estimate_candidate_all_scenarios(candidate, normalized)
    rule_results = evaluate_rules(candidate, normalized, failure_report, cost_estimates)

    failed_mandatory = [r for r in rule_results if r.mandatory and r.status == RuleStatus.FAIL]
    eligibility = EligibilityStatus.INELIGIBLE if failed_mandatory else EligibilityStatus.ELIGIBLE

    dimension_scores = compute_dimension_scores(
        candidate, normalized, rule_results, failure_report, cost_estimates, weights=weights
    )
    score = weighted_score(dimension_scores) if eligibility == EligibilityStatus.ELIGIBLE else None
    confidence = _confidence(normalized, failure_report, cost_estimates[CostScenario.PEAK_LOAD.value])

    return CandidateScore(
        candidate_id=candidate.id,
        eligibility=eligibility,
        ineligibility_reasons=[r.evidence for r in failed_mandatory],
        rule_results=rule_results,
        dimension_scores=dimension_scores,
        weighted_score=score,
        confidence=confidence,
        failure_report=failure_report,
        cost_estimates=cost_estimates,
    )


def evaluate_all(
    candidates: list[Candidate],
    normalized: NormalizedRequirements,
    weights: dict[ScoringDimension, float] | None = None,
) -> list[CandidateScore]:
    scores = [evaluate_candidate(candidate, normalized, weights=weights) for candidate in candidates]
    return sorted(
        scores,
        key=lambda s: (
            0 if s.eligibility == EligibilityStatus.ELIGIBLE else 1,
            -(s.weighted_score or 0.0),
        ),
    )


def select_recommendation(scores: list[CandidateScore]) -> CandidateScore | None:
    eligible = [s for s in scores if s.eligibility == EligibilityStatus.ELIGIBLE]
    return eligible[0] if eligible else None
