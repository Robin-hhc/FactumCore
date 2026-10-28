"""Public subprocess integration; synthetic mechanisms, no production acceptance."""

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("pipeline_fixture", Path(__file__).parents[1] / "pipeline_harness.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_document_apply_checks_business_data_without_requiring_upstream_review(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("review-required", b"# Source\nIndependent review is required.\n")
    view_ref = p.view("review-required", bundle_ref, "review-rule", p.card("review-rule", bundle))
    assert "review_trust" not in p.catalog
    result = p.call("knowledge-apply", {"operation_id": "review-required", "view_ref": view_ref})
    assert "proof_ref" not in p.record(result["data"]["apply_result_ref"])
    assert (p.root / "knowledge/rules/review-rule.md").exists()
    assert not list(p.root.rglob("host-event.json"))


def test_raw_to_reviewed_stable_generation_and_post_ingest_correction(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("create-card", b"# Original\nCapture marker is a fixture rule.\n")
    view_ref = p.view("create-card", bundle_ref, "capture-rule", p.card("capture-rule", bundle))
    handoff = p.call("knowledge-governance-handoff", {"operation_id": "create-card", "view_ref": view_ref})
    assert handoff["phase"] == "handed_off"
    assert not (p.root / "knowledge/rules/capture-rule.md").exists()
    applied_ref, review = p.apply("create-card", view_ref)
    assert review["view_digest"] == p.record(view_ref)["digest"]
    assert "review_trust" not in p.catalog
    card_path = p.root / "knowledge/rules/capture-rule.md"
    original_card = card_path.read_bytes()
    built = p.call("knowledge-index-build", {"operation_id": "build-first"})["data"]
    assert not (p.root / "artifacts/indexes/local/active.json").exists()
    checked = p.call(
        "knowledge-query-regression",
        {
            "operation_id": "check-first",
            "workflow": {"attempt_id": "host-owned-metadata"},
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
        "update-source", b"# Original\nChanged marker requires another independent content review.\n"
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
    assert advanced["knowledge_apply_watermark"] is None
    assert advanced["verification_tier"] == "current_source_bytes_only"
    current = p.call("knowledge-query", {**search, "operation_id": "consume-updated"}, "search")["data"]
    assert current["matches"][0]["card_id"] == "capture-rule"
    assert current["validity_epoch"] == advanced["validity_epoch"]
    # Pointer rollback cannot resurrect old current knowledge after the live blocker clears.
    p.write("artifacts/indexes/local/active.json", old_pointer)
    rolled_back = p.call(
        "knowledge-query", {**search, "operation_id": "consume-pointer-rollback"},
        "search", expected=3,
    )
    assert rolled_back["status"] == "blocked"
    assert rolled_back["diagnostics"][0]["code"] == "INDEX_STALE"
    assert rolled_back["data"] == {}
    old = p.call(
        "knowledge-query",
        {"operation_id": "history-after-update", "card_id": "capture-rule", "purpose": "historical"},
        "read",
    )
    assert "explicit synthetic rule" in old["data"]["claims"][0]["text"]
