"""New publication CLI behavior with exact authored synthetic business bytes."""

import importlib.util
import json
import os as os
from pathlib import Path
import shutil as shutil
import subprocess
import sys

import pytest as pytest
import yaml as yaml


SPEC = importlib.util.spec_from_file_location("publication_public_p7", Path(__file__).with_name("apply_p7.py"))
P6 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P6)
MANUAL_SPEC = importlib.util.spec_from_file_location("publication_manual_skills",
    P6.HELPER.ROOT / "himate/himate-knowledge-wifi-mp/evals/support/manual.py")
MANUAL = importlib.util.module_from_spec(MANUAL_SPEC)
MANUAL_SPEC.loader.exec_module(MANUAL)


def manual_pending(tmp_path):
    """Use real P1--P5 public entries, including authored plan and P4 review."""
    pipeline = MANUAL.ManualPipeline(tmp_path)
    operation = "manual-publication"
    pipeline.write("docs-raw/specs/manual.md", b"# Source\nCapture marker is a documented rule.\n")
    prepared = pipeline.call("knowledge-source", {"operation_id": operation}, "run")
    assert prepared["phase"] == "prepared"
    scan, material = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    bundle_ref = pipeline.record(material)["bundle_ref"]
    view = pipeline.view(operation, bundle_ref, "manual-rule", pipeline.card("manual-rule", pipeline.record(bundle_ref)),
                         scan_ref=scan, material_ref=material)
    pipeline.review(operation, view)
    record = pipeline.call("knowledge-source", {"operation_id": operation, "scan_ref": scan, "view_ref": view,
        "disposition_preview_ref": pipeline.record(view)["disposition_preview_ref"]}, "record")["data"]["ingest_record_ref"]
    return pipeline, {"operation_id": operation, "view_ref": view, "ingest_record_ref": record}


def publication_content(trial, operation="batch"):
    request = trial.content(operation, legacy_objects=False)
    ctx = trial.context(operation)
    view = trial.record(request["view_ref"])
    bundle = trial.record(".build/operations/" + operation + "-raw/capture.json")
    view.update(staged_objects=bundle.get("staged_objects", []), event_proposals=bundle.get("event_proposals", []),
                owned_files=ctx.owned_files())
    publication = P6.HELPER.load_contract("publication")
    view["publication_plan"] = publication.prepare_plan(ctx, view)
    view["content_digest"] = view["publication_plan"]["content_digest"]
    view = ctx.modules["records"].seal(view)
    raw = P6.HELPER.canonical(view)
    trial.write(request["view_ref"], raw)
    ctx.register_owned(request["view_ref"], raw)
    return request


def run_transport(trial, request, output, *, incoming=None):
    incoming = incoming or (trial.base / "transport-input.json")
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_bytes(P6.HELPER.canonical(request))
    # This helper deliberately tests the retained stage transport, not the
    # normal CLI presentation envelope used by all business journeys.
    return subprocess.run([sys.executable, str(trial.root / "knowledge.py"), "apply", "--legacy-transport",
        "--action", "batch", "--knowledge-root", str(trial.root), "--input", str(incoming), "--output", str(output)],
        capture_output=True, timeout=120)


def tree_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def assert_transport_denied(result, message):
    """Missing business inputs must never become the reason this test passes."""
    assert result.returncode == 2, result.stderr.decode(errors="replace")
    response = json.loads(result.stdout)
    assert response["status"] == "error"
    assert response["diagnostics"] == [{"code": "invalid_input", "message": message}]
