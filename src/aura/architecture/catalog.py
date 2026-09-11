"""The Phase 1 architecture pattern catalog (docs/IMPLEMENTATION_PHASES.md #3)."""

from __future__ import annotations

from aura.architecture.patterns import PatternDefinition, PatternSupport
from aura.domain.enums import FailureEventType as FE

SINGLE_REGION_MULTI_AZ = PatternDefinition(
    id="single-region-multi-az",
    name="Single-region, multi-AZ",
    description=(
        "All compute, cache, and database tiers are replicated synchronously across "
        "multiple Availability Zones in one AWS region. Tolerates AZ loss; does not "
        "tolerate regional loss."
    ),
    supports=PatternSupport(availability_min=99.95, rto_max_seconds=900, rpo_max_seconds=30),
    requires=[],
    tradeoffs=["no_regional_resilience"],
    failure_modes_tolerated=[
        FE.INSTANCE_FAILURE, FE.AZ_FAILURE, FE.DATABASE_FAILURE,
        FE.BAD_DEPLOYMENT, FE.DEPENDENCY_FAILURE, FE.NETWORK_DEGRADATION,
    ],
    multi_region=False,
    regional_resilience=False,
    primary_az_count=3,
    secondary_az_count=0,
)

MULTI_REGION_ACTIVE_PASSIVE = PatternDefinition(
    id="multi-region-active-passive",
    name="Multi-region active-passive",
    description=(
        "A fully staffed primary region plus a cold/minimal secondary region. Recovery "
        "requires database promotion and a traffic cutover, so RTO is dominated by "
        "operational/automation speed rather than infrastructure readiness."
    ),
    supports=PatternSupport(availability_min=99.95, rto_max_seconds=900, rpo_max_seconds=300),
    requires=["cross_region_replication"],
    tradeoffs=["higher_cost", "operational_complexity", "secondary_region_underutilized"],
    failure_modes_tolerated=[
        FE.INSTANCE_FAILURE, FE.AZ_FAILURE, FE.REGION_FAILURE, FE.DATABASE_FAILURE,
        FE.BAD_DEPLOYMENT, FE.DEPENDENCY_FAILURE, FE.NETWORK_DEGRADATION,
    ],
    multi_region=True,
    regional_resilience=True,
    primary_az_count=3,
    secondary_az_count=1,
)

MULTI_REGION_WARM_STANDBY = PatternDefinition(
    id="multi-region-warm-standby",
    name="Multi-region warm standby",
    description=(
        "The secondary region runs a scaled-down but live copy of the stack with "
        "continuous replication, so failover is a traffic cutover and a scale-up "
        "rather than a cold start."
    ),
    supports=PatternSupport(availability_min=99.99, rto_max_seconds=300, rpo_max_seconds=60),
    requires=["cross_region_replication", "standby_capacity"],
    tradeoffs=["moderate_idle_cost", "operational_complexity"],
    failure_modes_tolerated=[
        FE.INSTANCE_FAILURE, FE.AZ_FAILURE, FE.REGION_FAILURE, FE.DATABASE_FAILURE,
        FE.TRAFFIC_SPIKE, FE.BAD_DEPLOYMENT, FE.DEPENDENCY_FAILURE, FE.NETWORK_DEGRADATION,
    ],
    multi_region=True,
    regional_resilience=True,
    primary_az_count=3,
    secondary_az_count=2,
)

MULTI_REGION_ACTIVE_ACTIVE = PatternDefinition(
    id="multi-region-active-active",
    name="Multi-region active-active",
    description=(
        "Both regions serve production traffic concurrently behind global routing. "
        "Regional loss is nearly transparent to users, at the cost of write-conflict "
        "resolution and the highest infrastructure and operational spend."
    ),
    supports=PatternSupport(availability_min=99.995, rto_max_seconds=30, rpo_max_seconds=5),
    requires=["cross_region_replication", "conflict_resolution_strategy", "global_traffic_routing"],
    tradeoffs=["highest_cost", "data_consistency_complexity", "operational_complexity"],
    failure_modes_tolerated=[
        FE.INSTANCE_FAILURE, FE.AZ_FAILURE, FE.REGION_FAILURE, FE.DATABASE_FAILURE,
        FE.TRAFFIC_SPIKE, FE.BAD_DEPLOYMENT, FE.DEPENDENCY_FAILURE, FE.NETWORK_DEGRADATION,
    ],
    multi_region=True,
    regional_resilience=True,
    primary_az_count=3,
    secondary_az_count=3,
)

EVENT_DRIVEN_BUFFERED = PatternDefinition(
    id="event-driven-buffered",
    name="Event-driven buffered (single region)",
    description=(
        "A durable queue sits between ingestion and processing so traffic bursts are "
        "absorbed instead of overwhelming the compute or database tier. Strongest "
        "pattern for extreme, short-duration spikes; weakest for regional resilience."
    ),
    supports=PatternSupport(availability_min=99.9, rto_max_seconds=600, rpo_max_seconds=120),
    requires=["durable_queue"],
    tradeoffs=["eventual_consistency", "added_processing_latency", "no_regional_resilience"],
    failure_modes_tolerated=[
        FE.INSTANCE_FAILURE, FE.AZ_FAILURE, FE.TRAFFIC_SPIKE,
        FE.BAD_DEPLOYMENT, FE.DEPENDENCY_FAILURE, FE.NETWORK_DEGRADATION, FE.DATABASE_FAILURE,
    ],
    multi_region=False,
    regional_resilience=False,
    primary_az_count=3,
    secondary_az_count=0,
)

CATALOG: list[PatternDefinition] = [
    SINGLE_REGION_MULTI_AZ,
    MULTI_REGION_ACTIVE_PASSIVE,
    MULTI_REGION_WARM_STANDBY,
    MULTI_REGION_ACTIVE_ACTIVE,
    EVENT_DRIVEN_BUFFERED,
]


def get_pattern(pattern_id: str) -> PatternDefinition:
    for pattern in CATALOG:
        if pattern.id == pattern_id:
            return pattern
    raise KeyError(f"unknown architecture pattern: {pattern_id}")
