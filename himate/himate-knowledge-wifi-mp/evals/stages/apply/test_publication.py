"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_publication import (
    HELPER,
    Path,
    base64,
    installed_publication,
    pytest,
)


def test_plan_separates_content_identity_from_stage_addresses(publication_case):
    ctx, view, entry, raw = publication_case
    publication = HELPER.load_contract("publication")
    plan = publication.prepare_plan(ctx, view)
    moved = {**entry, "stage_ref": ctx.base + "/staged/second/" + entry["sha256"] + ".bin"}
    destination = ctx.root / moved["stage_ref"]
    destination.parent.mkdir(parents=True)
    destination.write_bytes(raw)
    other = publication.prepare_plan(ctx, {**view, "staged_objects": [moved]})
    assert plan["content_digest"] == other["content_digest"]
    assert plan["publication_plan_digest"] != other["publication_plan_digest"]
    assert plan["payloads"] == other["payloads"]
    assert not (ctx.root / entry["final_ref"]).exists()


def test_plan_rejects_changed_payload_and_unowned_stage_escape(publication_case):
    ctx, view, entry, _ = publication_case
    publication = HELPER.load_contract("publication")
    changed = {**view, "writes": [{**view["writes"][0], "bytes_b64": base64.b64encode(b"changed\n").decode()}]}
    with pytest.raises(ValueError, match="(bytes|digest|fingerprint)"):
        publication.prepare_plan(ctx, changed)
    escaped = {**entry, "stage_ref": ".build/operations/other/staged/a.bin"}
    with pytest.raises(ValueError):
        publication.prepare_plan(ctx, {**view, "staged_objects": [escaped]})


def test_plan_rejects_conflicting_formal_destinations(publication_case):
    ctx, view, entry, _ = publication_case
    publication = HELPER.load_contract("publication")
    conflict = {**entry, "sha256": "f" * 64}
    with pytest.raises(ValueError):
        publication.prepare_plan(ctx, {**view, "staged_objects": [entry, conflict]})


def test_published_history_does_not_require_draft_or_current_card_bytes(publication_case):
    publication, ctx, manifest, entry = installed_publication(publication_case)
    (ctx.root / entry["stage_ref"]).unlink()
    (ctx.root / "knowledge/rules/a.md").write_bytes(b"later legitimate revision\n")
    assert publication.read_manifest(ctx) == manifest
    with pytest.raises(ValueError, match="(changed|differs)"):
        publication.read_manifest(ctx, verify_files=True)


