"""P2 public semantic-plan entry and explicit retirement of byte operations."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

def test_missing_request_returns_structured_error_without_creating_knowledge(tmp_path):
    cli = Path(__file__).resolve().parents[3] / "knowledge.py"
    response = tmp_path / "response.json"
    knowledge = tmp_path / "absent-knowledge"
    result = subprocess.run(
        [
            sys.executable,
            str(cli), "change-plan", "--json",
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
    record = json.loads(response.read_text(encoding="utf-8") if response.exists() else result.stdout)
    assert record["status"] == "error"
    assert record["diagnostics"]
    assert not knowledge.exists()



@pytest.mark.parametrize("action", [None, "run", "verify", "rederive"])
def test_old_byte_entry_is_explicitly_moved_to_p4(harness, action):
    result = harness.run("change-plan", {"operation_id": "op", "bundle_ref": "unused", "decisions": []}, action, expected=2)
    assert result["diagnostics"][0]["code"] == "BYTE_PRODUCTION_MOVED"


def test_independent_review_is_explicitly_moved_to_p5(harness):
    result = harness.run("change-plan", {"operation_id": "op"}, "review", expected=2)
    assert result["diagnostics"][0]["code"] == "CONTENT_REVIEW_MOVED"
