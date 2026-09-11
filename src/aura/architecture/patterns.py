"""Architecture pattern catalog entries.

Each :class:`PatternDefinition` is a typed, known pattern (never an
arbitrarily generated graph) per docs/IMPLEMENTATION_PHASES.md. ``supports``
values are the pattern's *deliverable envelope*: the best availability/RTO/RPO
it can plausibly provide. Eligibility (aura.evaluation) requires the pattern's
envelope to meet or beat the workload's requirement.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PatternSupport(BaseModel):
    availability_min: float = Field(description="Best-case availability percentage this pattern delivers.")
    rto_max_seconds: float = Field(description="Worst-case recovery time this pattern delivers.")
    rpo_max_seconds: float = Field(description="Worst-case data loss window this pattern delivers.")


class PatternDefinition(BaseModel):
    id: str
    name: str
    description: str
    supports: PatternSupport
    requires: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    failure_modes_tolerated: list[str] = Field(default_factory=list)
    multi_region: bool
    regional_resilience: bool
    primary_az_count: int = 3
    secondary_az_count: int = 0
