"""Query-visible candidate maintenance projection over trusted synthetic data."""

import copy
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "maintenance_projection_support", Path(__file__).parents[1] / "support/contracts.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
maintenance, runtime = helper.module("maintenance"), helper.module("runtime")


def card(identity="card", snapshot="new", *, lifecycle="stable", claim_ids=("c1",)):
    source = {"evidence_ref": "e1", "source_id": "source", "snapshot_id": snapshot}
    return {"metadata": {"id": identity, "lifecycle": lifecycle, "scope": {"applicability": "unknown"},
                         "sources": [source], "claims": [{"id": claim, "source_refs": ["e1"]} for claim in claim_ids]},
            "claims": [{"id": claim, "source_records": [copy.deepcopy(source)]} for claim in claim_ids]}


def inputs(*, proposals=True, kind="raw"):
    resource = {"source_id": "source", "kind": kind, "path": "docs-raw/specs/source.md"}
    if kind == "code":
        resource.update(repo_id="code", path="module/source.c")
    lock = {"resources": [resource], "snapshots": [
        {"source_id": "source", "snapshot_id": "old", "sha256": "a" * 64},
        {"source_id": "source", "snapshot_id": "new", "sha256": "b" * 64}]}
    rows = [{"source_id": "source", "old_snapshot_ids": ["old"], "new_snapshot_id": "new",
             "source_lock_digest": "c" * 64}] if proposals else []
    view = {"batch_kind": "content", "event_proposals": rows,
            "publication_plan": {"event_proposals": copy.deepcopy(rows)},
            "writes": [{"path": "governance/sources.lock.yaml", "expected_old_digest": "c" * 64}]}
    previous = {"validity_epoch": 4, "blocked_claims": [], "processed_event_ids": [],
                "observed_sources": {}, "knowledge_apply_watermark": "formal-only"}
    return view, lock, previous


def block(*, reason="source_changed", identity="card", claim_id="c1"):
    return {"card_id": identity, "claim_id": claim_id, "reason": reason,
            "source_id": "source", "conditions": {"applicability": "unknown"}}


def project(view, lock, cards, previous, matches=None):
    return maintenance.project_state(view, lock, cards, previous,
                                     current_source_matches=matches if matches is not None else {("source", "new"): True})


def test_updated_claim_clears_old_block_and_leaves_all_inputs_unchanged():
    view, lock, previous = inputs()
    previous["blocked_claims"] = [block()]
    previous["digest"] = "sealed-formal-record"
    cards, matches = [card()], {("source", "new"): True}
    before = copy.deepcopy((view, lock, cards, previous, matches))
    result = project(view, lock, cards, previous, matches)
    assert result == {"validity_epoch": 6, "blocked_claims": [], "processing_digest": runtime.digest([])}
    assert (view, lock, cards, previous, matches) == before
    assert set(result) == {"validity_epoch", "blocked_claims", "processing_digest"}


@pytest.mark.parametrize("kind, reason", [("raw", "source_changed"), ("code", "code_changed")])
def test_new_event_blocks_only_candidate_claims_still_using_old_snapshot(kind, reason):
    view, lock, previous = inputs(kind=kind)
    result = project(view, lock, [card("repaired"), card("stale", "old")], previous)
    change = {"source_id": "source", "old_snapshot_ids": ["old"], "new_snapshot_id": "new", "new_sha256": "b" * 64}
    if kind == "code":
        change.update(source_kind="code", repo_id="code", path="module/source.c")
    assert result["validity_epoch"] == 5
    assert result["blocked_claims"] == [{"card_id": "stale", "claim_id": "c1", "reason": reason,
        "event_id": runtime.digest(change), "source_id": "source", "old_snapshot_ids": ["old"],
        "new_snapshot_id": "new", "conditions": {"applicability": "unknown"}}]
    assert result["processing_digest"] == runtime.digest(result["blocked_claims"])


