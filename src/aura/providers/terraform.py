"""Parse `terraform show -json` output into a :class:`DesiredState`.

Per ADR-0003 / docs/AWS_INTEGRATION.md, AURA never shells out to Terraform
and never calls ``terraform apply``: this module only reads a JSON file the
developer already produced with ``terraform plan -out=tfplan && terraform
show -json tfplan > tfplan.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aura.errors import TerraformPlanError
from aura.providers.models import DesiredState, TerraformResourceChange


def _collect_resources(module: dict[str, Any]) -> list[TerraformResourceChange]:
    resources = [
        TerraformResourceChange(
            address=resource["address"],
            type=resource["type"],
            name=resource["name"],
            provider_name=resource.get("provider_name"),
            values=resource.get("values", {}),
        )
        for resource in module.get("resources", [])
    ]
    for child_module in module.get("child_modules", []):
        resources.extend(_collect_resources(child_module))
    return resources


def parse_terraform_plan(plan: dict[str, Any]) -> DesiredState:
    root_module = plan.get("planned_values", {}).get("root_module")
    if root_module is None:
        raise TerraformPlanError(
            "no planned_values.root_module found; expected `terraform show -json` output"
        )
    return DesiredState(resources=_collect_resources(root_module))


def load_terraform_plan(path: str | Path) -> DesiredState:
    file_path = Path(path)
    if not file_path.exists():
        raise TerraformPlanError(f"terraform plan file not found: {file_path}")
    try:
        plan = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TerraformPlanError(f"could not read/parse {file_path}: {exc}") from exc
    return parse_terraform_plan(plan)