def test_cleanup_uses_owned_list_and_keeps_borrowed_and_unknown_files(publication_case):
    publication, ctx, manifest, entry = installed_publication(publication_case, record_only=True)
    unknown = ctx.root / ctx.base / "unregistered-helper.bin"
    unknown.write_bytes(b"not registered\n")
    borrowed = {"path": ".build/operations/previous/draft.md", "sha256": HELPER.sha(b"borrowed\n"),
                "bytes": 9, "owner_operation_id": "previous"}
    path = ctx.root / borrowed["path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(b"borrowed\n")
    owned = [{"path": entry["stage_ref"], "sha256": entry["sha256"], "bytes": entry["bytes"],
              "owner_operation_id": ctx.operation}, borrowed]
    completion = publication.write_completion(ctx, manifest, data={"published": True},
        retrieval={"complete": True, "scope": "record_only"}, owned_files=owned)
    finished = publication.cleanup(ctx, manifest, completion)
    assert finished["batch_complete"] is True and finished["cleanup"]["status"] == "done"
    assert not (ctx.root / entry["stage_ref"]).exists()
    assert unknown.read_bytes() == b"not registered\n" and path.read_bytes() == b"borrowed\n"
    assert finished["cleanup"]["retained"][0]["reason"] == "borrowed_operation"
    assert publication.read_completion(ctx, manifest) == finished


def test_cleanup_failure_preserves_publication_and_can_retry_only_cleanup(publication_case, monkeypatch):
    publication, ctx, manifest, entry = installed_publication(publication_case, record_only=True)
    owned = [{"path": entry["stage_ref"], "sha256": entry["sha256"], "bytes": entry["bytes"],
              "owner_operation_id": ctx.operation}]
    completion = publication.write_completion(ctx, manifest, data={"published": True},
        retrieval={"complete": True, "scope": "record_only"}, owned_files=owned)
    target = ctx.root / entry["stage_ref"]
    original = Path.unlink

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("synthetic cleanup denial")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", denied)
        failed = publication.cleanup(ctx, manifest, completion)
    assert failed["published"] is True and failed["batch_complete"] is False
    assert failed["cleanup"]["status"] == "cleanup_pending"
    assert target.exists() and publication.read_manifest(ctx) == manifest
    retried = publication.cleanup(ctx, manifest, failed)
    assert retried["batch_complete"] is True and not target.exists()
    with pytest.raises(ValueError, match="(changed|conflict)"):
        publication.write_completion(ctx, manifest, data={}, retrieval={"complete": True},
                                     owned_files=owned, expected_digest=completion["digest"])


def test_submission_uses_formal_closure_after_stage_cleanup(publication_case):
    publication, ctx, manifest, entry = installed_publication(publication_case, record_only=True)
    completion = publication.write_completion(ctx, manifest, data={"published": True},
        retrieval={"complete": True, "scope": "record_only"}, owned_files=[{
            "path": entry["stage_ref"], "sha256": entry["sha256"], "bytes": entry["bytes"],
            "owner_operation_id": ctx.operation}])
    publication.cleanup(ctx, manifest, completion)
    submission = HELPER.load_contract("submission")
    handoff = submission.publish_handoff(ctx, {"operation_id": ctx.operation,
        "publication_ref": publication.manifest_ref(ctx.operation)})
    assert publication.manifest_ref(ctx.operation) in handoff["commit_files"]
    assert publication.completion_ref(ctx.operation) in handoff["commit_files"]
    assert entry["final_ref"] in handoff["commit_files"]
    assert not any(ref.startswith(".build/") for ref in handoff["commit_files"])
    preserved = ctx.record(handoff["publish_handoff_ref"], "artifact_manifest")
    assert {"owner": "fixed_ci", "action": "reuse lint deterministic checks on submitted content",
            "status": "pending"} in preserved["external_obligations"]
    assert preserved["git_merge_verified"] is False and preserved["remote_push_verified"] is False


def test_processing_record_must_match_frozen_digest_before_formal_write(publication_case):
    ctx, view, _, _ = publication_case
    publication = HELPER.load_contract("publication")
    inventory = ctx.seal({"scope": ["docs-raw/specs"], "full_scan": False, "complete": True, "units": [{
        "unit_id": "one", "source_id": "raw", "path": "docs-raw/specs/a.md", "observed_fingerprint": "a" * 64,
        "previous_fingerprint": None, "change": "new", "progress": None, "read_error": None}]}, "source_inventory")
    pending = ctx.seal({"record_id": "pending", "target_path": "logs/ingest/pending.yaml", "batch_kind": "record_only",
        "status": "pending", "progress": {}, "scan_ref": ctx.base + "/inventory.json", "scan_digest": inventory["digest"],
        "inventory": inventory, "dispositions": [{"unit_id": "one", "action": "defer", "reason": "Required material missing",
        "observed_fingerprint": "a" * 64, "adopted_fingerprint": None, "progress": "blocked", "card_refs": [], "claim_refs": []}]}, "ingest_record")
    reference = ctx.save(ctx.base + "/pending.json", pending)
    with pytest.raises(ValueError, match="Pending record changed"):
        publication.publish_processing_record(ctx, view, reference, expected_digest="0" * 64)
    assert not (ctx.root / "logs/ingest/pending.yaml").exists()


def test_manifest_includes_actual_durable_maintenance_state(publication_case):
    ctx, _, _, _ = publication_case
    state = ctx.seal({"validity_epoch": 3, "blocked_claims": [{"card_id": "old", "claim_id": "c1", "reason": "source_changed"}],
        "processed_event_ids": [], "pending_event_ids": [], "pending_events": [], "observed_sources": {},
        "impact_scan_watermark": None, "knowledge_apply_watermark": None}, "maintenance_state")
    ctx.save("logs/events/state.json", state)
    _, _, manifest, _ = installed_publication(publication_case)
    row = next(row for row in manifest["files"] if row["path"] == "logs/events/state.json")
    assert row["kind"] == "maintenance_state"
    assert row["sha256"] == HELPER.sha((ctx.root / row["path"]).read_bytes())


def test_resealed_content_completion_requires_durable_retrieval_facts(publication_case):
    publication, ctx, manifest, _ = installed_publication(publication_case)
    forged = ctx.seal({"purpose": "knowledge_publication_completion", "protocol_version": manifest["protocol_version"],
        "publication_ref": publication.manifest_ref(ctx.operation), "publication_digest": manifest["digest"],
        "content_digest": manifest["content_digest"], "published": True, "batch_complete": True,
        "phase": "completed", "data": {"activated": True}, "retrieval": {"complete": True},
        "cleanup": {"status": "done", "owned": [], "deleted": [], "retained": [], "failed": []}}, "artifact_manifest")
    ctx.save(publication.completion_ref(ctx.operation), forged)
    with pytest.raises(ValueError, match="(retrieval|activation|regression)"):
        publication.read_completion(ctx, manifest)
