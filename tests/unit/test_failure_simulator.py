from __future__ import annotations

from aura.architecture.generator import generate_candidates
from aura.domain.enums import BlastRadius, FailureEventType, RuleStatus
from aura.domain.models import Workload
from aura.failure.simulator import simulate_candidate
from aura.requirements.normalizer import normalize


def _candidates(document):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    return generate_candidates(normalized), normalized


def _report_for(document, pattern_id):
    candidates, normalized = _candidates(document)
    candidate = next(c for c in candidates if c.id == pattern_id)
    return simulate_candidate(candidate, normalized)


def _scenario(report, event_type):
    return next(s for s in report.scenarios if s.event.type == event_type)


def test_single_region_survives_az_failure(workload_document):
    report = _report_for(workload_document, "single-region-multi-az")
    az = _scenario(report, FailureEventType.AZ_FAILURE)
    assert az.rto_status == RuleStatus.PASS
    assert az.affected_capabilities == []
    assert report.survives_az_failure is True


def test_single_region_hard_fails_region_failure(workload_document):
    report = _report_for(workload_document, "single-region-multi-az")
    region = _scenario(report, FailureEventType.REGION_FAILURE)
    assert region.expected_recovery_seconds is None
    assert region.rto_status == RuleStatus.FAIL
    assert region.blast_radius == BlastRadius.CRITICAL
    assert report.survives_region_failure is False
    assert "REGION_FAILURE" in report.hard_failures


def test_active_active_survives_region_failure(workload_document):
    report = _report_for(workload_document, "multi-region-active-active")
    region = _scenario(report, FailureEventType.REGION_FAILURE)
    assert region.expected_recovery_seconds is not None
    assert region.rto_status in (RuleStatus.PASS, RuleStatus.WARN)
    assert report.survives_region_failure is True


def test_database_failure_never_takes_down_multi_az_database(workload_document):
    for pattern_id in [
        "single-region-multi-az",
        "multi-region-active-passive",
        "multi-region-warm-standby",
        "multi-region-active-active",
        "event-driven-buffered",
    ]:
        report = _report_for(workload_document, pattern_id)
        db_result = _scenario(report, FailureEventType.DATABASE_FAILURE)
        assert "database" not in db_result.affected_components
        assert db_result.rpo_status == RuleStatus.PASS


def test_instance_failure_is_low_blast_radius_and_no_impact(workload_document):
    report = _report_for(workload_document, "single-region-multi-az")
    instance = _scenario(report, FailureEventType.INSTANCE_FAILURE)
    assert instance.blast_radius == BlastRadius.LOW
    assert instance.affected_capabilities == []


def test_dependency_failure_degrades_cache_without_taking_down_compute(workload_document):
    assert workload_document["application"]["stateful"] is True
    report = _report_for(workload_document, "single-region-multi-az")
    dependency = _scenario(report, FailureEventType.DEPENDENCY_FAILURE)
    assert dependency.affected_components == ["cache"]
    assert "compute" not in dependency.affected_components


def test_traffic_spike_absorbed_by_queue_in_event_driven_pattern(workload_document):
    report = _report_for(workload_document, "event-driven-buffered")
    spike = _scenario(report, FailureEventType.TRAFFIC_SPIKE)
    assert spike.expected_recovery_seconds == 0.0

    other_report = _report_for(workload_document, "single-region-multi-az")
    other_spike = _scenario(other_report, FailureEventType.TRAFFIC_SPIKE)
    assert other_spike.expected_recovery_seconds is not None
    assert other_spike.expected_recovery_seconds > 0.0


def test_bad_deployment_uses_declared_rollback_target(workload_document):
    assert workload_document["deployment"]["rollback_target_minutes"] == 5
    report = _report_for(workload_document, "single-region-multi-az")
    deployment = _scenario(report, FailureEventType.BAD_DEPLOYMENT)
    assert deployment.expected_recovery_seconds == 300.0


def test_network_degradation_flags_async_replication_risk(workload_document):
    report = _report_for(workload_document, "multi-region-active-passive")
    degradation = _scenario(report, FailureEventType.NETWORK_DEGRADATION)
    assert degradation.expected_data_loss_seconds is not None

    single_region_report = _report_for(workload_document, "single-region-multi-az")
    single_degradation = _scenario(single_region_report, FailureEventType.NETWORK_DEGRADATION)
    assert single_degradation.expected_data_loss_seconds is None


def test_all_scenarios_produce_eight_results(workload_document):
    report = _report_for(workload_document, "single-region-multi-az")
    assert len(report.scenarios) == 8
    assert {s.event.type for s in report.scenarios} == set(FailureEventType)
