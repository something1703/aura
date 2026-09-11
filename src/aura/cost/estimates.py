"""Scenario-based cost estimation for a candidate architecture.

Pricing constants below are **illustrative, generic USD assumptions**, not a
live AWS pricing feed — see docs/COST_MODEL.md "Important limitation". Every
line item states its assumption and a confidence level so a reviewer can
challenge it.

Each :class:`~aura.domain.enums.CostScenario` is expressed as one or more
``_LoadWindow`` (rps, hours) pairs so the compute/queue/CDN/LCU line items
—the ones that actually scale with request volume—are priced against the
right blend of traffic for that scenario, while capacity-based line items
(database, cache, load balancer base fee, DNS) stay scenario-independent.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from aura.architecture.generator import Candidate
from aura.cost.model import CostEstimate, CostLineItem
from aura.domain.enums import CostConfidence, CostScenario
from aura.requirements.normalizer import NormalizedRequirements

HOURS_PER_MONTH = 730.0
RPS_PER_TASK = 50.0
RPS_PER_LCU = 25.0
FAILOVER_DRILL_HOURS_PER_MONTH = 8.0
AVG_RESPONSE_GB = 0.00005  # ~50 KB average response, illustrative
CROSS_REGION_REPLICATION_FRACTION = 0.05

COMPUTE_TASK_HOUR_USD = 0.045
DATABASE_PRIMARY_INSTANCE_HOUR_USD = 0.58
DATABASE_SECONDARY_INSTANCE_HOUR_USD = 0.29
CACHE_NODE_HOUR_USD = 0.15
LOAD_BALANCER_HOUR_USD = 0.0225
LOAD_BALANCER_LCU_HOUR_USD = 0.008
CDN_GB_USD = 0.02
QUEUE_PER_MILLION_REQUESTS_USD = 0.40
DNS_HOSTED_ZONE_MONTH_USD = 0.50
CROSS_REGION_TRANSFER_GB_USD = 0.02

_CONFIDENCE_ORDER = [CostConfidence.LOW, CostConfidence.MEDIUM, CostConfidence.HIGH]


class _LoadWindow(BaseModel):
    rps: float
    hours: float
    label: str


def _load_windows(scenario: CostScenario, normalized: NormalizedRequirements) -> list[_LoadWindow]:
    average_rps = normalized.average_rps.value
    peak_rps = normalized.peak_rps.value
    peak_hours = min(max(normalized.peak_duration_seconds.value / 3600.0, 0.0) * 30, HOURS_PER_MONTH)

    if scenario == CostScenario.AVERAGE_LOAD:
        return [_LoadWindow(rps=average_rps, hours=HOURS_PER_MONTH, label="average load, full month")]
    if scenario == CostScenario.PEAK_LOAD:
        return [
            _LoadWindow(rps=average_rps, hours=HOURS_PER_MONTH - peak_hours, label="baseline hours"),
            _LoadWindow(rps=peak_rps, hours=peak_hours, label="daily peak burst (assumed once/day)"),
        ]
    if scenario == CostScenario.SUSTAINED_PEAK:
        return [_LoadWindow(rps=peak_rps, hours=HOURS_PER_MONTH, label="peak sustained all month")]
    if scenario == CostScenario.FAILURE_MODE:
        return [_LoadWindow(rps=peak_rps, hours=HOURS_PER_MONTH, label="peak load while degraded")]
    raise ValueError(f"unknown cost scenario: {scenario}")


def _monthly_requests(windows: list[_LoadWindow]) -> float:
    return sum(w.rps * 3600 * w.hours for w in windows)


def _secondary_capacity_factor(candidate: Candidate, component_id: str) -> float:
    component = candidate.topology.component(component_id)
    if component is None or not candidate.secondary_region:
        return 0.0
    primary_azs = len({i.az for i in component.instances if i.region == candidate.primary_region})
    secondary_azs = len({i.az for i in component.instances if i.region == candidate.secondary_region})
    if primary_azs == 0:
        return 0.0
    return secondary_azs / primary_azs


def _compute_line_item(candidate: Candidate, windows: list[_LoadWindow]) -> CostLineItem:
    secondary_factor = _secondary_capacity_factor(candidate, "compute")
    monthly_cost = 0.0
    peak_quantity = 0.0
    for window in windows:
        tasks = max(1, math.ceil(window.rps / RPS_PER_TASK)) * (1 + secondary_factor)
        monthly_cost += tasks * COMPUTE_TASK_HOUR_USD * window.hours
        peak_quantity = max(peak_quantity, tasks)

    total_rps = sum(w.rps for w in windows) or 1.0
    provisioned = peak_quantity * RPS_PER_TASK
    utilization = min(total_rps / provisioned, 1.0) if provisioned else None

    return CostLineItem(
        service="Compute (ECS/Fargate-equivalent tasks)",
        unit="task-hour",
        quantity=round(peak_quantity, 2),
        utilization=round(utilization, 2) if utilization is not None else None,
        unit_price_usd=COMPUTE_TASK_HOUR_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=(
            f"{RPS_PER_TASK:.0f} RPS/task, secondary-region capacity factor "
            f"{secondary_factor:.2f}, blend: {', '.join(w.label for w in windows)}"
        ),
        confidence=CostConfidence.MEDIUM,
    )


def _database_line_item(candidate: Candidate) -> CostLineItem:
    database = candidate.topology.component("database")
    primary_count = len(database.instances_in(region=candidate.primary_region))
    secondary_count = len(database.instances) - primary_count
    monthly_cost = (
        primary_count * DATABASE_PRIMARY_INSTANCE_HOUR_USD * HOURS_PER_MONTH
        + secondary_count * DATABASE_SECONDARY_INSTANCE_HOUR_USD * HOURS_PER_MONTH
    )
    return CostLineItem(
        service="Database (Multi-AZ relational, illustrative instance class)",
        unit="instance-hour",
        quantity=len(database.instances),
        utilization=None,
        unit_price_usd=DATABASE_PRIMARY_INSTANCE_HOUR_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=(
            f"{primary_count} primary-region instance(s) at ${DATABASE_PRIMARY_INSTANCE_HOUR_USD}/hr, "
            f"{secondary_count} secondary-region instance(s) at ${DATABASE_SECONDARY_INSTANCE_HOUR_USD}/hr"
        ),
        confidence=CostConfidence.MEDIUM,
    )


def _cache_line_item(candidate: Candidate) -> CostLineItem | None:
    cache = candidate.topology.component("cache")
    if cache is None:
        return None
    monthly_cost = len(cache.instances) * CACHE_NODE_HOUR_USD * HOURS_PER_MONTH
    return CostLineItem(
        service="Cache (in-memory, illustrative node class)",
        unit="node-hour",
        quantity=len(cache.instances),
        utilization=None,
        unit_price_usd=CACHE_NODE_HOUR_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=f"{len(cache.instances)} node(s) running continuously",
        confidence=CostConfidence.MEDIUM,
    )


def _load_balancer_line_item(candidate: Candidate, windows: list[_LoadWindow]) -> CostLineItem:
    load_balancer = candidate.topology.component("load-balancer")
    region_count = len(load_balancer.regions)
    base_cost = region_count * LOAD_BALANCER_HOUR_USD * HOURS_PER_MONTH
    lcu_cost = sum(math.ceil(w.rps / RPS_PER_LCU) * LOAD_BALANCER_LCU_HOUR_USD * w.hours for w in windows)
    return CostLineItem(
        service="Load balancer",
        unit="LB-hour + LCU-hour",
        quantity=region_count,
        utilization=None,
        unit_price_usd=LOAD_BALANCER_HOUR_USD,
        monthly_cost_usd=round(base_cost + lcu_cost, 2),
        assumption=f"one logical load balancer per region ({region_count}), {RPS_PER_LCU:.0f} RPS/LCU",
        confidence=CostConfidence.MEDIUM,
    )


def _cdn_line_item(candidate: Candidate, windows: list[_LoadWindow]) -> CostLineItem | None:
    if candidate.topology.component("cdn") is None:
        return None
    gb = _monthly_requests(windows) * AVG_RESPONSE_GB
    monthly_cost = gb * CDN_GB_USD
    return CostLineItem(
        service="CDN data transfer",
        unit="GB",
        quantity=round(gb, 2),
        utilization=None,
        unit_price_usd=CDN_GB_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=f"~{AVG_RESPONSE_GB * 1_000_000:.0f} KB average response size",
        confidence=CostConfidence.LOW,
    )


def _queue_line_item(candidate: Candidate, windows: list[_LoadWindow]) -> CostLineItem | None:
    if candidate.topology.component("queue") is None:
        return None
    million_requests = _monthly_requests(windows) / 1_000_000
    monthly_cost = million_requests * QUEUE_PER_MILLION_REQUESTS_USD
    return CostLineItem(
        service="Durable queue",
        unit="million requests",
        quantity=round(million_requests, 2),
        utilization=None,
        unit_price_usd=QUEUE_PER_MILLION_REQUESTS_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption="one queue message per request, illustrative pricing",
        confidence=CostConfidence.LOW,
    )


def _dns_line_item(candidate: Candidate) -> CostLineItem | None:
    if candidate.topology.component("global-router") is None:
        return None
    return CostLineItem(
        service="Global DNS / traffic routing",
        unit="hosted-zone-month",
        quantity=1,
        utilization=None,
        unit_price_usd=DNS_HOSTED_ZONE_MONTH_USD,
        monthly_cost_usd=round(DNS_HOSTED_ZONE_MONTH_USD, 2),
        assumption="one hosted zone with health-check-based routing",
        confidence=CostConfidence.HIGH,
    )


def _cross_region_transfer_line_item(candidate: Candidate, windows: list[_LoadWindow]) -> CostLineItem:
    gb = _monthly_requests(windows) * AVG_RESPONSE_GB * CROSS_REGION_REPLICATION_FRACTION
    monthly_cost = gb * CROSS_REGION_TRANSFER_GB_USD
    return CostLineItem(
        service="Cross-region data transfer (replication)",
        unit="GB",
        quantity=round(gb, 2),
        utilization=None,
        unit_price_usd=CROSS_REGION_TRANSFER_GB_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=(f"replication traffic assumed at {CROSS_REGION_REPLICATION_FRACTION:.0%} of request volume"),
        confidence=CostConfidence.LOW,
    )


def _failover_capacity_line_item(candidate: Candidate, normalized: NormalizedRequirements) -> CostLineItem | None:
    if not candidate.multi_region:
        return None
    secondary_factor = _secondary_capacity_factor(candidate, "compute")
    if secondary_factor >= 1.0:
        return None  # already at full parity (e.g. active-active): no failover scale-up needed
    peak_tasks = max(1, math.ceil(normalized.peak_rps.value / RPS_PER_TASK))
    extra_tasks = peak_tasks * (1 - secondary_factor)
    monthly_cost = extra_tasks * COMPUTE_TASK_HOUR_USD * FAILOVER_DRILL_HOURS_PER_MONTH
    return CostLineItem(
        service="Failover capacity scale-up (secondary region)",
        unit="task-hour",
        quantity=round(extra_tasks, 2),
        utilization=None,
        unit_price_usd=COMPUTE_TASK_HOUR_USD,
        monthly_cost_usd=round(monthly_cost, 2),
        assumption=(
            f"secondary region scaled to full parity for an assumed "
            f"{FAILOVER_DRILL_HOURS_PER_MONTH:.0f}h/month (DR drills + incident exposure)"
        ),
        confidence=CostConfidence.LOW,
    )


def _aggregate_confidence(line_items: list[CostLineItem]) -> CostConfidence:
    if not line_items:
        return CostConfidence.LOW
    worst_index = min(_CONFIDENCE_ORDER.index(item.confidence) for item in line_items)
    return _CONFIDENCE_ORDER[worst_index]


def estimate_candidate_cost(
    candidate: Candidate, normalized: NormalizedRequirements, scenario: CostScenario
) -> CostEstimate:
    windows = _load_windows(scenario, normalized)
    line_items = [
        _compute_line_item(candidate, windows),
        _database_line_item(candidate),
        _load_balancer_line_item(candidate, windows),
    ]
    for optional_item in (
        _cache_line_item(candidate),
        _cdn_line_item(candidate, windows),
        _queue_line_item(candidate, windows),
        _dns_line_item(candidate),
    ):
        if optional_item is not None:
            line_items.append(optional_item)

    if candidate.multi_region:
        line_items.append(_cross_region_transfer_line_item(candidate, windows))
        if scenario == CostScenario.FAILURE_MODE:
            failover_item = _failover_capacity_line_item(candidate, normalized)
            if failover_item is not None:
                line_items.append(failover_item)

    total = round(sum(item.monthly_cost_usd for item in line_items), 2)
    return CostEstimate(
        candidate_id=candidate.id,
        scenario=scenario,
        line_items=line_items,
        total_monthly_usd=total,
        confidence=_aggregate_confidence(line_items),
    )


def estimate_candidate_all_scenarios(
    candidate: Candidate, normalized: NormalizedRequirements
) -> dict[str, CostEstimate]:
    return {scenario.value: estimate_candidate_cost(candidate, normalized, scenario) for scenario in CostScenario}
