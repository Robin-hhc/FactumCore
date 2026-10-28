"""Public post-ingest document correction while the original bytes stay fixed."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("outcome", ["content", "skip"])
def test_unchanged_source_is_exempt_only_when_the_plan_actually_skips_it(outcome):
    spec = importlib.util.spec_from_file_location("post_ingest_public_contracts", ROOT / "himate-knowledge-wifi-mp/evals/contract_test_support.py")
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    module = support.module("review_inputs")
    plan = {"operation_id": "correction", "author_id": "author", "card_actions": [{"author_id": "author"}],
            "units": [{"unit_id": "u1", "outcome": outcome}], "scan_ref": "scan", "scan_digest": "a" * 64, "digest": "b" * 64}
    scan = {"operation_id": "correction", "digest": "a" * 64,
            "units": [{"unit_id": "u1", "change": "unchanged", "progress": "completed"}]}

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
    pipeline_spec = importlib.util.spec_from_file_location("post_ingest_installer", ROOT / "himate-knowledge-wifi-mp/evals/pipeline_harness.py")
    pipeline = importlib.util.module_from_spec(pipeline_spec)
    pipeline_spec.loader.exec_module(pipeline)
    frozen = pipeline.install_packages(tmp_path / "frozen-skills")
    harness.packages = frozen
    catalog = json.loads(harness.catalog.read_bytes())
    catalog["skills"] = {name: catalog["skills"][name] for name in pipeline.PUBLIC_SKILLS}
    for name, entry in catalog["skills"].items():
        entry.update(root=str(frozen / name), package_digest=fixture.package_hash(frozen / name))
    harness.catalog.write_bytes(canonical(catalog))
    (tmp_path / "config.yml").write_text(
        yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8"
    )
    return harness


def complete_document_operation(harness, operation, decision, statement, *, expected_change="unchanged"):
    scan_ref = harness.run("source-scan", {"operation_id": operation}, "scan")["data"]["scan_ref"]
    scan = harness.record(scan_ref)
    assert len(scan["units"]) == 1
    unit = scan["units"][0]
    reason = ("Revalidate unchanged document under current rules" if expected_change == "unfinished"
              else "Requested document wording correction")
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                    "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "content",
                    "reason": "Revalidate the affected Claim under the current rules"}
                   for row in scan.get("current_context", {}).get("affected_claims", [])]
    input_units = [unit["unit_id"]] + [row["unit_id"] for row in maintenance]
    material_request = {"operation_id": operation, "scan_ref": scan_ref}
    if decision == "update":
        assert unit["change"] == expected_change
        material_request.update(unit_ids=[unit["unit_id"]], candidate_card_ids=["rule"])
    material_ref = harness.run("source-prepare", material_request, "prepare")["data"]["material_ref"]
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
                   "reason": reason if decision == "update" else "New document knowledge"}],
        "maintenance_units": maintenance,
        "claim_changes": [{"unit_ids": input_units, "card_id": "rule", "claim_id": "rule-claim",
                           "action": decision, "before": "Synthetic fixture statement." if decision == "update" else None,
                           "after": statement, "conditions": "Synthetic design guidance only",
                           "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}],
                           "preserved": "Same assertion, applicability and source" if decision == "update" else "No old knowledge",
                           "reason": reason}],
        "card_actions": [{"card_id": "rule", "decision": decision, "author_id": "author",
                          "unit_ids": input_units, "reason": reason}],
        "target_queries": [{"id": "rule-query", "query": "Synthetic", "purpose": "guidance",
                            "required": ["rule"], "expected_claim_ids": ["rule#rule-claim"]}],
    }, "plan")["data"]["semantic_plan_ref"]
    card = harness.card("rule", bundle).replace(b"Synthetic fixture statement.", statement.encode())
    candidate = harness.write(f".build/operations/{operation}/candidate.md", card)
    view_ref = harness.run("view-materialize", {
        "operation_id": operation, "v3_required": True, "semantic_plan_ref": semantic,
        "bundle_ref": material["bundle_ref"],
        "decisions": [{"candidate_id": unit["unit_id"], "decision": decision,
                       "reason": reason, "card_inputs": [candidate]}],
    })["data"]["view_ref"]
    review_ref = harness.run("lint", {
        "operation_id": operation, "semantic_plan_ref": semantic, "view_ref": view_ref,
        "reviewer_id": "independent-reviewer", "independent_context": operation + "-review-context",
        "sampled_unit_ids": input_units, "unreviewed_unit_ids": [],
        "reason": "Read the exact candidate and unchanged original under current rules", "findings": [],
        "inputs": check_inputs,
    }, "review")["data"]["content_review_ref"]
    record_ref = harness.run("source-scan", {
        "operation_id": operation, "scan_ref": scan_ref, "view_ref": view_ref,
        "semantic_plan_ref": semantic,
        "disposition_preview_ref": harness.record(view_ref)["disposition_preview_ref"],
    }, "record")["data"]["ingest_record_ref"]
    batch = harness.run("apply", {
        "operation_id": operation, "v3_required": True, "view_ref": view_ref,
        "ingest_record_ref": record_ref,
        "check_inputs": check_inputs,
    }, "batch")
    assert batch["phase"] == "completed" and batch["data"]["activated"] is True
    applied, generation = batch["data"]["apply_result_ref"], batch["data"]["generation_ref"]
    search = harness.run("query", {"operation_id": operation + "-search", "query": "Synthetic", "purpose": "guidance"}, "search")["data"]
    assert search["matches"][0]["card_id"] == "rule"
    read = harness.run("query", {"operation_id": operation + "-read", "receipt_ref": search["receipt_ref"], "card_id": "rule"}, "read")["data"]
    assert read["generation_ref"] == search["generation_ref"]
    assert statement in (harness.root / "knowledge/rules/rule.md").read_text(encoding="utf-8")
    assert {claim["id"] for claim in read["claims"]} == {"rule-claim"}
    assert statement in read["claims"][0]["text"]
    assert read["card_digest"] == search["matches"][0]["card_digest"]
    return {"scan": scan, "view_ref": view_ref, "review_ref": review_ref, "generation_ref": generation,
            "apply_result_ref": applied}


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


def test_rules_upgrade_revalidates_identical_document_without_rewriting_old_acceptance(tmp_path):
    harness = frozen_harness(tmp_path)
    original = b"# Source\nSynthetic fixture statement for test readers.\n"
    harness.write("docs-raw/specs/source.md", original)
    first = complete_document_operation(harness, "old-rules", "create", "Synthetic fixture statement.")
    old_rules = harness.rules
    old_card = (harness.root / "knowledge/rules/rule.md").read_bytes()
    retained = {ref: (harness.root / ref).read_bytes() for ref in (
        "logs/operations/old-rules/journal.json", first["apply_result_ref"],
        "logs/ingest/old-rules.yaml", first["view_ref"], first["review_ref"], first["generation_ref"],
    )}

    # Change only an infrastructure comment in this isolated governance copy.
    contract = harness.root / "governance/contracts/indexing.py"
    contract.write_bytes(contract.read_bytes() + b"\n# Synthetic infrastructure-only rule upgrade.\n")
    lock_path = harness.root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_path.read_bytes())
    lock["files"]["contracts/indexing.py"]["sha256"] = hashlib.sha256(contract.read_bytes()).hexdigest()
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    harness.rules = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    assert harness.rules != old_rules

    refused = harness.run("query", {"operation_id": "old-active-rejected", "query": "Synthetic", "purpose": "guidance"}, "search", expected=2)
    assert refused["diagnostics"][0]["code"] == "STALE_RULES"
    refused = harness.run("apply", {"operation_id": "old-rules", "apply_result_ref": first["apply_result_ref"]}, "verify-result", expected=2)
    assert "rules identity mismatch" in refused["diagnostics"][0]["message"]
    rebuilt = harness.run("apply", {"operation_id": "new-rules-index"}, "index-build")
    assert harness.record(rebuilt["data"]["generation_ref"])["rules_digest"] == harness.rules

    second = complete_document_operation(
        harness, "new-rules", "update", "Synthetic fixture statement.", expected_change="unfinished"
    )
    assert (harness.root / "knowledge/rules/rule.md").read_bytes() == old_card
    assert (harness.root / "docs-raw/specs/source.md").read_bytes() == original
    for ref, raw in retained.items():
        assert (harness.root / ref).read_bytes() == raw
    applied = harness.record(second["apply_result_ref"])
    assert applied["rules_digest"] == harness.rules
    assert applied["operation_id"] == "new-rules"
    assert harness.record(second["review_ref"])["rules_digest"] == harness.rules
    assert harness.record(second["generation_ref"])["rules_digest"] == harness.rules
    active = harness.record("artifacts/indexes/local/active.json")
    assert active["rules_digest"] == harness.rules
    assert active["generation_ref"] == second["generation_ref"]
    assert second["generation_ref"] != first["generation_ref"]
