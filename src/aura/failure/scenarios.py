"""Business capabilities and the eight initial failure scenarios.

Blast radius must be grounded in declared business capabilities and
dependency-graph reachability, not vibes (docs/IMPLEMENTATION_PHASES.md #8).
Capabilities are declared per application type; ``core=True`` marks the
capability as the core business path, which is what makes an impact
CRITICAL rather than merely HIGH (docs/FAILURE_MODEL.md blast radius scale).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aura.architecture.generator import Candidate
from aura.domain.enums import FailureEventType, Severity


class BusinessCapability(BaseModel):
    id: str
    name: str
    core: bool
    depends_on: list[str]


_CAPABILITIES: dict[str, list[BusinessCapability]] = {
    "ecommerce": [
        BusinessCapability(
            id="browsing", name="Product browsing & search", core=False,
            depends_on=["cdn", "load-balancer", "compute", "cache"],
        ),
        BusinessCapability(
            id="checkout", name="Checkout & order placement", core=True,
            depends_on=["load-balancer", "compute", "database", "queue"],
        ),
        BusinessCapability(
            id="payments", name="Payment processing", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
        BusinessCapability(
            id="fulfillment-notifications", name="Order & fulfillment notifications", core=False,
            depends_on=["queue", "compute"],
        ),
    ],
    "fintech": [
        BusinessCapability(
            id="account-access", name="Account login & balance access", core=False,
            depends_on=["load-balancer", "compute", "cache"],
        ),
        BusinessCapability(
            id="transaction-processing", name="Transaction & transfer processing", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
        BusinessCapability(
            id="statements-reporting", name="Statements & reporting", core=False,
            depends_on=["compute", "database"],
        ),
        BusinessCapability(
            id="fraud-compliance", name="Fraud & compliance checks", core=True,
            depends_on=["compute", "database", "queue"],
        ),
    ],
    "media_streaming": [
        BusinessCapability(
            id="content-delivery", name="Content delivery & playback start", core=True,
            depends_on=["cdn", "load-balancer", "compute", "cache"],
        ),
        BusinessCapability(
            id="playback-session", name="Playback session & entitlement", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
        BusinessCapability(
            id="catalog-search", name="Catalog & search", core=False,
            depends_on=["compute", "cache", "database"],
        ),
        BusinessCapability(
            id="recommendations", name="Recommendations", core=False,
            depends_on=["compute", "database"],
        ),
    ],
    "saas": [
        BusinessCapability(
            id="application-access", name="Application login & dashboard", core=False,
            depends_on=["load-balancer", "compute", "cache"],
        ),
        BusinessCapability(
            id="core-workflow", name="Core product workflow", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
        BusinessCapability(
            id="background-processing", name="Background/async processing", core=False,
            depends_on=["queue", "compute"],
        ),
        BusinessCapability(
            id="reporting-analytics", name="Reporting & analytics", core=False,
            depends_on=["compute", "database"],
        ),
    ],
    "internal_tool": [
        BusinessCapability(
            id="core-workflow", name="Core internal workflow", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
        BusinessCapability(
            id="reporting", name="Reporting", core=False,
            depends_on=["compute", "database"],
        ),
    ],
    "data_platform": [
        BusinessCapability(
            id="ingestion", name="Data ingestion", core=True,
            depends_on=["queue", "compute"],
        ),
        BusinessCapability(
            id="processing-pipeline", name="Processing pipeline", core=True,
            depends_on=["compute", "database"],
        ),
        BusinessCapability(
            id="query-serving", name="Query serving", core=False,
            depends_on=["compute", "database", "cache"],
        ),
    ],
    "generic": [
        BusinessCapability(
            id="core-service", name="Core service", core=True,
            depends_on=["load-balancer", "compute", "database"],
        ),
    ],
}


def capabilities_for(application_type: str) -> list[BusinessCapability]:
    return _CAPABILITIES.get(application_type, _CAPABILITIES["generic"])


class FailureEvent(BaseModel):
    type: FailureEventType
    target_az: str | None = None
    target_region: str | None = None
    target_component: str | None = None
    severity: Severity
    assumptions: dict[str, str] = Field(default_factory=dict)


def build_failure_events(candidate: Candidate) -> list[FailureEvent]:
    """Build the eight initial scenarios (AGENT_FAILURE.md), sized to this candidate."""

    compute = candidate.topology.component("compute")
    database = candidate.topology.component("database")
    primary_az = sorted(compute.instances_in(region=candidate.primary_region), key=lambda i: i.az)[0].az

    events = [
        FailureEvent(
            type=FailureEventType.INSTANCE_FAILURE,
            target_component="compute",
            severity=Severity.LOW,
            assumptions={"scope": "single compute instance, ASG/ECS self-heals"},
        ),
        FailureEvent(
            type=FailureEventType.AZ_FAILURE,
            target_az=primary_az,
            target_region=candidate.primary_region,
            severity=Severity.HIGH,
            assumptions={"duration_seconds": "300"},
        ),
        FailureEvent(
            type=FailureEventType.DATABASE_FAILURE,
            target_component="database",
            severity=Severity.HIGH,
            assumptions={"scope": "loss of the current database primary/writer instance"},
        ),
        FailureEvent(
            type=FailureEventType.NETWORK_DEGRADATION,
            severity=Severity.MEDIUM,
            assumptions={"scope": "elevated latency/packet loss on cross-AZ or cross-region links"},
        ),
        FailureEvent(
            type=FailureEventType.TRAFFIC_SPIKE,
            severity=Severity.MEDIUM,
            assumptions={"scope": "traffic exceeds provisioned peak capacity"},
        ),
        FailureEvent(
            type=FailureEventType.BAD_DEPLOYMENT,
            target_component="compute",
            severity=Severity.MEDIUM,
            assumptions={"scope": "a bad release degrades or breaks the compute tier"},
        ),
        FailureEvent(
            type=FailureEventType.DEPENDENCY_FAILURE,
            target_component="cache" if candidate.topology.component("cache") else None,
            severity=Severity.LOW,
            assumptions={"scope": "a non-critical external/cache dependency becomes unavailable"},
        ),
        FailureEvent(
            type=FailureEventType.REGION_FAILURE,
            target_region=candidate.primary_region,
            severity=Severity.CRITICAL,
            assumptions={"duration_seconds": "3600"},
        ),
    ]
    return events
