"""Cost estimation types.

docs/COST_MODEL.md: every estimate carries service/unit/quantity/utilization/
unit_price/assumption/confidence, and AURA must never present an estimate as
an invoice. Unit prices in :mod:`aura.cost.estimates` are illustrative,
generic USD figures — not a live AWS pricing feed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aura.domain.enums import CostConfidence, CostScenario


class CostLineItem(BaseModel):
    service: str
    unit: str
    quantity: float
    utilization: float | None = None
    unit_price_usd: float
    monthly_cost_usd: float
    assumption: str
    confidence: CostConfidence


class CostEstimate(BaseModel):
    candidate_id: str
    scenario: CostScenario
    line_items: list[CostLineItem] = Field(default_factory=list)
    total_monthly_usd: float
    confidence: CostConfidence
