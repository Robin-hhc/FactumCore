"""Public maintenance API over a synthetic committed-content boundary."""

import base64
import copy
import importlib.util
from pathlib import Path

import pytest
import yaml


_helper_path = Path(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py"
_spec = importlib.util.spec_from_file_location("publication_event_contracts", _helper_path)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)


def context(harness, request):
    from support.stages.maintain import operation_context
    return operation_context(harness, request, "publish_changes")


def published_fixture(harness, *, install=True):
    _, old = harness.capture("old", b"# Source\nOld retained fixture evidence.\n")
    for row in old["staged_objects"]:
        harness.write(row["final_ref"], (harness.root / row["stage_ref"]).read_bytes())
    for name in ("updated", "deferred"):
        harness.write("knowledge/rules/" + name + ".md", harness.card(name, old, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": old["resources"], "snapshots": old["snapshots"],
    }).encode())
    bundle_ref, new = harness.capture("publish", b"# Source\nNew retained fixture evidence.\n")
    draft = harness.write(".build/operations/publish/updated.md", harness.card("updated", new, lifecycle="stable"))
    produced = harness.run("view-materialize", {
        "operation_id": "publish", "bundle_ref": bundle_ref,
        "target_queries": [{"id": "find-updated", "query": "Synthetic", "purpose": "guidance", "required": ["updated"]}],
        "decisions": [{"candidate_id": "updated", "decision": "update", "reason": "Synthetic published boundary",
                       "card_inputs": [draft]}],
    })["data"]
    view = harness.record(produced["view_ref"])
    # Model exact content commit only; this is not an end-to-end P7 success.
    if install:
        for row in view["writes"]:
            harness.write(row["path"], base64.b64decode(row["bytes_b64"]))
        for row in view["staged_objects"]:
            harness.write(row["final_ref"], (harness.root / row["stage_ref"]).read_bytes())
    return context(harness, {"operation_id": "publish", "view_ref": produced["view_ref"]}), view, old, new


def test_p7_publishes_frozen_transition_after_lock_update_and_clears_only_resolved_bytes(harness):
    ctx, view, old, new = published_fixture(harness)
    maintenance = ctx.modules["maintenance"]
    state = maintenance.state(ctx)
    block = {"source_id": "synthetic", "old_snapshot_ids": [old["snapshots"][0]["snapshot_id"]],
             "new_snapshot_id": new["snapshots"][0]["snapshot_id"], "reason": "source_changed"}
    state["blocked_claims"] = [
        {**block, "card_id": name, "claim_id": name + "-claim"} for name in ("updated", "deferred")
    ] + [{"card_id": "updated", "claim_id": "updated-claim", "reason": "semantic_review_required"}]
    maintenance.save_state(ctx, maintenance.state(ctx), state)
    with maintenance.writer_lock(ctx):
        result = maintenance.publish_changes(ctx, view["publication_plan"]["event_proposals"])
    assert result["event_refs"]
    event = harness.record(result["event_refs"][0])
    assert event["change"]["old_snapshot_ids"] == [old["snapshots"][0]["snapshot_id"]]
    assert event["change"]["new_snapshot_id"] == new["snapshots"][0]["snapshot_id"]
    assert {row["card_id"] for row in event["affected_claims"]} == {"deferred"}
    state = maintenance.state(ctx)
    assert not state["pending_event_ids"] and state["validity_epoch"] == 2
    assert any(row["card_id"] == "deferred" for row in state["blocked_claims"])
    assert not any(row["card_id"] == "updated" and row["reason"] == "source_changed"
                   for row in state["blocked_claims"])
    assert any(row["reason"] == "semantic_review_required" for row in state["blocked_claims"])
    with maintenance.writer_lock(ctx):
        repeated = maintenance.publish_changes(ctx, view["publication_plan"]["event_proposals"])
    assert repeated["event_refs"] == result["event_refs"]
    assert maintenance.state(ctx)["validity_epoch"] == 2
    assert (harness.root / ".build/runtime/writer.lock").is_file()
    assert not (harness.root / "logs/operations/.writer.lock").exists()


def test_independent_registration_resolves_explicit_staged_bundle_and_retains_event_original(harness):
    _, _, _, new = published_fixture(harness, install=False)
    original = new["snapshots"][0]["recovery"]["path"]
    assert not (harness.root / original).exists()
    response = harness.run("maintain", {
        "operation_id": "register-explicit", "bundle_ref": ".build/operations/publish/capture.json",
    }, "register-source-change")["data"]
    assert response["event_refs"] and response["validity_epoch"] == 1
    assert (harness.root / original).read_bytes() == b"# Source\nNew retained fixture evidence.\n"
    state = harness.record("logs/events/state.json")
    assert state["blocked_claims"] and not state["pending_event_ids"]
    assert {row["card_id"] for row in state["blocked_claims"]} == {"updated", "deferred"}


