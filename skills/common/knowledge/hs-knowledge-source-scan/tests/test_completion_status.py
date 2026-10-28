"""Public CLI recovery facts; synthetic sources never imply semantic acceptance."""

import pytest


def applied_batch(harness, *, fault_after=None, with_record=True):
    operation = "batch"
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic evidence.\n")
    scanned = harness.run("source-scan", {"operation_id": operation}, "scan")["data"]
    scan = harness.record(scanned["scan_ref"])
    unit = scan["units"][0]
    bundle_ref = harness.run("source-capture", {"operation_id": operation,
        "source_path": unit["path"], "source_id": unit["source_id"]})["data"]["bundle_ref"]
    candidate = harness.write(".build/candidates/new.md", harness.card("new", harness.record(bundle_ref)))
    plan = harness.run("change-plan", {"operation_id": operation, "bundle_ref": bundle_ref,
        "decisions": [{"candidate_id": "new", "decision": "create", "reason": "Synthetic recovery fixture",
                       "card_inputs": [candidate]}]})["data"]["plan_ref"]
    view = harness.run("view-materialize", {"operation_id": operation, "plan_ref": plan})["data"]["view_ref"]
    record = harness.run("source-scan", {
        "operation_id": operation, "scan_ref": scanned["scan_ref"], "view_ref": view,
        "dispositions": [{"unit_id": unit["unit_id"], "action": "create", "reason": "Synthetic recovery fixture",
                          "observed_fingerprint": unit["observed_fingerprint"],
                          "adopted_fingerprint": unit["observed_fingerprint"], "progress": "completed",
                          "card_refs": ["new"], "claim_refs": ["new#new-claim"]}],
    }, "record")["data"]["ingest_record_ref"] if with_record else None
    harness.run("apply", {"operation_id": operation, "view_ref": view,
                          **({"ingest_record_ref": record} if with_record else {}),
                          **({"fault_after": fault_after} if fault_after is not None else {})},
                expected=3 if fault_after is not None else 0)
    return view


def operation_status(harness):
    return harness.run("source-scan", {"operation_id": "status", "target_operation_id": "batch"}, "status")["data"]["operations"][0]


def test_committed_batch_lists_index_tail_without_reauthoring_original(harness):
    applied_batch(harness)
    response = harness.run("source-scan", {"operation_id": "reopened"}, "scan")["data"]
    assert response["actionable_unit_ids"] == []
    assert [(row["operation_id"], row["next_action"]) for row in response["finalization_pending"]] == [("batch", "rebuild_index")]
    status = operation_status(harness)
    assert {row["stage"] for row in status["facts"]} >= {"plan", "view", "apply"}
    assert status["stage_status"]["content_review"] == "unknown"
    assert status["completion"]["status"] == "pending"
    assert status["completion"]["next_action"] == "rebuild_index"


def test_independent_apply_without_processing_record_still_lists_local_tail(harness):
    applied_batch(harness, with_record=False)
    assert not (harness.root / "logs/ingest/batch.yaml").exists()
    response = harness.run("source-scan", {"operation_id": "reopened"}, "scan")["data"]
    assert [(row["operation_id"], row["next_action"]) for row in response["finalization_pending"]] == [("batch", "rebuild_index")]
    harness.write("docs-raw/troubleshooting/other.md", b"Unrelated source\n")
    narrow = harness.run("source-scan", {"operation_id": "narrow", "source": "docs-raw/troubleshooting"}, "scan")["data"]
    assert narrow["finalization_pending"] == []
    # Later external/current content must not trigger activation of the old view.
    card = harness.root / "knowledge/rules/new.md"
    card.write_bytes(card.read_bytes().replace(b"Synthetic fixture statement.", b"A later current statement."))
    historical = harness.run("source-scan", {"operation_id": "after-new-content"}, "scan")["data"]
    assert historical["finalization_pending"] == []
    assert historical["historical_finalization_unknown"][0]["operation_id"] == "batch"


