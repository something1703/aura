from __future__ import annotations

import copy

from aura.domain.models import Workload
from aura.requirements.normalizer import detect_conflicts, normalize


def test_normalize_retains_raw_and_parsed_values(workload_document):
    workload = Workload.model_validate(workload_document)
    normalized = normalize(workload, raw_document=workload_document)

    assert normalized.availability_target.raw == "99.9%"
    assert normalized.availability_target.value == 99.9
    assert normalized.rto_seconds.value == 600  # 10 minutes
    assert normalized.rto_seconds.raw == 10
    assert normalized.monthly_budget_usd.value == 5000.0


def test_normalize_without_raw_document_falls_back_to_value(workload_document):
    workload = Workload.model_validate(workload_document)
    normalized = normalize(workload)
    assert normalized.availability_target.raw == normalized.availability_target.value
    assert normalized.availability_target.source == "default"


def test_conflict_regional_recovery_without_multi_az(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["availability"]["multi_az_required"] = False
    doc["recovery"]["regional_disaster_required"] = True
    workload = Workload.model_validate(doc)
    conflicts = detect_conflicts(workload)
    assert any(c.id == "regional-recovery-without-multi-az" for c in conflicts)


def test_conflict_rollback_slower_than_rto(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["rto_minutes"] = 2
    doc["deployment"]["rollback_target_minutes"] = 10
    workload = Workload.model_validate(doc)
    conflicts = detect_conflicts(workload)
    assert any(c.id == "rollback-slower-than-rto" for c in conflicts)


def test_no_conflicts_for_consistent_workload(workload_document):
    workload = Workload.model_validate(workload_document)
    assert detect_conflicts(workload) == []


def test_confidence_drops_with_low_confidence_assumptions(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["assumptions"] = [
        {"id": "a1", "statement": "traffic may spike", "confidence": 0.5},
    ]
    workload = Workload.model_validate(doc)
    normalized = normalize(workload, raw_document=doc)
    assert normalized.confidence == 0.5


def test_confidence_defaults_to_one_with_no_assumptions_or_conflicts(workload_document):
    workload = Workload.model_validate(workload_document)
    normalized = normalize(workload, raw_document=workload_document)
    assert normalized.confidence == 1.0