def test_no_proposal_still_rechecks_existing_freshness_blocks_like_content_publish():
    view, lock, previous = inputs(proposals=False)
    previous["blocked_claims"] = [block(), block(reason="semantic_review_required"), block(identity="*")]
    result = project(view, lock, {"card": card()}, previous)
    assert result["validity_epoch"] == 5
    assert result["blocked_claims"] == previous["blocked_claims"][1:]


@pytest.mark.parametrize("matches", [{}, {("source", "new"): False}, {("source", "new"): 1}])
def test_new_event_requires_verified_current_source_even_without_a_claim(matches):
    view, lock, previous = inputs()
    before = copy.deepcopy(previous)
    with pytest.raises(runtime.NodeError, match="not verified current"):
        project(view, lock, [], previous, matches)
    assert previous == before


def test_missing_current_observation_and_latest_snapshot_mismatch_retain_blocks():
    view, lock, previous = inputs(proposals=False)
    previous["blocked_claims"] = [block()]
    assert project(view, lock, [card()], previous, {})["blocked_claims"] == previous["blocked_claims"]
    previous["observed_sources"] = {"source": {"snapshot_id": "new", "event_id": "existing"}}
    assert project(view, lock, [card(snapshot="old")], previous,
                   {("source", "old"): True})["blocked_claims"] == previous["blocked_claims"]


@pytest.mark.parametrize("cards", [[], [card(lifecycle="deprecated")], [card(claim_ids=("replacement",))]])
def test_retired_or_removed_claim_clears_only_mechanical_block(cards):
    view, lock, previous = inputs(proposals=False)
    previous["blocked_claims"] = [block(), block(reason="semantic_review_required")]
    result = project(view, lock, cards, previous)
    assert result["validity_epoch"] == 5
    assert result["blocked_claims"] == previous["blocked_claims"][1:]


def test_processed_transition_does_not_increment_epoch_again():
    view, lock, previous = inputs()
    previous["processed_event_ids"] = [runtime.digest({"source_id": "source", "old_snapshot_ids": ["old"],
        "new_snapshot_id": "new", "new_sha256": "b" * 64})]
    assert project(view, lock, [card(snapshot="old")], previous)["validity_epoch"] == 4
    assert project(view, lock, [card(snapshot="old")], previous)["blocked_claims"] == []


def test_record_only_preserves_restrictions_and_pending_events():
    view, lock, previous = inputs(proposals=False)
    view["batch_kind"] = "record_only"
    previous.update(blocked_claims=[block()], pending_event_ids=["unfinished"])
    result = project(view, lock, [card()], previous)
    assert result["validity_epoch"] == 4 and result["blocked_claims"] == previous["blocked_claims"]
    view, lock, previous = inputs()
    view["batch_kind"] = "record_only"
    with pytest.raises(runtime.NodeError, match="Record-only"):
        project(view, lock, [], previous)


@pytest.mark.parametrize("pending", [{"pending_event_ids": ["unfinished"]}, {"pending_events": [{"event_id": "unfinished"}]}])
def test_content_projection_requires_pending_event_recovery(pending):
    view, lock, previous = inputs()
    previous.update(pending)
    with pytest.raises(runtime.NodeError, match="explicit recovery"):
        project(view, lock, [], previous)


def test_proposal_binding_cannot_be_replaced():
    view, lock, previous = inputs()
    view["event_proposals"][0]["source_lock_digest"] = "d" * 64
    with pytest.raises(runtime.NodeError, match="frozen publication"):
        project(view, lock, [], previous)
    view["publication_plan"]["event_proposals"] = copy.deepcopy(view["event_proposals"])
    with pytest.raises(runtime.NodeError, match="CAS binding"):
        project(view, lock, [], previous)


def test_proposal_requires_exact_old_snapshot_set():
    view, lock, previous = inputs()
    lock["snapshots"].append({"source_id": "source", "snapshot_id": "also-old", "sha256": "d" * 64})
    with pytest.raises(runtime.NodeError, match="candidate snapshots"):
        project(view, lock, [], previous)
