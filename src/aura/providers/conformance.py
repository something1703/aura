"""Desired-vs-observed comparison (docs/IMPLEMENTATION_PHASES.md Phase 2).

Two comparisons are supported:

- :func:`compare_candidate_to_observed` — AURA's recommended architecture
  (from the Phase 1 engines) vs. real AWS state. This is the
  ``aura validate-deployed`` architecture-conformance gate.
- :func:`compare_terraform_to_observed` — a Terraform plan's declared
  resources vs. real AWS state. This is plain drift detection, independent
  of any AURA workload.

Both reuse :class:`~aura.domain.enums.RuleStatus` so a conformance failure
reads exactly like an evaluation rule failure.
"""

from __future__ import annotations

from aura.architecture.generator import Candidate
from aura.domain.enums import RuleStatus
from aura.providers.models import AwsInventory, ConformanceCheck, ConformanceReport, DesiredState
from aura.requirements.normalizer import NormalizedRequirements

_TERRAFORM_TYPE_TO_KIND = {
    "aws_instance": "compute",
    "aws_db_instance": "database",
    "aws_lb": "load_balancer",
    "aws_elasticache_cluster": "cache",
}


def _status(ok: bool) -> RuleStatus:
    return RuleStatus.PASS if ok else RuleStatus.FAIL


def compare_candidate_to_observed(
    candidate: Candidate, normalized: NormalizedRequirements, inventory: AwsInventory
) -> ConformanceReport:
    checks: list[ConformanceCheck] = []

    compute_observed = inventory.of_kind("compute")
    database_observed = inventory.of_kind("database")
    lb_observed = inventory.of_kind("load_balancer")

    compute = candidate.topology.component("compute")
    expected_az_count = len({i.az for i in compute.instances if i.region == candidate.primary_region})
    observed_azs = {r.az for r in compute_observed + database_observed if r.az}
    for lb in lb_observed:
        observed_azs.update(lb.attributes.get("availability_zones", []))
    checks.append(
        ConformanceCheck(
            check_id="availability_zones.count",
            description="Number of distinct Availability Zones actually in use",
            expected=expected_az_count,
            observed=len(observed_azs),
            status=_status(len(observed_azs) >= expected_az_count),
        )
    )

    database = candidate.topology.component("database")
    expected_multi_az = database.is_multi_az() if database else False
    observed_multi_az = any(r.attributes.get("multi_az") for r in database_observed)
    checks.append(
        ConformanceCheck(
            check_id="database.multi_az",
            description="RDS Multi-AZ failover enabled",
            expected=expected_multi_az,
            observed=observed_multi_az,
            status=_status(observed_multi_az or not expected_multi_az),
        )
    )

    observed_encrypted = (
        all(r.attributes.get("storage_encrypted") for r in database_observed) if database_observed else False
    )
    checks.append(
        ConformanceCheck(
            check_id="database.encrypted",
            description="Database storage encryption at rest",
            expected=normalized.encryption_at_rest,
            observed=observed_encrypted,
            status=_status(observed_encrypted or not normalized.encryption_at_rest),
        )
    )

    checks.append(
        ConformanceCheck(
            check_id="compute.presence",
            description="Compute resources actually deployed",
            expected=">0",
            observed=len(compute_observed),
            status=_status(len(compute_observed) > 0),
        )
    )

    return ConformanceReport(checks=checks)


def compare_terraform_to_observed(desired: DesiredState, inventory: AwsInventory) -> ConformanceReport:
    checks: list[ConformanceCheck] = []
    for terraform_type, kind in _TERRAFORM_TYPE_TO_KIND.items():
        expected_count = len(desired.of_type(terraform_type))
        observed_count = len(inventory.of_kind(kind))
        if expected_count == 0 and observed_count == 0:
            continue
        checks.append(
            ConformanceCheck(
                check_id=f"drift.{kind}.count",
                description=f"Terraform-declared vs. observed {kind} resource count",
                expected=expected_count,
                observed=observed_count,
                status=_status(expected_count == observed_count),
            )
        )
    return ConformanceReport(checks=checks)
