"""The record command is a narrow public entry over the existing P5 engine."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from support.pipeline import Pipeline


def pending_view(base):
    flow = Pipeline(base)
    operation = "record-command"
    flow.capture(operation, b"# Source\nA synthetic source needs more authoritative material.\n")
    prepared = flow.prepared[operation]
    inventory = flow.record(prepared["scan_ref"])
    plan = flow.call("knowledge-change-plan", {
        "operation_id": operation,
        "scan_ref": prepared["scan_ref"],
        "material_ref": prepared["material_ref"],
        "author_id": "synthetic-author",
        "units": [{"unit_id": unit["unit_id"], "outcome": "defer",
                   "reason": "Authoritative material is not available",
                   "owner": "synthetic-owner", "next_step": "Acquire exact material"}
                  for unit in inventory["units"]],
        "claim_changes": [], "card_actions": [], "target_queries": [],
    }, "plan")["data"]
    view = flow.call("knowledge-view-materialize", {
        "operation_id": operation, "semantic_plan_ref": plan["semantic_plan_ref"], "decisions": [],
    }, "run")["data"]
    return flow, {"operation_id": operation, "view_ref": view["view_ref"]}


def invoke(root, *arguments):
    return subprocess.run([sys.executable, "-B", str(root / "knowledge.py"), "record", *arguments, "--json"],
                          env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, timeout=60)


def test_record_command_reuses_the_existing_record_bytes_and_pending_semantics(tmp_path):
    flow, request = pending_view(tmp_path)
    old = flow.call("knowledge-source", request, "record")
    record_ref = old["data"]["ingest_record_ref"]
    before = (flow.root / record_ref).read_bytes()
    direct = flow.call("knowledge-record", request)
    repeated = flow.call("knowledge-record", request, "record")
    assert direct == repeated == old
    assert (flow.root / record_ref).read_bytes() == before
    record = flow.record(record_ref)
    assert direct["phase"] == "recorded"
    assert record["status"] == "pending" and record["batch_kind"] == "record_only"
    assert record["dispositions"][0]["action"] == "defer"
    assert record["dispositions"][0]["progress"] == "blocked"
    assert record["authored_units"][0]["next_step"] == "Acquire exact material"
    assert not (flow.root / "logs/ingest").exists()
    assert not (flow.root / "artifacts").exists()


@pytest.mark.parametrize("arguments", [
    ["scan"], ["record"], ["--action", "prepare"], ["--action", "status"],
])
def test_record_command_cannot_select_an_unrelated_source_action(tmp_path, arguments):
    flow = Pipeline(tmp_path)
    result = invoke(flow.root, *arguments)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ACTION"
    assert not (flow.root / ".build").exists()


@pytest.mark.parametrize("reference", [
    ".build/operations/another/result.json", "logs/ingest/pretend-record.yaml",
])
def test_record_command_preserves_public_output_ownership(tmp_path, reference):
    flow = Pipeline(tmp_path)
    output = flow.root / reference
    result = invoke(flow.root, "--operation-id", "current", "--output", str(output))
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_OPERATION"
    assert not output.exists()


def test_record_command_executes_only_the_explicit_target_knowledge_root(tmp_path):
    first = Pipeline(tmp_path / "first")
    second, request = pending_view(tmp_path / "second")
    incoming = second.base / "record-request.json"
    output = second.base / "record-result.json"
    incoming.write_text(json.dumps(request), encoding="utf-8")
    result = invoke(first.root, "--knowledge-root", str(second.root), "--input", str(incoming),
                    "--output", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    presentation = json.loads(result.stdout)
    record = json.loads(output.read_bytes())
    assert presentation["phase"] == record["phase"] == "recorded"
    assert Path(presentation["cli_transport"]["knowledge_root"]) == second.root
    assert (second.root / record["data"]["ingest_record_ref"]).is_file()
    assert not (first.root / ".build").exists()
    assert not (first.root / "logs").exists()


def test_record_command_cannot_create_a_missing_target_for_its_error_output(tmp_path):
    flow = Pipeline(tmp_path)
    missing = tmp_path / "absent-knowledge"
    result = invoke(flow.root, "--knowledge-root", str(missing),
                    "--output", str(missing / ".build/diagnostic.json"))
    assert result.returncode == 2
    assert not missing.exists()
