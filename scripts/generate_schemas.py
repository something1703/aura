#!/usr/bin/env python3
"""Regenerate schemas/*.json from the Pydantic domain models.

These are a machine-readable contract for external tooling/editors; they are
derived, not hand-maintained. Re-run after changing Workload or Candidate.
"""

from __future__ import annotations

import json
from pathlib import Path

from aura.architecture.generator import Candidate
from aura.domain.models import Workload

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


def main() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    (SCHEMAS_DIR / "workload.schema.json").write_text(
        json.dumps(Workload.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (SCHEMAS_DIR / "architecture.schema.json").write_text(
        json.dumps(Candidate.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {SCHEMAS_DIR / 'workload.schema.json'}")
    print(f"wrote {SCHEMAS_DIR / 'architecture.schema.json'}")


if __name__ == "__main__":
    main()
