from __future__ import annotations

import pytest

from aura.errors import WorkloadLoadError
from aura.requirements.loader import load_workload_document


def test_loads_flash_commerce_example(flash_commerce_path):
    document = load_workload_document(flash_commerce_path)
    assert document["application"]["name"] == "flash-commerce"


def test_missing_file_raises(tmp_path):
    with pytest.raises(WorkloadLoadError):
        load_workload_document(tmp_path / "does-not-exist.yaml")


def test_empty_file_raises(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(WorkloadLoadError):
        load_workload_document(path)


def test_non_mapping_document_raises(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(WorkloadLoadError):
        load_workload_document(path)


def test_invalid_yaml_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("application: [unclosed\n", encoding="utf-8")
    with pytest.raises(WorkloadLoadError):
        load_workload_document(path)
