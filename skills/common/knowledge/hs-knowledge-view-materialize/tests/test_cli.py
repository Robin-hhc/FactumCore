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


def test_complete_stable_view_contains_card_navigation_and_lock(harness):
    ref, _ = harness.view()
    view = harness.record(ref)
    assert {write["path"] for write in view["writes"]} == {
        "knowledge/rules/new.md",
        "knowledge/rules/index.md",
        "governance/sources.lock.yaml",
    }
    assert (
        b"lifecycle: stable"
        in (
            harness.root / ".build/operations/op/final-view/knowledge/rules/new.md"
        ).read_bytes()
    )
    assert not (harness.root / "knowledge").exists()


def test_navigation_change_after_plan_requires_replan(harness):
    plan, _ = harness.plan()
    harness.write("knowledge/rules/index.md", b"Concurrent unrelated navigation edit\n")
    result = harness.run(
        "view-materialize", {"operation_id": "op", "plan_ref": plan}, expected=2
    )
    assert result["diagnostics"][0]["code"] == "BASELINE_CHANGED"
