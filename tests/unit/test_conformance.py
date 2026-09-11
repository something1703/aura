from __future__ import annotations

from aura.architecture.generator import generate_candidates
from aura.domain.enums import RuleStatus
from aura.domain.models import Workload
from aura.providers.conformance import compare_candidate_to_observed, compare_terraform_to_observed
from aura.providers.models import AwsInventory, DesiredState, ObservedResource, TerraformResourceChange
from aura.requirements.normalizer import normalize


def _single_region_candidate(document):
    workload = Workload.model_validate(document)
    normalized = normalize(workload, raw_document=document)
    candidate = next(c for c in generate_candidates(normalized) if c.id == "single-region-multi-az")
    return candidate, normalized


def test_matching_deployment_passes_all_checks(workload_document):
    candidate, normalized = _single_region_candidate(workload_document)
    inventory = AwsInventory(
        region="ap-south-1",
        availability_zones=["ap-south-1a", "ap-south-1b", "ap-south-1c"],
        resources=[
            ObservedResource(kind="compute", id="i-1", region="ap-south-1", az="ap-south-1a"),
            ObservedResource(kind="compute", id="i-2", region="ap-south-1", az="ap-south-1b"),
            ObservedResource(kind="compute", id="i-3", region="ap-south-1", az="ap-south-1c"),
            ObservedResource(
                kind="database",
                id="db-1",
                region="ap-south-1",
                az="ap-south-1a",
                attributes={"multi_az": True, "storage_encrypted": True},
            ),
        ],
    )
    report = compare_candidate_to_observed(candidate, normalized, inventory)
    assert report.passed
    assert all(c.status == RuleStatus.PASS for c in report.checks)


def test_fewer_observed_azs_fails_conformance(workload_document):
    candidate, normalized = _single_region_candidate(workload_document)
    inventory = AwsInventory(
        region="ap-south-1",
        availability_zones=["ap-south-1a", "ap-south-1b"],
        resources=[
            ObservedResource(kind="compute", id="i-1", region="ap-south-1", az="ap-south-1a"),
            ObservedResource(kind="compute", id="i-2", region="ap-south-1", az="ap-south-1b"),
            ObservedResource(
                kind="database",
                id="db-1",
                region="ap-south-1",
                az="ap-south-1a",
                attributes={"multi_az": True, "storage_encrypted": True},
            ),
        ],
    )
    report = compare_candidate_to_observed(candidate, normalized, inventory)
    az_check = next(c for c in report.checks if c.check_id == "availability_zones.count")
    assert az_check.status == RuleStatus.FAIL
    assert not report.passed


def test_unencrypted_database_fails_when_encryption_required(workload_document):
    candidate, normalized = _single_region_candidate(workload_document)
    assert normalized.encryption_at_rest is True
    inventory = AwsInventory(
        region="ap-south-1",
        availability_zones=["ap-south-1a", "ap-south-1b", "ap-south-1c"],
        resources=[
            ObservedResource(kind="compute", id="i-1", region="ap-south-1", az="ap-south-1a"),
            ObservedResource(
                kind="database",
                id="db-1",
                region="ap-south-1",
                az="ap-south-1a",
                attributes={"multi_az": True, "storage_encrypted": False},
            ),
        ],
    )
    report = compare_candidate_to_observed(candidate, normalized, inventory)
    encryption_check = next(c for c in report.checks if c.check_id == "database.encrypted")
    assert encryption_check.status == RuleStatus.FAIL


def test_no_deployed_resources_fails_presence_check(workload_document):
    candidate, normalized = _single_region_candidate(workload_document)
    inventory = AwsInventory(region="ap-south-1", availability_zones=[], resources=[])
    report = compare_candidate_to_observed(candidate, normalized, inventory)
    presence_check = next(c for c in report.checks if c.check_id == "compute.presence")
    assert presence_check.status == RuleStatus.FAIL
    assert not report.passed


def test_terraform_drift_matching_counts_passes():
    desired = DesiredState(
        resources=[
            TerraformResourceChange(address="aws_instance.a", type="aws_instance", name="a"),
            TerraformResourceChange(address="aws_instance.b", type="aws_instance", name="b"),
        ]
    )
    inventory = AwsInventory(
        region="ap-south-1",
        availability_zones=[],
        resources=[
            ObservedResource(kind="compute", id="i-1", region="ap-south-1"),
            ObservedResource(kind="compute", id="i-2", region="ap-south-1"),
        ],
    )
    report = compare_terraform_to_observed(desired, inventory)
    assert report.passed


def test_terraform_drift_mismatched_counts_fails():
    desired = DesiredState(
        resources=[
            TerraformResourceChange(address="aws_instance.a", type="aws_instance", name="a"),
            TerraformResourceChange(address="aws_instance.b", type="aws_instance", name="b"),
            TerraformResourceChange(address="aws_instance.c", type="aws_instance", name="c"),
        ]
    )
    inventory = AwsInventory(
        region="ap-south-1",
        availability_zones=[],
        resources=[ObservedResource(kind="compute", id="i-1", region="ap-south-1")],
    )
    report = compare_terraform_to_observed(desired, inventory)
    assert not report.passed
    compute_check = next(c for c in report.checks if c.check_id == "drift.compute.count")
    assert compute_check.expected == 3
    assert compute_check.observed == 1
