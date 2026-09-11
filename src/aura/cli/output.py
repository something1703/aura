"""Deterministic JSON rendering for CLI output.

Sorted keys + fixed indent so `aura ... | diff` against golden files is
stable across runs and machines (docs/TESTING.md golden-file tests).
"""

from __future__ import annotations

import json
from typing import Any


def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)
