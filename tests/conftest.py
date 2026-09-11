from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def base_workload_document() -> dict:
    """A minimal, valid workload document other tests can mutate."""

    return {
        "application": {"name": "checkout", "type": "ecommerce", "stateful": True},
        "traffic": {
            "average_rps": 100,
            "peak_rps": 1000,
            "peak_duration_minutes": 10,
            "growth_percent_per_month": 5,
        },
        "availability": {"target": "99.9%", "multi_az_required": True},
        "recovery": {
            "rto_minutes": 10,
            "rpo_minutes": 5,
            "regional_disaster_required": False,
        },
        "consistency": {"orders": "strong", "catalog": "eventual"},
        "geography": {"primary_regions": ["ap-south-1"], "user_regions": ["IN"]},
        "budget": {"monthly_usd": 5000, "hard_limit": False},
        "deployment": {
            "frequency_per_day": 5,
            "downtime_allowed": True,
            "rollback_target_minutes": 5,
        },
        "security": {
            "internet_facing": True,
            "data_classification": "confidential",
            "encryption_at_rest": True,
            "encryption_in_transit": True,
        },
    }


@pytest.fixture
def workload_document() -> dict:
    return base_workload_document()


@pytest.fixture
def flash_commerce_path() -> Path:
    return REPO_ROOT / "config" / "flash-commerce.yaml"
