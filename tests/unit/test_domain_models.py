from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from aura.domain.models import Workload


def test_valid_workload_parses(workload_document):
    workload = Workload.model_validate(workload_document)
    assert workload.application.name == "checkout"
    assert workload.availability.target == 99.9
    assert workload.budget.monthly_usd == 5000.0


def test_rejects_empty_application_name(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["application"]["name"] = "   "
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_negative_rto(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["rto_minutes"] = -5
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_negative_rpo(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["rpo_minutes"] = -1
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_invalid_percentage_target(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["availability"]["target"] = "150%"
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_zero_percentage_target(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["availability"]["target"] = 0
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_peak_below_average(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["traffic"]["peak_rps"] = 10
    doc["traffic"]["average_rps"] = 100
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_impossible_budget_format(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["budget"]["monthly_usd"] = "a lot of money"
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_unknown_consistency_mode(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["consistency"]["orders"] = "sometimes"
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_rejects_unknown_top_level_field(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["unexpected_field"] = "oops"
    with pytest.raises(ValidationError):
        Workload.model_validate(doc)


def test_currency_shorthand_normalizes(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["budget"]["monthly_usd"] = "$15k"
    workload = Workload.model_validate(doc)
    assert workload.budget.monthly_usd == 15000.0


def test_duration_shorthand_normalizes(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["recovery"]["rto_minutes"] = "300s"
    workload = Workload.model_validate(doc)
    assert workload.recovery.rto_minutes == 5.0
