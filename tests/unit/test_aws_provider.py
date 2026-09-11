from __future__ import annotations

import builtins
from unittest.mock import MagicMock

import pytest

from aura.errors import AwsProviderError
from aura.providers.aws import Boto3AwsProvider, collect_inventory


class _FakeBoto3:
    def __init__(self, clients: dict[str, MagicMock]) -> None:
        self._clients = clients

    def client(self, service: str, region_name: str | None = None):
        return self._clients[service]


def _paginated(client: MagicMock, pages: list[dict]) -> None:
    paginator = MagicMock()
    paginator.paginate.return_value = pages
    client.get_paginator.return_value = paginator


@pytest.fixture
def fake_provider() -> Boto3AwsProvider:
    provider = Boto3AwsProvider()

    ec2 = MagicMock()
    ec2.describe_availability_zones.return_value = {
        "AvailabilityZones": [{"ZoneName": "ap-south-1b"}, {"ZoneName": "ap-south-1a"}]
    }
    _paginated(
        ec2,
        [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-111",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running"},
                                "Placement": {"AvailabilityZone": "ap-south-1a"},
                            },
                            {
                                "InstanceId": "i-222",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "terminated"},
                                "Placement": {"AvailabilityZone": "ap-south-1b"},
                            },
                        ]
                    }
                ]
            }
        ],
    )

    rds = MagicMock()
    _paginated(
        rds,
        [
            {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-1",
                        "MultiAZ": True,
                        "StorageEncrypted": True,
                        "Engine": "postgres",
                        "AvailabilityZone": "ap-south-1a",
                    }
                ]
            }
        ],
    )

    elbv2 = MagicMock()
    _paginated(
        elbv2,
        [
            {
                "LoadBalancers": [
                    {
                        "LoadBalancerArn": "arn:aws:elasticloadbalancing:lb/main",
                        "Scheme": "internet-facing",
                        "AvailabilityZones": [{"ZoneName": "ap-south-1a"}, {"ZoneName": "ap-south-1b"}],
                    }
                ]
            }
        ],
    )

    elasticache = MagicMock()
    _paginated(
        elasticache,
        [{"CacheClusters": [{"CacheClusterId": "cache-1", "Engine": "redis", "PreferredAvailabilityZone": "ap-south-1a"}]}],
    )

    provider._boto3 = _FakeBoto3(
        {"ec2": ec2, "rds": rds, "elbv2": elbv2, "elasticache": elasticache}
    )
    return provider


def test_describe_availability_zones_sorted(fake_provider):
    assert fake_provider.describe_availability_zones("ap-south-1") == ["ap-south-1a", "ap-south-1b"]


def test_describe_instances_excludes_terminated(fake_provider):
    instances = fake_provider.describe_instances("ap-south-1")
    assert len(instances) == 1
    assert instances[0].id == "i-111"
    assert instances[0].az == "ap-south-1a"
    assert instances[0].kind == "compute"


def test_describe_db_instances_maps_multi_az_and_encryption(fake_provider):
    databases = fake_provider.describe_db_instances("ap-south-1")
    assert len(databases) == 1
    assert databases[0].attributes["multi_az"] is True
    assert databases[0].attributes["storage_encrypted"] is True


def test_describe_load_balancers_maps_azs(fake_provider):
    load_balancers = fake_provider.describe_load_balancers("ap-south-1")
    assert load_balancers[0].attributes["availability_zones"] == ["ap-south-1a", "ap-south-1b"]


def test_describe_cache_clusters(fake_provider):
    clusters = fake_provider.describe_cache_clusters("ap-south-1")
    assert clusters[0].kind == "cache"
    assert clusters[0].id == "cache-1"


def test_collect_inventory_aggregates_all_resource_kinds(fake_provider):
    inventory = collect_inventory(fake_provider, "ap-south-1")
    assert inventory.region == "ap-south-1"
    assert inventory.availability_zones == ["ap-south-1a", "ap-south-1b"]
    assert len(inventory.of_kind("compute")) == 1
    assert len(inventory.of_kind("database")) == 1
    assert len(inventory.of_kind("load_balancer")) == 1
    assert len(inventory.of_kind("cache")) == 1


def test_boto3_missing_raises_clean_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("no module named boto3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(AwsProviderError):
        Boto3AwsProvider()
