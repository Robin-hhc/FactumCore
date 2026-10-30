"""Real source algorithms over isolated staging fixtures."""
import json
import pytest
import yaml
from support.staging import (runtime, operations, materials, resources, validation, make_context, write, formal)

def test_capture_new_and_changed_only_stage_and_freeze_event_proposal(tmp_path):
    source = "docs-raw/specs/source.md"
    write(tmp_path, source, b"# First\n")
    before = formal(tmp_path)
    first, _ = operations.capture(make_context(tmp_path, "first", source_path=source, source_id="source"))
    assert formal(tmp_path) == before
    old = json.loads((tmp_path / first["bundle_ref"]).read_bytes())
    write(tmp_path, "governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0",
          "resources": old["resources"], "snapshots": old["snapshots"]}).encode())
    write(tmp_path, source, b"# Changed\n")
    before = formal(tmp_path)
    changed, _ = operations.capture(make_context(tmp_path, "second", source_path=source, source_id="source"))
    bundle = json.loads((tmp_path / changed["bundle_ref"]).read_bytes())
    assert formal(tmp_path) == before
    assert changed["event_refs"] == [] and len(bundle["event_proposals"]) == 1
    assert bundle["event_proposals"][0]["source_lock_digest"] == before["governance/sources.lock.yaml"]
    assert all(row["stage_ref"].startswith(".build/operations/second/") for row in bundle["staged_objects"])
    assert all(row["final_ref"].startswith("logs/evidence/published/") for row in bundle["staged_objects"])
    assert resources.recover_snapshot(tmp_path, bundle["snapshots"][0], staged_objects=bundle["staged_objects"]) == b"# Changed\n"
    with pytest.raises(validation.ContractError):
        resources.recover_snapshot(tmp_path, bundle["snapshots"][0])


def test_prepare_child_capture_stays_in_same_operation(tmp_path):
    write(tmp_path, "docs-raw/specs/source.md", b"# Source\n")
    write(tmp_path, "governance/sources.lock.yaml", b"schema_version: '2.0'\nresources: []\nsnapshots: []\n")
    write(tmp_path, "governance/framework.lock.yaml", b"synthetic rules identity\n")
    ctx = make_context(tmp_path, "batch", targets=[{"source_path": "docs-raw/specs/source.md"}])
    ctx.args.rules_digest = runtime.sha((tmp_path / "governance/framework.lock.yaml").read_bytes())
    before = formal(tmp_path)
    output, _ = materials.prepare(ctx)
    assert formal(tmp_path) == before
    material = json.loads((tmp_path / output["material_ref"]).read_bytes())
    child_ref = material["bundles"][0]["bundle_ref"]
    assert child_ref.startswith(".build/operations/batch/sources/")
    assert json.loads((tmp_path / child_ref).read_bytes())["operation_id"] == "batch"
    assert {p.name for p in (tmp_path / ".build/operations").iterdir()} == {"batch"}


def test_existing_snapshot_keeps_old_fields_and_published_hash_recovers(tmp_path):
    source, raw = "docs-raw/specs/source.md", b"# Frozen\n"
    write(tmp_path, source, raw)
    output, _ = operations.capture(make_context(tmp_path, "seed", source_path=source, source_id="source"))
    old = json.loads((tmp_path / output["bundle_ref"]).read_bytes())
    snapshot = old["snapshots"][0]
    snapshot["recovery"] = {"method": "evidence_object", "path": "logs/evidence/objects/legacy.bin", "status": "available"}
    snapshot["extraction"]["text_ref"] = "logs/evidence/extractions/legacy.txt"
    snapshot["locator"]["reference"] = "logs/evidence/locators/legacy.json"
    snapshot["extraction"]["locator_ref"] = snapshot["locator"]["reference"]
    write(tmp_path, "governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0",
          "resources": old["resources"], "snapshots": [snapshot]}).encode())
    output, _ = operations.capture(make_context(tmp_path, "again", source_path=source, source_id="source"))
    bundle = json.loads((tmp_path / output["bundle_ref"]).read_bytes())
    assert bundle["snapshots"] == [snapshot]
    assert resources.recover_snapshot(tmp_path, snapshot, staged_objects=bundle["staged_objects"]) == raw
    # Simulate only the explicit P6 mapped object publication; remove current raw.
    for row in bundle["staged_objects"]:
        write(tmp_path, row["final_ref"], (tmp_path / row["stage_ref"]).read_bytes())
    (tmp_path / source).unlink()
    assert resources.recover_snapshot(tmp_path, snapshot) == raw
    ref = {"evidence_ref": "source", "source_id": "source", "snapshot_id": snapshot["snapshot_id"],
           "locator": {"kind": "lines", "start": 1, "end": 1}}
    result = operations.resolve_source(make_context(tmp_path, "reader"), ref)
    assert result["text"] == "# Frozen\n"
