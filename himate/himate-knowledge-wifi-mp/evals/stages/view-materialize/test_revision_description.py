"""Revision and exact-description business oracles migrated from retired producers."""
import base64
import hashlib
import json


def test_revision_rejects_reusing_old_operation(harness):
    ref, _ = harness.view()
    result = harness.run("view-materialize", {"operation_id": "op", "previous_view_ref": ref,
        "revision_reason": "Returned for correction", "decisions": []}, action="revise", expected=2)
    assert result["diagnostics"][0]["code"] == "NEW_OPERATION_REQUIRED"


def test_revision_produces_new_view_without_overwriting_old_candidate(harness):
    ref, _ = harness.view()
    before = (harness.root / ref).read_bytes()
    bundle_ref, bundle = harness.capture("revision")
    candidate = harness.write(".build/candidates/revised.md", harness.card("revised", bundle))
    result = harness.run("view-materialize", {"operation_id": "revision", "previous_view_ref": ref,
        "revision_reason": "Partial acceptance requires smaller exact view", "bundle_ref": bundle_ref,
        "decisions": [{"candidate_id": "revised", "decision": "create", "reason": "Explicit revision",
                       "card_inputs": [candidate]}]}, action="revise")
    assert result["phase"] == "ready" and result["data"]["content_review_required"] is True
    assert result["data"]["view_ref"] != ref
    assert harness.record(result["data"]["view_ref"])["operation_id"] == "revision"
    revision = harness.record(result["data"]["revision_ref"])
    assert revision["previous_view_ref"] == ref and revision["previous_view_digest"] == harness.record(ref)["digest"]
    assert (harness.root / ref).read_bytes() == before
    assert not (harness.root / "knowledge").exists()


def test_description_binds_exact_view_without_another_operations_stage_gate(harness):
    ref, _ = harness.view()
    view = harness.record(ref)
    journal = {"schema_version": "2.0", "record_kind": "transaction_journal", "operation_id": "another",
        "rules_digest": view["rules_digest"], "tool_identity": view["tool_identity"], "status": "prepared",
        "view_ref": ".build/operations/another/final-view.json", "view_digest": "0" * 64, "entries": []}
    journal["digest"] = hashlib.sha256(json.dumps(journal, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write("logs/operations/another/journal.json", json.dumps(journal).encode())
    result = harness.run("view-materialize", {"operation_id": "op", "view_ref": ref}, action="describe")
    assert result["phase"] == "described"
    assert result["data"]["view_digest"] == view["digest"]
    assert result["data"]["source_set_digest"] == view["source_set_digest"]
    assert result["data"]["baseline_digest"] == view["baseline_digest"]
    rejected = harness.run("view-materialize", {"operation_id": "different", "view_ref": ref}, action="describe", expected=2)
    assert rejected["diagnostics"][0]["code"] == "OPERATION_MISMATCH"


def test_displayed_byte_tamper_blocks_identical_production_reentry(harness):
    ref, _ = harness.view()
    view = harness.record(ref)
    request = harness.record(view["plan_ref"])["request"]
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", b"changed")
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "FINAL_BYTES_CHANGED"


def test_resealed_view_cannot_replace_actual_authored_bytes(harness):
    ref, _ = harness.view()
    view = harness.record(ref)
    request = harness.record(view["plan_ref"])["request"]
    row = next(row for row in view["writes"] if row["path"] == "knowledge/rules/new.md")
    raw = base64.b64decode(row["bytes_b64"]).replace(b"Synthetic fixture statement.", b"Altered proposed statement.")
    row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=hashlib.sha256(raw).hexdigest())
    view.pop("digest")
    view["digest"] = hashlib.sha256(json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(ref, json.dumps(view).encode())
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", raw)
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "FINAL_BYTES_CHANGED"
    assert not (harness.root / "knowledge").exists()
