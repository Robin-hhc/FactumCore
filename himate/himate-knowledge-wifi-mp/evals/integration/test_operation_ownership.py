"""Owned staging files are explicit; unrelated operation files are never adopted."""

import importlib.util
import json
from pathlib import Path

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ownership_contracts", DOMAIN / "evals/support/contracts.py"
)
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
runtime = SUPPORT.module("runtime")
records = SUPPORT.module("records")
validation = SUPPORT.module("validation")


def context(root, operation="owned"):
    schemas = json.loads((DOMAIN / "governance/schemas/records.schema.json").read_bytes())
    return runtime.OperationContext(
        root, {"operation_id": operation},
        modules={"records": records, "validation": validation},
        rules={"schemas": {"record": schemas}},
        tool={"skill": "hs-fixture", "package_digest": "0" * 64,
              "requirements_digest": "0" * 64, "runtime": "fixture"},
        rules_digest="0" * 64,
    )


def test_save_records_only_this_operations_actual_staging_outputs(tmp_path):
    ctx = context(tmp_path)
    saved = ctx.seal({"purpose": "read_material"}, "artifact_manifest")
    ctx.save(ctx.base + "/material.json", saved)
    other = tmp_path / ".build/operations/other/unrelated.md"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"unrelated")
    ctx.save("logs/events/explicit.json", ctx.seal({"purpose": "independent_event"}, "artifact_manifest"))

    owned = ctx.owned_files()
    assert owned == [{"path": ctx.base + "/material.json",
                      "sha256": runtime.sha(runtime.canonical(saved)),
                      "bytes": len(runtime.canonical(saved)), "owner_operation_id": "owned"}]
    assert other.read_bytes() == b"unrelated"


def test_register_owned_rejects_other_operation_and_formal_assets(tmp_path):
    ctx = context(tmp_path)
    for ref in (".build/operations/other/a.md", "knowledge/rules/a.md", "../escape"):
        with pytest.raises(ValueError):
            ctx.register_owned(ref, b"unrelated")


def test_owned_fingerprint_does_not_silently_follow_later_edits(tmp_path):
    ctx = context(tmp_path)
    ref = ctx.base + "/draft.md"
    runtime.write_bytes(tmp_path, ref, b"reviewed")
    ctx.register_owned(ref, b"reviewed")
    (tmp_path / ref).write_bytes(b"changed after observation")
    assert ctx.owned_files()[0]["sha256"] == runtime.sha(b"reviewed")


def test_subcapture_still_registers_to_the_parent_operation(tmp_path):
    ctx = context(tmp_path)
    ctx.base += "/sources/capture"
    saved = ctx.seal({"purpose": "capture"}, "artifact_manifest")
    ctx.save(ctx.base + "/bundle.json", saved)
    assert ctx.owned_files()[0]["owner_operation_id"] == "owned"
    assert (tmp_path / ".build/operations/owned/owned-files.json").is_file()
    assert not (tmp_path / ctx.base / "owned-files.json").exists()


def test_repeated_save_has_the_same_ownership_observation(tmp_path):
    ctx = context(tmp_path)
    saved = ctx.seal({"purpose": "input"}, "artifact_manifest")
    ref = ctx.base + "/input.json"
    ctx.save(ref, saved)
    before = (tmp_path / ctx.base / "owned-files.json").read_bytes()
    ctx.save(ref, saved)
    assert (tmp_path / ctx.base / "owned-files.json").read_bytes() == before


def test_corrupt_ownership_ledger_is_not_a_cleanup_authority(tmp_path):
    ctx = context(tmp_path)
    ctx.save(ctx.base + "/input.json", ctx.seal({"purpose": "input"}, "artifact_manifest"))
    path = tmp_path / ctx.base / "owned-files.json"
    ledger = json.loads(path.read_bytes())
    ledger["files"][0]["path"] = ".build/operations/other/a.md"
    path.write_bytes(runtime.canonical(ledger))
    with pytest.raises(ValueError):
        ctx.owned_files()
