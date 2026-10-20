"""Public subprocess integration; synthetic mechanisms, no production acceptance."""

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("pipeline_fixture", Path(__file__).parents[1] / "pipeline_harness.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_confirmation_displays_fixed_attachments_and_bundle_limitations(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    source = p.write(
        "docs-raw/specs/source.md", b"# Source\n![diagram](diagram.png)\n[deferred](https://example.invalid/source)\n"
    )
    p.write("docs-raw/specs/diagram.png", b"opaque synthetic image bytes")
    captured = p.call(
        "knowledge-source-capture",
        {
            "operation_id": "attachments",
            "source_id": "with-attachments",
            "source_path": source,
            "attachments": ["docs-raw/specs/diagram.png"],
        },
    )["data"]
    bundle = p.record(captured["bundle_ref"])
    view = p.view("attachments", captured["bundle_ref"], "attachment-rule", p.card("attachment-rule", bundle))
    prepared = p.call("knowledge-confirmation-prepare", {"operation_id": "attachments", "view_ref": view})["data"]
    display = p.record(prepared["display_ref"])
    assert display["source_bundle_display"]["bundle_digest"] == bundle["digest"]
    assert bundle["snapshots"][1]["sha256"] in display["display_text"]
    assert bundle["snapshots"][1]["recovery"]["path"] in display["display_text"]
    assert all(gap in display["display_text"] for gap in bundle["limitations"])


def test_raw_to_confirmed_stable_generation_and_live_source_change(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("create-card", b"# Original\nCapture marker is a fixture rule.\n")
    view_ref = p.view("create-card", bundle_ref, "capture-rule", p.card("capture-rule", bundle))
    handoff = p.call("knowledge-governance-handoff", {"operation_id": "create-card", "view_ref": view_ref})
    assert handoff["phase"] == "handed_off"
    assert not (p.root / "knowledge/rules/capture-rule.md").exists()
    applied_ref, display = p.apply("create-card", view_ref)
    assert "Capture marker is a fixture rule" in display["display_text"]
    assert display["source_displays"][0]["source_ref"]["snapshot_id"] == bundle["snapshots"][0]["snapshot_id"]
    card_path = p.root / "knowledge/rules/capture-rule.md"
    original_card = card_path.read_bytes()
    built = p.call("knowledge-index-build", {"operation_id": "build-first"})["data"]
    regression = {
        "operation_id": "invalid-workflow-regression",
        "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "find-rule", "query": "capture", "required": ["capture-rule"]}],
    }
    p.call("knowledge-query-regression", {**regression, "workflow": {"attempt_id": "bad"}}, expected=2)
    assert not (p.root / "artifacts/indexes/local/active.json").exists()
    checked = p.call(
        "knowledge-query-regression",
        {
            "operation_id": "check-first",
            "generation_ref": built["generation_ref"],
            "expected_active": built["expected_active"],
            "cases": [{"id": "find-rule", "query": "capture", "required": ["capture-rule"]}],
        },
    )
    assert checked["data"]["activated"]
    search = {"operation_id": "consume-first", "query": "capture", "purpose": "current"}
    found = p.call("knowledge-query", search, "search")["data"]
    assert [row["card_id"] for row in found["matches"]] == ["capture-rule"]
    first_generation = found["generation_ref"]
    old_pointer = (p.root / "artifacts/indexes/local/active.json").read_bytes()
    new_bundle_ref, new_bundle = p.capture(
        "update-source", b"# Original\nChanged marker requires another human review.\n"
    )
    stale = p.call("knowledge-query", {**search, "operation_id": "consume-stale"}, "search")["data"]
    assert stale["matches"] == []
    assert stale["validity_epoch"] > found["validity_epoch"]
    history = p.call(
        "knowledge-query", {**search, "operation_id": "consume-history", "purpose": "historical"}, "search"
    )["data"]
    assert [row["card_id"] for row in history["matches"]] == ["capture-rule"]
    assert history["generation_ref"] == first_generation
    assert card_path.read_bytes() == original_card
    assert applied_ref.endswith("apply-result.json")
    updated_view = p.view(
        "update-source",
        new_bundle_ref,
        "capture-rule",
        p.card("capture-rule", new_bundle, "Capture marker has an explicitly reviewed update."),
        decision="update",
    )
    updated_apply, _ = p.apply("update-source", updated_view)
    next_generation = p.call("knowledge-index-build", {"operation_id": "build-updated"})["data"]
    p.call(
        "knowledge-query-regression",
        {
            "operation_id": "check-updated",
            "generation_ref": next_generation["generation_ref"],
            "expected_active": next_generation["expected_active"],
            "cases": [{"id": "reviewed-source", "query": "capture", "required": ["capture-rule"]}],
        },
    )
    advanced = p.call(
        "knowledge-maintain",
        {
            "operation_id": "advance-updated",
            "apply_result_ref": updated_apply,
            "generation_ref": next_generation["generation_ref"],
        },
        "advance",
    )["data"]
    assert advanced["cleared_claims"] and not advanced["blocked_claims"]
    assert advanced["knowledge_apply_watermark"] == p.record(updated_apply)["digest"]
    current = p.call("knowledge-query", {**search, "operation_id": "consume-updated"}, "search")["data"]
    assert current["matches"][0]["card_id"] == "capture-rule"
    assert current["validity_epoch"] == advanced["validity_epoch"]
    # Pointer rollback cannot resurrect old current knowledge after the live blocker clears.
    p.write("artifacts/indexes/local/active.json", old_pointer)
    rolled_back = p.call("knowledge-query", {**search, "operation_id": "consume-pointer-rollback"}, "search")["data"]
    assert rolled_back["matches"] == []
    old = p.call(
        "knowledge-query",
        {"operation_id": "history-after-update", "card_id": "capture-rule", "purpose": "historical"},
        "read",
    )
    assert "explicit synthetic rule" in old["data"]["claims"][0]["text"]
