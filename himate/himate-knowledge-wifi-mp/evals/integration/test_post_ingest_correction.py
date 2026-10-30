"""Public post-ingest document correction while the original bytes stay fixed."""

from support.correction import frozen_harness, complete_document_operation
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[4]




@pytest.mark.parametrize("outcome", ["content", "skip"])
def test_unchanged_source_is_exempt_only_when_the_plan_actually_skips_it(outcome):
    spec = importlib.util.spec_from_file_location("post_ingest_public_contracts", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py")
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






def test_user_can_correct_ingested_document_without_changing_original(tmp_path):
    harness = frozen_harness(tmp_path)
    original = b"# Source\nSynthetic fixture statement for test readers.\n"
    harness.write("docs-raw/specs/source.md", original)
    original_sha = hashlib.sha256(original).hexdigest()
    first = complete_document_operation(harness, "first", "create", "Synthetic fixture statement.")
    old_publication = (harness.root / first["publication_ref"]).read_bytes()
    old_completion = (harness.root / first["completion_ref"]).read_bytes()
    old_result = (harness.root / first["apply_result_ref"]).read_bytes()
    old_record = (harness.root / "logs/ingest/first.yaml").read_bytes()
    assert harness.record(first["apply_result_ref"])["status"] == "committed"
    assert harness.record(first["publication_ref"])["reviewed_view_digest"] == first["reviewed_view"]["digest"]
    assert harness.record(first["completion_ref"])["batch_complete"] is True
    old_journal_ref = ".build/operations/first/transaction/journal.json"
    assert not (harness.root / old_journal_ref).exists()
    assert not (harness.root / first["view_ref"]).exists()
    assert not (harness.root / first["review_ref"]).exists()

    second = complete_document_operation(harness, "correction", "update", "Synthetic fixture statement for test readers.")
    assert first["view_ref"] != second["view_ref"]
    assert first["generation_ref"] != second["generation_ref"]
    assert second["review"]["sampled_unit_ids"] == [second["scan"]["units"][0]["unit_id"]]
    assert (harness.root / first["publication_ref"]).read_bytes() == old_publication
    assert (harness.root / first["completion_ref"]).read_bytes() == old_completion
    assert (harness.root / first["apply_result_ref"]).read_bytes() == old_result
    assert not (harness.root / old_journal_ref).exists()
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
        first["publication_ref"], first["completion_ref"], first["apply_result_ref"],
        "logs/ingest/old-rules.yaml", first["generation_ref"],
    )}
    assert first["review"]["rules_digest"] == old_rules
    assert harness.record(first["publication_ref"])["reviewed_view_digest"] == first["reviewed_view"]["digest"]
    assert not (harness.root / first["view_ref"]).exists()
    assert not (harness.root / first["review_ref"]).exists()
    assert not (harness.root / ".build/operations/old-rules/transaction/journal.json").exists()

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
    assert refused["diagnostics"][0]["code"] == "STALE_RULES"
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
    assert second["review"]["rules_digest"] == harness.rules
    assert harness.record(second["generation_ref"])["rules_digest"] == harness.rules
    active = harness.record("artifacts/indexes/local/active.json")
    assert active["rules_digest"] == harness.rules
    assert active["generation_ref"] == second["generation_ref"]
    assert second["generation_ref"] != first["generation_ref"]
