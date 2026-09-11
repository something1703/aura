from __future__ import annotations

import copy

from aura.architecture.generator import generate_candidates
from aura.domain.enums import EligibilityStatus, RuleStatus
from aura.domain.models import Workload
from aura.evaluation.engine import evaluate_all, evaluate_candidate, select_recommendation
from aura.requirements.normalizer import normalize


def _evaluate(document):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidates = generate_candidates(normalized)
    return evaluate_all(candidates, normalized), normalized


def test_single_region_is_ineligible_when_regional_dr_required(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["regional_disaster_required"] = True
    scores, _ = _evaluate(doc)
    single_region = next(s for s in scores if s.candidate_id == "single-region-multi-az")
    assert single_region.eligibility == EligibilityStatus.INELIGIBLE
    assert single_region.weighted_score is None
    assert single_region.ineligibility_reasons


def test_eligible_candidate_beats_ineligible_regardless_of_raw_score(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["regional_disaster_required"] = True
    scores, _ = _evaluate(doc)
    eligible_indices = [i for i, s in enumerate(scores) if s.eligibility == EligibilityStatus.ELIGIBLE]
    ineligible_indices = [i for i, s in enumerate(scores) if s.eligibility == EligibilityStatus.INELIGIBLE]
    if eligible_indices and ineligible_indices:
        assert max(eligible_indices) < min(ineligible_indices)


def test_at_least_three_candidates_and_one_rejected(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["regional_disaster_required"] = True
    doc["availability"]["multi_az_required"] = True
    scores, _ = _evaluate(doc)
    eligible = [s for s in scores if s.eligibility == EligibilityStatus.ELIGIBLE]
    ineligible = [s for s in scores if s.eligibility == EligibilityStatus.INELIGIBLE]
    assert len(eligible) >= 3
    assert len(ineligible) >= 1


def test_select_recommendation_picks_top_eligible(workload_document):
    scores, _ = _evaluate(workload_document)
    recommendation = select_recommendation(scores)
    assert recommendation is not None
    assert recommendation.eligibility == EligibilityStatus.ELIGIBLE
    eligible_scores = [s.weighted_score for s in scores if s.eligibility == EligibilityStatus.ELIGIBLE]
    assert recommendation.weighted_score == max(eligible_scores)


def test_hard_budget_violation_makes_candidate_ineligible(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["budget"]["monthly_usd"] = 10
    doc["budget"]["hard_limit"] = True
    scores, _ = _evaluate(doc)
    assert all(s.eligibility == EligibilityStatus.INELIGIBLE for s in scores)
    for s in scores:
        budget_result = next(r for r in s.rule_results if r.rule_id == "budget.monthly")
        assert budget_result.status == RuleStatus.FAIL


def test_soft_budget_violation_keeps_candidate_eligible(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["budget"]["monthly_usd"] = 10
    doc["budget"]["hard_limit"] = False
    scores, _ = _evaluate(doc)
    assert any(s.eligibility == EligibilityStatus.ELIGIBLE for s in scores)


def test_encryption_missing_for_confidential_internet_facing_is_ineligible(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["security"]["encryption_at_rest"] = False
    scores, _ = _evaluate(doc)
    assert all(s.eligibility == EligibilityStatus.INELIGIBLE for s in scores)


def test_dimension_scores_sum_weights_to_100(workload_document):
    scores, _ = _evaluate(workload_document)
    total_weight = sum(d.weight for d in scores[0].dimension_scores)
    assert round(total_weight, 4) == 100.0


def test_custom_weights_are_applied(workload_document):
    from aura.domain.enums import ScoringDimension

    workload = Workload.model_validate(workload_document)
    normalized = normalize(workload, raw_document=workload_document)
    candidates = generate_candidates(normalized)
    candidate = candidates[0]

    default_score = evaluate_candidate(candidate, normalized)
    security_heavy_score = evaluate_candidate(candidate, normalized, weights={ScoringDimension.SECURITY: 90})
    default_security_weight = next(
        d.weight for d in default_score.dimension_scores if d.dimension == ScoringDimension.SECURITY
    )
    heavy_security_weight = next(
        d.weight for d in security_heavy_score.dimension_scores if d.dimension == ScoringDimension.SECURITY
    )
    assert heavy_security_weight > default_security_weight