def test_cross_operation_regression_activation_and_repeated_noop_stay_complete(harness):
    view = applied_batch(harness)
    built = harness.run("index-build", {"operation_id": "index-other"})["data"]
    own_index = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "index-other"}, "status")["data"]["operations"][0]
    assert "index" in {row["stage"] for row in own_index["facts"]}
    assert own_index["completion"]["status"] == "unknown"
    assert own_index["completion"]["next_action"] == "inspect_finalization"
    before_query = operation_status(harness)
    assert before_query["completion"]["next_action"] == "resume_queries"
    checked = harness.run("query-regression", {
        "operation_id": "query-other", "view_ref": view, "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "find-new", "query": "Synthetic", "purpose": "guidance", "required": ["new"]}],
    })["data"]
    assert checked["activated"]
    own_query = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "query-other"}, "status")["data"]["operations"][0]
    assert {row["stage"] for row in own_query["facts"]} >= {"regression", "activation"}
    assert own_query["completion"]["status"] == "unknown"
    after_query = operation_status(harness)
    assert after_query["completion"]["status"] == "complete"
    assert {row["stage"] for row in after_query["facts"]} >= {"index", "regression", "activation"}
    records_before = sorted((harness.root / "logs/ingest").glob("*"))
    for attempt in range(3):
        scanned = harness.run("source-scan", {"operation_id": "noop-" + str(attempt)}, "scan")["data"]
        assert scanned["actionable_unit_ids"] == []
        assert scanned["finalization_pending"] == []
    assert sorted((harness.root / "logs/ingest").glob("*")) == records_before
    # A later active generation must not erase the earlier observed activation.
    later = harness.run("index-build", {"operation_id": "later-generation"})["data"]
    harness.run("index-build", {"operation_id": "later-activation", "generation_ref": later["generation_ref"],
                                "expected_active": later["expected_active"]}, "activate")
    assert operation_status(harness)["completion"]["status"] == "complete"


def test_unbound_or_irrelevant_regression_is_not_batch_completion(harness):
    view = applied_batch(harness)
    built = harness.run("index-build", {"operation_id": "unrelated-index"})["data"]
    checked = harness.run("query-regression", {
        "operation_id": "irrelevant-query", "view_ref": view, "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "irrelevant", "query": "No such card", "forbidden": ["nonexistent-card"]}],
    })["data"]
    assert checked["activated"]
    status = operation_status(harness)
    assert status["completion"]["status"] != "complete"
    assert status["completion"]["next_action"] == "inspect_finalization"
    assert status["stage_status"]["regression"] == "unknown"


@pytest.mark.parametrize("source", ["docs-raw/specs/typo.md", "docs-raw/troubleshooting/not-there"])
def test_missing_explicit_scope_without_history_is_an_error(harness, source):
    result = harness.run("source-scan", {"operation_id": "typo", "source": source}, "scan", expected=2)
    assert result["diagnostics"][0]["code"] == "RAW_SCOPE_NOT_FOUND"
    assert not (harness.root / ".build/operations/typo/source-inventory.json").exists()


def test_default_empty_raw_scope_is_valid_and_status_is_readonly(harness):
    result = harness.run("source-scan", {"operation_id": "empty"}, "scan")["data"]
    assert result["complete"] and result["actionable_unit_ids"] == []
    before = {p.relative_to(harness.root).as_posix(): p.read_bytes() for p in harness.root.rglob("*") if p.is_file()}
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "empty"}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "not_applicable"
    assert {p.relative_to(harness.root).as_posix(): p.read_bytes() for p in harness.root.rglob("*") if p.is_file()} == before


def test_portable_formal_only_history_is_visible_without_private_tail_requirement(harness):
    applied_batch(harness)
    # Model a consuming clone that retains shared records and current knowledge.
    import shutil
    shutil.rmtree(harness.root / ".build")
    shutil.rmtree(harness.root / "logs/operations")
    scanned = harness.run("source-scan", {"operation_id": "consumer"}, "scan")["data"]
    assert scanned["actionable_unit_ids"] == [] and scanned["finalization_pending"] == []
    statuses = harness.run("source-scan", {"operation_id": "status"}, "status")["data"]["operations"]
    imported = next(row for row in statuses if row["operation_id"] == "batch")
    assert "record_formal" in {row["stage"] for row in imported["facts"]}
    assert imported["completion"]["status"] == "unknown"
    assert imported["completion"]["next_action"] == "check_local_index"


def test_missing_explicit_scope_preserves_registered_deletion(harness):
    source = "docs-raw/specs/tracked.md"
    harness.write(source, b"Tracked source\n")
    scanned = harness.run("source-scan", {"operation_id": "tracked"}, "scan")["data"]
    unit = harness.record(scanned["scan_ref"])["units"][0]
    proposed = harness.run("source-scan", {"operation_id": "tracked", "scan_ref": scanned["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "defer", "reason": "Needs authoritative context",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None,
                          "progress": "blocked", "card_refs": [], "claim_refs": []}]}, "record")["data"]
    harness.run("apply", {"operation_id": "tracked", "ingest_record_ref": proposed["ingest_record_ref"]})
    (harness.root / source).unlink()
    repeated = harness.run("source-scan", {"operation_id": "deleted", "source": source}, "scan")["data"]
    assert harness.record(repeated["scan_ref"])["units"][0]["change"] == "missing"


