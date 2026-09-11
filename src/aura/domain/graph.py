"""Generic typed graph used to represent a candidate architecture's topology.

Per docs/IMPLEMENTATION_PHASES.md the generator "does not generate arbitrary
graph structures" — it instantiates known, typed components (compute,
database, cache, queue, load balancer, CDN, global router) at a coarse tier
granularity. This keeps candidate generation, failure simulation, and blast
radius classification deterministic and testable.

Redundancy is modelled physically: a :class:`Component` has one
:class:`Instance` per (AZ, region) placement. A component survives a failure
as long as at least one of its instances survives; the failure simulator
(``aura.failure.simulator``) uses this directly instead of walking an
abstract redundancy-group concept.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Instance(BaseModel):
    az: str
    region: str


class Component(BaseModel):
    id: str
    kind: str
    instances: list[Instance]
    depends_on: list[str] = Field(default_factory=list)
    critical_dependency: dict[str, bool] = Field(default_factory=dict)
    replication: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def azs(self) -> set[str]:
        return {instance.az for instance in self.instances}

    @property
    def regions(self) -> set[str]:
        return {instance.region for instance in self.instances}

    def is_multi_az(self) -> bool:
        return len(self.azs) > 1

    def is_multi_region(self) -> bool:
        return len(self.regions) > 1

    def instances_in(self, *, region: str | None = None, az: str | None = None) -> list[Instance]:
        return [
            instance
            for instance in self.instances
            if (region is None or instance.region == region) and (az is None or instance.az == az)
        ]

    def is_dependency_critical(self, dependency_id: str) -> bool:
        return self.critical_dependency.get(dependency_id, True)


class Graph(BaseModel):
    components: list[Component]

    def component(self, component_id: str) -> Component | None:
        return next((c for c in self.components if c.id == component_id), None)

    def dependents_of(self, component_id: str) -> list[Component]:
        """Components that declare a dependency on ``component_id``."""

        return [c for c in self.components if component_id in c.depends_on]

    @property
    def regions(self) -> set[str]:
        regions: set[str] = set()
        for component in self.components:
            regions |= component.regions
        regions.discard("global")
        return regions
