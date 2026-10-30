"""Ordinary observations do not implicitly adopt private execution history."""

import hashlib
import json


def publication(harness, *, complete=True):
    """Synthetic sealed observations; never a claim of real P6 execution."""
    def save(ref, purpose, payload):
        value = {"schema_version": "2.0", "record_kind": "artifact_manifest",
                 "operation_id": "published", "rules_digest": harness.rules,
                 "tool_identity": {"skill": "hs-knowledge-apply", "package_digest": "0" * 64,
                                   "runtime": "synthetic", "requirements_digest": "0" * 64},
                 "purpose": purpose, "protocol_version": "1.0", **payload}
        value["digest"] = digest(value)
        harness.write(ref, json.dumps(value).encode())
        return value

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    view = {"batch_kind": "record_only", "writes": [], "deletes": []}
    manifest = save("logs/publications/published/manifest.json", "knowledge_publication", {
        "published": True, "content_digest": "c" * 64, "publication_plan_digest": "d" * 64,
        "reviewed_view_digest": "e" * 64, "batch_kind": "record_only", "files": [], "deletes": [],
        "published_view": view, "published_view_digest": digest(view), "processing_record": None,
        "event_refs": [], "apply_result": None, "trace": {"view_ref": ".build/operations/published/final-view.json"},
    })
    save("logs/publications/published/completion.json", "knowledge_publication_completion", {
        "publication_ref": "logs/publications/published/manifest.json", "publication_digest": manifest["digest"],
        "content_digest": manifest["content_digest"], "published": True, "batch_complete": complete,
        "phase": "recorded" if complete else "cleanup_pending", "data": {"transaction_status": "committed"},
        "retrieval": {"complete": True, "scope": "record_only"}, "cleanup": {"status": "done" if complete else "cleanup_pending",
            "owned": [], "deleted": [], "retained": [], "failed": []},
    })


def test_scan_ignores_unrelated_corrupt_execution_history(harness):
    harness.write("docs-raw/specs/current.md", b"# Current original\n")
    for ref in (
        ".build/operations/abandoned/source-inventory.json",
        ".build/operations/abandoned/batch-intent.json",
        "logs/operations/abandoned/journal.json",
        "artifacts/indexes/local/gen-abandoned/manifest.json",
    ):
        harness.write(ref, b"{broken")

    result = harness.run("source", {"operation_id": "fresh"}, "scan")["data"]
    inventory = harness.record(result["scan_ref"])
    assert [(row["path"], row["change"]) for row in inventory["units"]] == [
        ("docs-raw/specs/current.md", "new")
    ]
    assert result["finalization_pending"] == []
    assert result["historical_finalization_unknown"] == []
    assert result["execution_history"] == {"status": "not_inspected"}


def test_target_status_ignores_unrelated_bad_history_but_global_reports_it(harness):
    harness.run("source", {"operation_id": "target"}, "scan")
    before = harness.run("source", {
        "operation_id": "inspect-before", "target_operation_id": "target",
    }, "status")["data"]
    for ref in (
        ".build/operations/unrelated/regression/broken.json",
        "logs/ingest/unrelated.yaml",
        "artifacts/indexes/local/gen-unrelated/manifest.json",
    ):
        harness.write(ref, b"{broken")

    after = harness.run("source", {
        "operation_id": "inspect-after", "target_operation_id": "target",
    }, "status")["data"]
    assert before["complete"] is after["complete"] is True
    assert before["operations"] == after["operations"]
    assert after["catalog_gaps"] == []
    overview = harness.run("source", {"operation_id": "overview"}, "status")["data"]
    assert overview["complete"] is False
    assert {gap["ref"] for gap in overview["catalog_gaps"]} >= {
        "logs/ingest/unrelated.yaml",
        ".build/operations/unrelated/regression/broken.json",
    }


def test_published_target_uses_formal_closure_without_reading_cleaned_private_paths(harness):
    publication(harness)
    harness.write(".build/operations/published/final-view.json", b"{obsolete broken draft")
    harness.write("logs/operations/published/journal.json", b"{obsolete broken journal")
    result = harness.run("source", {
        "operation_id": "inspect-publication", "target_operation_id": "published",
    }, "status")["data"]
    assert result["complete"] is True and result["catalog_gaps"] == []
    row = result["operations"][0]
    assert row["gaps"] == []
    assert {fact["stage"] for fact in row["facts"]} == {"publication", "publication_completion"}
    assert row["completion"]["status"] == "complete"
    assert row["completion"]["published"] is True
    assert row["completion"]["batch_complete"] is True
    overview = harness.run("source", {"operation_id": "global-history"}, "status")["data"]
    assert overview["complete"] is False
    published = next(item for item in overview["operations"] if item["operation_id"] == "published")
    assert published["completion"]["status"] == "complete"
    assert {gap["stage"] for gap in published["gaps"]} >= {"view", "transaction"}


def test_published_cleanup_pending_is_not_complete_or_unpublished(harness):
    publication(harness, complete=False)
    row = harness.run("source", {
        "operation_id": "inspect-pending", "target_operation_id": "published",
    }, "status")["data"]["operations"][0]
    assert row["completion"]["status"] == "pending"
    assert row["completion"]["published"] is True
    assert row["completion"]["batch_complete"] is False
    assert row["completion"]["next_action"] == "cleanup"
