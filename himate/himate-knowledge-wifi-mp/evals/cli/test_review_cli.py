"""The review entry retains the existing independent P4 data checks."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from support.pipeline import Pipeline, sha


def review_view(base, *, purpose="current"):
    flow = Pipeline(base)
    operation, card_id = "review-command", "review-rule"
    bundle_ref, bundle = flow.capture(operation, b"# Source\nCapture marker is an explicit synthetic rule.\n")
    view_ref = flow.view(operation, bundle_ref, card_id, flow.card(card_id, bundle), queries=[{
        "id": "find-review", "query": "capture", "purpose": purpose,
        "required": [card_id], "expected_claim_ids": [card_id + "#c1"],
    }])
    view = flow.record(view_ref)
    plan = flow.record(view["semantic_plan_ref"])
    request = {
        "operation_id": operation, "view_ref": view_ref,
        "semantic_plan_ref": view["semantic_plan_ref"],
        "reviewer_id": "synthetic-independent-reader", "independent_context": "fresh-synthetic-context",
        "sampled_unit_ids": [row["unit_id"] for row in plan["units"] + plan.get("maintenance_units", [])],
        "unreviewed_unit_ids": [], "reason": "Synthetic reader checked this exact selected candidate", "findings": [],
    }
    return flow, request


def invoke(root, *arguments):
    return subprocess.run([sys.executable, "-B", str(root / "knowledge.py"), "review", *arguments, "--json"],
                          env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, timeout=60)


def formal_bytes(root):
    return {path.relative_to(root).as_posix(): sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file() and path.relative_to(root).parts[0] != ".build"}


def test_review_command_reuses_existing_review_identity_and_full_checks(tmp_path):
    flow, request = review_view(tmp_path)
    before = formal_bytes(flow.root)
    legacy = flow.call("knowledge-lint", request, "review")
    review_ref = legacy["data"]["content_review_ref"]
    saved = (flow.root / review_ref).read_bytes()
    direct = flow.call("knowledge-review", request)
    explicit = flow.call("knowledge-review", request, "review")
    for result in (direct, explicit):
        assert result["status"] == "passed" and result["complete"] is True
        assert result["checks"] == legacy["checks"]
        assert result["review"] == legacy["review"]
        assert result["data"]["content_review_ref"] == review_ref
        assert result["data"]["fixed_checks_executed"] is True
        assert result["data"]["full_scope"] is True
    assert (flow.root / review_ref).read_bytes() == saved
    assert formal_bytes(flow.root) == before
    assert not (flow.root / "knowledge/rules/review-rule.md").exists()
    assert not (flow.root / "artifacts/indexes/local/active.json").exists()


def test_review_command_keeps_actual_query_failure_and_return_target(tmp_path):
    flow, request = review_view(tmp_path, purpose="implementation")
    before = formal_bytes(flow.root)
    result = flow.call("knowledge-review", request, expected=1)
    assert result["status"] == "failed"
    assert result["data"]["fixed_checks_executed"] is True
    assert result["data"]["return_to"] == ["P2"]
    assert any(row["code"] == "TARGET_QUERY_EXPECTATION_FAILED" for row in result["findings"])
    outcome = next(row for row in result["checks"] if row["check_id"] == "index.build")["candidate_queries"]["outcomes"][0]
    assert outcome["case_id"] == "find-review" and outcome["purpose"] == "implementation"
    assert outcome["actual"] == [] and outcome["actual_claim_ids"] == []
    assert formal_bytes(flow.root) == before


@pytest.mark.parametrize("arguments", [
    ["review"], ["check"], ["--action", "lint"], ["--action", "record-review"],
])
def test_review_command_cannot_select_an_unrelated_or_positional_action(tmp_path, arguments):
    flow = Pipeline(tmp_path)
    result = invoke(flow.root, *arguments)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ACTION"
    assert not (flow.root / ".build").exists()


def test_review_command_rejects_legacy_transport(tmp_path):
    flow = Pipeline(tmp_path)
    result = invoke(flow.root, "--legacy-transport")
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ARGUMENT"
    assert not (flow.root / ".build").exists()


def test_review_command_without_a_view_keeps_the_review_error_instead_of_formal_lint(tmp_path):
    flow = Pipeline(tmp_path)
    request = {"operation_id": "missing-review-view"}
    legacy = flow.call("knowledge-lint", request, "review", expected=2)
    direct = flow.call("knowledge-review", request, expected=2)
    assert direct["status"] == "error" and direct["phase"] == "invalid"
    assert direct["diagnostics"] == legacy["diagnostics"]
    assert direct["tool_identity"] == legacy["tool_identity"]
    assert not (flow.root / "knowledge").exists()
    assert not (flow.root / "artifacts").exists()


@pytest.mark.parametrize("reference", [
    ".build/operations/another/result.json", "logs/ingest/pretend-review.yaml",
])
def test_review_command_preserves_public_output_ownership(tmp_path, reference):
    flow = Pipeline(tmp_path)
    output = flow.root / reference
    result = invoke(flow.root, "--operation-id", "current", "--output", str(output))
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_OPERATION"
    assert not output.exists()


def test_review_command_executes_only_the_explicit_target_knowledge_root(tmp_path):
    first = Pipeline(tmp_path / "first")
    second, request = review_view(tmp_path / "second")
    incoming = second.base / "review-request.json"
    output = second.base / "review-result.json"
    incoming.write_text(json.dumps(request), encoding="utf-8")
    result = invoke(first.root, "--knowledge-root", str(second.root), "--input", str(incoming),
                    "--output", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    presentation = json.loads(result.stdout)
    report = json.loads(output.read_bytes())
    assert presentation["phase"] == report["phase"] == "passed"
    assert Path(presentation["cli_transport"]["knowledge_root"]) == second.root
    assert (second.root / report["data"]["content_review_ref"]).is_file()
    assert not (first.root / ".build").exists()
    assert not (first.root / "logs").exists()


def test_review_is_discoverable_in_public_command_help(tmp_path):
    flow = Pipeline(tmp_path)
    result = invoke(flow.root, "--help")
    assert result.returncode == 0
    assert "review" in result.stdout.decode("utf-8")
