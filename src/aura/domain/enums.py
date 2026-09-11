"""Domain enumerations shared across AURA's engines.

Kept in one module so every engine (architecture, evaluation, failure, cost,
reporting) shares a single vocabulary instead of re-declaring status codes.
"""

from __future__ import annotations

from enum import StrEnum


class ApplicationType(StrEnum):
    ECOMMERCE = "ecommerce"
    FINTECH = "fintech"
    MEDIA_STREAMING = "media_streaming"
    SAAS = "saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PLATFORM = "data_platform"
    GENERIC = "generic"


class ConsistencyMode(StrEnum):
    STRONG = "strong"
    EVENTUAL = "eventual"


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RequirementPriority(StrEnum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"


class RuleStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class EvidenceType(StrEnum):
    MODELLED = "MODELLED"
    SIMULATED = "SIMULATED"
    MEASURED = "MEASURED"


class FailureEventType(StrEnum):
    INSTANCE_FAILURE = "INSTANCE_FAILURE"
    AZ_FAILURE = "AZ_FAILURE"
    REGION_FAILURE = "REGION_FAILURE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    NETWORK_DEGRADATION = "NETWORK_DEGRADATION"
    TRAFFIC_SPIKE = "TRAFFIC_SPIKE"
    BAD_DEPLOYMENT = "BAD_DEPLOYMENT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"


class BlastRadius(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FailureDomain(StrEnum):
    """Failure-domain hierarchy, narrowest to broadest (docs/FAILURE_MODEL.md)."""

    INSTANCE = "instance"
    AZ = "az"
    REGION = "region"
    PROVIDER = "provider"


class ScoringDimension(StrEnum):
    RELIABILITY = "reliability"
    SCALABILITY = "scalability"
    SECURITY = "security"
    PERFORMANCE = "performance"
    OPERATIONS = "operations"
    COST = "cost"
    COMPLEXITY = "complexity"
    SUSTAINABILITY = "sustainability"


class CostScenario(StrEnum):
    AVERAGE_LOAD = "average_load"
    PEAK_LOAD = "peak_load"
    SUSTAINED_PEAK = "sustained_peak"
    FAILURE_MODE = "failure_mode"


class CostConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
