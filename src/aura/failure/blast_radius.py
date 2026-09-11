"""Blast radius classification (docs/FAILURE_MODEL.md).

    LOW      — no declared business capability is impacted.
    MEDIUM   — exactly one non-core capability impacted (one bounded feature).
    HIGH     — more than one non-core capability impacted.
    CRITICAL — any core (core business path) capability is impacted.

A component is not "critical" merely because it sounds important — impact is
derived from which declared capabilities become unreachable, per
docs/IMPLEMENTATION_PHASES.md #8.
"""

from __future__ import annotations

from aura.domain.enums import BlastRadius
from aura.failure.scenarios import BusinessCapability


def classify(impacted_capabilities: list[BusinessCapability]) -> BlastRadius:
    if not impacted_capabilities:
        return BlastRadius.LOW
    if any(capability.core for capability in impacted_capabilities):
        return BlastRadius.CRITICAL
    if len(impacted_capabilities) > 1:
        return BlastRadius.HIGH
    return BlastRadius.MEDIUM
