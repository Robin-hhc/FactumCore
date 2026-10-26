"""Public post-ingest document correction while the original bytes stay fixed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("outcome", ["content", "skip"])
def test_unchanged_source_is_exempt_only_when_the_plan_actually_skips_it(outcome):
    scripts = ROOT / "skills/common/knowledge/hs-knowledge-change-plan/scripts"
    spec = importlib.util.spec_from_file_location("post_ingest_plan_v3", scripts / "plan_v3.py")
    module = importlib.util.module_from_spec(spec)
    support_spec = importlib.util.spec_from_file_location("post_ingest_plan_support", scripts / "support.py")
    support_module = importlib.util.module_from_spec(support_spec)
    with patch.dict(sys.modules, {support_spec.name: support_module}):
        support_spec.loader.exec_module(support_module)
        with patch.dict(sys.modules, {"support": support_module}):
            spec.loader.exec_module(module)
    plan = {"operation_id": "correction", "author_id": "author", "card_actions": [{"author_id": "author"}],
            "units": [{"unit_id": "u1", "outcome": outcome}], "scan_ref": "scan", "scan_digest": "a" * 64, "digest": "b" * 64}
    scan = {"digest": "a" * 64, "units": [{"unit_id": "u1", "change": "unchanged", "progress": "completed"}]}

    class Context:
        operation = "correction"
        base = ".build/operations/correction"

        def record(self, ref, kind):
            return {"plan": plan, "scan": scan}[ref]

        def seal(self, value, kind):
            return {**value, "record_kind": kind, "digest": "c" * 64}

        def save(self, ref, record):
            self.saved = record
            return ref

    context = Context()
    sampled = ["u1"] if outcome == "content" else []
    result, phase = module.content_review(context, {
        "semantic_plan_ref": "plan", "reviewer_id": "independent", "independent_context": "fresh-context",
        "sampled_unit_ids": sampled, "unreviewed_unit_ids": [], "reason": "Respect the authored content/skip decision", "findings": [],
    })
    assert phase == "reviewed"
    assert result["skip_sample"]["sampled_unit_ids"] == sampled
    assert context.saved["sampled_unit_ids"] == sampled


def frozen_harness(tmp_path):
    fixture_path = ROOT / "skills/common/knowledge/hs-knowledge-source-scan/tests/conftest.py"
    spec = importlib.util.spec_from_file_location("post_ingest_source_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = fixture.Harness(tmp_path)
    frozen = tmp_path / "frozen-skills"
    shutil.copytree(harness.packages, frozen, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    harness.packages = frozen
    catalog = json.loads(harness.catalog.read_bytes())
    for name, entry in catalog["skills"].items():
        entry.update(root=str(frozen / name), package_digest=fixture.package_hash(frozen / name))
    harness.catalog.write_bytes(canonical(catalog))
    (tmp_path / "config.yml").write_text(
        yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8"
    )
    return harness


def complete_document_operation(harness, operation, decision, statement):
    scan_ref = harness.run("source-scan", {"operation_id": operation}, "scan")["data"]["scan_ref"]
    scan = harness.record(scan_ref)
    assert len(scan["units"]) == 1
    unit = scan["units"][0]
    material_request = {"operation_id": operation, "scan_ref": scan_ref}
    if decision == "update":
        assert unit["change"] == "unchanged"
        material_request.update(unit_ids=[unit["unit_id"]], candidate_card_ids=["rule"])
    material_ref = harness.run("source-scan", material_request, "prepare")["data"]["material_ref"]
    material = harness.record(material_ref)
    check_inputs = {}
    if decision == "update":
        assert material["unit_ids"] == [unit["unit_id"]]
        old_card = next(row for row in material["candidates"] if row["card_id"] == "rule")
        check_inputs["historical_card_objects"] = {
            old_card["card_digest"]: str(harness.root / old_card["card_ref"])
        }
    bundle = harness.record(material["bundle_ref"])
    semantic = harness.run("change-plan", {
        "operation_id": operation, "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "author",
        "units": [{"unit_id": unit["unit_id"], "outcome": "content",
                   "reason": "User requested wording correction" if decision == "update" else "New document knowledge"}],
        "claim_changes": [{"unit_ids": [unit["unit_id"]], "card_id": "rule", "claim_id": "rule-claim",
                           "action": decision, "before": "Synthetic fixture statement." if decision == "update" else None,
                           "after": statement, "conditions": "Synthetic design guidance only",
                           "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}],
                           "preserved": "Same assertion, applicability and source; wording clarified" if decision == "update" else "No old knowledge",
                           "reason": "Clarify existing knowledge without changing its original"}],
        "card_actions": [{"card_id": "rule", "decision": decision, "author_id": "author",
                          "unit_ids": [unit["unit_id"]], "reason": "Requested document wording"}],
        "target_queries": [{"id": "rule-query", "query": "Synthetic", "purpose": "guidance",
                            "required": ["rule"], "expected_claim_ids": ["rule#rule-claim"]}],
    }, "plan")["data"]["semantic_plan_ref"]
    card = harness.card("rule", bundle).replace(b"Synthetic fixture statement.", statement.encode())
    candidate = harness.write(f".build/operations/{operation}/candidate.md", card)
    plan_ref = harness.run("change-plan", {
        "operation_id": operation, "v3_required": True, "semantic_plan_ref": semantic,
        "bundle_ref": material["bundle_ref"],
        "decisions": [{"candidate_id": unit["unit_id"], "decision": decision,
                       "reason": "Authored requested wording", "card_inputs": [candidate]}],
    })["data"]["plan_ref"]
    view_ref = harness.run("view-materialize", {"operation_id": operation, "plan_ref": plan_ref})["data"]["view_ref"]
    review_ref = harness.run("change-plan", {
        "operation_id": operation, "semantic_plan_ref": semantic, "view_ref": view_ref,
        "reviewer_id": "independent-reviewer", "independent_context": operation + "-review-context",
        "sampled_unit_ids": [unit["unit_id"]], "unreviewed_unit_ids": [],
        "reason": "Read the requested change, exact candidate and unchanged original", "findings": [],
    }, "review")["data"]["content_review_ref"]
    lint_ref = f".build/operations/{operation}/final-lint.json"
    lint_input = harness.write(f".build/operations/{operation}/lint-input.json", canonical({"view_ref": view_ref, "inputs": check_inputs}))
    lint = subprocess.run([
        sys.executable, str(harness.packages / "hs-knowledge-lint/scripts/cli.py"),
        "--knowledge-root", str(harness.root), "--rules-digest", harness.rules,
        "--input", str(harness.root / lint_input), "--output", str(harness.root / lint_ref),
    ], capture_output=True)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    record_ref = harness.run("source-scan", {
        "operation_id": operation, "scan_ref": scan_ref, "view_ref": view_ref, "lint_ref": lint_ref,
        "dispositions": [{"unit_id": unit["unit_id"], "action": decision, "reason": "Requested document wording",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": unit["observed_fingerprint"],
                          "progress": "completed", "card_refs": ["rule"], "claim_refs": ["rule#rule-claim"]}],
    }, "record")["data"]["ingest_record_ref"]
    applied = harness.run("apply", {
        "operation_id": operation, "v3_required": True, "view_ref": view_ref,
        "ingest_record_ref": record_ref, "lint_report_ref": lint_ref, "content_review_ref": review_ref,
        "check_inputs": check_inputs,
    })["data"]["apply_result_ref"]
    built = harness.run("index-build", {"operation_id": operation}, "build")["data"]
    generation = built["generation_ref"]
    harness.run("query-regression", {
        "operation_id": operation, "v3_required": True, "apply_result_ref": applied, "generation_ref": generation,
        "expected_active": built["expected_active"],
    })
    search = harness.run("query", {"operation_id": operation + "-search", "query": "Synthetic", "purpose": "guidance"}, "search")["data"]
    assert search["matches"][0]["card_id"] == "rule"
    read = harness.run("query", {"operation_id": operation + "-read", "receipt_ref": search["receipt_ref"], "card_id": "rule"}, "read")["data"]
    assert read["generation_ref"] == search["generation_ref"]
    assert statement in (harness.root / "knowledge/rules/rule.md").read_text(encoding="utf-8")
    assert {claim["id"] for claim in read["claims"]} == {"rule-claim"}
    assert statement in read["claims"][0]["text"]
    assert read["card_digest"] == search["matches"][0]["card_digest"]
    return {"scan": scan, "view_ref": view_ref, "review_ref": review_ref, "generation_ref": generation}


def test_user_can_correct_ingested_document_without_changing_original(tmp_path):
    harness = frozen_harness(tmp_path)
    original = b"# Source\nSynthetic fixture statement for test readers.\n"
    harness.write("docs-raw/specs/source.md", original)
    original_sha = hashlib.sha256(original).hexdigest()
    first = complete_document_operation(harness, "first", "create", "Synthetic fixture statement.")
    old_journal = (harness.root / "logs/operations/first/journal.json").read_bytes()
    old_result = (harness.root / "logs/operations/first/apply-result.json").read_bytes()
    old_record = (harness.root / "logs/ingest/first.yaml").read_bytes()
    assert harness.record("logs/operations/first/journal.json")["status"] == "committed"

    second = complete_document_operation(harness, "correction", "update", "Synthetic fixture statement for test readers.")
    assert first["view_ref"] != second["view_ref"]
    assert first["generation_ref"] != second["generation_ref"]
    assert harness.record(second["review_ref"])["sampled_unit_ids"] == [second["scan"]["units"][0]["unit_id"]]
    assert (harness.root / "logs/operations/first/journal.json").read_bytes() == old_journal
    assert (harness.root / "logs/operations/first/apply-result.json").read_bytes() == old_result
    assert (harness.root / "logs/ingest/first.yaml").read_bytes() == old_record
    assert (harness.root / "docs-raw/specs/source.md").read_bytes() == original
    assert hashlib.sha256((harness.root / "docs-raw/specs/source.md").read_bytes()).hexdigest() == original_sha
    assert "review_trust" not in json.loads(harness.catalog.read_bytes())
    assert not list(harness.root.rglob("confirmation-display.json"))
    assert not list(harness.root.rglob("manual-review.json"))
    assert not (harness.root / "logs/host-events").exists()
