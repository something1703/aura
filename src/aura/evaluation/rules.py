"""The nine Phase 1 evaluation rules (docs/IMPLEMENTATION_PHASES.md #5).

Each rule inspects one candidate plus its already-computed failure report and
cost estimates (AGENT_ORCHESTRATOR.md runs Architecture -> Failure -> Cost ->
rules, in that order, so rules never re-derive what those engines already
computed). A rule marked ``mandatory=True`` makes the candidate INELIGIBLE
when it FAILs (docs/SCORING_ENGINE.md); other rules only influence the score.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from aura.architecture.generator import Candidate
from aura.cost.model import CostEstimate
from aura.domain.enums import CostScenario, DataClassification, RuleStatus, Severity
from aura.domain.enums import FailureEventType as FE
from aura.failure.simulator import CandidateFailureReport
from aura.requirements.normalizer import NormalizedRequirements


class RuleResult(BaseModel):
    rule_id: str
    status: RuleStatus
    severity: Severity
    observed: Any
    required: Any
    evidence: str
    mandatory: bool


def _severity_for(status: RuleStatus, if_failed: Severity) -> Severity:
    if status == RuleStatus.PASS:
        return Severity.INFO
    if status == RuleStatus.WARN:
        _step_down = {
            Severity.CRITICAL: Severity.HIGH,
            Severity.HIGH: Severity.MEDIUM,
            Severity.MEDIUM: Severity.LOW,
            Severity.LOW: Severity.LOW,
        }
        return _step_down.get(if_failed, Severity.LOW)
    return if_failed


def _scenario(report: CandidateFailureReport, event_type: FE):
    return next(s for s in report.scenarios if s.event.type == event_type)


def availability_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    required = normalized.availability_target.value
    observed = candidate.supports.availability_min
    status = RuleStatus.PASS if observed >= required else RuleStatus.FAIL
    return RuleResult(
        rule_id="availability.target",
        status=status,
        severity=_severity_for(status, Severity.CRITICAL),
        observed=observed,
        required=required,
        evidence=f"{candidate.name} delivers up to {observed}% availability; workload requires {required}%.",
        mandatory=True,
    )


def capacity_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    average = normalized.average_rps.value
    peak = normalized.peak_rps.value
    burst_ratio = peak / average if average else 0.0
    has_buffer = candidate.topology.component("queue") is not None

    if burst_ratio > 20 and not has_buffer:
        status = RuleStatus.FAIL
    elif burst_ratio > 10 and not has_buffer:
        status = RuleStatus.WARN
    else:
        status = RuleStatus.PASS

    return RuleResult(
        rule_id="capacity.burst_ratio",
        status=status,
        severity=_severity_for(status, Severity.HIGH),
        observed=round(burst_ratio, 1),
        required="<=10x without a buffering component",
        evidence=(
            f"peak/average ratio is {burst_ratio:.1f}x; "
            f"{'a durable queue absorbs the burst' if has_buffer else 'no buffering component is present'}."
        ),
        mandatory=False,
    )


def rto_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    scenario = _scenario(failure_report, FE.AZ_FAILURE)
    required = normalized.rto_seconds.value
    return RuleResult(
        rule_id="rto.max",
        status=scenario.rto_status,
        severity=_severity_for(scenario.rto_status, Severity.CRITICAL),
        observed=scenario.expected_recovery_seconds,
        required=required,
        evidence=f"AZ failure recovery path: {scenario.recovery_action}",
        mandatory=True,
    )


def rpo_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    scenario = _scenario(failure_report, FE.AZ_FAILURE)
    required = normalized.rpo_seconds.value
    status = scenario.rpo_status if scenario.rpo_status != RuleStatus.NOT_EVALUATED else RuleStatus.PASS
    observed = scenario.expected_data_loss_seconds if scenario.expected_data_loss_seconds is not None else 0.0
    return RuleResult(
        rule_id="rpo.max",
        status=status,
        severity=_severity_for(status, Severity.CRITICAL),
        observed=observed,
        required=required,
        evidence=f"AZ failure expected data loss window: {observed}s (database replication: "
        f"{candidate.topology.component('database').replication or 'synchronous multi-AZ'}).",
        mandatory=True,
    )


def budget_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    observed = cost_estimates[CostScenario.PEAK_LOAD.value].total_monthly_usd
    required = normalized.monthly_budget_usd.value
    hard_limit = normalized.budget_hard_limit

    if observed <= required:
        status = RuleStatus.PASS
    elif hard_limit:
        status = RuleStatus.FAIL
    else:
        status = RuleStatus.WARN

    return RuleResult(
        rule_id="budget.monthly",
        status=status,
        severity=_severity_for(status, Severity.HIGH if hard_limit else Severity.MEDIUM),
        observed=round(observed, 2),
        required=required,
        evidence=(
            f"estimated peak-load monthly cost ${observed:,.2f} vs "
            f"{'hard' if hard_limit else 'preferred'} budget ${required:,.2f}."
        ),
        mandatory=hard_limit,
    )


def regional_resilience_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    required = bool(normalized.regional_disaster_required.value)
    if not required:
        return RuleResult(
            rule_id="resilience.regional",
            status=RuleStatus.NOT_EVALUATED,
            severity=Severity.INFO,
            observed=candidate.regional_resilience,
            required=required,
            evidence="workload did not declare regional_disaster_required; evaluated for information only.",
            mandatory=False,
        )

    region_scenario = _scenario(failure_report, FE.REGION_FAILURE)
    status = (
        RuleStatus.PASS
        if candidate.regional_resilience and region_scenario.rto_status != RuleStatus.FAIL
        else RuleStatus.FAIL
    )
    return RuleResult(
        rule_id="resilience.regional",
        status=status,
        severity=_severity_for(status, Severity.CRITICAL),
        observed=candidate.regional_resilience,
        required=required,
        evidence=f"regional failure recovery path: {region_scenario.recovery_action}",
        mandatory=True,
    )


def security_boundary_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    needs_encryption = normalized.internet_facing and normalized.data_classification in {
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
    }
    observed = {
        "encryption_at_rest": normalized.encryption_at_rest,
        "encryption_in_transit": normalized.encryption_in_transit,
    }
    satisfied = normalized.encryption_at_rest and normalized.encryption_in_transit
    status = RuleStatus.PASS if (not needs_encryption or satisfied) else RuleStatus.FAIL
    return RuleResult(
        rule_id="security.boundary",
        status=status,
        severity=_severity_for(status, Severity.CRITICAL),
        observed=observed,
        required=(
            f"encryption at rest and in transit for internet-facing {normalized.data_classification.value} data"
            if needs_encryption
            else "not required"
        ),
        evidence=(
            f"internet-facing + {normalized.data_classification.value} data requires full encryption."
            if needs_encryption
            else "data classification does not mandate encryption for this workload."
        ),
        mandatory=needs_encryption,
    )


def deployment_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    scenario = _scenario(failure_report, FE.BAD_DEPLOYMENT)
    required = normalized.rto_seconds.value
    return RuleResult(
        rule_id="deployment.rollback",
        status=scenario.rto_status,
        severity=_severity_for(scenario.rto_status, Severity.MEDIUM),
        observed=scenario.expected_recovery_seconds,
        required=required,
        evidence=f"bad-deployment recovery: {scenario.recovery_action}",
        mandatory=False,
    )


_COMPLEXITY_TAGS = {"operational_complexity", "data_consistency_complexity"}


def operational_complexity_rule(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> RuleResult:
    complexity_hits = [t for t in candidate.tradeoffs if t in _COMPLEXITY_TAGS]
    status = RuleStatus.WARN if len(complexity_hits) >= 2 else RuleStatus.PASS
    return RuleResult(
        rule_id="operations.complexity",
        status=status,
        severity=_severity_for(status, Severity.LOW),
        observed=complexity_hits,
        required="<2 significant operational-complexity tradeoffs",
        evidence=f"declared tradeoffs: {', '.join(candidate.tradeoffs) or 'none'}.",
        mandatory=False,
    )


RuleFunc = Callable[[Candidate, NormalizedRequirements, CandidateFailureReport, dict[str, CostEstimate]], RuleResult]

RULES: list[RuleFunc] = [
    availability_rule,
    capacity_rule,
    rto_rule,
    rpo_rule,
    budget_rule,
    regional_resilience_rule,
    security_boundary_rule,
    deployment_rule,
    operational_complexity_rule,
]


def evaluate_rules(
    candidate: Candidate,
    normalized: NormalizedRequirements,
    failure_report: CandidateFailureReport,
    cost_estimates: dict[str, CostEstimate],
) -> list[RuleResult]:
    return [rule(candidate, normalized, failure_report, cost_estimates) for rule in RULES]