def test_rolled_back_transaction_is_terminal_and_never_resumed(harness):
    import json

    harness.write(".isolated-knowledge-fixture", b"HIMATE_SYNTHETIC_FIXTURE_V2")
    catalog = json.loads(harness.catalog.read_bytes())
    catalog["test_fixture_root"] = str(harness.root)
    harness.catalog.write_text(json.dumps(catalog), encoding="utf-8")
    applied_batch(harness, fault_after=1)
    assert operation_status(harness)["completion"]["next_action"] == "recover_transaction"
    harness.run("apply", {"operation_id": "batch"}, "rollback")
    status = operation_status(harness)
    assert status["completion"]["scope"] == "rolled_back"
    assert status["completion"]["status"] == "not_applicable"
    assert status["completion"]["next_action"] == "prepare_material"
    assert next(row for row in status["facts"] if row["stage"] == "transaction")["status"] == "rolled_back"


def test_empty_raw_inventory_with_maintenance_debt_is_not_a_noop(harness):
    import hashlib
    import json

    scanned = harness.run("source-scan", {"operation_id": "maintenance-only"}, "scan")["data"]
    inventory = harness.record(scanned["scan_ref"])
    inventory["current_context"]["affected_claims"] = [{"card_id": "code-card", "claim_id": "c1", "reason": "rules_changed"}]
    inventory.pop("digest")
    inventory["digest"] = hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(scanned["scan_ref"], json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode())
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "maintenance-only"}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] != "not_applicable"


def test_frozen_batch_status_binds_plan_review_lint_and_original_cases(tmp_path):
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[5]
    spec = importlib.util.spec_from_file_location("scan_status_v3_fixture",
        root / "himate-knowledge-wifi-mp/evals/tests/test_post_ingest_correction.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = fixture.frozen_harness(tmp_path)
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement for test readers.\n")
    finished = fixture.complete_document_operation(harness, "first", "create", "Synthetic fixture statement.")
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "first"}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert {row["stage"] for row in status["facts"]} >= {"semantic_plan", "view", "content_review", "lint", "index", "regression", "activation"}
    original_report = next((harness.root / ".build/operations/first/regression").glob("*.json"))
    original_ref = original_report.relative_to(harness.root).as_posix()
    # A real successful alternate query still cannot replace frozen batch cases.
    alternate = harness.run("query-regression", {"operation_id": "alternate-query", "report_ref": original_ref,
        "view_ref": finished["view_ref"], "cases": [{"id": "other-query", "query": "fixture", "purpose": "guidance", "required": ["rule"]}]}, "verify")
    assert alternate["data"]["passed"]
    original_report.rename(original_report.with_suffix(".retained"))
    rejected = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "first"}, "status")["data"]["operations"][0]
    assert rejected["completion"]["status"] != "complete"
    assert rejected["completion"]["next_action"] == "inspect_finalization"


@pytest.mark.parametrize("raw", [b"[]", b"null", b"{broken", b'{"record_kind":"ingest_record"}'])
def test_status_reports_bad_formal_history_without_hiding_other_operations(harness, raw):
    harness.write("docs-raw/specs/source.md", b"Known pending input\n")
    harness.run("source-scan", {"operation_id": "known"}, "scan")
    harness.write("logs/ingest/broken.yaml", raw)
    response = harness.run("source-scan", {"operation_id": "status"}, "status")["data"]
    known = next(row for row in response["operations"] if row["operation_id"] == "known")
    assert known["facts"][0]["stage"] == "scan"
    assert known["completion"]["status"] != "complete"
    assert response["complete"] is False
    assert response["catalog_gaps"][0]["ref"] == "logs/ingest/broken.yaml"


def test_missing_original_cas_baseline_is_unknown_and_never_reconstructed(harness):
    import hashlib
    import json

    applied_batch(harness)
    built = harness.run("index-build", {"operation_id": "legacy-index"})["data"]
    manifest = harness.record(built["generation_ref"])
    manifest.pop("expected_active")
    manifest.pop("digest")
    manifest["digest"] = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(built["generation_ref"], json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    completion = operation_status(harness)["completion"]
    assert completion["status"] == "unknown"
    assert completion["next_action"] == "inspect_finalization"
    assert "expected_active" not in completion


def test_unreadable_local_journal_requires_inspection_not_clone_readiness(harness):
    applied_batch(harness)
    harness.write("logs/operations/batch/journal.json", b"[]")
    status = operation_status(harness)
    assert status["completion"]["status"] == "unknown"
    assert status["completion"]["next_action"] == "recover_transaction"
    assert any(gap["stage"] == "transaction" for gap in status["gaps"])
