"""Read-only CloudWatch metrics (Phase 3 runtime evidence).

Everything upstream of this module is ``MODELLED`` (graph reasoning) or, in
the chaos runner, ``SIMULATED`` (a controlled test was actually executed).
This is the first place in AURA that can produce ``MEASURED`` evidence
(docs/FAILURE_MODEL.md evidence policy) — real numbers pulled from a real,
deployed system, e.g. actual RDS cross-region replica lag versus the RPO
AURA's cost/failure model assumed.

Read-only (``get_metric_statistics``/``list_metrics`` only); boto3 stays an
optional, lazily-imported dependency, same as :mod:`aura.providers.aws`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, Field

from aura.errors import AwsProviderError


class MetricDatapoint(BaseModel):
    timestamp: str
    value: float
    unit: str


class MetricSeries(BaseModel):
    namespace: str
    metric_name: str
    dimensions: dict[str, str]
    statistic: str
    datapoints: list[MetricDatapoint] = Field(default_factory=list)

    @property
    def latest(self) -> float | None:
        if not self.datapoints:
            return None
        return sorted(self.datapoints, key=lambda d: d.timestamp)[-1].value


class ObservabilityProvider(Protocol):
    def get_metric(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str],
        statistic: str,
        minutes: int,
        region: str,
    ) -> MetricSeries: ...


class Boto3ObservabilityProvider:
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise AwsProviderError(
                "boto3 is not installed; run `pip install 'aura[aws]'` to use observability features"
            ) from exc
        self._boto3 = boto3

    def get_metric(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str],
        statistic: str = "Average",
        minutes: int = 15,
        region: str = "ap-south-1",
    ) -> MetricSeries:
        try:
            client = self._boto3.client("cloudwatch", region_name=region)
        except Exception as exc:  # noqa: BLE001 - boundary to an external, untyped API
            raise AwsProviderError(f"could not create cloudwatch client for {region}: {exc}") from exc

        end = datetime.now(UTC)
        start = end - timedelta(minutes=minutes)
        try:
            response = client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{"Name": k, "Value": v} for k, v in dimensions.items()],
                StartTime=start,
                EndTime=end,
                Period=60,
                Statistics=[statistic],
            )
        except Exception as exc:  # noqa: BLE001
            raise AwsProviderError(f"get_metric_statistics failed: {exc}") from exc

        datapoints = sorted(
            (
                MetricDatapoint(
                    timestamp=dp["Timestamp"].isoformat(),
                    value=dp[statistic],
                    unit=dp.get("Unit", ""),
                )
                for dp in response.get("Datapoints", [])
            ),
            key=lambda d: d.timestamp,
        )
        return MetricSeries(
            namespace=namespace,
            metric_name=metric_name,
            dimensions=dimensions,
            statistic=statistic,
            datapoints=datapoints,
        )
