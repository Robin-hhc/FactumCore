import pytest

import importlib.util
from pathlib import Path

_fixture_spec = importlib.util.spec_from_file_location("maintain_fixture_helpers", Path(__file__).with_name("conftest.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
canonical = _fixture.canonical
operation_context = _fixture.operation_context
public_module = _fixture.public_module


def interrupt_publish(harness, request, action):
    context = operation_context(harness, request, action)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic publish interruption")

    context.save = fail
    with pytest.raises(RuntimeError, match="synthetic publish interruption"):
        public_module("maintenance").execute(context)
    return harness.record("logs/events/state.json")


def test_changed_raw_blocks_affected_claim_once_without_editing_official_card(harness):
    import yaml

    ref, old = harness.capture("old")
    card = harness.card("existing", old, lifecycle="stable")
    harness.write("knowledge/rules/existing.md", card)
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    new_ref, _ = harness.capture(
        "changed", b"# Source\nChanged authorized synthetic evidence.\n"
    )
    result = harness.run(
        "maintain",
        {"operation_id": "changed", "bundle_ref": new_ref},
        "register-source-change",
    )
    state = harness.record("logs/events/state.json")
    assert state["validity_epoch"] == 1
    assert state["blocked_claims"][0]["card_id"] == "existing"
    assert state["knowledge_apply_watermark"] is None
    assert (harness.root / "knowledge/rules/existing.md").read_bytes() == card
    assert result["data"]["event_refs"]
    assert (
        harness.run("maintain", {"operation_id": "changed"}, "status")["data"]["state"][
            "validity_epoch"
        ]
        == 1
    )


def test_manual_advance_never_claims_missing_semantic_review(harness):
    response = harness.run(
        "maintain",
        {"operation_id": "manual", "clear_claims": ["claim"]},
        "advance",
    )
    assert response["data"]["cleared_claims"] == []
    assert response["data"]["verification_tier"] == "current_source_bytes_only"
    assert response["data"]["knowledge_apply_watermark"] is None


def test_source_repair_can_clear_stale_bytes_without_apply_or_index_history(harness):
    import yaml

    _, old = harness.capture("old")
    harness.write("knowledge/rules/existing.md", harness.card("existing", old, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": old["resources"], "snapshots": old["snapshots"],
    }).encode())
    new_ref, new = harness.capture("changed", b"# Source\nChanged authorized synthetic evidence.\n")
    harness.run("maintain", {"operation_id": "changed", "bundle_ref": new_ref}, "register-source-change")
    stale = harness.run("maintain", {"operation_id": "still-stale"}, "advance")
    assert stale["data"]["blocked_claims"] and not stale["data"]["cleared_claims"]
    harness.write("knowledge/rules/existing.md", harness.card("existing", new, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": new["resources"], "snapshots": new["snapshots"],
    }).encode())
    current = harness.run("maintain", {"operation_id": "current"}, "advance")
    assert not current["data"]["blocked_claims"] and current["data"]["cleared_claims"]
    assert current["data"]["knowledge_apply_watermark"] is None
    assert not list((harness.root / "logs/operations").glob("*/apply-result.json"))


def test_interrupted_event_publish_keeps_blocks_and_resumes_without_epoch_duplication(
    harness,
):
    import json
    import yaml

    _, old = harness.capture("initial")
    harness.write(
        "knowledge/rules/existing.md", harness.card("existing", old, lifecycle="stable")
    )
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    # Capture the new bytes before declaring the old source formally, then restore the old lock.
    harness.write(
        "governance/sources.lock.yaml",
        b"schema_version: '2.0'\nresources: []\nsnapshots: []\n",
    )
    new_ref, _ = harness.capture("new", b"# Source\nChanged fixture evidence.\n")
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    interrupt_publish(harness, {"operation_id": "new", "bundle_ref": new_ref}, "register-source-change")
    interrupted = json.loads((harness.root / "logs/events/state.json").read_text())
    assert interrupted["validity_epoch"] == 1 and interrupted["blocked_claims"]
    assert interrupted["pending_event_ids"]
    assert interrupted["pending_events"][0]["change"]["new_snapshot_id"]
    assert interrupted["pending_events"][0]["source_snapshot"]["recovery"]["path"]
    harness.run("maintain", {"operation_id": "recover"}, "recover-events")
    harness.run(
        "maintain",
        {"operation_id": "new", "bundle_ref": new_ref},
        "register-source-change",
    )
    recovered = harness.record("logs/events/state.json")
    assert recovered["validity_epoch"] == 1 and not recovered["pending_event_ids"]
    assert recovered["impact_scan_watermark"]


def raw_pending(harness):
    import yaml

    _, old = harness.capture("initial")
    harness.write("knowledge/rules/existing.md", harness.card("existing", old, lifecycle="stable"))
    old_lock = yaml.safe_dump({"schema_version": "2.0", "resources": old["resources"],
                              "snapshots": old["snapshots"]}).encode()
    harness.write("governance/sources.lock.yaml", b"schema_version: '2.0'\nresources: []\nsnapshots: []\n")
    new_ref, new = harness.capture("changed", b"# Source\nChanged fixture evidence.\n")
    harness.write("governance/sources.lock.yaml", old_lock)
    pending = interrupt_publish(harness, {"operation_id": "changed", "bundle_ref": new_ref}, "register-source-change")
    assert pending["blocked_claims"] and pending["pending_event_ids"]
    return old, new_ref, new, pending


def replace_state(harness, state):
    sealed = public_module("records").seal(state)
    harness.write("logs/events/state.json", canonical(sealed))
    return sealed


