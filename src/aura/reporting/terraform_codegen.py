"""Generate real Terraform files from an AURA :class:`Candidate`.

Closes the loop the project previously left open: `terraform/environments/
flash-commerce/` was hand-written by reading one recommendation once — if
the workload changed and AURA recommended something else, that Terraform
would sit there unchanged until a human rewrote it. This module renders the
*same* topology data the analysis already computed
(``candidate.topology``, ``candidate.primary_region``, ...) into Terraform,
so regenerating after a workload change produces infrastructure that
actually matches the new decision.

Deliberately not a black box: :func:`build_terraform_context` is the one
place that turns a Candidate into Terraform inputs, and every value it
derives can be traced back to a specific piece of the candidate's topology
or the workload's normalized requirements — nothing here re-decides
anything the evaluation engine didn't already decide.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from aura.architecture.generator import Candidate
from aura.cost.estimates import RPS_PER_TASK
from aura.domain.graph import Component
from aura.requirements.normalizer import NormalizedRequirements

_TEMPLATE_DIR = Path(__file__).parent / "templates" / "terraform"
_TEMPLATES = ["providers.tf.j2", "variables.tf.j2", "main.tf.j2", "outputs.tf.j2"]


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _az_count(component: Component | None, region: str | None) -> int:
    if component is None or region is None:
        return 0
    return len({i.az for i in component.instances if i.region == region})


def _task_count(rps: float) -> int:
    return max(1, math.ceil(rps / RPS_PER_TASK))


def build_terraform_context(candidate: Candidate, normalized: NormalizedRequirements) -> dict[str, Any]:
    """Derive every Terraform input from the candidate's actual topology."""

    topology = candidate.topology
    compute = topology.component("compute")
    database = topology.component("database")
    cache = topology.component("cache")
    queue = topology.component("queue")
    has_cdn_or_router = topology.component("cdn") is not None or topology.component("global-router") is not None

    primary_az_count = _az_count(compute, candidate.primary_region)
    secondary_az_count = _az_count(compute, candidate.secondary_region)
    db_secondary_az_count = _az_count(database, candidate.secondary_region)
    cache_secondary_az_count = _az_count(cache, candidate.secondary_region)

    peak_tasks = _task_count(normalized.peak_rps.value)
    # Same secondary-capacity ratio the cost engine derives from the
    # topology (0 for active-passive, partial for warm-standby, full for
    # active-active) — reused here rather than re-guessed.
    secondary_ratio = (secondary_az_count / primary_az_count) if candidate.multi_region and primary_az_count else 0.0

    return {
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "workload_name": normalized.application_name,
        "primary_region": candidate.primary_region,
        "secondary_region": candidate.secondary_region,
        "is_multi_region": candidate.multi_region,
        "primary_az_count": primary_az_count,
        "secondary_az_count": secondary_az_count,
        "primary_desired_count": peak_tasks,
        "secondary_desired_count": round(peak_tasks * secondary_ratio),
        "has_cache": cache is not None,
        "has_secondary_cache": cache_secondary_az_count > 0,
        "has_queue": queue is not None,
        "has_cdn_or_router": has_cdn_or_router,
        "database_multi_az_secondary": db_secondary_az_count > 1,
        "peak_rps": normalized.peak_rps.value,
        "rps_per_task": RPS_PER_TASK,
    }


def generate_terraform_files(candidate: Candidate, normalized: NormalizedRequirements) -> dict[str, str]:
    """Render the full root module (providers/variables/main/outputs).

    Returns ``{filename: content}`` — write these under
    ``terraform/environments/<name>/`` to keep the relative
    ``../../modules/...`` source paths the templates emit correct.
    """

    context = build_terraform_context(candidate, normalized)
    env = _jinja_env()
    return {
        template_name.removesuffix(".j2"): env.get_template(template_name).render(**context)
        for template_name in _TEMPLATES
    }
