from __future__ import annotations

import json

import pytest

from aura.errors import TerraformPlanError
from aura.providers.terraform import load_terraform_plan, parse_terraform_plan

_SAMPLE_PLAN = {
    "format_version": "1.2",
    "terraform_version": "1.6.0",
    "planned_values": {
        "root_module": {
            "resources": [
                {
                    "address": "aws_lb.main",
                    "mode": "managed",
                    "type": "aws_lb",
                    "name": "main",
                    "provider_name": "registry.terraform.io/hashicorp/aws",
                    "values": {"internal": False},
                }
            ],
            "child_modules": [
                {
                    "address": "module.compute",
                    "resources": [
                        {
                            "address": "module.compute.aws_instance.web[0]",
                            "type": "aws_instance",
                            "name": "web",
                            "provider_name": "registry.terraform.io/hashicorp/aws",
                            "values": {"availability_zone": "ap-south-1a"},
                        },
                        {
                            "address": "module.compute.aws_instance.web[1]",
                            "type": "aws_instance",
                            "name": "web",
                            "provider_name": "registry.terraform.io/hashicorp/aws",
                            "values": {"availability_zone": "ap-south-1b"},
                        },
                    ],
                    "child_modules": [],
                },
                {
                    "address": "module.data",
                    "resources": [
                        {
                            "address": "module.data.aws_db_instance.primary",
                            "type": "aws_db_instance",
                            "name": "primary",
                            "provider_name": "registry.terraform.io/hashicorp/aws",
                            "values": {"multi_az": True, "storage_encrypted": True},
                        }
                    ],
                    "child_modules": [],
                },
            ],
        }
    },
}


def test_parse_terraform_plan_flattens_nested_modules():
    desired = parse_terraform_plan(_SAMPLE_PLAN)
    addresses = {r.address for r in desired.resources}
    assert "aws_lb.main" in addresses
    assert "module.compute.aws_instance.web[0]" in addresses
    assert "module.data.aws_db_instance.primary" in addresses
    assert len(desired.of_type("aws_instance")) == 2
    assert len(desired.of_type("aws_db_instance")) == 1


def test_parse_terraform_plan_preserves_values():
    desired = parse_terraform_plan(_SAMPLE_PLAN)
    db = desired.of_type("aws_db_instance")[0]
    assert db.values["multi_az"] is True
    assert db.values["storage_encrypted"] is True


def test_parse_terraform_plan_requires_planned_values():
    with pytest.raises(TerraformPlanError):
        parse_terraform_plan({"format_version": "1.2"})


def test_load_terraform_plan_from_file(tmp_path):
    path = tmp_path / "tfplan.json"
    path.write_text(json.dumps(_SAMPLE_PLAN), encoding="utf-8")
    desired = load_terraform_plan(path)
    assert len(desired.resources) == 4


def test_load_terraform_plan_missing_file(tmp_path):
    with pytest.raises(TerraformPlanError):
        load_terraform_plan(tmp_path / "does-not-exist.json")


def test_load_terraform_plan_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TerraformPlanError):
        load_terraform_plan(path)