@pytest.mark.parametrize("damage,diagnostic", [
    ("missing_payload", "EVENT_RECOVERY_REQUIRED"),
    ("changed_identity", "EVENT_CONFLICT"),
    ("wrong_snapshot", "EVENT_CONFLICT"),
    ("missing_evidence", "SOURCE_INTEGRITY_ERROR"),
    ("changed_evidence", "SOURCE_INTEGRITY_ERROR"),
])
def test_pending_event_recovery_rejects_missing_or_wrong_bound_inputs_without_erasing_limits(harness, damage, diagnostic):
    old, _, _, state = raw_pending(harness)
    event_id = state["pending_event_ids"][0]
    event = state["pending_events"][0]
    if damage == "missing_payload":
        state["pending_events"] = []
    elif damage == "changed_identity":
        event["change"]["new_sha256"] = "f" * 64
        state["pending_events"] = [public_module("records").seal(event)]
    elif damage == "wrong_snapshot":
        event["source_snapshot"] = old["snapshots"][0]
        state["pending_events"] = [public_module("records").seal(event)]
    else:
        evidence = harness.root / event["source_snapshot"]["recovery"]["path"]
        if damage == "missing_evidence":
            evidence.unlink()
        else:
            evidence.write_bytes(b"Wrong exact evidence bytes\n")
    replace_state(harness, state)
    before = (harness.root / "logs/events/state.json").read_bytes()
    formal = {path: (harness.root / path).read_bytes()
              for path in ("knowledge/rules/existing.md", "governance/sources.lock.yaml")}
    result = harness.run("maintain", {"operation_id": "recover-bad"}, "recover-events",
                         expected=3 if damage == "missing_payload" else 2)
    assert result["diagnostics"][0]["code"] == diagnostic
    assert (harness.root / "logs/events/state.json").read_bytes() == before
    assert harness.record("logs/events/state.json")["blocked_claims"]
    assert not (harness.root / ("logs/events/" + event_id + ".json")).exists()
    assert all((harness.root / path).read_bytes() == data for path, data in formal.items())
    assert not (harness.root / "artifacts/indexes").exists()


def test_pending_event_cannot_be_bypassed_by_advance_after_source_bytes_are_repaired(harness):
    import yaml

    _, _, new, _ = raw_pending(harness)
    harness.write("knowledge/rules/existing.md", harness.card("existing", new, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": new["resources"], "snapshots": new["snapshots"],
    }).encode())
    before = (harness.root / "logs/events/state.json").read_bytes()
    result = harness.run("maintain", {"operation_id": "premature-advance"}, "advance", expected=3)
    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "EVENT_RECOVERY_REQUIRED"
    assert (harness.root / "logs/events/state.json").read_bytes() == before


def test_advance_only_clears_freshness_and_retains_semantic_and_applicability_restrictions(harness):
    import yaml

    _, new_ref, new, pending = raw_pending(harness)
    harness.run("maintain", {"operation_id": "recover"}, "recover-events")
    harness.run("maintain", {"operation_id": "changed", "bundle_ref": new_ref}, "register-source-change")
    harness.write("knowledge/rules/existing.md", harness.card("existing", new, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": new["resources"], "snapshots": new["snapshots"],
    }).encode())
    state = harness.record("logs/events/state.json")
    retained = [{**pending["blocked_claims"][0], "reason": reason}
                for reason in ("semantic_review_required", "applicability_unverified")]
    state["blocked_claims"].extend(retained)
    replace_state(harness, state)
    formal = (harness.root / "knowledge/rules/existing.md").read_bytes()
    result = harness.run("maintain", {"operation_id": "mechanical-advance"}, "advance")["data"]
    assert result["blocked_claims"] == retained
    assert result["cleared_claims"] == pending["blocked_claims"]
    assert result["verification_tier"] == "current_source_bytes_only"
    assert result["knowledge_apply_watermark"] is None
    assert (harness.root / "knowledge/rules/existing.md").read_bytes() == formal
    assert not list((harness.root / ".build/operations").glob("*/calls/*"))


def test_code_event_publish_recovers_original_identity_without_repeating_epoch_or_changing_assets(harness):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("maintenance_code_fixture", Path(__file__).with_name("test_reference_audit.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    code_fixture = fixture.code_fixture

    source, raw, old, _ = code_fixture(harness)
    formal = {path: (harness.root / path).read_bytes()
              for path in ("knowledge/rules/audit-current.md", "governance/sources.lock.yaml")}
    source.write_bytes(raw.replace(b"1", b"2"))
    repo_id = old["resources"][0]["repo_id"]
    captured = harness.run("source", {"operation_id": "new-code", "kind": "code", "repo_id": repo_id,
        "relative_path": "file.c", "source_id": "selected-code"}, "capture")
    request = {"operation_id": "new-code", "bundle_ref": captured["data"]["bundle_ref"]}
    pending = interrupt_publish(harness, request, "register-code-change")
    assert pending["validity_epoch"] == 1
    assert pending["blocked_claims"][0]["reason"] == "code_changed"
    event_id = pending["pending_event_ids"][0]
    staged = pending["pending_events"][0]
    assert staged["change"]["source_kind"] == "code"
    harness.run("maintain", {"operation_id": "recover-code"}, "recover-events")
    harness.run("maintain", request, "register-code-change")
    recovered = harness.record("logs/events/state.json")
    assert recovered["validity_epoch"] == 1 and not recovered["pending_event_ids"]
    assert recovered["processed_event_ids"] == [event_id]
    assert harness.record("logs/events/" + event_id + ".json") == staged
    assert recovered["blocked_claims"] == pending["blocked_claims"]
    assert all((harness.root / path).read_bytes() == data for path, data in formal.items())
    assert not (harness.root / "artifacts/indexes").exists()
    assert not list((harness.root / ".build/operations").glob("*/calls/*"))
