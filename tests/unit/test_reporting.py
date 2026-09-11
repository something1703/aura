from __future__ import annotations

import copy

from aura.architecture.generator import generate_candidates
from aura.domain.models import Workload
from aura.evaluation.engine import evaluate_all
from aura.reporting.adr import generate_adrs
from aura.reporting.context import build_context
from aura.reporting.diagram import to_mermaid
from aura.reporting.markdown import render_report
from aura.requirements.normalizer import normalize


def _context(document, generated_at="2026-01-01T00:00:00+00:00"):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidates = generate_candidates(normalized)
    scores = evaluate_all(candidates, normalized)
    return build_context(workload, normalized, candidates, scores, generated_at=generated_at)


def test_report_renders_recommendation_section(workload_document):
    ctx = _context(workload_document)
    report = render_report(ctx)
    assert "# AURA Architecture Report" in report
    assert "## 1. Executive Recommendation" in report
    assert "```mermaid" in report
    if ctx.recommendation:
        assert ctx.recommended_candidate.name in report


def test_report_is_deterministic(workload_document):
    ctx1 = _context(workload_document)
    ctx2 = _context(workload_document)
    assert render_report(ctx1) == render_report(ctx2)


def test_report_handles_no_eligible_candidate(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["availability"]["target"] = "99.999%"
    ctx = _context(doc)
    assert ctx.recommendation is None
    report = render_report(ctx)
    assert "No eligible candidate" in report


def test_generate_adrs_produces_six_documents(workload_document):
    ctx = _context(workload_document)
    documents = generate_adrs(ctx)
    assert len(documents) == 6
    assert all(name.startswith("ADR-000") for name in documents)
    for content in documents.values():
        assert "## Status" in content
        assert "## Decision" in content
        assert "## Consequences" in content


def test_generate_adrs_empty_when_no_recommendation(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["availability"]["target"] = "99.999%"
    ctx = _context(doc)
    assert generate_adrs(ctx) == {}


def test_to_mermaid_includes_all_components(workload_document):
    workload = Workload.model_validate(workload_document)
    normalized = normalize(workload, raw_document=workload_document)
    candidate = generate_candidates(normalized)[0]
    diagram = to_mermaid(candidate.topology)
    assert diagram.startswith("flowchart LR")
    for component in candidate.topology.components:
        assert component.id.replace("-", "_") in diagram
