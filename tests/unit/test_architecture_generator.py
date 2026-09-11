from __future__ import annotations

import copy

import pytest

from aura.architecture.catalog import CATALOG
from aura.architecture.generator import choose_secondary_region, generate_candidates
from aura.domain.models import Workload
from aura.requirements.normalizer import normalize


def _normalized(document):
    workload = Workload.model_validate(document)
    return normalize(workload, raw_document=document)


def test_generates_one_candidate_per_pattern(workload_document):
    candidates = generate_candidates(_normalized(workload_document))
    assert [c.id for c in candidates] == [p.id for p in CATALOG]


def test_single_region_pattern_has_no_secondary(workload_document):
    candidates = generate_candidates(_normalized(workload_document))
    single_region = next(c for c in candidates if c.id == "single-region-multi-az")
    assert single_region.secondary_region is None
    assert single_region.topology.regions == {"ap-south-1"}


def test_multi_region_patterns_get_assumed_secondary_when_only_one_declared(workload_document):
    assert workload_document["geography"]["primary_regions"] == ["ap-south-1"]
    candidates = generate_candidates(_normalized(workload_document))
    active_passive = next(c for c in candidates if c.id == "multi-region-active-passive")
    assert active_passive.secondary_region == "ap-southeast-1"
    assert active_passive.secondary_region_assumed is True
    assert "ap-southeast-1" in active_passive.topology.regions


def test_explicit_second_region_is_not_assumed(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["geography"]["primary_regions"] = ["ap-south-1", "eu-west-1"]
    secondary = choose_secondary_region(_normalized(doc))
    assert secondary.region == "eu-west-1"
    assert secondary.assumed is False


def test_stateful_workload_gets_cache_component(workload_document):
    assert workload_document["application"]["stateful"] is True
    candidates = generate_candidates(_normalized(workload_document))
    for candidate in candidates:
        assert candidate.topology.component("cache") is not None


def test_stateless_workload_has_no_cache_component(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["application"]["stateful"] = False
    candidates = generate_candidates(_normalized(doc))
    for candidate in candidates:
        assert candidate.topology.component("cache") is None


def test_internet_facing_ecommerce_gets_cdn(workload_document):
    candidates = generate_candidates(_normalized(workload_document))
    for candidate in candidates:
        assert candidate.topology.component("cdn") is not None


def test_internal_tool_has_no_cdn(workload_document):
    doc = copy.deepcopy(workload_document)
    doc["application"]["type"] = "internal_tool"
    doc["security"]["internet_facing"] = False
    candidates = generate_candidates(_normalized(doc))
    for candidate in candidates:
        assert candidate.topology.component("cdn") is None


def test_event_driven_pattern_has_queue(workload_document):
    candidates = generate_candidates(_normalized(workload_document))
    event_driven = next(c for c in candidates if c.id == "event-driven-buffered")
    assert event_driven.topology.component("queue") is not None
    compute = event_driven.topology.component("compute")
    assert "queue" in compute.depends_on


def test_active_active_flags_strong_consistency_limitation(workload_document):
    assert workload_document["consistency"]["orders"] == "strong"
    candidates = generate_candidates(_normalized(workload_document))
    active_active = next(c for c in candidates if c.id == "multi-region-active-active")
    assert any("orders" in limitation for limitation in active_active.known_limitations)


def test_compute_depends_on_database_critically(workload_document):
    candidates = generate_candidates(_normalized(workload_document))
    for candidate in candidates:
        compute = candidate.topology.component("compute")
        assert "database" in compute.depends_on
        assert compute.is_dependency_critical("database") is True


@pytest.mark.parametrize("pattern_id", [p.id for p in CATALOG])
def test_every_candidate_has_multi_az_compute_in_primary_region(workload_document, pattern_id):
    candidates = generate_candidates(_normalized(workload_document))
    candidate = next(c for c in candidates if c.id == pattern_id)
    compute = candidate.topology.component("compute")
    primary_instances = compute.instances_in(region=candidate.primary_region)
    assert len({i.az for i in primary_instances}) >= 2
