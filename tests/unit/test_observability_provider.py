from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from aura.providers.observability import Boto3ObservabilityProvider


@pytest.fixture
def fake_provider() -> Boto3ObservabilityProvider:
    provider = Boto3ObservabilityProvider()

    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Timestamp": datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc), "Average": 5.0, "Unit": "Seconds"},
            {"Timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), "Average": 3.0, "Unit": "Seconds"},
        ]
    }

    class _FakeBoto3:
        def client(self, service, region_name=None):
            assert service == "cloudwatch"
            return cloudwatch

    provider._boto3 = _FakeBoto3()
    return provider, cloudwatch


def test_get_metric_returns_sorted_datapoints(fake_provider):
    provider, _ = fake_provider
    series = provider.get_metric(
        namespace="AWS/RDS",
        metric_name="ReplicaLag",
        dimensions={"DBInstanceIdentifier": "aura-demo-secondary"},
        statistic="Average",
        minutes=30,
        region="ap-southeast-1",
    )
    assert series.namespace == "AWS/RDS"
    assert len(series.datapoints) == 2
    assert series.datapoints[0].timestamp < series.datapoints[1].timestamp
    assert series.latest == 5.0


def test_get_metric_passes_correct_dimensions(fake_provider):
    provider, cloudwatch = fake_provider
    provider.get_metric(
        namespace="AWS/ApplicationELB",
        metric_name="UnHealthyHostCount",
        dimensions={"TargetGroup": "targetgroup/aura-demo-primary-tg/abc"},
        region="ap-south-1",
    )
    call_kwargs = cloudwatch.get_metric_statistics.call_args.kwargs
    assert call_kwargs["Namespace"] == "AWS/ApplicationELB"
    assert call_kwargs["Dimensions"] == [
        {"Name": "TargetGroup", "Value": "targetgroup/aura-demo-primary-tg/abc"}
    ]


def test_latest_is_none_with_no_datapoints():
    from aura.providers.observability import MetricSeries

    series = MetricSeries(namespace="AWS/RDS", metric_name="ReplicaLag", dimensions={}, statistic="Average")
    assert series.latest is None
