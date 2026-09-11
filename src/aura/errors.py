"""Shared AURA exception types.

CLI commands catch these at the boundary and print a clean message instead of
a Python traceback; everything else should let them propagate.
"""

from __future__ import annotations


class AuraError(Exception):
    """Base class for all expected AURA errors."""


class WorkloadLoadError(AuraError):
    """The workload YAML file could not be read or parsed."""


class WorkloadValidationError(AuraError):
    """The workload document failed schema/domain validation."""

    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class TerraformPlanError(AuraError):
    """A `terraform show -json` file could not be read or parsed."""


class AwsProviderError(AuraError):
    """A read-only AWS call could not be completed (missing boto3, credentials, API error)."""
