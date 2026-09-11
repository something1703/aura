"""Render a candidate topology as a Mermaid flowchart for embedding in reports.

Solid arrows are critical dependencies; dashed arrows are non-critical
(graceful-degradation) dependencies — this mirrors exactly what the failure
simulator treats as critical vs. not.
"""

from __future__ import annotations

from aura.domain.graph import Graph


def _safe_id(component_id: str) -> str:
    return component_id.replace("-", "_")


def to_mermaid(graph: Graph) -> str:
    lines = ["flowchart LR"]
    for component in graph.components:
        regions = ", ".join(sorted(component.regions)) or "n/a"
        label = f"{component.id} ({component.kind})\\n{regions}"
        lines.append(f'    {_safe_id(component.id)}["{label}"]')
    for component in graph.components:
        for dependency_id in component.depends_on:
            arrow = "-->" if component.is_dependency_critical(dependency_id) else "-.->"
            lines.append(f"    {_safe_id(component.id)} {arrow} {_safe_id(dependency_id)}")
    return "\n".join(lines)
