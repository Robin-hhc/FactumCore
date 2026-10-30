"""Public local ingest and optional human publishing over synthetic originals."""

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


def staged_path(harness, bundle, reference):
    entries = [row for row in bundle["staged_objects"] if row["final_ref"] == reference]
    assert len(entries) == 1
    path = (harness.root / entries[0]["stage_ref"]).absolute()
    return Path("\\\\?\\" + str(path)) if os.name == "nt" else path


@pytest.fixture(autouse=True)
def install_target_packages(harness):
    # The fixture already contains the frozen executable closure. Agent Skill
    # installation and catalog contents are not execution dependencies.
    assert (harness.root / "knowledge.py").is_file()
    assert (harness.root / "runtime/manifest.json").is_file()


@pytest.mark.parametrize("unrelated_nav_changes", [False, True, "historical_fallback", "local_only", "uncommitted_raw", "nested"])
def test_current_ingest_review_lint_record_apply_query_without_human_confirmation(harness, unrelated_nav_changes):
    if unrelated_nav_changes == "nested":
        nested = harness.base / "himate" / harness.root.name
        assert nested.resolve().is_relative_to(harness.base.resolve())
        nested.parent.mkdir()
        harness.root.rename(nested)
        harness.root = nested
    domain_path = harness.root.relative_to(harness.base).as_posix()
    def git(*args):
        return subprocess.run(["git", "-C", str(harness.base), *args], capture_output=True, check=True).stdout.decode().strip()

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    (harness.base / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": domain_path}, "repos": []}), encoding="utf-8")
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement.\n")
    if unrelated_nav_changes != "uncommitted_raw":
        git("init", "-q")
        git("add", "--", domain_path + "/docs-raw/specs/source.md")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "original")
        initial_commit = git("rev-parse", "HEAD")
    prepared = harness.run("source", {"operation_id": "op"}, "run")
    assert prepared["phase"] == "prepared"
    scan_ref, materials = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    scan = harness.record(scan_ref)
    unit = scan["units"][0]
    material = harness.record(materials)
    bundle = harness.record(material["bundle_ref"])
    if unrelated_nav_changes == "uncommitted_raw":
        assert bundle["snapshots"][0]["recovery"]["method"] == "evidence_object"
        assert not (harness.base / ".git").exists()
    else:
        assert bundle["snapshots"][0]["recovery"]["kind"] == "git"
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        # P1 binds exact retained stage bytes to their preallocated final ref.
        # This test still removes Git access without publishing before P6.
        snapshot = bundle["snapshots"][0]
        local = dict(snapshot["local_recovery"])
        assert staged_path(harness, bundle, local["path"]).is_file()
        assert not (harness.root / local["path"]).exists()
        snapshot["local_recovery"] = local
        if unrelated_nav_changes == "local_only":
            snapshot["recovery"] = local
        bundle.pop("digest")
        bundle["digest"] = hashlib.sha256(canonical(bundle)).hexdigest()
        harness.write(material["bundle_ref"], canonical(bundle))
        material["bundle_digest"] = bundle["digest"]
        material.pop("digest")
        material["digest"] = hashlib.sha256(canonical(material)).hexdigest()
        harness.write(materials, canonical(material))
    semantic = harness.run("change-plan", {"operation_id": "op", "scan_ref": scan_ref, "material_ref": materials,
        "author_id": "author", "units": [{"unit_id": unit["unit_id"], "outcome": "content", "reason": "New independent topic"}],
        "claim_changes": [{"unit_ids": [unit["unit_id"]], "card_id": "new", "claim_id": "new-claim", "action": "create",
                           "before": None, "after": "Synthetic fixture statement", "conditions": "Synthetic design only",
                           "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}],
                           "preserved": "No old knowledge", "reason": "New topic"}],
        "card_actions": [{"card_id": "new", "decision": "create", "author_id": "author", "unit_ids": [unit["unit_id"]], "reason": "Independent rule"}],
        "target_queries": [{"id": "new-rule", "query": "Synthetic", "purpose": "guidance", "required": ["new"], "expected_claim_ids": ["new#new-claim"]}]}, "plan")["data"]["semantic_plan_ref"]
    if unrelated_nav_changes == "historical_fallback":
        # This candidate actually adopts retained local originals with no
        # current Git configuration. Removing an input after P4 is a different
        # stale-input case, covered separately by the batch drift tests.
        configuration = (harness.base / "config.yml").read_bytes()
        (harness.base / "config.yml").unlink()
    candidate = harness.write(".build/candidates/new.md", harness.card("new", bundle))
    view_ref = harness.run("view-materialize", {"operation_id": "op", "v3_required": True, "semantic_plan_ref": semantic,
        "bundle_ref": material["bundle_ref"], "decisions": [{"candidate_id": unit["unit_id"], "decision": "create",
        "reason": "Authored planned rule", "card_inputs": [candidate]}]})["data"]["view_ref"]
    reviewed = harness.run("lint", {"operation_id": "op", "semantic_plan_ref": semantic, "view_ref": view_ref,
        "reviewer_id": "independent", "independent_context": "second-context", "sampled_unit_ids": [unit["unit_id"]],
        "unreviewed_unit_ids": [], "reason": "New rule needs full risk sample", "findings": []}, "review")
    review = reviewed["data"]["content_review_ref"]
    assert "review_trust" not in json.loads(harness.catalog.read_bytes())
    assert reviewed["status"] == "passed" and reviewed["data"]["fixed_checks_executed"] is True
    record_ref = harness.run("source", {"operation_id": "op", "scan_ref": scan_ref, "view_ref": view_ref,
        "disposition_preview_ref": harness.record(view_ref)["disposition_preview_ref"]}, "record")["data"]["ingest_record_ref"]
    apply_request = {"operation_id": "op", "v3_required": True, "view_ref": view_ref,
                     "ingest_record_ref": record_ref, "content_review_ref": review}
    if unrelated_nav_changes == "uncommitted_raw":
        original_path = staged_path(harness, bundle, bundle["snapshots"][0]["recovery"]["path"])
        original_bytes = original_path.read_bytes()
        for defect in ("missing", "changed"):
            if defect == "missing":
                original_path.unlink()
            else:
                original_path.write_bytes(b"!" + original_bytes[1:])
            # The new frozen publication map rejects absent/corrupt payloads
            # as invalid input, before reaching the legacy admission gate.
            rejected = harness.run("apply", apply_request, "batch", expected=2)
            assert rejected["phase"] == "invalid"
            assert rejected["diagnostics"][0]["code"] == (
                "invalid_input" if defect == "missing" else "STAGED_OBJECT_CHANGED")
            assert not (harness.root / "knowledge/rules/new.md").exists()
            assert not (harness.root / "logs/ingest/op.yaml").exists()
            original_path.write_bytes(original_bytes)
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        source = bundle["snapshots"][0]
        readable = harness.run("source", {"operation_id": "op", "bundle_ref": material["bundle_ref"],
                               "source_ref": {"evidence_ref": "e1", "source_id": source["source_id"],
                                              "snapshot_id": source["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}}, "resolve-source")
        assert base64.b64decode(readable["data"]["bytes_b64"]) == b"# Source\nSynthetic fixture statement.\n"
        # Keep the unavailable Git configuration absent through local admission.
        # The immutable captured original remains available and hash checked.
    if unrelated_nav_changes is True:
        extra = harness.write("knowledge/unrelated/index.md", b"[Broken navigation](missing.md)\n")
        blocked = harness.run("apply", apply_request, "batch", expected=3)
        assert "input" in blocked["diagnostics"][0]["message"].lower()
        assert not (harness.root / "knowledge/rules/new.md").exists()
        (harness.root / extra).unlink()
        changed = harness.record(review)
        changed.pop("digest")
        changed["view_digest"] = "0" * 64
        changed["digest"] = hashlib.sha256(canonical(changed)).hexdigest()
        ref = harness.write(".build/operations/op/foreign-view-review.json", canonical(changed))
        rejected = harness.run("apply", {**apply_request, "content_review_ref": ref}, "batch", expected=2)
        assert "exact final view" in rejected["diagnostics"][0]["message"]
        assert not (harness.root / "knowledge/rules/new.md").exists()
        # Role declarations and unresolved review findings are information for
        # the caller's workflow; apply neither certifies nor gates on them.
        material = harness.record(review)
        material.pop("digest")
        material["reviewer_id"] = "author"
        material["findings"] = [{"unit_id": unit["unit_id"], "return_to": "P2",
                                 "reason": "Caller must resolve this review finding", "evidence": ["L2"]}]
        material["digest"] = hashlib.sha256(canonical(material)).hexdigest()
        apply_request["content_review_ref"] = harness.write(".build/operations/op/review-material.json", canonical(material))
    completed = harness.run("apply", apply_request, "batch")
    assert completed["phase"] == "completed" and completed["data"]["activated"] is True
    applied = completed["data"]["apply_result_ref"]
    saved = harness.record("logs/ingest/op.yaml")
    assert "acceptance" not in saved
    assert saved["progress"]["apply"]["status"] == "applied"
    manifest = harness.record(completed["data"]["publication_ref"])
    assert saved["content_view_digest"] == manifest["reviewed_view_digest"]
    assert not (harness.root / view_ref).exists()
    generation, queries = completed["data"]["generation_ref"], completed["data"]["report_ref"]
    query = harness.run("query", {"operation_id": "local-query", "query": "Synthetic", "purpose": "guidance"}, "search")
    assert query["data"]["matches"][0]["card_id"] == "new"
    assert query["data"]["generation_ref"] == generation
    read = harness.run("query", {"operation_id": "local-read", "receipt_ref": query["data"]["receipt_ref"],
        "card_id": "new"}, "read")["data"]
    assert read["generation_ref"] == query["data"]["generation_ref"]
    assert read["card_digest"] == query["data"]["matches"][0]["card_digest"]
    assert {claim["id"] for claim in read["claims"]} == {"new-claim"}
    if unrelated_nav_changes in {"historical_fallback", "local_only", "uncommitted_raw"}:
        assert (harness.root / "knowledge/rules/new.md").is_file()
        assert (harness.root / "artifacts/indexes/local/active.json").is_file()
        assert not (harness.root / "logs/operations/op/submission-result.json").exists()
        if unrelated_nav_changes == "uncommitted_raw":
            assert not (harness.base / ".git").exists()
        else:
            assert git("rev-parse", "HEAD") == initial_commit
        if unrelated_nav_changes == "historical_fallback":
            (harness.base / "config.yml").write_bytes(configuration)
        return
    ready = harness.run("apply", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries}, "prepare-submission")
    assert ready["phase"] == "ready_to_submit"
    handoff = harness.record(ready["data"]["publish_handoff_ref"])
    assert {"owner": "fixed_ci", "action": "reuse lint deterministic checks on submitted content",
            "status": "pending"} in handoff["external_obligations"]
    assert "verification_tier" not in handoff
    git("add", "--", *[domain_path + "/" + ref for ref in ready["data"]["commit_files"]])
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "knowledge batch")
    commit = git("rev-parse", "HEAD")
    submitted = harness.run("apply", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries, "commit_sha": commit}, "verify-submission")
    assert submitted["phase"] == "submitted"


def test_local_source_recovery_still_rejects_unsafe_paths_and_locators(harness):
    bundle_ref, bundle = harness.capture("source-guards", b"# Source\nExact captured source.\n")
    snapshot = bundle["snapshots"][0]
    reference = {"evidence_ref": "e1", "source_id": snapshot["source_id"],
                 "snapshot_id": snapshot["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}
    request = {"operation_id": "source-guards", "bundle_ref": bundle_ref, "source_ref": reference}
    resolved = harness.run("source", request, "resolve-source")
    assert base64.b64decode(resolved["data"]["bytes_b64"]) == b"# Source\nExact captured source.\n"
    bad_locator = {**reference, "locator": {"kind": "lines", "start": 1, "end": 999}}
    rejected = harness.run("source", {**request, "source_ref": bad_locator}, "resolve-source", expected=2)
    assert rejected["status"] == "error"
    snapshot["recovery"] = {"method": "evidence_object", "path": "logs/evidence/../../outside.bin"}
    bundle.pop("digest")
    raw = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    bundle["digest"] = hashlib.sha256(raw).hexdigest()
    unsafe = harness.write(".build/operations/source-guards/unsafe-bundle.json", json.dumps(bundle).encode())
    rejected = harness.run("source", {**request, "bundle_ref": unsafe}, "resolve-source", expected=2)
    assert rejected["status"] == "error"
    assert not (harness.root / "knowledge/rules/new.md").exists()
