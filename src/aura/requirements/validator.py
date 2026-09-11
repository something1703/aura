"""Schema/domain validation: raw dict -> validated :class:`Workload`."""

from __future__ import annotations

from pydantic import ValidationError

from aura.domain.models import Workload
from aura.errors import WorkloadValidationError


def validate_workload(document: dict) -> Workload:
    """Validate a raw workload document, raising a clean error on failure."""

    try:
        return Workload.model_validate(document)
    except ValidationError as exc:
        details = [
            "{}: {}".format(".".join(str(part) for part in error["loc"]), error["msg"])
            for error in exc.errors()
        ]
        raise WorkloadValidationError(
            f"workload failed validation ({len(details)} issue(s))", details=details
        ) from exc
