from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aura.errors import AwsProviderError
from aura.providers.chaos import Boto3ChaosProvider, generate_synthetic_traffic


def _provider_with_clients(**clients):
    provider = Boto3ChaosProvider()

    class _FakeBoto3:
        def client(self, service, region_name=None):
            return clients[service]

    provider._boto3 = _FakeBoto3()
    return provider


def test_stop_one_task_targets_first_running_task():
    ecs = MagicMock()
    ecs.list_tasks.return_value = {"taskArns": ["arn:aws:ecs:ap-south-1:123:task/demo/abc"]}
    provider = _provider_with_clients(ecs=ecs)

    result = provider.stop_one_task(cluster="demo-cluster", region="ap-south-1")

    assert result.experiment == "terminate-disposable-task"
    assert result.target == "arn:aws:ecs:ap-south-1:123:task/demo/abc"
    ecs.stop_task.assert_called_once_with(
        cluster="demo-cluster",
        task="arn:aws:ecs:ap-south-1:123:task/demo/abc",
        reason="AURA controlled chaos experiment",
    )


def test_stop_one_task_raises_when_no_tasks_running():
    ecs = MagicMock()
    ecs.list_tasks.return_value = {"taskArns": []}
    provider = _provider_with_clients(ecs=ecs)

    with pytest.raises(AwsProviderError):
        provider.stop_one_task(cluster="demo-cluster", region="ap-south-1")
    ecs.stop_task.assert_not_called()


def test_deregister_one_target_targets_first_healthy_target():
    elbv2 = MagicMock()
    elbv2.describe_target_health.return_value = {
        "TargetHealthDescriptions": [{"Target": {"Id": "10.0.1.5", "Port": 80}}]
    }
    provider = _provider_with_clients(elbv2=elbv2)

    result = provider.deregister_one_target(target_group_arn="arn:tg", region="ap-south-1")

    assert result.experiment == "remove-healthy-target"
    elbv2.deregister_targets.assert_called_once_with(TargetGroupArn="arn:tg", Targets=[{"Id": "10.0.1.5", "Port": 80}])


def test_deregister_one_target_raises_when_no_targets():
    elbv2 = MagicMock()
    elbv2.describe_target_health.return_value = {"TargetHealthDescriptions": []}
    provider = _provider_with_clients(elbv2=elbv2)

    with pytest.raises(AwsProviderError):
        provider.deregister_one_target(target_group_arn="arn:tg", region="ap-south-1")


def test_generate_synthetic_traffic_counts_successes():
    fake_response = MagicMock()
    fake_response.status = 200
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)

    with patch("aura.providers.chaos.urllib.request.urlopen", return_value=fake_response):
        result = generate_synthetic_traffic("http://example.invalid/", duration_seconds=0.25, requests_per_second=10)

    assert result.requests_sent >= 1
    assert result.status_counts.get("200", 0) >= 1
    assert result.error_count == 0


def test_generate_synthetic_traffic_counts_connection_errors():
    import urllib.error

    with patch(
        "aura.providers.chaos.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = generate_synthetic_traffic("http://example.invalid/", duration_seconds=0.2, requests_per_second=10)

    assert result.error_count >= 1
    assert result.status_counts == {}
