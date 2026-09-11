"""Normalize a validated :class:`Workload` into canonical engineering requirements.

Per docs/REQUIREMENTS_ENGINE.md every requirement carries a VALUE, SOURCE,
CONFIDENCE, and MANDATORY/PREFERRED flag; per docs/IMPLEMENTATION_PHASES.md
the normalized model must retain the original user-supplied value (e.g. the
literal ``"$15k"`` alongside the parsed ``15000.0``) for reporting. This
module never invents missing values (AGENT_REQUIREMENTS.md): everything
either comes from the workload document or is an explicit default with
``source="default"``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from aura.domain.enums import ConsistencyMode, DataClassification, Severity
from aura.domain.models import Assumption, Workload

_MISSING = object()

_CONFLICT_CONFIDENCE_PENALTY = {
    Severity.CRITICAL: 0.25,
    Severity.HIGH: 0.15,
    Severity.MEDIUM: 0.08,
    Severity.LOW: 0.03,
    Severity.INFO: 0.0,
}


class Conflict(BaseModel):
    id: str
    statement: str
    severity: Severity


class NormalizedRequirement(BaseModel):
    value: Any
    raw: Any = None
    source: str = "user"
    confidence: float = 1.0
    mandatory: bool = True


class NormalizedRequirements(BaseModel):
    application_name: str
    application_type: str
    stateful: bool

    average_rps: NormalizedRequirement
    peak_rps: NormalizedRequirement
    peak_duration_seconds: NormalizedRequirement
    growth_percent_per_month: float

    availability_target: NormalizedRequirement
    multi_az_required: NormalizedRequirement

    rto_seconds: NormalizedRequirement
    rpo_seconds: NormalizedRequirement
    regional_disaster_required: NormalizedRequirement

    consistency: dict[str, ConsistencyMode]

    primary_regions: list[str]
    user_regions: list[str]

    monthly_budget_usd: NormalizedRequirement
    budget_hard_limit: bool

    deployment_frequency_per_day: float
    downtime_allowed: NormalizedRequirement
    rollback_target_seconds: NormalizedRequirement | None

    internet_facing: bool
    data_classification: DataClassification
    encryption_at_rest: bool
    encryption_in_transit: bool

    compliance_frameworks: list[str]

    assumptions: list[Assumption]
    conflicts: list[Conflict]
    confidence: float


def _raw_lookup(document: dict | None, *path: str) -> Any:
    if document is None:
        return _MISSING
    node: Any = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return _MISSING
        node = node[key]
    return node


def detect_conflicts(workload: Workload) -> list[Conflict]:
    """Report contradictory requirements instead of silently picking one.

    See docs/REQUIREMENTS_ENGINE.md "Contradiction detection".
    """

    conflicts: list[Conflict] = []

    if workload.recovery.regional_disaster_required and not workload.availability.multi_az_required:
        conflicts.append(
            Conflict(
                id="regional-recovery-without-multi-az",
                statement=(
                    "recovery.regional_disaster_required is true but "
                    "availability.multi_az_required is false; regional failover is "
                    "not credible without multi-AZ redundancy in the primary region."
                ),
                severity=Severity.HIGH,
            )
        )

    rollback = workload.deployment.rollback_target_minutes
    if rollback is not None and rollback > workload.recovery.rto_minutes:
        conflicts.append(
            Conflict(
                id="rollback-slower-than-rto",
                statement=(
                    f"deployment.rollback_target_minutes ({rollback}) exceeds "
                    f"recovery.rto_minutes ({workload.recovery.rto_minutes}); a bad "
                    "deployment could not be rolled back within the recovery objective."
                ),
                severity=Severity.MEDIUM,
            )
        )

    if workload.recovery.rto_minutes <= 1 and not workload.deployment.downtime_allowed:
        conflicts.append(
            Conflict(
                id="aggressive-rto-with-zero-downtime",
                statement=(
                    f"recovery.rto_minutes ({workload.recovery.rto_minutes}) is at or "
                    "below 1 minute with deployment.downtime_allowed=false; this is only "
                    "plausible with active-active or fully automated failover, which raises "
                    "cost and consistency complexity."
                ),
                severity=Severity.LOW,
            )
        )

    if (
        workload.budget.hard_limit
        and workload.recovery.regional_disaster_required
        and workload.budget.monthly_usd < 1000
    ):
        conflicts.append(
            Conflict(
                id="hard-low-budget-with-regional-dr",
                statement=(
                    f"budget.hard_limit is true with monthly_usd="
                    f"{workload.budget.monthly_usd} while regional disaster recovery is "
                    "required; cross-region infrastructure duplication is unlikely to fit "
                    "this budget."
                ),
                severity=Severity.MEDIUM,
            )
        )

    return conflicts


def _compute_confidence(workload: Workload, conflicts: list[Conflict]) -> float:
    confidence = 1.0
    for assumption in workload.assumptions:
        confidence *= assumption.confidence
    for conflict in conflicts:
        confidence -= _CONFLICT_CONFIDENCE_PENALTY.get(conflict.severity, 0.0)
    return round(max(0.0, min(1.0, confidence)), 4)


def normalize(workload: Workload, raw_document: dict | None = None) -> NormalizedRequirements:
    """Produce the canonical :class:`NormalizedRequirements` document."""

    conflicts = detect_conflicts(workload)
    confidence = _compute_confidence(workload, conflicts)

    def requirement(value: Any, *raw_path: str, mandatory: bool = True) -> NormalizedRequirement:
        raw = _raw_lookup(raw_document, *raw_path) if raw_path else _MISSING
        return NormalizedRequirement(
            value=value,
            raw=value if raw is _MISSING else raw,
            source="default" if raw is _MISSING else "user",
            confidence=1.0,
            mandatory=mandatory,
        )

    rollback_seconds = None
    if workload.deployment.rollback_target_minutes is not None:
        rollback_seconds = requirement(
            workload.deployment.rollback_target_minutes * 60,
            "deployment",
            "rollback_target_minutes",
            mandatory=False,
        )

    return NormalizedRequirements(
        application_name=workload.application.name,
        application_type=workload.application.type.value,
        stateful=workload.application.stateful,
        average_rps=requirement(workload.traffic.average_rps, "traffic", "average_rps"),
        peak_rps=requirement(workload.traffic.peak_rps, "traffic", "peak_rps"),
        peak_duration_seconds=requirement(
            workload.traffic.peak_duration_minutes * 60,
            "traffic",
            "peak_duration_minutes",
            mandatory=False,
        ),
        growth_percent_per_month=workload.traffic.growth_percent_per_month,
        availability_target=requirement(workload.availability.target, "availability", "target"),
        multi_az_required=requirement(workload.availability.multi_az_required, "availability", "multi_az_required"),
        rto_seconds=requirement(workload.recovery.rto_minutes * 60, "recovery", "rto_minutes"),
        rpo_seconds=requirement(workload.recovery.rpo_minutes * 60, "recovery", "rpo_minutes"),
        regional_disaster_required=requirement(
            workload.recovery.regional_disaster_required,
            "recovery",
            "regional_disaster_required",
            mandatory=False,
        ),
        consistency=dict(workload.consistency),
        primary_regions=list(workload.geography.primary_regions),
        user_regions=list(workload.geography.user_regions),
        monthly_budget_usd=requirement(
            workload.budget.monthly_usd,
            "budget",
            "monthly_usd",
            mandatory=workload.budget.hard_limit,
        ),
        budget_hard_limit=workload.budget.hard_limit,
        deployment_frequency_per_day=workload.deployment.frequency_per_day,
        downtime_allowed=requirement(workload.deployment.downtime_allowed, "deployment", "downtime_allowed"),
        rollback_target_seconds=rollback_seconds,
        internet_facing=workload.security.internet_facing,
        data_classification=workload.security.data_classification,
        encryption_at_rest=workload.security.encryption_at_rest,
        encryption_in_transit=workload.security.encryption_in_transit,
        compliance_frameworks=list(workload.compliance.frameworks),
        assumptions=list(workload.assumptions),
        conflicts=conflicts,
        confidence=confidence,
    )
