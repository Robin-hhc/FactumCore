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


def test_revision_rejects_reusing_old_operation(harness):
    ref, _ = harness.view()
    result = harness.run(
        "candidate-revise",
        {
            "operation_id": "op",
            "previous_view_ref": ref,
            "revision_reason": "Returned for correction",
            "decisions": [],
        },
        expected=2,
    )
    assert result["diagnostics"][0]["code"] == "NEW_OPERATION_REQUIRED"


def test_revision_produces_new_view_and_requires_fresh_confirmation(harness):
    ref, bundle = harness.view()
    candidate = harness.write(
        ".build/candidates/revised.md", harness.card("revised", bundle)
    )
    result = harness.run(
        "candidate-revise",
        {
            "operation_id": "revision",
            "previous_view_ref": ref,
            "revision_reason": "Partial acceptance requires smaller exact view",
            "decisions": [
                {
                    "candidate_id": "revised",
                    "decision": "create",
                    "reason": "Explicit revision",
                    "card_inputs": [candidate],
                }
            ],
        },
    )
    assert (
        result["phase"] == "ready" and result["data"]["confirmation_required"] is True
    )
    assert harness.record(result["data"]["view_ref"])["operation_id"] == "revision"
    assert result["data"]["view_ref"] != ref
    assert not (harness.root / "knowledge").exists()
