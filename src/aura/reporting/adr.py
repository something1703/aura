"""Generate ADRs for the meaningful decisions in the recommended architecture.

Per docs/IMPLEMENTATION_PHASES.md #9: compute model, data model, region
strategy, deployment strategy, scaling strategy, recovery strategy — one ADR
each, only when a candidate was actually selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from aura.domain.enums import FailureEventType
from aura.reporting.context import ReportContext

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class AdrSpec:
    number: int
    slug: str
    title: str
    context: str
    decision: str
    consequences: list[str]


def _scenario(ctx: ReportContext, event_type: FailureEventType):
    return next(s for s in ctx.recommendation.failure_report.scenarios if s.event.type == event_type)


def _compute_adr(ctx: ReportContext, number: int) -> AdrSpec:
    candidate = ctx.recommended_candidate
    compute = candidate.topology.component("compute")
    secondary_has_compute = bool(candidate.secondary_region and compute.instances_in(region=candidate.secondary_region))
    return AdrSpec(
        number=number,
        slug="compute-model",
        title="Compute Model",
        context=(
            f"{ctx.workload.application.name} must sustain "
            f"{ctx.normalized.average_rps.value:.0f} RPS average and "
            f"{ctx.normalized.peak_rps.value:.0f} RPS peak for "
            f"{ctx.normalized.peak_duration_seconds.value / 60:.0f} minute(s)."
        ),
        decision=(
            f"Run the compute tier as horizontally autoscaled tasks across "
            f"{len(compute.azs)} Availability Zone(s) in {candidate.primary_region}"
            + (f", plus a footprint in {candidate.secondary_region}" if secondary_has_compute else "")
            + f". {candidate.scaling_model}"
        ),
        consequences=[
            "Compute is stateless and horizontally scalable; state lives in the database/cache tier.",
            *[t for t in candidate.tradeoffs if "cost" in t or "complexity" in t],
        ],
    )


def _data_model_adr(ctx: ReportContext, number: int) -> AdrSpec:
    candidate = ctx.recommended_candidate
    database = candidate.topology.component("database")
    return AdrSpec(
        number=number,
        slug="data-model",
        title="Data Model & Replication Strategy",
        context=candidate.data_strategy,
        decision=(
            f"Use a Multi-AZ relational database with "
            f"{database.replication or 'synchronous in-region'} replication across "
            f"{len(database.regions)} region(s)."
        ),
        consequences=[limitation for limitation in candidate.known_limitations if "consist" in limitation.lower()]
        or ["Consistency model matches the declared per-domain requirements; no conflicts identified."],
    )


def _region_strategy_adr(ctx: ReportContext, number: int) -> AdrSpec:
    candidate = ctx.recommended_candidate
    region_scenario = _scenario(ctx, FailureEventType.REGION_FAILURE)
    return AdrSpec(
        number=number,
        slug="region-strategy",
        title="Region Strategy",
        context=(
            f"Regional disaster recovery required: {ctx.normalized.regional_disaster_required.value}. "
            f"Declared user regions: {', '.join(ctx.normalized.user_regions) or 'none declared'}."
        ),
        decision=(f"{candidate.availability_model} Regional failure recovery: {region_scenario.recovery_action}"),
        consequences=list(candidate.tradeoffs) or ["No significant region-strategy tradeoffs identified."],
    )


def _deployment_strategy_adr(ctx: ReportContext, number: int) -> AdrSpec:
    scenario = _scenario(ctx, FailureEventType.BAD_DEPLOYMENT)
    return AdrSpec(
        number=number,
        slug="deployment-strategy",
        title="Deployment Strategy",
        context=(
            f"Deployment frequency: {ctx.normalized.deployment_frequency_per_day:.0f}/day. "
            f"Downtime allowed: {ctx.normalized.downtime_allowed.value}."
        ),
        decision=(
            f"Detect bad deployments via {scenario.detection.lower()}; recover via {scenario.recovery_action.lower()} "
            f"(expected {scenario.expected_recovery_seconds}s, target RTO {scenario.rto_required_seconds}s)."
        ),
        consequences=scenario.notes or ["Rollback path meets the declared recovery objective."],
    )


def _scaling_strategy_adr(ctx: ReportContext, number: int) -> AdrSpec:
    candidate = ctx.recommended_candidate
    spike_scenario = _scenario(ctx, FailureEventType.TRAFFIC_SPIKE)
    capacity_rule = next(r for r in ctx.recommendation.rule_results if r.rule_id == "capacity.burst_ratio")
    return AdrSpec(
        number=number,
        slug="scaling-strategy",
        title="Scaling Strategy",
        context=(
            f"Peak-to-average burst ratio is {capacity_rule.observed}x "
            f"(growth ~{ctx.normalized.growth_percent_per_month:.0f}%/month)."
        ),
        decision=f"{candidate.scaling_model} Traffic-spike handling: {spike_scenario.recovery_action}",
        consequences=spike_scenario.notes or ["Provisioned headroom is expected to absorb the declared burst."],
    )


def _recovery_strategy_adr(ctx: ReportContext, number: int) -> AdrSpec:
    az_scenario = _scenario(ctx, FailureEventType.AZ_FAILURE)
    region_scenario = _scenario(ctx, FailureEventType.REGION_FAILURE)
    return AdrSpec(
        number=number,
        slug="recovery-strategy",
        title="Recovery Strategy",
        context=(f"RTO target {ctx.normalized.rto_seconds.value}s, RPO target {ctx.normalized.rpo_seconds.value}s."),
        decision=(
            f"AZ failure: {az_scenario.recovery_action} (expected {az_scenario.expected_recovery_seconds}s, "
            f"status {az_scenario.rto_status.value}). Region failure: {region_scenario.recovery_action} "
            f"(expected {region_scenario.expected_recovery_seconds}s, status {region_scenario.rto_status.value})."
        ),
        consequences=[
            *az_scenario.notes,
            *region_scenario.notes,
        ]
        or ["Recovery paths meet the declared RTO/RPO targets under modelled conditions."],
    )


_BUILDERS = [
    _compute_adr,
    _data_model_adr,
    _region_strategy_adr,
    _deployment_strategy_adr,
    _scaling_strategy_adr,
    _recovery_strategy_adr,
]


def generate_adrs(ctx: ReportContext) -> dict[str, str]:
    """Render one ADR per meaningful decision. Empty if no candidate was selected."""

    if ctx.recommendation is None or ctx.recommended_candidate is None:
        return {}

    template = _env.get_template("adr.md.j2")
    documents: dict[str, str] = {}
    for number, builder in enumerate(_BUILDERS, start=1):
        spec = builder(ctx, number)
        filename = f"ADR-{number:04d}-{spec.slug}.md"
        documents[filename] = template.render(
            number=spec.number,
            title=spec.title,
            context=spec.context,
            decision=spec.decision,
            consequences=spec.consequences,
        )
    return documents
