"""Merge-time code evidence remains business data under lint's public entry."""

import importlib.util
from pathlib import Path

import pytest


_root = Path(__file__).resolve().parents[5]
_spec = importlib.util.spec_from_file_location(
    "merge_contract_test_support", _root / "himate-knowledge-wifi-mp/evals/contract_test_support.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
legacy = _helper.module("legacy_runtime")
engine = _helper.module("code_review")


def final_view(context, mode="code_gate"):
    ref = ".build/operations/op/view.json"
    view = context.record("final_view", "op", review_mode=mode,
        writes=[{"path": "knowledge/index.md", "expected_old_digest": None,
                 "final_digest": legacy.digest(b"new"), "bytes_b64": "bmV3"}], deletes=[],
        source_refs=[], plan_ref=".build/operations/op/plan.json", plan_digest="0" * 64,
        baseline_digest=legacy.digest({"files": {"knowledge/index.md": None}}))
    context.save(ref, view)
    return {"operation_id": "op", "view_ref": ref}


def test_missing_code_evidence_never_claims_a_passing_merge_check(tmp_path):
    context = legacy.Context.synthetic(tmp_path, "hs-knowledge-lint")
    result = engine.local_check(context, final_view(context), "merge")
    proof = context.read(result["merge_check_ref"])
    assert proof["record_kind"] == "merge_check" and proof["mode"] == "merge"
    assert result["check_status"] == proof["status"] == "incomplete"
    assert proof["gaps"] and not result.get("proof_verified", False)


def test_business_failure_is_retained_without_catalog_or_workflow_qualification(tmp_path, monkeypatch):
    context = legacy.Context.synthetic(tmp_path, "hs-knowledge-lint")
    request = final_view(context)

    def failure(*args, **kwargs):
        raise engine.Failed("specific business failure")

    monkeypatch.setattr(engine, "evaluate", failure)
    result = engine.local_check(context, {**request, "workflow": "harness metadata"}, "merge")
    proof = context.read(result["merge_check_ref"])
    assert result["check_status"] == proof["status"] == "failed"
    assert proof["gaps"] == ["specific business failure"]
    assert not (tmp_path / "logs/workflows").exists()


def test_public_code_recheck_reports_incomplete_directly_without_a_sibling_cli(harness):
    validation, runtime = _helper.module("validation"), _helper.module("runtime")
    context = legacy.Context(harness.root, harness.rules,
        runtime.tool_identity(harness.packages / "hs-knowledge-lint"), domain=validation,
        rules=validation.load_rules(harness.root, harness.rules))
    response = harness.run("lint", final_view(context), "code-recheck", expected=2)
    proof = harness.record(response["data"]["merge_check_ref"])
    assert response["phase"] == proof["status"] == "incomplete"
    assert response["data"]["mode"] == "merge"
    assert not list((harness.root / ".build/operations").glob("*/calls/*"))


def test_document_view_remains_exempt_from_merge_code_gate(tmp_path):
    context = legacy.Context.synthetic(tmp_path, "hs-knowledge-lint")
    with pytest.raises(legacy.Invalid, match="pure-document views are exempt"):
        engine.local_check(context, final_view(context, "manual_document"), "merge")
