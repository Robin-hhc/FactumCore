"""Workflow progress metadata does not gate queries of unchanged source bytes."""
import base64
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import yaml
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("shared_pending_fixture", Path(__file__).resolve().parents[2] / "support/stages/apply_helpers.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.mark.parametrize("include_raw_refs", [False, True])
def test_processing_status_does_not_gate_query_of_unchanged_actual_sources(tmp_path, include_raw_refs):
    # This isolated test key signs publication receipts only.
    publication_key = Ed25519PrivateKey.generate()
    p = fixture.Pipeline(tmp_path)
    workspace = p.root.parent
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(workspace), *args], capture_output=True, check=True).stdout.decode().strip()
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    (workspace / "config.yml").write_bytes(yaml.safe_dump({"knowledge_roots": {"wifi": p.root.name}, "repos": []}).encode())
    original = b"# Fixture\nPublished capture statement remains unchanged.\n"
    p.write("docs-raw/specs/raw-source.md", original)
    git("add", "config.yml", p.root.name + "/docs-raw/specs/raw-source.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixed original")
    bundle_ref, bundle = p.capture("create", original)
    assert bundle["snapshots"][0]["recovery"]["kind"] == "git"
    view_ref = p.view("create", bundle_ref, "pending-rule", p.card("pending-rule", bundle))
    applied_ref, _ = p.apply("create", view_ref)
    view = p.record(view_ref)
    path = "knowledge/rules/pending-rule.md"
    card_sha = fixture.sha((p.root / path).read_bytes())
    inventory = {"schema_version": "2.0", "record_kind": "source_inventory", "operation_id": "create", "rules_digest": p.rules, "tool_identity": view["tool_identity"],
        "scope": ["docs-raw/specs"], "full_scan": False, "complete": True, "units": [{"unit_id": "u1", "path": "docs-raw/specs/raw-source.md", "source_id": "raw-source", "observed_fingerprint": fixture.sha(original), "previous_fingerprint": None, "change": "new", "read_error": None, "progress": None}]}
    inventory["digest"] = fixture.sha(fixture.canonical(inventory))
    accepted = {"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "create", "status": "applied", "batch_kind": "content", "rules_digest": p.rules, "tool_identity": view["tool_identity"],
        "scan_ref": ".build/operations/create/inventory.json", "scan_digest": inventory["digest"], "inventory": inventory, "content_view_digest": view["digest"],
        "dispositions": [{"unit_id": "u1", "action": "create", "reason": "Exact reviewed source", "observed_fingerprint": fixture.sha(original), "adopted_fingerprint": fixture.sha(original), "progress": "completed", "card_refs": ["pending-rule"], "claim_refs": [{"card_id": "pending-rule", "claim_id": "c1"}]}],
        "progress": {"apply": {"status": "applied", "operation_id": "create", "view_digest": view["digest"]}},
        "acceptance": {"content_view_digest": view["digest"], "rules_digest": p.rules, "proof_digests": [], "cards": [{"path": path, "card_id": "pending-rule", "sha256": card_sha, "review_mode": "manual_document", "claim_ids": ["c1"], "review_result": "supported"}]}}
    accepted["digest"] = fixture.sha(fixture.canonical(accepted))
    accepted_ref = p.write("logs/ingest/accepted.yaml", fixture.canonical(accepted))
    p.catalog["publication_trust"] = {"fixture": {"synthetic": True, "fixture_root": str(p.root), "public_key_b64": base64.b64encode(publication_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}
    p.catalog_path.write_bytes(fixture.canonical(p.catalog))
    def publish(label):
        payload = {"knowledge_commit": git("rev-parse", "HEAD"), "rules_digest": p.rules, "card_digests": {path: card_sha}, "acceptance_records": {accepted_ref: fixture.sha((p.root / accepted_ref).read_bytes())}}
        receipt_ref = p.write("logs/publication/" + label + ".json", fixture.canonical({"adapter_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(publication_key.sign(fixture.canonical(payload))).decode()}))
        built = p.call("knowledge-index-build", {"operation_id": "build-" + label, "channel": "shared", "publication_receipt_ref": receipt_ref})["data"]
        p.call("knowledge-index-build", {"operation_id": "activate-" + label, "generation_ref": built["generation_ref"], "expected_active": built["expected_active"]}, "activate")
    git("add", p.root.name + "/knowledge", p.root.name + "/governance", p.root.name + "/logs/ingest")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "accepted card before pending facts")
    publish("baseline")
    baseline = p.call("knowledge-query", {"operation_id": "before-pending", "channel": "shared", "purpose": "current", "query": "capture"})["data"]
    assert [row["card_id"] for row in baseline["matches"]] == ["pending-rule"]
    scan_ref = p.call("knowledge-source", {"operation_id": "pending"}, "scan")["data"]["scan_ref"]
    scan = p.record(scan_ref)
    assert scan["units"][0]["change"] == "unchanged"
    unit = scan["units"][0]
    deferred = p.call("knowledge-source", {"operation_id": "pending", "scan_ref": scan_ref,
        "dispositions": [{"unit_id": unit["unit_id"], "action": "defer", "reason": "Independent review found a missing assumption; investigation pending", "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None, "progress": "blocked", "card_refs": ["pending-rule"] if include_raw_refs else [], "claim_refs": [{"card_id": "pending-rule", "claim_id": "c1"}] if include_raw_refs else []}],
        "pending": [{"card_id": "pending-rule", "claim_id": "c1", "outcome": "defer", "reason": "Missing assumption remains unresolved"}]}, "record")["data"]["ingest_record_ref"]
    applied = p.call("knowledge-apply", {"operation_id": "pending", "ingest_record_ref": deferred})
    assert applied["phase"] == "committed"
    pending_ref = "logs/ingest/pending.yaml"
    pending = yaml.safe_load((p.root / pending_ref).read_bytes())
    assert pending["batch_kind"] == "record_only" and pending["pending"][0]["claim_id"] == "c1"
    git("add", p.root.name + "/knowledge", p.root.name + "/governance", p.root.name + "/logs/ingest")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "accepted card and unresolved shared fact")
    for ref in (".build", "logs/operations", "logs/events", "logs/evidence"):
        target = (p.root / ref).resolve()
        assert target.is_relative_to(p.root.resolve())
        if target.exists():
            native = str(target)
            if os.name == "nt" and not native.startswith("\\\\?\\"):
                native = "\\\\?\\" + native
            shutil.rmtree(native)
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == original
    publish("pending")
    result = p.call("knowledge-query", {"operation_id": "new-machine-query", "channel": "shared", "purpose": "current", "query": "capture"})["data"]
    assert [row["card_id"] for row in result["matches"]] == ["pending-rule"], "Query checks actual source bytes rather than workflow progress"
