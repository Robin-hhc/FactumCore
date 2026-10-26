"""Public local ingest and optional human publishing over synthetic originals."""

import base64
import hashlib
import json
import subprocess
import shutil
import sys

import pytest
import yaml


@pytest.fixture(autouse=True)
def pin_fixture(harness):
    package_hash = sys.modules[type(harness).__module__].package_hash

    frozen = harness.base / "frozen-skills"
    shutil.copytree(harness.packages, frozen, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    harness.packages = frozen
    catalog = json.loads(harness.catalog.read_bytes())
    for name, spec in catalog["skills"].items():
        spec.update(root=str(frozen / name), package_digest=package_hash(frozen / name))
    harness.catalog.write_text(json.dumps(catalog), encoding="utf-8")
    path = harness.root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(path.read_bytes())
    for row in lock["files"].values():
        row["sha256"] = hashlib.sha256((harness.root / row["path"]).read_bytes()).hexdigest()
    path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    harness.rules = hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("unrelated_nav_changes", [False, True, "historical_fallback", "local_only", "uncommitted_raw"])
def test_current_ingest_review_lint_record_apply_query_without_human_confirmation(harness, unrelated_nav_changes):
    def git(*args):
        return subprocess.run(["git", "-C", str(harness.base), *args], capture_output=True, check=True).stdout.decode().strip()

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    (harness.base / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8")
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement.\n")
    if unrelated_nav_changes != "uncommitted_raw":
        git("init", "-q")
        git("add", "--", harness.root.name + "/docs-raw/specs/source.md")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "original")
        initial_commit = git("rev-parse", "HEAD")
    scan_ref = harness.run("source-scan", {"operation_id": "op"}, "scan")["data"]["scan_ref"]
    scan = harness.record(scan_ref)
    unit = scan["units"][0]
    materials = harness.run("source-scan", {"operation_id": "op", "scan_ref": scan_ref}, "prepare")["data"]["material_ref"]
    material = harness.record(materials)
    bundle = harness.record(material["bundle_ref"])
    if unrelated_nav_changes == "uncommitted_raw":
        assert bundle["snapshots"][0]["recovery"]["method"] == "evidence_object"
        assert not (harness.base / ".git").exists()
    else:
        assert bundle["snapshots"][0]["recovery"]["kind"] == "git"
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        # Local completion may use exact retained capture bytes. This does not
        # claim that another clone can recover the same source.
        snapshot = bundle["snapshots"][0]
        local = {"method": "evidence_object", "path": "logs/evidence/objects/" + snapshot["sha256"] + ".bin"}
        assert (harness.root / local["path"]).is_file()
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
    candidate = harness.write(".build/candidates/new.md", harness.card("new", bundle))
    plan = harness.run("change-plan", {"operation_id": "op", "v3_required": True, "semantic_plan_ref": semantic,
        "bundle_ref": material["bundle_ref"], "decisions": [{"candidate_id": unit["unit_id"], "decision": "create",
        "reason": "Authored planned rule", "card_inputs": [candidate]}]})["data"]["plan_ref"]
    view_ref = harness.run("view-materialize", {"operation_id": "op", "plan_ref": plan})["data"]["view_ref"]
    review = harness.run("change-plan", {"operation_id": "op", "semantic_plan_ref": semantic, "view_ref": view_ref,
        "reviewer_id": "independent", "independent_context": "second-context", "sampled_unit_ids": [unit["unit_id"]],
        "unreviewed_unit_ids": [], "reason": "New rule needs full risk sample", "findings": []}, "review")["data"]["content_review_ref"]
    assert "review_trust" not in json.loads(harness.catalog.read_bytes())
    lint_ref = ".build/operations/op/final-lint.json"
    lint_input = harness.write(".build/operations/op/lint-input.json", canonical({"view_ref": view_ref}))
    lint = subprocess.run([sys.executable, str(harness.packages / "hs-knowledge-lint/scripts/cli.py"),
        "--knowledge-root", str(harness.root), "--rules-digest", harness.rules,
        "--input", str(harness.root / lint_input), "--output", str(harness.root / lint_ref)], capture_output=True)
    assert lint.returncode == 0, lint.stdout
    record_ref = harness.run("source-scan", {"operation_id": "op", "scan_ref": scan_ref, "view_ref": view_ref, "lint_ref": lint_ref,
        "dispositions": [{"unit_id": unit["unit_id"], "action": "create", "reason": "New exact design rule",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": unit["observed_fingerprint"],
                          "progress": "completed", "card_refs": ["new"], "claim_refs": ["new#new-claim"]}]}, "record")["data"]["ingest_record_ref"]
    apply_request = {"operation_id": "op", "v3_required": True, "view_ref": view_ref,
                     "ingest_record_ref": record_ref, "lint_report_ref": lint_ref, "content_review_ref": review}
    if unrelated_nav_changes == "uncommitted_raw":
        original_path = harness.root / bundle["snapshots"][0]["recovery"]["path"]
        original_bytes = original_path.read_bytes()
        for defect in ("missing", "changed"):
            if defect == "missing":
                original_path.unlink()
            else:
                original_path.write_bytes(b"!" + original_bytes[1:])
            rejected = harness.run("apply", apply_request, expected=3)
            assert rejected["phase"] == "awaiting"
            assert not (harness.root / "knowledge/rules/new.md").exists()
            assert not (harness.root / "logs/ingest/op.yaml").exists()
            original_path.write_bytes(original_bytes)
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        configuration = (harness.base / "config.yml").read_bytes()
        if unrelated_nav_changes == "historical_fallback":
            (harness.base / "config.yml").unlink()
        source = bundle["snapshots"][0]
        readable = harness.run("source-capture", {"operation_id": "op", "bundle_ref": material["bundle_ref"],
                               "source_ref": {"evidence_ref": "e1", "source_id": source["source_id"],
                                              "snapshot_id": source["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}}, "resolve-source")
        assert base64.b64decode(readable["data"]["bytes_b64"]) == b"# Source\nSynthetic fixture statement.\n"
        # Keep the unavailable Git configuration absent through local admission.
        # The immutable captured original remains available and hash checked.
    if unrelated_nav_changes is True:
        extra = harness.write("knowledge/unrelated/index.md", b"[Broken navigation](missing.md)\n")
        blocked = harness.run("apply", apply_request, expected=3)
        assert "fixed" in blocked["diagnostics"][0]["message"]
        assert not (harness.root / "knowledge/rules/new.md").exists()
        (harness.root / extra).unlink()
        for defect in ("author", "findings"):
            forged = harness.record(review)
            forged.pop("digest")
            if defect == "author":
                forged["reviewer_id"] = "author"
            else:
                forged["findings"] = [{"unit_id": unit["unit_id"], "return_to": "P3", "reason": "Unresolved contradiction", "evidence": ["L2"]}]
            forged["digest"] = hashlib.sha256(canonical(forged)).hexdigest()
            ref = harness.write(".build/operations/op/forged-review-" + defect + ".json", canonical(forged))
            blocked = harness.run("apply", {**apply_request, "content_review_ref": ref}, expected=3)
            assert blocked["status"] == "blocked"
            assert not (harness.root / "knowledge/rules/new.md").exists()
    applied = harness.run("apply", apply_request)["data"]["apply_result_ref"]
    saved = harness.record("logs/ingest/op.yaml")
    assert saved["acceptance"]["cards"][0]["card_id"] == "new"
    assert saved["acceptance"]["cards"][0]["review_result"] == "supported"
    generation = harness.run("index-build", {"operation_id": "op"}, "build")["data"]["generation_ref"]
    queries = harness.run("query-regression", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "generation_ref": generation})["data"]["report_ref"]
    query = harness.run("query", {"operation_id": "local-query", "query": "Synthetic", "purpose": "guidance"}, "search")
    assert query["data"]["matches"][0]["card_id"] == "new"
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
    ready = harness.run("publish-handoff", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries})
    assert ready["phase"] == "ready_to_submit"
    handoff = harness.record(ready["data"]["publish_handoff_ref"])
    assert {"owner": "authorized_committer", "action": "provide exact originals and portable recovery locations for CI and other clones",
            "status": "pending"} in handoff["external_obligations"]
    git("add", "--", *[harness.root.name + "/" + ref for ref in ready["data"]["commit_files"]])
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "knowledge batch")
    commit = git("rev-parse", "HEAD")
    submitted = harness.run("publish-handoff", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries, "commit_sha": commit}, "verify-submission")
    assert submitted["phase"] == "submitted"


def test_local_source_recovery_still_rejects_unsafe_paths_and_locators(harness):
    bundle_ref, bundle = harness.capture("source-guards", b"# Source\nExact captured source.\n")
    snapshot = bundle["snapshots"][0]
    reference = {"evidence_ref": "e1", "source_id": snapshot["source_id"],
                 "snapshot_id": snapshot["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}
    request = {"operation_id": "source-guards", "bundle_ref": bundle_ref, "source_ref": reference}
    resolved = harness.run("source-capture", request, "resolve-source")
    assert base64.b64decode(resolved["data"]["bytes_b64"]) == b"# Source\nExact captured source.\n"
    bad_locator = {**reference, "locator": {"kind": "lines", "start": 1, "end": 999}}
    rejected = harness.run("source-capture", {**request, "source_ref": bad_locator}, "resolve-source", expected=2)
    assert rejected["status"] == "error"
    snapshot["recovery"] = {"method": "evidence_object", "path": "logs/evidence/../../outside.bin"}
    bundle.pop("digest")
    raw = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    bundle["digest"] = hashlib.sha256(raw).hexdigest()
    unsafe = harness.write(".build/operations/source-guards/unsafe-bundle.json", json.dumps(bundle).encode())
    rejected = harness.run("source-capture", {**request, "bundle_ref": unsafe}, "resolve-source", expected=2)
    assert rejected["status"] == "error"
    assert not (harness.root / "knowledge/rules/new.md").exists()
