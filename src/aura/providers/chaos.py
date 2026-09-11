"""Controlled failure experiments — the sanctioned first tier only.

docs/IMPLEMENTATION_PHASES.md "Controlled chaos":

    The first chaos experiments should be non-destructive and isolated:
    1. terminate a disposable task;
    2. remove one healthy target in a test environment;
    3. generate synthetic traffic;
    4. simulate a dependency timeout.
    Only later should multi-AZ or regional experiments be considered, and
    never in production without explicit authorization.

This module implements exactly 1, 2, and 3. (4 needs fault-injection support
inside the running application itself — nothing this demo's placeholder
container provides; documented as a gap in terraform/README.md.)

Unlike every other provider in :mod:`aura.providers`, ``stop_one_task`` and
``deregister_one_target`` are genuinely **mutating** AWS calls. Nothing here
runs from CI, nothing runs automatically, and the CLI (``aura chaos``)
refuses to run either without an explicit ``--confirm`` flag
(AGENTS.md "Human approval boundary": "introducing destructive failure
tests" requires human approval).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import BaseModel, Field

from aura.errors import AwsProviderError


class ChaosResult(BaseModel):
    experiment: str
    target: str
    action_taken: str
    region: str


class ChaosProvider(Protocol):
    def stop_one_task(self, cluster: str, region: str) -> ChaosResult: ...
    def deregister_one_target(self, target_group_arn: str, region: str) -> ChaosResult: ...


class Boto3ChaosProvider:
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise AwsProviderError(
                "boto3 is not installed; run `pip install 'aura[aws]'` to use chaos experiments"
            ) from exc
        self._boto3 = boto3

    def stop_one_task(self, cluster: str, region: str) -> ChaosResult:
        """Terminate one disposable ECS task.

        The service's desired_count is untouched, so the orchestrator
        replaces it — this *is* the docs' "terminate a disposable task"
        experiment, not an approximation of it.
        """

        client = self._boto3.client("ecs", region_name=region)
        try:
            tasks = client.list_tasks(cluster=cluster, desiredStatus="RUNNING").get("taskArns", [])
        except Exception as exc:  # noqa: BLE001
            raise AwsProviderError(f"list_tasks failed: {exc}") from exc
        if not tasks:
            raise AwsProviderError(f"no running tasks found in cluster {cluster}")

        target = tasks[0]
        try:
            client.stop_task(cluster=cluster, task=target, reason="AURA controlled chaos experiment")
        except Exception as exc:  # noqa: BLE001
            raise AwsProviderError(f"stop_task failed: {exc}") from exc

        return ChaosResult(
            experiment="terminate-disposable-task",
            target=target,
            action_taken="stop_task (orchestrator will replace it)",
            region=region,
        )

    def deregister_one_target(self, target_group_arn: str, region: str) -> ChaosResult:
        """Remove one healthy target from an ALB target group.

        Health checks mark it absent and the ALB routes around it; this does
        not terminate the underlying task/instance.
        """

        client = self._boto3.client("elbv2", region_name=region)
        try:
            health = client.describe_target_health(TargetGroupArn=target_group_arn)
        except Exception as exc:  # noqa: BLE001
            raise AwsProviderError(f"describe_target_health failed: {exc}") from exc

        targets = [t["Target"] for t in health.get("TargetHealthDescriptions", [])]
        if not targets:
            raise AwsProviderError(f"no registered targets found in {target_group_arn}")

        target = targets[0]
        try:
            client.deregister_targets(TargetGroupArn=target_group_arn, Targets=[target])
        except Exception as exc:  # noqa: BLE001
            raise AwsProviderError(f"deregister_targets failed: {exc}") from exc

        return ChaosResult(
            experiment="remove-healthy-target",
            target=str(target),
            action_taken="deregister_targets (ALB routes around it)",
            region=region,
        )


class SyntheticTrafficResult(BaseModel):
    url: str
    requests_sent: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    error_count: int
    min_latency_ms: float | None
    max_latency_ms: float | None
    avg_latency_ms: float | None


def generate_synthetic_traffic(
    url: str, *, duration_seconds: float = 30.0, requests_per_second: float = 2.0, timeout_seconds: float = 5.0
) -> SyntheticTrafficResult:
    """Non-destructive: plain HTTP GETs against a public endpoint.

    Unlike the two experiments above this needs no AWS permissions at all —
    it is ordinary outbound HTTP traffic, so it is not gated by --confirm.
    """

    interval = 1.0 / requests_per_second if requests_per_second > 0 else 1.0
    deadline = time.monotonic() + duration_seconds
    status_counts: dict[str, int] = {}
    latencies_ms: list[float] = []
    error_count = 0
    sent = 0

    while time.monotonic() < deadline:
        start = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                status_counts[str(response.status)] = status_counts.get(str(response.status), 0) + 1
        except urllib.error.HTTPError as exc:
            status_counts[str(exc.code)] = status_counts.get(str(exc.code), 0) + 1
        except (urllib.error.URLError, TimeoutError):
            error_count += 1
        else:
            latencies_ms.append((time.monotonic() - start) * 1000)
        sent += 1
        time.sleep(max(0.0, interval - (time.monotonic() - start)))

    return SyntheticTrafficResult(
        url=url,
        requests_sent=sent,
        status_counts=status_counts,
        error_count=error_count,
        min_latency_ms=round(min(latencies_ms), 1) if latencies_ms else None,
        max_latency_ms=round(max(latencies_ms), 1) if latencies_ms else None,
        avg_latency_ms=round(sum(latencies_ms) / len(latencies_ms), 1) if latencies_ms else None,
    )
