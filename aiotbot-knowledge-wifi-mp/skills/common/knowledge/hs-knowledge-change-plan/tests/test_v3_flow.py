"""Current public flow over committed synthetic raw and a fixture human signer."""

import base64
import hashlib
import json
import subprocess
import shutil
import sys
import time

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


@pytest.mark.parametrize("unrelated_nav_changes", [False, True, "historical_fallback", "local_only"])
def test_current_ingest_plan_review_confirm_lint_record_apply_query_submit(harness, unrelated_nav_changes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def git(*args):
        return subprocess.run(["git", "-C", str(harness.base), *args], capture_output=True, check=True).stdout.decode().strip()

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    (harness.base / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8")
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement.\n")
    git("init", "-q")
    git("add", "--", harness.root.name + "/docs-raw/specs/source.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "original")
    scan_ref = harness.run("source-scan", {"operation_id": "op"}, "scan")["data"]["scan_ref"]
    scan = harness.record(scan_ref)
    unit = scan["units"][0]
    materials = harness.run("source-scan", {"operation_id": "op", "scan_ref": scan_ref}, "prepare")["data"]["material_ref"]
    material = harness.record(materials)
    bundle = harness.record(material["bundle_ref"])
    assert bundle["snapshots"][0]["recovery"]["kind"] == "git"
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        # Negative fixture: the retained bytes are genuine capture output, but a
        # local object must not stand in for actual cross-clone Git recovery.
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
    key = Ed25519PrivateKey.generate()
    catalog = json.loads(harness.catalog.read_bytes())
    catalog["review_trust"] = {"adapters": {"fixture": {"synthetic": True, "fixture_root": str(harness.root),
        "public_key_b64": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}}
    harness.catalog.write_bytes(canonical(catalog))
    harness.write(".isolated-knowledge-fixture", b"AIOTBOT_SYNTHETIC_FIXTURE_V2")
    prepared = harness.run("confirmation-prepare", {"operation_id": "op", "view_ref": view_ref})
    display_ref = prepared["data"]["display_ref"]
    display = harness.record(display_ref)
    payload = {"actor_type": "human", "actor_id": "fixture-human", "decision": "approve", "display_digest": display["digest"],
               "view_digest": display["view_digest"], "challenge": display["challenge"], "issued_at": time.time()}
    event = {"schema_version": "2.0", "record_kind": "host_event", "adapter_id": "fixture", "payload": payload,
             "signature_b64": base64.b64encode(key.sign(canonical(payload))).decode()}
    event_ref = harness.write(".build/operations/op/event.json", canonical(event))
    proof = harness.run("confirmation-record", {"operation_id": "op", "display_ref": display_ref, "host_event_ref": event_ref})["data"]["manual_review_ref"]
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
    apply_request = {"operation_id": "op", "v3_required": True, "view_ref": view_ref, "proof_ref": proof,
                     "ingest_record_ref": record_ref, "lint_report_ref": lint_ref, "content_review_ref": review}
    if unrelated_nav_changes in {"historical_fallback", "local_only"}:
        configuration = (harness.base / "config.yml").read_bytes()
        if unrelated_nav_changes == "historical_fallback":
            (harness.base / "config.yml").unlink()
        source = bundle["snapshots"][0]
        readable = harness.run("source-capture", {"operation_id": "op", "bundle_ref": material["bundle_ref"],
                               "source_ref": {"evidence_ref": "e1", "source_id": source["source_id"],
                                              "snapshot_id": source["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}}, "resolve-source")
        assert base64.b64decode(readable["data"]["bytes_b64"]) == b"# Source\nSynthetic fixture statement.\n"
        blocked = harness.run("apply", apply_request, expected=3)
        assert "recover" in blocked["diagnostics"][0]["message"] or "portable" in blocked["diagnostics"][0]["message"]
        assert not (harness.root / "knowledge/rules/new.md").exists()
        (harness.base / "config.yml").write_bytes(configuration)
        return
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
            assert "conflict" in blocked["diagnostics"][0]["message"] or "findings" in blocked["diagnostics"][0]["message"]
            assert not (harness.root / "knowledge/rules/new.md").exists()
    applied = harness.run("apply", apply_request)["data"]["apply_result_ref"]
    saved = harness.record("logs/ingest/op.yaml")
    assert saved["acceptance"]["cards"][0]["card_id"] == "new"
    generation = harness.run("index-build", {"operation_id": "op"}, "build")["data"]["generation_ref"]
    queries = harness.run("query-regression", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "generation_ref": generation})["data"]["report_ref"]
    ready = harness.run("publish-handoff", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries})
    assert ready["phase"] == "ready_to_submit"
    git("add", "--", *[harness.root.name + "/" + ref for ref in ready["data"]["commit_files"]])
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "knowledge batch")
    commit = git("rev-parse", "HEAD")
    submitted = harness.run("publish-handoff", {"operation_id": "op", "v3_required": True,
        "apply_result_ref": applied, "query_report_ref": queries, "commit_sha": commit}, "verify-submission")
    assert submitted["phase"] == "submitted"
