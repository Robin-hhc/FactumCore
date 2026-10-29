"""Live generations retain formal inputs rather than producer execution files."""

import importlib.util
import json
from pathlib import Path
import shutil

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("published_input_support", DOMAIN / "evals/contract_test_support.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
runtime, inputs = SUPPORT.module("runtime"), SUPPORT.module("input_snapshot")
staging, operations = SUPPORT.module("staging"), SUPPORT.module("source_operations")


def fixture(root):
    (root / "governance").mkdir()
    (root / "governance/framework.lock.yaml").write_bytes(b"explicit synthetic rules\n")
    source = root / "docs-raw/specs/source.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"# Frozen source\n")
    modules = {name: SUPPORT.module(name) for name in ("records", "validation", "source_resources", "source_operations")}
    ctx = runtime.OperationContext(root, {"operation_id": "batch", "source_id": "source",
        "source_path": "docs-raw/specs/source.md"}, modules=modules,
        rules={"schemas": {"record": json.loads((DOMAIN / "governance/schemas/records.schema.json").read_bytes())}},
        rules_digest=runtime.sha((root / "governance/framework.lock.yaml").read_bytes()),
        tool={"skill": "hs-fixture", "package_digest": "0" * 64, "requirements_digest": "0" * 64, "runtime": "fixture"})
    result, _ = operations.capture(ctx)
    bundle = ctx.record(result["bundle_ref"], "source_bundle")
    draft = ctx.base + "/draft.md"
    runtime.write_bytes(root, draft, b"authored draft differs from stable output\n")
    old = b"exact historical card\n"
    old_ref = ctx.base + "/old.md"
    runtime.write_bytes(root, old_ref, old)
    entry = staging.stage_bytes(ctx, "logs/evidence/published/cards/" + runtime.sha(old) + ".md", old, kind="card")
    bundle["staged_objects"].append(entry)
    prewrite = inputs.capture_inputs(ctx, bundle=bundle, material={"current_files": [],
        "adopted_objects": [{"path": draft}, {"path": old_ref}]})
    return ctx, bundle, prewrite, entry


def test_prewrite_recovers_only_explicit_staging_and_detects_changed_bytes(tmp_path):
    ctx, bundle, snapshot, _ = fixture(tmp_path)
    assert inputs.compare_inputs(ctx, snapshot)["unchanged"]
    source_entry = next(row for row in bundle["staged_objects"] if row["kind"] == "original")
    (tmp_path / source_entry["stage_ref"]).write_bytes(b"changed\n")
    assert not inputs.compare_inputs(ctx, snapshot)["unchanged"]


def test_published_inputs_survive_removal_of_all_producer_staging(tmp_path):
    ctx, bundle, prewrite, old = fixture(tmp_path)
    for row in bundle["staged_objects"]:
        runtime.write_bytes(tmp_path, row["final_ref"], runtime.fixed_bytes(tmp_path, row["stage_ref"]))
    snapshot = inputs.published_inputs(ctx, prewrite, staged_objects=bundle["staged_objects"])
    assert not snapshot["business_records"]
    assert old["final_ref"] in snapshot["adopted_objects"]
    assert all(not key.startswith(".build/") for key in snapshot["adopted_objects"])
    shutil.rmtree(tmp_path / ".build")
    assert inputs.compare_inputs(ctx, snapshot, stage="postwrite")["unchanged"]
    (tmp_path / old["final_ref"]).write_bytes(b"corrupt historical card\n")
    assert not inputs.compare_inputs(ctx, snapshot, stage="postwrite")["unchanged"]


def test_published_inputs_cannot_pretend_evidence_was_installed(tmp_path):
    ctx, bundle, prewrite, _ = fixture(tmp_path)
    with pytest.raises(runtime.NodeError) as error:
        inputs.published_inputs(ctx, prewrite, staged_objects=bundle["staged_objects"])
    assert error.value.code == "BATCH_INPUT_CHANGED"
