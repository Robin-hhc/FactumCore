"""Public boundary tests; no real WiFi originals or human approvals."""

import json
import subprocess
import sys
from pathlib import Path


def test_missing_request_returns_structured_error_without_creating_knowledge(tmp_path):
    cli = Path(__file__).parents[1] / "scripts/cli.py"
    response = tmp_path / "response.json"
    knowledge = tmp_path / "absent-knowledge"
    result = subprocess.run(
        [
            sys.executable,
            str(cli),
            "--input",
            str(tmp_path / "missing.json"),
            "--output",
            str(response),
            "--knowledge-root",
            str(knowledge),
            "--rules-digest",
            "0" * 64,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    record = json.loads(response.read_text(encoding="utf-8"))
    assert record["status"] == "error"
    assert record["diagnostics"]
    assert not knowledge.exists()


def test_manual_candidate_routes_without_code_lint(harness):
    ref, _ = harness.view()
    result = harness.run("candidate-inspect", {"operation_id": "op", "view_ref": ref})
    assert result["phase"] == "manual_ready"
    assert result["data"]["review_mode"] == "manual_document"
    assert not (harness.root / "logs/local-checks").exists()


def test_displayed_byte_tamper_cannot_be_inspected_as_ready(harness):
    ref, _ = harness.view()
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", b"changed")
    result = harness.run(
        "candidate-inspect", {"operation_id": "op", "view_ref": ref}, expected=2
    )
    assert result["diagnostics"][0]["code"] == "FINAL_BYTES_CHANGED"


def test_resealed_view_cannot_drift_from_its_frozen_plan(harness):
    import base64
    import hashlib
    import json

    ref, _ = harness.view()
    view = harness.record(ref)
    write = next(w for w in view["writes"] if w["path"] == "knowledge/rules/new.md")
    raw = base64.b64decode(write["bytes_b64"]).replace(
        b"Synthetic fixture statement.", b"Altered proposed statement."
    )
    write["bytes_b64"] = base64.b64encode(raw).decode()
    write["final_digest"] = hashlib.sha256(raw).hexdigest()
    view.pop("digest")
    view["digest"] = hashlib.sha256(
        json.dumps(
            view, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    harness.write(
        ref,
        json.dumps(
            view, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode(),
    )
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", raw)
    result = harness.run(
        "candidate-inspect", {"operation_id": "op", "view_ref": ref}, expected=2
    )
    assert result["diagnostics"][0]["code"] == "OPERATION_CONFLICT"
    assert not (harness.root / "knowledge").exists()
