"""Exact directory bindings survive only where unfinished local work needs them."""

import copy
import json
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("dbox_snapshot_cases", Path(__file__).resolve().parents[2] / "support/stages/apply_publication.py")
publication_cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publication_cases)


@pytest.fixture
def external_case(tmp_path):
    ctx, _, _, _ = publication_cases.publication_case.__wrapped__(tmp_path)
    source = tmp_path / "external"
    source.mkdir()
    (source / "a.md").write_bytes(b"# External\nExact first version.\n")
    config = ctx.root / "docs-raw/sources/dbox.local.yml"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"schema_version": "1.0", "path": str(source)}), encoding="utf-8")
    logical = "docs-raw/sources/dbox/a.md"
    observed = ctx.modules["source_resources"].read_dbox(ctx.root, logical)
    entry = {"kind": "external_raw", "path": logical, "sha256": observed["sha256"],
             "bytes": observed["bytes"], "dbox_binding": observed["dbox_binding"]}
    inputs = publication_cases.HELPER.load_contract("input_snapshot")
    snapshot = inputs.capture_inputs(ctx, material={"current_files": [entry]})
    return ctx, inputs, source, config, entry, snapshot


def test_current_snapshot_detects_same_bytes_in_a_different_root(external_case):
    ctx, inputs, source, config, _, snapshot = external_case
    replacement = source.with_name("replacement")
    replacement.mkdir()
    (replacement / "a.md").write_bytes((source / "a.md").read_bytes())
    config.write_text(json.dumps({"schema_version": "1.0", "path": str(replacement)}), encoding="utf-8")
    result = inputs.compare_inputs(ctx, snapshot)
    assert result["unchanged"] is False
    assert any(row["group"] == "current_files" for row in result["changes"])


def test_published_inputs_drop_execution_guard_but_local_index_keeps_it(external_case):
    ctx, inputs, source, config, entry, snapshot = external_case
    published = inputs.published_inputs(ctx, snapshot)
    assert inputs.source_execution_files(published) == {}
    assert str(source) not in json.dumps(published)
    scope = inputs.execution_scope({entry["path"]: entry})
    local = inputs.execution_inputs(ctx, published, {entry["path"]: entry}, scope)
    assert inputs.source_execution_files(local) == {entry["path"]: entry}
    config.unlink()
    assert inputs.compare_inputs(ctx, published, stage="postwrite")["unchanged"] is True
    assert inputs.compare_inputs(ctx, local, stage="postwrite")["unchanged"] is False


@pytest.mark.parametrize("fault", ["empty", "different_hash", "extra"])
def test_execution_scope_cannot_lose_or_replace_private_entries(external_case, fault):
    ctx, inputs, _, _, entry, snapshot = external_case
    published = inputs.published_inputs(ctx, snapshot)
    original = {entry["path"]: entry}
    scope = inputs.execution_scope(original)
    files = copy.deepcopy(original)
    if fault == "empty":
        files.clear()
    elif fault == "different_hash":
        files[entry["path"]]["sha256"] = "0" * 64
    else:
        other = copy.deepcopy(entry)
        other["path"] = "docs-raw/sources/dbox/other.md"
        files[other["path"]] = other
    with pytest.raises(ValueError, match="bindings"):
        inputs.execution_inputs(ctx, published, files, scope)


def test_unbound_virtual_path_cannot_be_used_as_an_ordinary_current_file(external_case):
    ctx, inputs, _, _, entry, _ = external_case
    with pytest.raises(ValueError, match="binding"):
        inputs.capture_inputs(ctx, material={"current_files": [{"path": entry["path"], "sha256": entry["sha256"]}]})
