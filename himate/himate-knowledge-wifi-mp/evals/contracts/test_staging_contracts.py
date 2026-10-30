"""Explicit per-operation staging; synthetic development-contract fixtures."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location("staging_support", Path(__file__).parents[1] / "support/contracts.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def modules():
    return helper.module("staging"), helper.module("runtime")


def context(root, operation="new"):
    return SimpleNamespace(root=root, operation=operation, base=".build/operations/" + operation)


def test_stage_is_explicit_and_does_not_publish(tmp_path):
    staging, runtime = modules()
    ref = "logs/evidence/published/objects/" + runtime.sha(b"exact") + ".bin"
    entry = staging.stage_bytes(context(tmp_path), ref, b"exact", kind="original")
    assert entry["stage_ref"].startswith(".build/operations/new/")
    assert not (tmp_path / "logs").exists()
    assert staging.read_bytes(tmp_path, ref, [entry]) == b"exact"
    with pytest.raises(FileNotFoundError):
        staging.read_bytes(tmp_path, ref)
    assert staging.merge_entries([entry], [entry]) == [entry]


def test_mapping_integrity_and_owner_are_checked(tmp_path):
    staging, runtime = modules()
    ref = "logs/evidence/published/objects/" + runtime.sha(b"exact") + ".bin"
    entry = staging.stage_bytes(context(tmp_path), ref, b"exact", kind="original")
    (tmp_path / entry["stage_ref"]).write_bytes(b"changed")
    with pytest.raises(runtime.NodeError) as failure:
        staging.read_bytes(tmp_path, ref, [entry])
    assert failure.value.code == "STAGED_OBJECT_CHANGED"
    with pytest.raises(runtime.NodeError) as failure:
        staging.validate_entries(tmp_path, [{**entry, "owner_operation_id": "other"}])
    assert failure.value.code == "STAGING_OWNER_MISMATCH"
    with pytest.raises(runtime.NodeError) as failure:
        staging.merge_entries([entry], [{**entry, "sha256": "f" * 64}])
    assert failure.value.code == "STAGING_CONFLICT"


@pytest.mark.parametrize("field,value", [
    ("stage_ref", ".build/operations/new/../other/x"),
    ("stage_ref", "logs/evidence/old.bin"),
    ("final_ref", ".build/operations/old/x"),
    ("bytes", True), ("sha256", "bad"),
])
def test_invalid_mapping_rejected(tmp_path, field, value):
    staging, runtime = modules()
    entry = staging.stage_bytes(context(tmp_path), "logs/evidence/published/objects/a.bin", b"exact", kind="original")
    with pytest.raises(runtime.NodeError):
        staging.validate_entries(tmp_path, [{**entry, field: value}])


def test_published_read_has_no_implicit_stage_fallback(tmp_path):
    staging, runtime = modules()
    ref = "logs/evidence/published/objects/" + runtime.sha(b"exact") + ".bin"
    entry = staging.stage_bytes(context(tmp_path, "abandoned"), ref, b"exact", kind="original")
    assert staging.entries_from_bundle({"staged_objects": [entry]}) == [entry]
    assert staging.entries_from_bundle({}) == []
    with pytest.raises(FileNotFoundError):
        staging.read_bytes(tmp_path, ref, [])


def test_two_absent_final_targets_cannot_alias_by_case(tmp_path):
    staging, runtime = modules()
    entry = staging.stage_bytes(context(tmp_path), "logs/evidence/published/objects/exact.bin", b"exact", kind="original")
    with pytest.raises(runtime.NodeError) as failure:
        staging.validate_entries(tmp_path, [entry, {**entry, "final_ref": entry["final_ref"].replace("exact.bin", "EXACT.bin")}])
    assert failure.value.code == "STAGING_CONFLICT"
