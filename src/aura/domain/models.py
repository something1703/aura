"""Typed workload domain model.

This is the canonical shape of "what the business is asking for." Every
downstream engine (architecture, evaluation, failure, cost, reporting)
consumes a validated :class:`Workload`, never raw YAML.

Validation intentionally rejects (per docs/IMPLEMENTATION_PHASES.md):

- negative RTO/RPO;
- invalid percentage targets;
- peak traffic below average traffic;
- impossible budget formats;
- unknown consistency modes;
- empty application names.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from aura.domain.enums import ApplicationType, ConsistencyMode, DataClassification
from aura.domain.parsing import parse_currency_usd, parse_duration_seconds, parse_percentage

Percentage = Annotated[float, BeforeValidator(parse_percentage), Field(gt=0, le=100)]
UsdAmount = Annotated[float, BeforeValidator(parse_currency_usd), Field(gt=0)]


def _minutes_from_human_value(value: object) -> float:
    return parse_duration_seconds(value, assumed_unit_seconds=60) / 60


DurationMinutes = Annotated[float, BeforeValidator(_minutes_from_human_value), Field(ge=0)]


class AuraBaseModel(BaseModel):
    """Shared config: unknown fields are a validation error, not silently dropped."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Application(AuraBaseModel):
    name: str = Field(min_length=1)
    type: ApplicationType = ApplicationType.GENERIC
    stateful: bool = False

    @field_validator("name")
    @classmethod
    def _reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("application.name must not be empty")
        return value


class Traffic(AuraBaseModel):
    average_rps: float = Field(gt=0)
    peak_rps: float = Field(gt=0)
    peak_duration_minutes: float = Field(default=0, ge=0)
    growth_percent_per_month: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _peak_at_least_average(self) -> "Traffic":
        if self.peak_rps < self.average_rps:
            raise ValueError(
                f"traffic.peak_rps ({self.peak_rps}) must be >= "
                f"traffic.average_rps ({self.average_rps})"
            )
        return self


class Availability(AuraBaseModel):
    target: Percentage
    multi_az_required: bool = False


class Recovery(AuraBaseModel):
    rto_minutes: DurationMinutes
    rpo_minutes: DurationMinutes
    regional_disaster_required: bool = False


class Geography(AuraBaseModel):
    primary_regions: list[str] = Field(min_length=1)
    user_regions: list[str] = Field(default_factory=list)


class Budget(AuraBaseModel):
    monthly_usd: UsdAmount
    hard_limit: bool = False


class Deployment(AuraBaseModel):
    frequency_per_day: float = Field(default=0, ge=0)
    downtime_allowed: bool = True
    rollback_target_minutes: float | None = Field(default=None, ge=0)


class Security(AuraBaseModel):
    internet_facing: bool = False
    data_classification: DataClassification = DataClassification.INTERNAL
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True


class Compliance(AuraBaseModel):
    frameworks: list[str] = Field(default_factory=list)


class Assumption(AuraBaseModel):
    id: str
    statement: str
    confidence: float = Field(ge=0, le=1)


class Workload(AuraBaseModel):
    application: Application
    traffic: Traffic
    availability: Availability
    recovery: Recovery
    consistency: dict[str, ConsistencyMode] = Field(default_factory=dict)
    geography: Geography
    budget: Budget
    deployment: Deployment = Field(default_factory=Deployment)
    security: Security = Field(default_factory=Security)
    compliance: Compliance = Field(default_factory=Compliance)
    assumptions: list[Assumption] = Field(default_factory=list)

    @field_validator("consistency", mode="before")
    @classmethod
    def _validate_consistency_modes(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        unknown = {
            domain: mode
            for domain, mode in value.items()
            if mode not in {m.value for m in ConsistencyMode}
        }
        if unknown:
            raise ValueError(f"unknown consistency mode(s): {unknown}")
        return value
