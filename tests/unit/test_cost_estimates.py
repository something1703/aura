from __future__ import annotations

from aura.architecture.generator import generate_candidates
from aura.cost.estimates import estimate_candidate_all_scenarios, estimate_candidate_cost
from aura.domain.enums import CostConfidence, CostScenario
from aura.domain.models import Workload
from aura.requirements.normalizer import normalize


def _candidate(document, pattern_id):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidates = generate_candidates(normalized)
    return next(c for c in candidates if c.id == pattern_id), normalized


def test_returns_all_four_scenarios(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    estimates = estimate_candidate_all_scenarios(candidate, normalized)
    assert set(estimates.keys()) == {s.value for s in CostScenario}
    for estimate in estimates.values():
        assert estimate.total_monthly_usd > 0


def test_cost_increases_with_load(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    estimates = estimate_candidate_all_scenarios(candidate, normalized)
    average = estimates[CostScenario.AVERAGE_LOAD.value].total_monthly_usd
    peak = estimates[CostScenario.PEAK_LOAD.value].total_monthly_usd
    sustained = estimates[CostScenario.SUSTAINED_PEAK.value].total_monthly_usd
    assert average <= peak <= sustained


def test_single_region_failure_mode_equals_sustained_peak(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    sustained = estimate_candidate_cost(candidate, normalized, CostScenario.SUSTAINED_PEAK)
    failure = estimate_candidate_cost(candidate, normalized, CostScenario.FAILURE_MODE)
    assert failure.total_monthly_usd == sustained.total_monthly_usd


def test_active_passive_failure_mode_costs_more_than_sustained_peak(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-active-passive")
    sustained = estimate_candidate_cost(candidate, normalized, CostScenario.SUSTAINED_PEAK)
    failure = estimate_candidate_cost(candidate, normalized, CostScenario.FAILURE_MODE)
    assert failure.total_monthly_usd > sustained.total_monthly_usd
    assert any("Failover capacity" in item.service for item in failure.line_items)


def test_active_active_has_no_failover_scaleup_item(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-active-active")
    failure = estimate_candidate_cost(candidate, normalized, CostScenario.FAILURE_MODE)
    assert not any("Failover capacity" in item.service for item in failure.line_items)


def test_single_region_has_no_cross_region_transfer(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    estimate = estimate_candidate_cost(candidate, normalized, CostScenario.AVERAGE_LOAD)
    assert not any("Cross-region" in item.service for item in estimate.line_items)


def test_multi_region_has_cross_region_transfer(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-warm-standby")
    estimate = estimate_candidate_cost(candidate, normalized, CostScenario.AVERAGE_LOAD)
    assert any("Cross-region" in item.service for item in estimate.line_items)


def test_stateless_workload_has_no_cache_line_item(workload_document):
    import copy

    doc = copy.deepcopy(workload_document)
    doc["application"]["stateful"] = False
    candidate, normalized = _candidate(doc, "single-region-multi-az")
    estimate = estimate_candidate_cost(candidate, normalized, CostScenario.AVERAGE_LOAD)
    assert not any("Cache" in item.service for item in estimate.line_items)


def test_low_confidence_line_item_drags_down_overall_confidence(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    estimate = estimate_candidate_cost(candidate, normalized, CostScenario.AVERAGE_LOAD)
    assert any(item.confidence == CostConfidence.LOW for item in estimate.line_items)
    assert estimate.confidence == CostConfidence.LOW
