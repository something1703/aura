"""Shared types for the Phase 2 desired-vs-observed comparison.

``ObservedResource``/``AwsInventory`` come from :mod:`aura.providers.aws`
(read-only boto3 calls). ``TerraformResourceChange``/``DesiredState`` come
from :mod:`aura.providers.terraform` (parsing ``terraform show -json``
output — AURA never shells out to Terraform itself, per ADR-0003).
``ConformanceCheck``/``ConformanceReport`` are produced by
:mod:`aura.providers.conformance`, reusing :class:`~aura.domain.enums.RuleStatus`
so a conformance failure reads the same way an evaluation rule failure does.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aura.domain.enums import RuleStatus


class ObservedResource(BaseModel):
    kind: str  # compute | database | load_balancer | cache | queue
    id: str
    region: str
    az: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class AwsInventory(BaseModel):
    region: str
    availability_zones: list[str]
    resources: list[ObservedResource]

    def of_kind(self, kind: str) -> list[ObservedResource]:
        return [r for r in self.resources if r.kind == kind]


class TerraformResourceChange(BaseModel):
    address: str
    type: str
    name: str
    provider_name: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class DesiredState(BaseModel):
    resources: list[TerraformResourceChange]

    def of_type(self, terraform_type: str) -> list[TerraformResourceChange]:
        return [r for r in self.resources if r.type == terraform_type]


class ConformanceCheck(BaseModel):
    check_id: str
    description: str
    expected: Any
    observed: Any
    status: RuleStatus


class ConformanceReport(BaseModel):
    checks: list[ConformanceCheck]

    @property
    def passed(self) -> bool:
        return all(c.status != RuleStatus.FAIL for c in self.checks)
