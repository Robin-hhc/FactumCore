"""Signed repository acceptance survives removal of machine-private execution files."""

import base64
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("portable_fixture", Path(__file__).with_name("p7_test_helpers.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.mark.parametrize("nested", [False, True], ids=["flat", "nested-without-config"])
def test_accepted_repository_works_without_machine_private_review_files(tmp_path, nested):
    # This isolated test key signs publication receipts only.
    publication_key = Ed25519PrivateKey.generate()
    pipeline = fixture.Pipeline(tmp_path)
    workspace = pipeline.root.parent
    if nested:
        moved = workspace / "himate" / pipeline.root.name
        assert moved.resolve().is_relative_to(workspace.resolve())
        moved.parent.mkdir()
        pipeline.root.rename(moved)
        pipeline.root = moved
        pipeline.catalog["test_fixture_root"] = str(moved)
        pipeline.catalog["workspaces"] = {}
        pipeline.catalog_path.write_bytes(fixture.canonical(pipeline.catalog))
    domain_path = pipeline.root.relative_to(workspace).as_posix()
    bundle_ref, bundle = pipeline.capture("create", b"# Fixture\nPublished capture rule.\n")
    # This legacy hand-built acceptance fixture starts with durable source
    # evidence. New capture does not publish its staged objects by itself.
    for entry in bundle["staged_objects"]:
        raw = (pipeline.root / entry["stage_ref"]).read_bytes()
        assert fixture.sha(raw) == entry["sha256"] and len(raw) == entry["bytes"]
        pipeline.write(entry["final_ref"], raw)
    view_ref = pipeline.view("create", bundle_ref, "portable-rule", pipeline.card("portable-rule", bundle))
    pipeline.apply("create", view_ref)
    view = pipeline.record(view_ref)
    path = "knowledge/rules/portable-rule.md"
    card_sha = fixture.sha((pipeline.root / path).read_bytes())
    scan_ref = pipeline.call("knowledge-source-scan", {"operation_id": "create"}, "scan")["data"]["scan_ref"]
    scan = pipeline.record(scan_ref)
    inventory = scan["units"][0]
    record = {
        "schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "create",
        "status": "applied", "batch_kind": "content",
        "rules_digest": pipeline.rules, "tool_identity": view["tool_identity"],
        "content_view_digest": view["digest"],
        "scan_ref": scan_ref, "scan_digest": scan["digest"], "inventory": scan,
        "dispositions": [{"unit_id": inventory["unit_id"], "action": "update", "reason": "Applied the exact reviewed rule",
                          "observed_fingerprint": inventory["observed_fingerprint"], "adopted_fingerprint": inventory["observed_fingerprint"],
                          "progress": "completed", "card_refs": ["portable-rule"], "claim_refs": [{"card_id": "portable-rule", "claim_id": "c1"}]}],
        "progress": {"apply": {"status": "applied", "operation_id": "create", "view_digest": view["digest"]}},
        "acceptance": {"content_view_digest": view["digest"], "rules_digest": pipeline.rules,
                       "cards": [{"path": path, "card_id": "portable-rule", "sha256": card_sha, "review_mode": "manual_document",
                                  "claim_ids": ["c1"], "review_result": "supported"}],
                       "proof_digests": []},
    }
    record["digest"] = fixture.sha(fixture.canonical(record))
    record_ref = pipeline.write("logs/ingest/create.yaml", fixture.canonical(record))

    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(workspace), *args],
                              capture_output=True, check=True).stdout.decode().strip()

    git("init", "--initial-branch=main", "-q")
    git("config", "core.autocrlf", "false")
    git("add", *[domain_path + "/" + ref for ref in ("knowledge", "governance", "logs/ingest", "logs/evidence")])
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "accepted synthetic repository")
    pipeline.catalog["publication_trust"] = {"fixture-publication": {"synthetic": True, "fixture_root": str(pipeline.root),
        "public_key_b64": base64.b64encode(publication_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}
    pipeline.catalog_path.write_bytes(fixture.canonical(pipeline.catalog))
    payload = {"rules_digest": pipeline.rules, "knowledge_commit": git("rev-parse", "HEAD"), "card_digests": {path: card_sha},
               "acceptance_records": {record_ref: fixture.sha((pipeline.root / record_ref).read_bytes())}}
    publication = {"adapter_id": "fixture-publication", "payload": payload,
                   "signature_b64": base64.b64encode(publication_key.sign(fixture.canonical(payload))).decode()}
    receipt_ref = pipeline.write("logs/publication/accepted.json", fixture.canonical(publication))
    # Only machine-private execution state is removed from this isolated fixture.
    for relative in (".build", "logs/operations"):
        target = (pipeline.root / relative).resolve()
        assert target.is_relative_to(pipeline.root.resolve())
        if target.exists():
            shutil.rmtree(target)
        assert not target.exists()
    assert not (workspace / "config.yml").exists()
    built = pipeline.call("knowledge-index-build", {"operation_id": "portable-build", "channel": "shared", "publication_receipt_ref": receipt_ref})["data"]
    pipeline.call("knowledge-index-build", {"operation_id": "portable-activate", "generation_ref": built["generation_ref"], "expected_active": None}, "activate")
    result = pipeline.call("knowledge-query", {"operation_id": "portable-search", "channel": "shared", "purpose": "current", "query": "capture"})["data"]
    assert [match["card_id"] for match in result["matches"]] == ["portable-rule"]
    # An obsolete machine registration is not an execution prerequisite.
    pipeline.catalog["workspaces"] = {"wrong-workspace": {"config": str(pipeline.catalog_path), "rules_digest": pipeline.rules}}
    pipeline.catalog_path.write_bytes(fixture.canonical(pipeline.catalog))
    queried = pipeline.call("knowledge-query", {"operation_id": "old-registration", "channel": "shared", "purpose": "current", "query": "capture"})
    assert [row["card_id"] for row in queried["data"]["matches"]] == ["portable-rule"]
    # Processing history is optional metadata. Its presence is not an index/query gate.
    pipeline.write(record_ref, (pipeline.root / record_ref).read_bytes() + b"\n")
    queried = pipeline.call("knowledge-query", {"operation_id": "dirty-summary", "channel": "shared", "purpose": "current", "query": "capture"})
    assert [row["card_id"] for row in queried["data"]["matches"]] == ["portable-rule"]