def test_processed_event_missing_on_disk_never_reports_success(harness):
    ctx, view, _, _ = published_fixture(harness)
    maintenance = ctx.modules["maintenance"]
    proposals = view["publication_plan"]["event_proposals"]
    with maintenance.writer_lock(ctx):
        result = maintenance.publish_changes(ctx, proposals)
    (harness.root / result["event_refs"][0]).unlink()
    before = (harness.root / "logs/events/state.json").read_bytes()
    with maintenance.writer_lock(ctx), pytest.raises(ValueError) as error:
        maintenance.publish_changes(ctx, proposals)
    assert error.value.code == "EVENT_INTEGRITY_ERROR"
    assert (harness.root / "logs/events/state.json").read_bytes() == before


@pytest.mark.parametrize("damage", ["caller_transition", "formal_snapshot", "formal_object"])
def test_event_publication_rejects_unbound_transition_or_unavailable_formal_evidence(harness, damage):
    ctx, view, _, new = published_fixture(harness)
    proposals = copy.deepcopy(view["publication_plan"]["event_proposals"])
    if damage == "caller_transition":
        proposals[0]["source_lock_digest"] = "0" * 64
    elif damage == "formal_snapshot":
        lock = yaml.safe_load((harness.root / "governance/sources.lock.yaml").read_bytes())
        lock["snapshots"] = [row for row in lock["snapshots"] if row["snapshot_id"] != proposals[0]["new_snapshot_id"]]
        harness.write("governance/sources.lock.yaml", yaml.safe_dump(lock).encode())
    else:
        harness.write(new["snapshots"][0]["recovery"]["path"], b"Damaged formal evidence\n")
    with ctx.modules["maintenance"].writer_lock(ctx), pytest.raises(ValueError):
        ctx.modules["maintenance"].publish_changes(ctx, proposals)
    assert not (harness.root / "logs/events").exists()


def test_record_only_does_not_publish_unadopted_source_events(harness):
    _, _, _, new = published_fixture(harness, install=False)
    ref, _ = harness.capture("record-only", b"# Source\nNew retained fixture evidence.\n")
    produced = harness.run("view-materialize", {
        "operation_id": "record-only", "bundle_ref": ref,
        "decisions": [{"candidate_id": "source", "decision": "defer", "reason": "Needs authority"}],
    })["data"]
    view = harness.record(produced["view_ref"])
    assert view["batch_kind"] == "record_only" and view["publication_plan"]["event_proposals"] == []
    ctx = context(harness, {"operation_id": "record-only", "view_ref": produced["view_ref"]})
    with ctx.modules["maintenance"].writer_lock(ctx):
        result = ctx.modules["maintenance"].publish_changes(ctx, [])
    assert result["event_refs"] == [] and result["validity_epoch"] == 0
    assert not (harness.root / "logs/events").exists()
    assert not (harness.root / new["snapshots"][0]["recovery"]["path"]).exists()


def test_public_batch_publishes_source_event_after_content_and_keeps_deferred_card_blocked(harness):
    ctx, view, old, new = published_fixture(harness, install=False)
    assert not (harness.root / "logs/events").exists()
    response = harness.run("apply", {"operation_id": "publish", "view_ref": ctx.request["view_ref"]}, "batch")
    assert response["phase"] == "completed" and response["data"]["batch_complete"] is True
    manifest = harness.record(response["data"]["publication_ref"])
    assert len(manifest["event_refs"]) == 1
    event = harness.record(manifest["event_refs"][0])
    assert event["change"]["old_snapshot_ids"] == [old["snapshots"][0]["snapshot_id"]]
    assert event["change"]["new_snapshot_id"] == new["snapshots"][0]["snapshot_id"]
    state = harness.record("logs/events/state.json")
    assert state["blocked_claims"] and {row["card_id"] for row in state["blocked_claims"]} == {"deferred"}
    assert not state["pending_event_ids"]
    assert not (harness.root / ctx.request["view_ref"]).exists()
    repeated = harness.run("apply", {"operation_id": "publish"}, "batch")
    assert repeated["data"]["batch_complete"] is True
    assert harness.record("logs/events/state.json") == state


def test_independent_registration_of_prepared_bundle_does_not_publish_borrowed_cards(harness):
    published_fixture(harness, install=False)
    scan = harness.run("source", {"operation_id": "material-register"}, "scan")["data"]
    material = harness.run("source", {
        "operation_id": "material-register", "scan_ref": scan["scan_ref"],
    }, "prepare")["data"]
    bundle = harness.record(material["bundle_ref"])
    cards = [row for row in bundle["staged_objects"] if row["final_ref"].startswith("logs/evidence/published/cards/")]
    assert cards and all(not (harness.root / row["final_ref"]).exists() for row in cards)
    result = harness.run("maintain", {
        "operation_id": "register-material", "bundle_ref": material["bundle_ref"],
    }, "register-source-change")["data"]
    assert result["event_refs"]
    assert all(not (harness.root / row["final_ref"]).exists() for row in cards)
    assert all((harness.root / row["stage_ref"]).is_file() for row in cards)
