"""A working source-lock edit cannot replace a published card's exact original."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("lineage_fixture", Path(__file__).with_name("p7_test_helpers.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_published_reference_rejects_retargeted_local_snapshot(tmp_path):
    # This isolated test key signs publication receipts only.
    publication_key = Ed25519PrivateKey.generate()
    p = fixture.Pipeline(tmp_path)
    bundle_ref, bundle = p.capture("create", b"# Fixture\nOriginal capture statement.\n")
    view_ref = p.view("create", bundle_ref, "lineage-rule", p.card("lineage-rule", bundle))
    p.apply("create", view_ref)
    view = p.record(view_ref)
    card_path = "knowledge/rules/lineage-rule.md"
    card_sha = fixture.sha((p.root / card_path).read_bytes())
    scan_ref = p.call("knowledge-source", {"operation_id": "summary-scan"}, "scan")["data"]["scan_ref"]
    scan = p.record(scan_ref)
    unit = scan["units"][0]
    record = {"schema_version": "2.0", "record_kind": "ingest_record", "operation_id": "summary-scan", "rules_digest": p.rules, "tool_identity": view["tool_identity"],
              "scan_ref": scan_ref, "scan_digest": scan["digest"], "inventory": scan, "content_view_digest": view["digest"],
              "dispositions": [{"unit_id": unit["unit_id"], "action": "update", "reason": "exact accepted source", "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": unit["observed_fingerprint"], "progress": "completed", "card_refs": ["lineage-rule"], "claim_refs": []}],
              "progress": {"apply": {"status": "applied", "operation_id": "summary-scan", "view_digest": view["digest"]}},
              "acceptance": {"content_view_digest": view["digest"], "rules_digest": p.rules, "proof_digests": ["a" * 64], "cards": [{"path": card_path, "card_id": "lineage-rule", "sha256": card_sha, "review_mode": "manual_document", "claim_ids": ["c1"], "review_result": "supported"}]}}
    record["digest"] = fixture.sha(fixture.canonical(record))
    record_ref = p.write("logs/ingest/accepted.yaml", fixture.canonical(record))
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(p.root.parent), *args], capture_output=True, check=True).stdout.decode().strip()
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("add", "himate-knowledge-wifi-mp/knowledge", "himate-knowledge-wifi-mp/governance", "himate-knowledge-wifi-mp/logs/ingest", "himate-knowledge-wifi-mp/logs/evidence")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "accepted fixture")
    p.catalog["publication_trust"] = {"fixture": {"synthetic": True, "fixture_root": str(p.root), "public_key_b64": base64.b64encode(publication_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}
    p.catalog_path.write_bytes(fixture.canonical(p.catalog))
    payload = {"knowledge_commit": git("rev-parse", "HEAD"), "rules_digest": p.rules, "card_digests": {card_path: card_sha}, "acceptance_records": {record_ref: fixture.sha((p.root / record_ref).read_bytes())}}
    receipt_ref = p.write("logs/publication/accepted.json", fixture.canonical({"adapter_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(publication_key.sign(fixture.canonical(payload))).decode()}))
    built = p.call("knowledge-index-build", {"operation_id": "build", "channel": "shared", "publication_receipt_ref": receipt_ref})["data"]
    p.call("knowledge-index-build", {"operation_id": "activate", "generation_ref": built["generation_ref"], "expected_active": None}, "activate")
    replacement = b"# Fixture\nAn unrelated replacement statement.\n"
    p.write("docs-raw/specs/raw-source.md", replacement)
    forged_ref = p.write("logs/evidence/replacement.bin", replacement)
    lock = yaml.safe_load((p.root / "governance/sources.lock.yaml").read_bytes())
    lock["snapshots"][0].update(sha256=fixture.sha(replacement), bytes=len(replacement), recovery={"path": forged_ref})
    p.write("governance/sources.lock.yaml", yaml.safe_dump(lock).encode())
    incoming, outgoing = tmp_path / "query.json", tmp_path / "answer.json"
    incoming.write_bytes(fixture.canonical({"operation_id": "retargeted-source", "channel": "shared", "purpose": "current", "query": "capture"}))
    result = subprocess.run([sys.executable, str(p.skills / "hs-knowledge-query/scripts/cli.py"), "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(p.root), "--rules-digest", p.rules, "--catalog", str(p.catalog_path)], capture_output=True, text=True)
    report = json.loads(outgoing.read_bytes())
    assert result.returncode in {0, 2, 3}, result.stderr
    assert result.returncode != 0 or not report["data"]["matches"], "A published card must not use a retargeted local snapshot as its original"
