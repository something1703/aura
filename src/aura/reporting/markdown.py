"""Render the full architecture report as Markdown (AGENT_REPORTER.md sections)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from aura import __version__
from aura.reporting.context import ReportContext
from aura.reporting.diagram import to_mermaid

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_report(ctx: ReportContext) -> str:
    diagram = to_mermaid(ctx.recommended_candidate.topology) if ctx.recommended_candidate else ""
    template = _env.get_template("report.md.j2")
    return template.render(ctx=ctx, diagram=diagram, aura_version=__version__)
