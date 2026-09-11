"""YAML loading for workload specifications.

Kept deliberately dumb: this module only turns a file on disk into a Python
dict. Structural/domain validation belongs to :mod:`aura.requirements.validator`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from aura.errors import WorkloadLoadError


def load_workload_document(path: str | Path) -> dict:
    """Read and parse a workload YAML file into a plain dict."""

    file_path = Path(path)
    if not file_path.exists():
        raise WorkloadLoadError(f"workload file not found: {file_path}")
    if not file_path.is_file():
        raise WorkloadLoadError(f"workload path is not a file: {file_path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkloadLoadError(f"could not read {file_path}: {exc}") from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkloadLoadError(f"invalid YAML in {file_path}: {exc}") from exc

    if document is None:
        raise WorkloadLoadError(f"workload file is empty: {file_path}")
    if not isinstance(document, dict):
        raise WorkloadLoadError(f"workload file must contain a YAML mapping at the top level: {file_path}")

    return document
