"""Failure simulation: remove nodes, traverse dependencies, estimate recovery.

Implements the eight-step process from docs/FAILURE_MODEL.md:
detect affected nodes -> remove them -> traverse dependencies -> determine
impacted capabilities -> identify recovery mechanisms -> estimate recovery
envelope -> compare to RTO/RPO -> produce a recommendation.

Every result is tagged ``MODELLED`` (docs/FAILURE_MODEL.md evidence
policy): this is graph/rule reasoning, not a controlled test or a
production measurement.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aura.architecture.generator import Candidate
from aura.domain.enums import BlastRadius, EvidenceType, FailureEventType, RuleStatus
from aura.domain.graph import Graph
from aura.failure.blast_radius import classify
from aura.failure.scenarios import (
    BusinessCapability,
    FailureEvent,
    build_failure_events,
    capabilities_for,
)
from aura.requirements.normalizer import NormalizedRequirements

_BLAST_RADIUS_ORDER = [BlastRadius.LOW, BlastRadius.MEDIUM, BlastRadius.HIGH, BlastRadius.CRITICAL]
_DEFAULT_BAD_DEPLOYMENT_ROLLBACK_SECONDS = 300.0
_MULTI_AZ_FAILOVER_SECONDS = 90.0
_INSTANCE_REPLACEMENT_SECONDS = 30.0
_AUTOSCALE_REACTION_SECONDS = 120.0


def evaluate_component_availability(
    graph: Graph,
    *,
    failed_azs: frozenset[str] = frozenset(),
    failed_regions: frozenset[str] = frozenset(),
    failed_components: frozenset[str] = frozenset(),
) -> dict[str, bool]:
    """Physical survival (>=1 live instance) then critical-dependency propagation."""

    functional: dict[str, bool] = {}
    for component in graph.components:
        if component.id in failed_components:
            functional[component.id] = False
            continue
        alive = [
            instance
            for instance in component.instances
            if instance.region not in failed_regions and instance.az not in failed_azs
        ]
        functional[component.id] = len(alive) > 0

    changed = True
    while changed:
        changed = False
        for component in graph.components:
            if not functional[component.id]:
                continue
            for dependency_id in component.depends_on:
                if not component.is_dependency_critical(dependency_id):
                    continue
                if not functional.get(dependency_id, True):
                    functional[component.id] = False
                    changed = True
                    break
    return functional


def impacted_capabilities(
    capabilities: list[BusinessCapability], functional: dict[str, bool], graph: Graph
) -> list[BusinessCapability]:
    impacted = []
    for capability in capabilities:
        effective_deps = [dep for dep in capability.depends_on if graph.component(dep) is not None]
        if effective_deps and any(not functional.get(dep, True) for dep in effective_deps):
            impacted.append(capability)
    return impacted


class FailureScenarioResult(BaseModel):
    event: FailureEvent
    detection: str
    affected_components: list[str]
    affected_capabilities: list[str]
    recovery_action: str
    expected_recovery_seconds: float | None
    rto_required_seconds: float
    rto_status: RuleStatus
    expected_data_loss_seconds: float | None
    rpo_required_seconds: float
    rpo_status: RuleStatus
    blast_radius: BlastRadius
    confidence: float
    evidence: EvidenceType = EvidenceType.MODELLED
    notes: list[str] = Field(default_factory=list)


def _status_against(expected: float | None, required: float) -> RuleStatus:
    if expected is None:
        return RuleStatus.FAIL
    if expected <= required:
        return RuleStatus.PASS
    if expected <= required * 1.5:
        return RuleStatus.WARN
    return RuleStatus.FAIL


def _build_result(
    candidate: Candidate,
    event: FailureEvent,
    normalized: NormalizedRequirements,
    *,
    detection: str,
    recovery_action: str,
    expected_recovery_seconds: float | None,
    expected_data_loss_seconds: float | None,
    failed_azs: frozenset[str] = frozenset(),
    failed_regions: frozenset[str] = frozenset(),
    failed_components: frozenset[str] = frozenset(),
    confidence: float = 0.7,
    notes: list[str] | None = None,
) -> FailureScenarioResult:
    graph = candidate.topology
    functional = evaluate_component_availability(
        graph, failed_azs=failed_azs, failed_regions=failed_regions, failed_components=failed_components
    )
    affected_components = sorted(cid for cid, up in functional.items() if not up)
    capabilities = capabilities_for(normalized.application_type)
    impacted = impacted_capabilities(capabilities, functional, graph)

    rto_required = normalized.rto_seconds.value
    rpo_required = normalized.rpo_seconds.value
    rto_status = _status_against(expected_recovery_seconds, rto_required)
    rpo_status = (
        _status_against(expected_data_loss_seconds, rpo_required)
        if expected_data_loss_seconds is not None
        else RuleStatus.NOT_EVALUATED
    )

    return FailureScenarioResult(
        event=event,
        detection=detection,
        affected_components=affected_components,
        affected_capabilities=[c.id for c in impacted],
        recovery_action=recovery_action,
        expected_recovery_seconds=expected_recovery_seconds,
        rto_required_seconds=rto_required,
        rto_status=rto_status,
        expected_data_loss_seconds=expected_data_loss_seconds,
        rpo_required_seconds=rpo_required,
        rpo_status=rpo_status,
        blast_radius=classify(impacted),
        confidence=confidence,
        notes=notes or [],
    )


def _simulate_instance_failure(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Load balancer / orchestrator health checks",
        recovery_action="Automatic instance or task replacement by the compute orchestrator.",
        expected_recovery_seconds=_INSTANCE_REPLACEMENT_SECONDS,
        expected_data_loss_seconds=None,
        confidence=0.85,
    )


def _simulate_az_failure(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    database = candidate.topology.component("database")
    sync_replication = database is not None and database.replication in (None, "sync")
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Target group health checks and Multi-AZ database failover monitor",
        recovery_action=(
            "Traffic drains to the healthy AZ's targets; the database fails over to its standby in another AZ."
        ),
        expected_recovery_seconds=_MULTI_AZ_FAILOVER_SECONDS,
        expected_data_loss_seconds=0.0 if sync_replication else candidate.supports.rpo_max_seconds,
        failed_azs=frozenset({event.target_az}) if event.target_az else frozenset(),
        confidence=0.8,
    )


def _simulate_database_failure(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    database = candidate.topology.component("database")
    single_instance = database is None or len(database.instances) <= 1
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Database automated failover monitor",
        recovery_action=(
            "No standby instance exists; the database must be restored from backup."
            if single_instance
            else "Automated failover promotes the standby replica in another AZ to primary/writer."
        ),
        expected_recovery_seconds=None if single_instance else _MULTI_AZ_FAILOVER_SECONDS,
        expected_data_loss_seconds=None if single_instance else 0.0,
        failed_components=frozenset({"database"}) if single_instance else frozenset(),
        confidence=0.75,
        notes=["single database instance: no automated failover path"] if single_instance else [],
    )


def _simulate_network_degradation(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    database = candidate.topology.component("database")
    async_replication = database is not None and database.replication == "async"
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Elevated latency/error-rate alarms on cross-AZ or cross-region links",
        recovery_action=(
            "No topology change; degraded network conditions clear on their own or via provider mitigation."
        ),
        expected_recovery_seconds=0.0,
        expected_data_loss_seconds=candidate.supports.rpo_max_seconds if async_replication else None,
        confidence=0.5,
        notes=(
            ["asynchronous cross-region replication lag may widen toward the pattern's worst-case RPO"]
            if async_replication
            else []
        ),
    )


def _simulate_traffic_spike(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    queue = candidate.topology.component("queue")
    if queue is not None:
        return _build_result(
            candidate,
            event,
            normalized,
            detection="Queue depth / backlog age alarms",
            recovery_action="The durable queue absorbs the burst; workers drain the backlog as autoscaling catches up.",
            expected_recovery_seconds=0.0,
            expected_data_loss_seconds=None,
            confidence=0.7,
        )
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Autoscaling target-tracking alarms / elevated latency and error rate",
        recovery_action="Horizontal autoscale-out of the compute tier until capacity matches demand.",
        expected_recovery_seconds=_AUTOSCALE_REACTION_SECONDS,
        expected_data_loss_seconds=None,
        confidence=0.55,
        notes=["no buffering component: requests during the scale-out window may be throttled or dropped"],
    )


def _simulate_bad_deployment(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    rollback = normalized.rollback_target_seconds
    notes = []
    if rollback is None:
        recovery_seconds = _DEFAULT_BAD_DEPLOYMENT_ROLLBACK_SECONDS
        notes.append("no deployment.rollback_target_minutes declared; assumed 5-minute rollback")
    else:
        recovery_seconds = float(rollback.value)
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Deployment health checks / canary analysis",
        recovery_action="Automated rollback to the last known-good revision.",
        expected_recovery_seconds=recovery_seconds,
        expected_data_loss_seconds=None,
        confidence=0.6,
        notes=notes,
    )


def _simulate_dependency_failure(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    cache = candidate.topology.component("cache")
    if cache is None:
        return _build_result(
            candidate,
            event,
            normalized,
            detection="Application-level dependency health checks",
            recovery_action=(
                "Circuit breaker isolates the dependency; degraded-mode behavior is assumed but "
                "not modelled explicitly."
            ),
            expected_recovery_seconds=None,
            expected_data_loss_seconds=None,
            confidence=0.4,
            notes=["no explicit non-critical dependency component modelled for this workload"],
        )
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Application-level dependency health checks / circuit breaker",
        recovery_action=(
            "Circuit breaker isolates the cache; requests fall through to the database with degraded latency."
        ),
        expected_recovery_seconds=0.0,
        expected_data_loss_seconds=None,
        failed_components=frozenset({cache.id}),
        confidence=0.75,
        notes=["database load increases for the duration of the outage (cache-miss fallthrough)"],
    )


def _simulate_region_failure(candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements):
    if not candidate.regional_resilience:
        return _build_result(
            candidate,
            event,
            normalized,
            detection="Regional health checks",
            recovery_action="No secondary region exists: there is no automated or manual recovery path.",
            expected_recovery_seconds=None,
            expected_data_loss_seconds=None,
            failed_regions=frozenset({event.target_region}) if event.target_region else frozenset(),
            confidence=0.9,
            notes=["hard failure: pattern has no regional resilience"],
        )
    recovery_action = {
        "multi-region-active-passive": (
            "Promote the database in the secondary region and cut traffic over via DNS/global routing."
        ),
        "multi-region-warm-standby": (
            "Cut traffic over to the already-running warm standby region and scale it to full capacity."
        ),
        "multi-region-active-active": (
            "The global router removes the failed region from rotation; the healthy region continues serving."
        ),
    }.get(candidate.id, "Fail over to the secondary region.")
    return _build_result(
        candidate,
        event,
        normalized,
        detection="Regional health checks / global router failover",
        recovery_action=recovery_action,
        expected_recovery_seconds=candidate.supports.rto_max_seconds,
        expected_data_loss_seconds=candidate.supports.rpo_max_seconds,
        failed_regions=frozenset({event.target_region}) if event.target_region else frozenset(),
        confidence=0.6,
        notes=["assumes the secondary region's declared envelope; not load-tested"],
    )


_SIMULATORS = {
    FailureEventType.INSTANCE_FAILURE: _simulate_instance_failure,
    FailureEventType.AZ_FAILURE: _simulate_az_failure,
    FailureEventType.DATABASE_FAILURE: _simulate_database_failure,
    FailureEventType.NETWORK_DEGRADATION: _simulate_network_degradation,
    FailureEventType.TRAFFIC_SPIKE: _simulate_traffic_spike,
    FailureEventType.BAD_DEPLOYMENT: _simulate_bad_deployment,
    FailureEventType.DEPENDENCY_FAILURE: _simulate_dependency_failure,
    FailureEventType.REGION_FAILURE: _simulate_region_failure,
}


def simulate_failure_event(
    candidate: Candidate, event: FailureEvent, normalized: NormalizedRequirements
) -> FailureScenarioResult:
    return _SIMULATORS[event.type](candidate, event, normalized)


class CandidateFailureReport(BaseModel):
    candidate_id: str
    scenarios: list[FailureScenarioResult]
    worst_blast_radius: BlastRadius
    hard_failures: list[str]
    survives_az_failure: bool
    survives_region_failure: bool


def simulate_candidate(candidate: Candidate, normalized: NormalizedRequirements) -> CandidateFailureReport:
    events = build_failure_events(candidate)
    scenarios = [simulate_failure_event(candidate, event, normalized) for event in events]

    worst = max(
        (s.blast_radius for s in scenarios),
        key=lambda b: _BLAST_RADIUS_ORDER.index(b),
        default=BlastRadius.LOW,
    )
    hard_failures = [s.event.type.value for s in scenarios if s.rto_status == RuleStatus.FAIL]

    az_result = next((s for s in scenarios if s.event.type == FailureEventType.AZ_FAILURE), None)
    region_result = next((s for s in scenarios if s.event.type == FailureEventType.REGION_FAILURE), None)

    return CandidateFailureReport(
        candidate_id=candidate.id,
        scenarios=scenarios,
        worst_blast_radius=worst,
        hard_failures=hard_failures,
        survives_az_failure=bool(az_result and az_result.rto_status != RuleStatus.FAIL),
        survives_region_failure=bool(region_result and region_result.rto_status != RuleStatus.FAIL),
    )


def simulate_all(candidates: list[Candidate], normalized: NormalizedRequirements) -> dict[str, CandidateFailureReport]:
    return {candidate.id: simulate_candidate(candidate, normalized) for candidate in candidates}
