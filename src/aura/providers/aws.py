"""Read-only AWS inventory (Phase 2, docs/AWS_INTEGRATION.md).

Every method here is a ``describe_*``/``list_*`` call — nothing in this
module creates, modifies, or deletes AWS resources (ADR-0003, SECURITY.md).
boto3 is an optional dependency (the ``aura[aws]`` extra) and is imported
lazily so Phase 1 usage never needs it installed.

Domain/evaluation code must never import boto3 directly
(docs/ARCHITECTURE.md "Dependency rule") — it goes through
:class:`AwsProvider` instead, which is why this module returns the
provider-agnostic :class:`~aura.providers.models.ObservedResource`, not raw
boto3 response dicts.
"""

from __future__ import annotations

from typing import Any, Protocol

from aura.errors import AwsProviderError
from aura.providers.models import AwsInventory, ObservedResource


class AwsProvider(Protocol):
    def describe_availability_zones(self, region: str) -> list[str]: ...
    def describe_instances(self, region: str) -> list[ObservedResource]: ...
    def describe_ecs_tasks(self, region: str) -> list[ObservedResource]: ...
    def describe_db_instances(self, region: str) -> list[ObservedResource]: ...
    def describe_load_balancers(self, region: str) -> list[ObservedResource]: ...
    def describe_cache_clusters(self, region: str) -> list[ObservedResource]: ...


class Boto3AwsProvider:
    """Read-only boto3-backed provider using the standard AWS credential chain."""

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise AwsProviderError(
                "boto3 is not installed; run `pip install 'aura[aws]'` to use AWS inventory"
            ) from exc
        self._boto3 = boto3

    def _client(self, service: str, region: str) -> Any:
        try:
            return self._boto3.client(service, region_name=region)
        except Exception as exc:  # botocore raises many distinct error types here
            raise AwsProviderError(f"could not create {service} client for {region}: {exc}") from exc

    def _call(self, description: str, fn, *args, **kwargs) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - boundary to an external, untyped API
            raise AwsProviderError(f"{description} failed: {exc}") from exc

    def describe_availability_zones(self, region: str) -> list[str]:
        client = self._client("ec2", region)
        response = self._call(
            "describe_availability_zones",
            client.describe_availability_zones,
            Filters=[{"Name": "region-name", "Values": [region]}],
        )
        return sorted(az["ZoneName"] for az in response.get("AvailabilityZones", []))

    def describe_instances(self, region: str) -> list[ObservedResource]:
        client = self._client("ec2", region)
        resources: list[ObservedResource] = []
        paginator = client.get_paginator("describe_instances")
        for page in self._call("describe_instances", lambda: list(paginator.paginate())):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    if instance.get("State", {}).get("Name") == "terminated":
                        continue
                    resources.append(
                        ObservedResource(
                            kind="compute",
                            id=instance["InstanceId"],
                            region=region,
                            az=instance.get("Placement", {}).get("AvailabilityZone"),
                            attributes={
                                "instance_type": instance.get("InstanceType"),
                                "state": instance.get("State", {}).get("Name"),
                            },
                        )
                    )
        return resources

    def describe_ecs_tasks(self, region: str) -> list[ObservedResource]:
        """Fargate/ECS compute — invisible to describe_instances since it isn't EC2."""

        client = self._client("ecs", region)
        resources: list[ObservedResource] = []

        clusters_response = self._call("list_clusters", client.list_clusters)
        for cluster_arn in clusters_response.get("clusterArns", []):
            task_arns: list[str] = []
            paginator = client.get_paginator("list_tasks")
            for page in self._call(
                "list_tasks",
                lambda p=paginator, c=cluster_arn: list(p.paginate(cluster=c, desiredStatus="RUNNING")),
            ):
                task_arns.extend(page.get("taskArns", []))

            if not task_arns:
                continue

            described = self._call("describe_tasks", client.describe_tasks, cluster=cluster_arn, tasks=task_arns)
            for task in described.get("tasks", []):
                resources.append(
                    ObservedResource(
                        kind="compute",
                        id=task["taskArn"],
                        region=region,
                        az=task.get("availabilityZone"),
                        attributes={
                            "cluster": cluster_arn.split("/")[-1],
                            "last_status": task.get("lastStatus"),
                            "launch_type": task.get("launchType"),
                        },
                    )
                )
        return resources

    def describe_db_instances(self, region: str) -> list[ObservedResource]:
        client = self._client("rds", region)
        resources: list[ObservedResource] = []
        paginator = client.get_paginator("describe_db_instances")
        for page in self._call("describe_db_instances", lambda: list(paginator.paginate())):
            for db in page.get("DBInstances", []):
                resources.append(
                    ObservedResource(
                        kind="database",
                        id=db["DBInstanceIdentifier"],
                        region=region,
                        az=db.get("AvailabilityZone"),
                        attributes={
                            "multi_az": db.get("MultiAZ", False),
                            "storage_encrypted": db.get("StorageEncrypted", False),
                            "engine": db.get("Engine"),
                        },
                    )
                )
        return resources

    def describe_load_balancers(self, region: str) -> list[ObservedResource]:
        client = self._client("elbv2", region)
        resources: list[ObservedResource] = []
        paginator = client.get_paginator("describe_load_balancers")
        for page in self._call("describe_load_balancers", lambda: list(paginator.paginate())):
            for lb in page.get("LoadBalancers", []):
                azs = [z["ZoneName"] for z in lb.get("AvailabilityZones", [])]
                resources.append(
                    ObservedResource(
                        kind="load_balancer",
                        id=lb["LoadBalancerArn"],
                        region=region,
                        az=None,
                        attributes={"availability_zones": azs, "scheme": lb.get("Scheme")},
                    )
                )
        return resources

    def describe_cache_clusters(self, region: str) -> list[ObservedResource]:
        client = self._client("elasticache", region)
        resources: list[ObservedResource] = []
        paginator = client.get_paginator("describe_cache_clusters")
        for page in self._call("describe_cache_clusters", lambda: list(paginator.paginate())):
            for cluster in page.get("CacheClusters", []):
                resources.append(
                    ObservedResource(
                        kind="cache",
                        id=cluster["CacheClusterId"],
                        region=region,
                        az=cluster.get("PreferredAvailabilityZone"),
                        attributes={"engine": cluster.get("Engine")},
                    )
                )
        return resources


def collect_inventory(provider: AwsProvider, region: str) -> AwsInventory:
    """Safe resource discovery only (docs/AWS_INTEGRATION.md Step 2)."""

    resources: list[ObservedResource] = []
    resources.extend(provider.describe_instances(region))
    resources.extend(provider.describe_ecs_tasks(region))
    resources.extend(provider.describe_db_instances(region))
    resources.extend(provider.describe_load_balancers(region))
    resources.extend(provider.describe_cache_clusters(region))
    availability_zones = provider.describe_availability_zones(region)
    return AwsInventory(region=region, availability_zones=availability_zones, resources=resources)
