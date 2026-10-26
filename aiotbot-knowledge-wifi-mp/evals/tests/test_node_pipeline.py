"""Public subprocess integration; synthetic mechanisms, no production acceptance."""

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("pipeline_fixture", Path(__file__).parents[1] / "pipeline_harness.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_document_admission_requires_independent_review_without_human_events(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("review-required", b"# Source\nIndependent review is required.\n")
    view_ref = p.view("review-required", bundle_ref, "review-rule", p.card("review-rule", bundle))
    assert "review_trust" not in p.catalog
    p.call("knowledge-apply", {"operation_id": "review-required", "view_ref": view_ref}, expected=2)
    assert not (p.root / "knowledge/rules/review-rule.md").exists()
    proof_ref, review = p.review("review-required", view_ref)
    for field, value in (("reviewer_id", review["author_id"]), ("view_digest", "0" * 64)):
        bad = {**review, field: value}
        bad.pop("digest")
        bad["digest"] = FIXTURE.sha(FIXTURE.canonical(bad))
        bad_ref = p.write(f".build/operations/review-required/bad-{field}.json", FIXTURE.canonical(bad))
        p.call("knowledge-apply", {"operation_id": "review-required", "view_ref": view_ref,
                                   "content_review_ref": bad_ref}, expected=3 if field == "reviewer_id" else 2)
        assert not (p.root / "knowledge/rules/review-rule.md").exists()
    p.call("knowledge-apply", {"operation_id": "review-required", "view_ref": view_ref,
                               "content_review_ref": proof_ref})
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
