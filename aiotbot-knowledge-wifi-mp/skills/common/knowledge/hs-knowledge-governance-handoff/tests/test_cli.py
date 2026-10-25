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


def test_handoff_freezes_exact_view_and_stops_before_governance(harness):
    ref, _ = harness.view()
    result = harness.run("governance-handoff", {"operation_id": "op", "view_ref": ref})
    handoff = harness.record(result["data"]["handoff_ref"])
    assert handoff["view_ref"] == ref
    assert handoff["view_digest"] == harness.record(ref)["digest"]
    assert handoff["target_workflow"] == "hs-knowledge-ingest"
    assert handoff["target_phase"] == "P4"
    assert result["phase"] == "handed_off"
    assert not (harness.root / "knowledge").exists()
