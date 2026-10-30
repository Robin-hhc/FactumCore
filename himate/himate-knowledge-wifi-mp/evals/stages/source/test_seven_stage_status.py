"""Saved seven-stage stops are observations, never replay or fresh index health."""

import hashlib
import json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def fact(harness, operation, reference, payload, kind="artifact_manifest"):
    # These are deliberately synthetic saved facts, not a successful ingest.
    value = {"schema_version": "2.0", "record_kind": kind, "operation_id": operation,
             "rules_digest": harness.rules, "tool_identity": {"skill": "hs-knowledge-apply",
             "package_digest": "0" * 64, "runtime": "synthetic", "requirements_digest": "0" * 64}, **payload}
    value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
    harness.write(reference, canonical(value))
    return value


def status(harness, operation):
    return harness.run("source", {"operation_id": "inspect", "target_operation_id": operation}, "status")["data"]["operations"][0]


def intent(harness, operation="batch"):
    return fact(harness, operation, f".build/operations/{operation}/batch-intent.json",
                {"purpose": "batch_execution_intent", "view_ref": f".build/operations/{operation}/final-view.json",
                 "view_digest": "1" * 64, "ingest_record_ref": None, "cases": [], "channel": "local", "index_inputs": {}})


def journal(harness, operation="batch", *, batch_kind="content", state="committed"):
    return fact(harness, operation, f"logs/operations/{operation}/journal.json",
                {"status": state, "batch_kind": batch_kind, "view_ref": f".build/operations/{operation}/final-view.json",
                 "view_digest": "1" * 64, "execution_checks": "safety_only", "entries": []}, "transaction_journal")


def test_prepare_action_is_available_without_implicit_scan(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\nExplicit material input.\n")
    result = harness.run("source", {"operation_id": "independent-prepare", "targets": [
        {"source_path": "docs-raw/specs/source.md"},
    ]}, "prepare")
    assert result["phase"] == "prepared"
    material = harness.record(result["data"]["material_ref"])
    assert material["purpose"] == "source_materials"
    assert "scan_ref" not in material and material["unit_ids"] == []
    assert material["targets"][0]["source_path"] == "docs-raw/specs/source.md"
    assert not (harness.root / ".build/operations/independent-prepare/source-inventory.json").exists()


def test_status_discovers_all_immutable_material_versions(harness):
    for key in ("a" * 64, "b" * 64):
        fact(harness, "materials", f".build/operations/materials/materials/{key}/material.json", {"purpose": "source_materials"})
    result = status(harness, "materials")
    assert len([row for row in result["facts"] if row["stage"] == "materials"]) == 2
    assert result["stage_status"]["materials"] == "saved"


def test_intent_without_transaction_resumes_same_batch(harness):
    intent(harness)
    result = status(harness, "batch")["completion"]
    assert result["status"] == "pending" and result["next_action"] == "resume_batch"
    assert result["verification"] == "saved_facts_only"


def test_committed_content_without_build_locates_index_stop(harness):
    intent(harness)
    journal(harness)
    result = status(harness, "batch")["completion"]
    assert result["status"] == "pending" and result["next_action"] == "rebuild_index"
    assert result["index_health"] == "not_examined"


def test_build_stop_retains_genuine_null_active_baseline(harness):
    intent(harness)
    journal(harness)
    fact(harness, "batch", ".build/operations/batch/batch-build.json",
         {"purpose": "batch_index", "view_digest": "1" * 64,
          "generation_ref": "artifacts/indexes/local/gen-synthetic/manifest.json", "expected_active": None})
    result = status(harness, "batch")["completion"]
    assert result["status"] == "pending" and result["next_action"] == "resume_queries"
    assert "expected_active" in result and result["expected_active"] is None


def test_build_without_original_active_baseline_is_unknown(harness):
    intent(harness)
    journal(harness)
    fact(harness, "batch", ".build/operations/batch/batch-build.json",
         {"purpose": "batch_index", "view_digest": "1" * 64,
          "generation_ref": "artifacts/indexes/local/gen-synthetic/manifest.json"})
    result = status(harness, "batch")["completion"]
    assert result["status"] == "unknown" and result["next_action"] == "inspect_finalization"
    assert "expected_active" not in result


def test_record_only_completion_needs_no_index_or_queries(harness):
    intent(harness)
    journal(harness, batch_kind="record_only")
    fact(harness, "batch", ".build/operations/batch/batch-complete.json",
         {"purpose": "batch_completion", "view_digest": "1" * 64, "phase": "recorded",
          "data": {"transaction_status": "committed", "batch_complete": True}})
    result = status(harness, "batch")["completion"]
    assert result["status"] == "complete" and result["scope"] == "record_only"
    assert result["next_action"] is None and result["index_health"] == "not_examined"


def test_batch_completion_cannot_override_uncommitted_journal(harness):
    intent(harness)
    journal(harness, state="recovery_required")
    fact(harness, "batch", ".build/operations/batch/batch-complete.json",
         {"purpose": "batch_completion", "view_digest": "1" * 64, "phase": "recorded",
          "data": {"transaction_status": "committed", "batch_complete": True}})
    result = status(harness, "batch")["completion"]
    assert result["status"] == "unknown" and result["next_action"] == "recover_transaction"


def test_batch_summary_cannot_hide_an_unreadable_local_journal(harness):
    intent(harness)
    harness.write("logs/operations/batch/journal.json", b"[]")
    fact(harness, "batch", ".build/operations/batch/batch-complete.json",
         {"purpose": "batch_completion", "view_digest": "1" * 64, "phase": "recorded",
          "data": {"transaction_status": "committed", "batch_complete": True}})
    result = status(harness, "batch")["completion"]
    assert result["status"] == "unknown" and result["next_action"] == "recover_transaction"


def test_target_reads_new_staged_transaction_protocol(harness):
    intent(harness)
    fact(harness, "batch", ".build/operations/batch/transaction/journal.json",
         {"status": "recovery_required", "batch_kind": "content", "view_digest": "1" * 64,
          "view_ref": ".build/operations/batch/final-view.json", "entries": []}, "transaction_journal")
    result = status(harness, "batch")
    assert result["completion"]["next_action"] == "recover_transaction"
    assert next(row for row in result["facts"] if row["stage"] == "transaction")["ref"] == (
        ".build/operations/batch/transaction/journal.json")


def test_conflicting_new_and_legacy_journals_are_not_arbitrarily_selected(harness):
    intent(harness)
    journal(harness, batch_kind="record_only")
    fact(harness, "batch", ".build/operations/batch/transaction/journal.json",
         {"status": "recovery_required", "batch_kind": "content", "view_digest": "1" * 64,
          "view_ref": ".build/operations/batch/final-view.json", "entries": []}, "transaction_journal")
    result = status(harness, "batch")
    assert result["completion"]["status"] == "unknown"
    assert result["completion"]["next_action"] == "recover_transaction"
    assert any(gap["stage"] == "transaction" for gap in result["gaps"])
