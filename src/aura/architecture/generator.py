"""Candidate architecture generation.

For every pattern in the catalog, build one concrete :class:`Candidate`:
a typed topology graph placed in the workload's actual regions, plus the
narrative fields AGENT_ARCHITECTURE.md requires (availability model, scaling
model, data strategy, failure strategy, cost assumptions, known limitations).

Patterns are never silently dropped here — even a structurally mismatched
pattern (e.g. single-region when regional DR is required) is generated so
the evaluation engine can mark it INELIGIBLE with evidence (Phase 1
acceptance test: "at least 1 rejected candidate with reasons").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aura.architecture.catalog import CATALOG
from aura.architecture.patterns import PatternDefinition, PatternSupport
from aura.domain.enums import ApplicationType
from aura.domain.graph import Component, Graph, Instance
from aura.requirements.normalizer import NormalizedRequirements

_AZ_LETTERS = "abcdef"

_CDN_APPLICATION_TYPES = {
    ApplicationType.ECOMMERCE,
    ApplicationType.SAAS,
    ApplicationType.MEDIA_STREAMING,
}

_REGION_DR_PAIRS = {
    "ap-south-1": "ap-southeast-1",
    "ap-southeast-1": "ap-southeast-2",
    "ap-southeast-2": "ap-southeast-1",
    "ap-northeast-1": "ap-northeast-2",
    "us-east-1": "us-west-2",
    "us-west-2": "us-east-1",
    "us-east-2": "us-west-2",
    "eu-west-1": "eu-central-1",
    "eu-central-1": "eu-west-1",
    "sa-east-1": "us-east-1",
}


class SecondaryRegion(BaseModel):
    region: str
    assumed: bool


class Candidate(BaseModel):
    id: str
    name: str
    description: str
    supports: PatternSupport
    requires: list[str]
    tradeoffs: list[str]
    failure_modes_tolerated: list[str]
    multi_region: bool
    regional_resilience: bool
    primary_region: str
    secondary_region: str | None
    secondary_region_assumed: bool
    topology: Graph
    availability_model: str
    scaling_model: str
    data_strategy: str
    failure_strategy: str
    cost_assumptions: list[str]
    known_limitations: list[str]


def _az_ids(region: str, count: int) -> list[str]:
    return [f"{region}{_AZ_LETTERS[i]}" for i in range(count)]


def _instances(region: str, count: int) -> list[Instance]:
    return [Instance(az=az, region=region) for az in _az_ids(region, max(count, 1))]


def choose_secondary_region(normalized: NormalizedRequirements) -> SecondaryRegion:
    """Pick a secondary region for multi-region patterns.

    An explicit second entry in ``geography.primary_regions`` is preferred.
    Otherwise a conventional AWS DR pairing is used and flagged as assumed —
    it is not something the workload declared.
    """

    primary = normalized.primary_regions[0]
    if len(normalized.primary_regions) > 1:
        return SecondaryRegion(region=normalized.primary_regions[1], assumed=False)
    if primary in _REGION_DR_PAIRS:
        return SecondaryRegion(region=_REGION_DR_PAIRS[primary], assumed=True)
    return SecondaryRegion(region=f"{primary}-dr", assumed=True)


def _build_topology(
    pattern: PatternDefinition,
    normalized: NormalizedRequirements,
    primary_region: str,
    secondary_region: str | None,
) -> Graph:
    components: list[Component] = []
    is_active_active = pattern.id == "multi-region-active-active"
    is_event_driven = pattern.id == "event-driven-buffered"

    lb_instances = _instances(primary_region, pattern.primary_az_count)
    if pattern.multi_region and secondary_region:
        lb_instances += _instances(secondary_region, pattern.secondary_az_count)
    components.append(Component(id="load-balancer", kind="load_balancer", instances=lb_instances))

    if pattern.multi_region:
        components.append(
            Component(
                id="global-router",
                kind="dns",
                instances=[Instance(az="global", region="global")],
                depends_on=["load-balancer"],
                critical_dependency={"load-balancer": True},
                attributes={
                    "routing_policy": "latency-and-health" if is_active_active else "failover",
                },
            )
        )

    queue_id: str | None = None
    if is_event_driven:
        queue_id = "queue"
        components.append(
            Component(
                id=queue_id,
                kind="queue",
                instances=_instances(primary_region, pattern.primary_az_count),
                attributes={"durable": True, "visibility_timeout_seconds": 30},
            )
        )

    db_instances = _instances(primary_region, pattern.primary_az_count)
    db_replication: str | None = None
    if pattern.multi_region and secondary_region:
        db_instances += _instances(
            secondary_region,
            pattern.secondary_az_count if pattern.secondary_az_count else 1,
        )
        db_replication = "sync" if is_active_active else "async"
    components.append(
        Component(id="database", kind="database", instances=db_instances, replication=db_replication)
    )

    cache_id: str | None = None
    if normalized.stateful:
        cache_id = "cache"
        cache_instances = _instances(primary_region, pattern.primary_az_count)
        if pattern.multi_region and secondary_region and is_active_active:
            cache_instances += _instances(secondary_region, pattern.secondary_az_count)
        components.append(Component(id=cache_id, kind="cache", instances=cache_instances))

    compute_instances = _instances(primary_region, pattern.primary_az_count)
    if pattern.multi_region and secondary_region:
        secondary_compute_azs = pattern.secondary_az_count if pattern.id != "multi-region-active-passive" else 0
        if secondary_compute_azs:
            compute_instances += _instances(secondary_region, secondary_compute_azs)

    compute_depends_on = ["database"]
    compute_critical = {"database": True}
    if cache_id:
        compute_depends_on.append(cache_id)
        compute_critical[cache_id] = False
    if queue_id:
        compute_depends_on.append(queue_id)
        compute_critical[queue_id] = True

    components.append(
        Component(
            id="compute",
            kind="compute",
            instances=compute_instances or _instances(primary_region, 1),
            depends_on=compute_depends_on,
            critical_dependency=compute_critical,
        )
    )

    if normalized.internet_facing and normalized.application_type in {t.value for t in _CDN_APPLICATION_TYPES}:
        components.append(
            Component(
                id="cdn",
                kind="cdn",
                instances=[Instance(az="edge", region="global")],
                depends_on=["load-balancer"],
                critical_dependency={"load-balancer": False},
            )
        )

    return Graph(components=components)


def _availability_model(pattern: PatternDefinition, primary_region: str, secondary: SecondaryRegion | None) -> str:
    text = f"{pattern.primary_az_count} Availability Zones in {primary_region}"
    if pattern.multi_region and secondary:
        role = "active" if pattern.id == "multi-region-active-active" else "standby"
        assumed = " (assumed DR pairing)" if secondary.assumed else ""
        text += f", plus {pattern.secondary_az_count} AZ(s) {role} in {secondary.region}{assumed}"
    return text + "."


def _scaling_model(normalized: NormalizedRequirements, is_event_driven: bool) -> str:
    text = (
        f"Horizontal autoscaling of the compute tier sized for a peak of "
        f"{normalized.peak_rps.value:.0f} RPS sustained for "
        f"{normalized.peak_duration_seconds.value / 60:.0f} minute(s), growing "
        f"~{normalized.growth_percent_per_month:.0f}%/month."
    )
    if is_event_driven:
        text += " Ingestion is decoupled from processing through a durable queue to absorb bursts above provisioned capacity."
    return text


def _data_strategy(normalized: NormalizedRequirements, db_replication: str | None) -> str:
    modes = ", ".join(f"{domain}={mode.value}" for domain, mode in sorted(normalized.consistency.items()))
    replication_text = {
        None: "single-region multi-AZ synchronous replication",
        "sync": "synchronous cross-region replication",
        "async": "asynchronous cross-region replication",
    }[db_replication]
    return f"Consistency requirements: {modes or 'none declared'}. Database strategy: {replication_text}."


def _failure_strategy(pattern: PatternDefinition) -> str:
    tolerated = ", ".join(mode.value if hasattr(mode, "value") else str(mode) for mode in pattern.failure_modes_tolerated)
    return f"{pattern.description} Explicitly modelled failure modes: {tolerated}."


def _cost_assumptions(pattern: PatternDefinition, topology: Graph) -> list[str]:
    assumptions = []
    for component in topology.components:
        assumptions.append(
            f"{component.kind}:{component.id} — {len(component.instances)} instance(s) across "
            f"{len(component.regions)} region(s)"
        )
    return assumptions


def _known_limitations(pattern: PatternDefinition, normalized: NormalizedRequirements, secondary: SecondaryRegion | None) -> list[str]:
    limitations = list(pattern.tradeoffs)
    if secondary and secondary.assumed:
        limitations.append(
            f"secondary region {secondary.region} was assumed (workload declared only one primary region)"
        )
    if pattern.id == "multi-region-active-active":
        strong_domains = [d for d, m in normalized.consistency.items() if m.value == "strong"]
        if strong_domains:
            limitations.append(
                f"active-active requires conflict resolution for strongly-consistent domain(s): "
                f"{', '.join(sorted(strong_domains))}"
            )
    if pattern.id == "event-driven-buffered" and any(m.value == "strong" for m in normalized.consistency.values()):
        limitations.append(
            "buffered/asynchronous processing conflicts with strongly-consistent domains unless the "
            "critical path bypasses the queue"
        )
    return limitations


def generate_candidate(pattern: PatternDefinition, normalized: NormalizedRequirements) -> Candidate:
    primary_region = normalized.primary_regions[0]
    secondary: SecondaryRegion | None = None
    secondary_region_name: str | None = None
    if pattern.multi_region:
        secondary = choose_secondary_region(normalized)
        secondary_region_name = secondary.region

    topology = _build_topology(pattern, normalized, primary_region, secondary_region_name)
    db_replication = topology.component("database").replication if topology.component("database") else None

    return Candidate(
        id=pattern.id,
        name=pattern.name,
        description=pattern.description,
        supports=pattern.supports,
        requires=list(pattern.requires),
        tradeoffs=list(pattern.tradeoffs),
        failure_modes_tolerated=list(pattern.failure_modes_tolerated),
        multi_region=pattern.multi_region,
        regional_resilience=pattern.regional_resilience,
        primary_region=primary_region,
        secondary_region=secondary_region_name,
        secondary_region_assumed=bool(secondary and secondary.assumed),
        topology=topology,
        availability_model=_availability_model(pattern, primary_region, secondary),
        scaling_model=_scaling_model(normalized, pattern.id == "event-driven-buffered"),
        data_strategy=_data_strategy(normalized, db_replication),
        failure_strategy=_failure_strategy(pattern),
        cost_assumptions=_cost_assumptions(pattern, topology),
        known_limitations=_known_limitations(pattern, normalized, secondary),
    )


def generate_candidates(normalized: NormalizedRequirements) -> list[Candidate]:
    """Generate one candidate per catalog pattern, in catalog order."""

    return [generate_candidate(pattern, normalized) for pattern in CATALOG]
