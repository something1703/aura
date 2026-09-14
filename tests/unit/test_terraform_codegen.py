from __future__ import annotations

from aura.architecture.generator import generate_candidates
from aura.domain.models import Workload
from aura.reporting.terraform_codegen import build_terraform_context, generate_terraform_files
from aura.requirements.normalizer import normalize


def _candidate(document, pattern_id):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidates = generate_candidates(normalized)
    return next(c for c in candidates if c.id == pattern_id), normalized


def test_multi_region_context_has_secondary_fields(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-warm-standby")
    ctx = build_terraform_context(candidate, normalized)

    assert ctx["is_multi_region"] is True
    assert ctx["secondary_region"] == candidate.secondary_region
    assert ctx["has_cache"] is True
    assert ctx["has_queue"] is False
    # warm-standby: AURA places no compute in the secondary at full parity,
    # only a fraction of the primary's AZ count.
    assert 0 < ctx["secondary_desired_count"] < ctx["primary_desired_count"]


def test_single_region_context_has_no_secondary(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    ctx = build_terraform_context(candidate, normalized)

    assert ctx["is_multi_region"] is False
    assert ctx["secondary_region"] is None
    assert ctx["secondary_desired_count"] == 0
    assert ctx["has_cache"] is True


def test_active_passive_has_zero_secondary_compute(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-active-passive")
    ctx = build_terraform_context(candidate, normalized)

    assert ctx["is_multi_region"] is True
    # AURA's own topology places no compute in the passive secondary.
    assert ctx["secondary_desired_count"] == 0


def test_active_active_has_full_parity_secondary_compute(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-active-active")
    ctx = build_terraform_context(candidate, normalized)

    assert ctx["secondary_desired_count"] == ctx["primary_desired_count"]
    assert ctx["has_secondary_cache"] is True


def test_event_driven_context_has_queue_and_no_region(workload_document):
    candidate, normalized = _candidate(workload_document, "event-driven-buffered")
    ctx = build_terraform_context(candidate, normalized)

    assert ctx["has_queue"] is True
    assert ctx["is_multi_region"] is False


def test_desired_count_derived_from_peak_rps(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    ctx = build_terraform_context(candidate, normalized)

    from aura.cost.estimates import RPS_PER_TASK

    expected = -(-int(normalized.peak_rps.value) // int(RPS_PER_TASK))  # ceil division
    assert ctx["primary_desired_count"] == expected


def test_generate_terraform_files_returns_four_files(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    files = generate_terraform_files(candidate, normalized)

    assert set(files.keys()) == {"providers.tf", "variables.tf", "main.tf", "outputs.tf"}
    for content in files.values():
        assert content.strip()


def test_single_region_main_tf_has_no_secondary_modules(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    files = generate_terraform_files(candidate, normalized)

    assert 'module "network_secondary"' not in files["main.tf"]
    assert 'module "database_secondary"' not in files["main.tf"]
    assert "aws_kms_key" not in files["main.tf"]
    assert 'module "network_primary"' in files["main.tf"]


def test_multi_region_main_tf_has_secondary_modules_and_kms_key(workload_document):
    candidate, normalized = _candidate(workload_document, "multi-region-warm-standby")
    files = generate_terraform_files(candidate, normalized)

    assert 'module "network_secondary"' in files["main.tf"]
    assert 'module "database_secondary"' in files["main.tf"]
    assert "aws_kms_key" in files["main.tf"]


def test_event_driven_main_tf_wires_queue_into_compute(workload_document):
    candidate, normalized = _candidate(workload_document, "event-driven-buffered")
    files = generate_terraform_files(candidate, normalized)

    assert 'module "queue"' in files["main.tf"]
    assert "has_sqs_queue" in files["main.tf"]
    assert "sqs_queue_arn" in files["main.tf"]


def test_non_stateful_workload_has_no_cache_module(workload_document):
    import copy

    doc = copy.deepcopy(workload_document)
    doc["application"]["stateful"] = False
    candidate, normalized = _candidate(doc, "single-region-multi-az")
    files = generate_terraform_files(candidate, normalized)

    assert 'module "cache_primary"' not in files["main.tf"]
    assert "cache_endpoint" not in files["outputs.tf"]


def test_variables_tf_declares_desired_count_defaults(workload_document):
    candidate, normalized = _candidate(workload_document, "single-region-multi-az")
    ctx = build_terraform_context(candidate, normalized)
    files = generate_terraform_files(candidate, normalized)

    assert f"default = {ctx['primary_desired_count']}" in files["variables.tf"]
