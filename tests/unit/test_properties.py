"""Property-style tests (docs/TESTING.md "Property tests").

Each test checks a monotonicity/invariant property rather than one fixed
input/output pair, so a future rule or scoring change that violates the
property fails loudly even if no example-based test happens to cover it.
"""

from __future__ import annotations

import copy

from aura.architecture.generator import generate_candidates
from aura.domain.enums import EligibilityStatus, RuleStatus, ScoringDimension
from aura.domain.models import Workload
from aura.evaluation.engine import evaluate_all
from aura.evaluation.rules import availability_rule
from aura.evaluation.scoring import DEFAULT_WEIGHTS, compute_dimension_scores
from aura.failure.simulator import evaluate_component_availability
from aura.requirements.normalizer import normalize


def _normalized(document):
    workload = Workload.model_validate(document)
    return normalize(workload, raw_document=document)


def test_increasing_required_availability_never_improves_rule_status(workload_document):
    doc_low = copy.deepcopy(workload_document)
    doc_low["availability"]["target"] = "90%"
    doc_high = copy.deepcopy(workload_document)
    doc_high["availability"]["target"] = "99.999%"

    normalized_low = _normalized(doc_low)
    normalized_high = _normalized(doc_high)
    candidate = generate_candidates(normalized_low)[0]

    result_low = availability_rule(candidate, normalized_low, None, {})
    result_high = availability_rule(candidate, normalized_high, None, {})

    order = {RuleStatus.PASS: 0, RuleStatus.WARN: 1, RuleStatus.FAIL: 2}
    assert order[result_high.status] >= order[result_low.status]


def test_lowering_budget_never_improves_cost_score(workload_document):
    doc_low_budget = copy.deepcopy(workload_document)
    doc_low_budget["budget"]["monthly_usd"] = 1000
    doc_high_budget = copy.deepcopy(workload_document)
    doc_high_budget["budget"]["monthly_usd"] = 100_000

    normalized_low = _normalized(doc_low_budget)
    normalized_high = _normalized(doc_high_budget)
    candidate = generate_candidates(normalized_low)[0]

    from aura.cost.estimates import estimate_candidate_all_scenarios
    from aura.evaluation.rules import evaluate_rules
    from aura.failure.simulator import simulate_candidate

    failure_report = simulate_candidate(candidate, normalized_low)
    cost_low = estimate_candidate_all_scenarios(candidate, normalized_low)
    cost_high = estimate_candidate_all_scenarios(candidate, normalized_high)
    rules_low = evaluate_rules(candidate, normalized_low, failure_report, cost_low)
    rules_high = evaluate_rules(candidate, normalized_high, failure_report, cost_high)

    scores_low = compute_dimension_scores(candidate, normalized_low, rules_low, failure_report, cost_low)
    scores_high = compute_dimension_scores(candidate, normalized_high, rules_high, failure_report, cost_high)

    cost_score_low = next(s.value for s in scores_low if s.dimension == ScoringDimension.COST)
    cost_score_high = next(s.value for s in scores_high if s.dimension == ScoringDimension.COST)

    assert cost_score_high >= cost_score_low


def test_removing_a_critical_dependency_edge_cannot_reduce_availability(workload_document):
    normalized = _normalized(workload_document)
    candidate = generate_candidates(normalized)[0]
    graph = candidate.topology

    non_critical_graph = graph.model_copy(deep=True)
    compute = non_critical_graph.component("compute")
    compute.critical_dependency["database"] = False

    failed_azs = frozenset({sorted(graph.component("database").azs)[0]})

    critical_result = evaluate_component_availability(graph, failed_azs=failed_azs)
    relaxed_result = evaluate_component_availability(non_critical_graph, failed_azs=failed_azs)

    for component_id in critical_result:
        assert relaxed_result[component_id] or not critical_result[component_id]


def test_mandatory_rule_failure_always_blocks_eligibility(workload_document):
    scenarios = []

    doc = copy.deepcopy(workload_document)
    doc["budget"]["monthly_usd"] = 1
    doc["budget"]["hard_limit"] = True
    scenarios.append(doc)

    doc = copy.deepcopy(workload_document)
    doc["security"]["encryption_in_transit"] = False
    scenarios.append(doc)

    doc = copy.deepcopy(workload_document)
    doc["availability"]["target"] = "99.9999%"
    scenarios.append(doc)

    for document in scenarios:
        normalized = _normalized(document)
        candidates = generate_candidates(normalized)
        scores = evaluate_all(candidates, normalized)
        for score in scores:
            has_mandatory_fail = any(r.mandatory and r.status == RuleStatus.FAIL for r in score.rule_results)
            if has_mandatory_fail:
                assert score.eligibility == EligibilityStatus.INELIGIBLE
                assert score.weighted_score is None


def test_default_weights_sum_to_100():
    assert sum(DEFAULT_WEIGHTS.values()) == 100
