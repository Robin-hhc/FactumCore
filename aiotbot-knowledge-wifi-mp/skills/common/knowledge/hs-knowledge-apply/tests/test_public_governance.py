"""Real public CLIs + copied 2.0 domain, synthetic host and navigation only.

Set AIOTBOT_TEST_GOVERNANCE when running outside the monorepo. No private
cross-Skill imports, real source documents, gold or installed host are used.
"""

import base64
import json
import importlib.util
import marshal
import os
import pathlib
import shutil
import subprocess
import struct
import sys
import tempfile
import time
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "hs-knowledge-apply/scripts"))
from support import canonical, digest, package_digest, seal  # noqa: E402 - isolated package test seam


class PublicGovernanceTests(unittest.TestCase):
    def test_v3_handoff_requires_batch_target_query_evidence(self):
        import yaml

        path = self.root / "governance/framework.lock.yaml"
        lock = yaml.safe_load(path.read_text(encoding="utf-8"))
        for item in lock["files"].values():
            item["sha256"] = digest((self.root / item["path"]).read_bytes())
        path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
        self.rules_digest = digest(path.read_bytes())
        request = self.prepare_and_approve("gate")
        applied = self.invoke("hs-knowledge-apply", request)
        result = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "gate", "v3_required": True,
                             "apply_result_ref": applied["data"]["apply_result_ref"]}, expected=3)
        self.assertIn("query", result["diagnostics"][0]["message"])

    def test_record_only_batch_applies_shared_failure_fact_without_card_writes(self):
        import yaml

        # Freeze only the isolated fixture during concurrent rule development.
        lock_path = self.root / "governance/framework.lock.yaml"
        lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        for item in lock["files"].values():
            item["sha256"] = digest((self.root / item["path"]).read_bytes())
        lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
        self.rules_digest = digest(lock_path.read_bytes())
        common = {"schema_version": "2.0", "operation_id": "facts", "rules_digest": self.rules_digest,
                  "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
                                    "runtime": "fixture", "requirements_digest": "0" * 64}}
        scan = seal({**common, "record_kind": "source_inventory", "scope": ["docs-raw/specs"],
                     "full_scan": True, "complete": False,
                     "units": [{"unit_id": "u1", "path": "docs-raw/specs/missing.md", "source_id": "source",
                                "observed_fingerprint": None, "previous_fingerprint": None, "change": "added",
                                "read_error": "unreadable", "progress": "blocked"}]})
        record = seal({**common, "record_kind": "ingest_record", "record_id": "facts",
                       "target_path": "logs/ingest/facts.yaml", "batch_kind": "record_only",
                       "scan_ref": ".build/operations/facts/scan.json", "scan_digest": scan["digest"],
                       "inventory": scan, "progress": {}, "dispositions": [{"unit_id": "u1", "action": "failed",
                       "reason": "unreadable", "observed_fingerprint": None, "adopted_fingerprint": None,
                       "progress": "blocked", "card_refs": [], "claim_refs": []}]})
        parent = self.root / ".build/operations/facts"
        parent.mkdir(parents=True)
        (parent / "record.yaml").write_bytes(canonical(record))
        before = (self.root / "knowledge/index.md").read_bytes()
        result = self.invoke("hs-knowledge-apply", {"operation_id": "facts", "v3_required": True,
                             "ingest_record_ref": ".build/operations/facts/record.yaml"})
        self.assertEqual(result["phase"], "committed")
        saved = json.loads((self.root / "logs/ingest/facts.yaml").read_bytes())
        self.assertEqual(saved["dispositions"][0]["progress"], "blocked")
        self.assertEqual(saved["progress"]["apply"]["status"], "recorded")
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), before)
        ready = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "facts", "v3_required": True,
                            "apply_result_ref": result["data"]["apply_result_ref"]})
        self.assertEqual(ready["phase"], "record_only_ready")
        self.assertEqual(ready["data"]["commit_files"], ["logs/ingest/facts.yaml"])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "add", "--", "logs/ingest/facts.yaml"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "record fact"], check=True, capture_output=True)
        commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        submitted = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "facts", "v3_required": True,
                                "apply_result_ref": result["data"]["apply_result_ref"], "commit_sha": commit}, action="verify-submission")
        self.assertEqual(submitted["phase"], "submitted")
        self.assertEqual(submitted["data"]["commit_sha"], commit)

    def setUp(self):
        configured = os.environ.get("AIOTBOT_TEST_GOVERNANCE")
        domain = (
            pathlib.Path(configured)
            if configured
            else pathlib.Path(__file__).resolve().parents[6]
            / "aiotbot-knowledge-wifi-mp/governance"
        )
        if not domain.joinpath("contracts/validation.py").is_file():
            self.skipTest("2.0 domain fixture path not supplied")
        scratch = pathlib.Path(
            os.environ.get("AIOTBOT_TEST_TMP", tempfile.gettempdir())
        )
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(
            prefix="governance-cli-", dir=str(scratch)
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        shutil.copytree(
            domain,
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.rules_digest = digest(
            (self.root / "governance/framework.lock.yaml").read_bytes()
        )
        self.root.joinpath(".isolated-knowledge-fixture").write_text(
            "AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
        )
        self.root.joinpath("knowledge").mkdir()
        self.root.joinpath("knowledge/index.md").write_bytes(b"old navigation")
        self.counter = 0
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        self.key = Ed25519PrivateKey.generate()
        self.catalog = {
            "schema_version": "2.0",
            "skills": {},
            "review_trust": {
                "adapters": {
                    "fixture": {
                        "synthetic": True,
                        "fixture_root": str(self.root),
                        "public_key_b64": base64.b64encode(
                            self.key.public_key().public_bytes(
                                Encoding.Raw, PublicFormat.Raw
                            )
                        ).decode(),
                    }
                }
            },
        }
        for name in (
            "hs-knowledge-source-capture",
            "hs-knowledge-confirmation-prepare",
            "hs-knowledge-confirmation-record",
            "hs-knowledge-apply",
            "hs-knowledge-recover",
            "hs-knowledge-publish-handoff",
        ):
            package = SKILLS / name
            self.catalog["skills"][name] = {
                "root": str(package),
                "entry": "scripts/cli.py",
                "python": sys.executable,
                "package_digest": package_digest(package),
            }
        self.catalog_path = self.root / "installed-catalog.json"
        self.catalog_path.write_bytes(canonical(self.catalog))

    def invoke(self, skill, request, action="run", expected=0):
        self.counter += 1
        parent = self.root / (".build/operations/" + request["operation_id"])
        parent.mkdir(parents=True, exist_ok=True)
        inp = parent / ("request-" + str(self.counter) + ".json")
        out = parent / ("response-" + str(self.counter) + ".json")
        inp.write_bytes(canonical(request))
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    pathlib.Path(self.catalog["skills"][skill]["root"])
                    / "scripts/cli.py"
                ),
                "--input",
                str(inp),
                "--output",
                str(out),
                "--knowledge-root",
                str(self.root),
                "--rules-digest",
                self.rules_digest,
                "--catalog",
                str(self.catalog_path),
                "--action",
                action,
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )
        result = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        self.assertEqual(
            completed.returncode,
            expected,
            (completed.stderr.decode(errors="replace"), result),
        )
        return result

    def prepare_and_approve(self, op, include_card=False, workflow=None):
        old = self.root.joinpath("knowledge/index.md").read_bytes()
        row = {
            "path": "knowledge/index.md",
            "expected_old_digest": digest(old),
            "final_digest": digest(b"new navigation"),
            "bytes_b64": base64.b64encode(b"new navigation").decode(),
        }
        writes = [row]
        if include_card:
            original = b"isolated synthetic design\n"
            raw_path = self.root / "docs-raw/specs/fixture-original.md"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(original)
            captured = self.invoke(
                "hs-knowledge-source-capture",
                {
                    "operation_id": op,
                    "source_path": "docs-raw/specs/fixture-original.md",
                    "source_id": "fixture-source",
                },
            )
            bundle_ref = captured["data"]["bundle_ref"]
            bundle = json.loads((self.root / bundle_ref).read_bytes())
            snapshot = bundle["snapshots"][0]
            self.fixture_original_ref = snapshot["recovery"]["path"]
            source_lock = {
                "schema_version": "2.0",
                "resources": bundle["resources"],
                "snapshots": bundle["snapshots"],
            }
            source_raw = canonical(source_lock)
            writes.append(
                {
                    "path": "governance/sources.lock.yaml",
                    "expected_old_digest": digest(
                        (self.root / "governance/sources.lock.yaml").read_bytes()
                    ),
                    "final_digest": digest(source_raw),
                    "bytes_b64": base64.b64encode(source_raw).decode(),
                }
            )
            card = (self.root / "governance/templates/flow.md").read_text(
                encoding="utf-8"
            )
            for key, value in {
                "card_id": "fixture-flow",
                "title": "Synthetic flow",
                "summary": "Synthetic design guidance",
                "owner": "fixture-owner",
                "evidence_ref": "e1",
                "source_id": "fixture-source",
                "snapshot_id": snapshot["snapshot_id"],
                "claim_id": "c1",
                "claim_text": "Fixture-only design statement.",
            }.items():
                card = card.replace("{{" + key + "}}", value)
            card = card.replace("lifecycle: draft", "lifecycle: stable").encode("utf-8")
            writes.append(
                {
                    "path": "knowledge/flows/fixture-flow.md",
                    "expected_old_digest": None,
                    "final_digest": digest(card),
                    "bytes_b64": base64.b64encode(card).decode(),
                }
            )
        view = seal(
            {
                "schema_version": "2.0",
                "record_kind": "final_view",
                "operation_id": op,
                "rules_digest": self.rules_digest,
                "tool_identity": {
                    "skill": "hs-fixture-materializer",
                    "package_digest": "0" * 64,
                    "runtime": "fixture",
                    "requirements_digest": "0" * 64,
                },
                "review_mode": "manual_document",
                "writes": writes,
                "deletes": [],
                "source_refs": bundle["snapshots"] if include_card else [],
                **({"bundle_ref": bundle_ref} if include_card else {}),
                "plan_ref": f".build/operations/{op}/synthetic-plan.json",
                "plan_digest": "0" * 64,
                "baseline_digest": digest(
                    {
                        "files": {
                            item["path"]: item["expected_old_digest"] for item in writes
                        }
                    }
                ),
            }
        )
        ref = f".build/operations/{op}/view.json"
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(view))
        prepared = self.invoke(
            "hs-knowledge-confirmation-prepare",
            {
                "operation_id": op,
                "view_ref": ref,
                **({"workflow": workflow} if workflow else {}),
            },
        )
        self.assertEqual(prepared["phase"], "awaiting_human")
        display_ref = prepared["data"]["display_ref"]
        self.invoke(
            "hs-knowledge-confirmation-record",
            {"operation_id": op, "display_ref": display_ref},
            expected=3,
        )
        display = json.loads((self.root / display_ref).read_text(encoding="utf-8"))
        payload = {
            "actor_type": "human",
            "actor_id": "synthetic-human",
            "decision": "approve",
            "display_digest": display["digest"],
            "view_digest": display["view_digest"],
            "challenge": display["challenge"],
            "issued_at": time.time(),
        }
        event = {
            "schema_version": "2.0",
            "record_kind": "host_event",
            "adapter_id": "fixture",
            "payload": payload,
            "signature_b64": base64.b64encode(
                self.key.sign(canonical(payload))
            ).decode(),
        }
        event_ref = f".build/operations/{op}/host-event.json"
        (self.root / event_ref).write_bytes(canonical(event))
        reviewed = self.invoke(
            "hs-knowledge-confirmation-record",
            {
                "operation_id": op,
                "display_ref": display_ref,
                "host_event_ref": event_ref,
            },
        )
        return {
            "operation_id": op,
            "view_ref": ref,
            "proof_ref": reviewed["data"]["manual_review_ref"],
        }

    def test_workflow_artifact_binds_actual_display_json_without_approving_it(self):
        workflow = {
            "run_id": "fixture-run",
            "node_id": "prepare_confirmation",
            "attempt_id": "first",
        }
        self.prepare_and_approve("workflow", workflow=workflow)
        manifest_path = (
            self.root
            / "logs/workflows/fixture-run/nodes/prepare_confirmation/first/result.json"
        )
        self.assertTrue(manifest_path.is_file())
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(record["phase"], "awaiting_human")
        display_ref = record["result"]["display_ref"]
        self.assertEqual(
            record["artifact_digests"][display_ref],
            digest((self.root / display_ref).read_bytes()),
        )
        self.assertTrue(manifest_path.with_suffix(".md").is_file())

    def test_public_prepare_record_apply_verify_publish(self):
        request = self.prepare_and_approve("public")
        applied = self.invoke("hs-knowledge-apply", request)
        self.assertEqual(
            self.root.joinpath("knowledge/index.md").read_bytes(), b"new navigation"
        )
        verify_request = {
            "operation_id": "public",
            "apply_result_ref": applied["data"]["apply_result_ref"],
        }
        verified = self.invoke(
            "hs-knowledge-apply", verify_request, action="verify-result"
        )
        self.assertTrue(verified["data"]["result_verified"])
        handoff = self.invoke("hs-knowledge-publish-handoff", verify_request)
        record = json.loads(
            (self.root / handoff["data"]["publish_handoff_ref"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(record["git_merge_verified"])
        self.assertFalse(record["remote_push_verified"])
        self.assertEqual(record["verification_tier"], "synthetic_host")

    def test_public_recover_delegates_to_single_apply_engine(self):
        request = self.prepare_and_approve("recover")
        self.invoke("hs-knowledge-apply", {**request, "fault_after": 1}, expected=3)
        inspected = self.invoke(
            "hs-knowledge-recover",
            {
                "operation_id": "recover",
                "workflow": {
                    "run_id": "recover-run",
                    "node_id": "recover_transaction",
                    "attempt_id": "inspect1",
                },
            },
            action="inspect",
        )
        self.assertEqual(inspected["data"]["transaction_status"], "recovery_required")
        resumed = self.invoke(
            "hs-knowledge-recover",
            {
                "operation_id": "recover",
                "workflow": {
                    "run_id": "recover-run",
                    "node_id": "recover_transaction",
                    "attempt_id": "resume1",
                },
            },
            action="resume",
        )
        self.assertEqual(resumed["data"]["transaction_status"], "committed")

    def test_invalid_workflow_is_rejected_before_apply_mutates_files(self):
        request = self.prepare_and_approve("invalid-workflow")
        for workflow in ({"attempt_id": "partial"}, {}, None, []):
            self.invoke(
                "hs-knowledge-apply",
                {**request, "workflow": workflow},
                expected=2,
            )
        self.assertEqual(
            (self.root / "knowledge/index.md").read_bytes(), b"old navigation"
        )
        self.assertFalse(
            (self.root / "logs/operations/invalid-workflow/journal.json").exists()
        )

    def test_card_eligibility_ignores_unrelated_navigation_and_source_append(self):
        request = self.prepare_and_approve("card", include_card=True)
        applied = self.invoke("hs-knowledge-apply", request)
        path = "knowledge/flows/fixture-flow.md"
        card_digest = digest((self.root / path).read_bytes())
        verify = {
            "operation_id": "card",
            "apply_result_ref": applied["data"]["apply_result_ref"],
            "card_path": path,
            "card_digest": card_digest,
        }
        self.root.joinpath("knowledge/index.md").write_bytes(
            b"later unrelated navigation"
        )
        source_lock_path = self.root / "governance/sources.lock.yaml"
        current = json.loads(source_lock_path.read_text(encoding="utf-8"))
        current["resources"].append({"source_id": "unrelated-source", "kind": "raw"})
        source_lock_path.write_bytes(canonical(current))
        verified = self.invoke("hs-knowledge-apply", verify, action="verify-result")
        self.assertEqual(
            verified["data"]["eligible_files"], [{"path": path, "sha256": card_digest}]
        )
        self.root.joinpath(self.fixture_original_ref).write_bytes(b"tampered")
        self.invoke("hs-knowledge-apply", verify, action="verify-result", expected=2)

    def test_timestamp_valid_unpinned_pyc_is_never_executed(self):
        source = self.root / "governance/contracts/validation.py"
        cached = pathlib.Path(importlib.util.cache_from_source(str(source)))
        cached.parent.mkdir(parents=True, exist_ok=True)
        code = compile(
            "raise RuntimeError('UNPINNED CACHE EXECUTED')", str(source), "exec"
        )
        metadata = source.stat()
        cached.write_bytes(
            importlib.util.MAGIC_NUMBER
            + struct.pack("<III", 0, int(metadata.st_mtime), metadata.st_size)
            + marshal.dumps(code)
        )
        self.prepare_and_approve("hostile-cache")

    def test_own_support_and_business_pyc_are_never_executed(self):
        name = "hs-knowledge-confirmation-prepare"
        copied = self.root / "isolated-installed" / name
        shutil.copytree(
            SKILLS / name, copied, ignore=shutil.ignore_patterns("__pycache__")
        )
        for module in ("support", "prepare"):
            source = copied / "scripts" / (module + ".py")
            cached = pathlib.Path(importlib.util.cache_from_source(str(source)))
            cached.parent.mkdir(parents=True, exist_ok=True)
            code = compile(
                "raise RuntimeError('UNPINNED PACKAGE CACHE EXECUTED')",
                str(source),
                "exec",
            )
            metadata = source.stat()
            cached.write_bytes(
                importlib.util.MAGIC_NUMBER
                + struct.pack("<III", 0, int(metadata.st_mtime), metadata.st_size)
                + marshal.dumps(code)
            )
        self.catalog["skills"][name]["root"] = str(copied)
        self.catalog["skills"][name]["package_digest"] = package_digest(copied)
        self.catalog_path.write_bytes(canonical(self.catalog))
        self.prepare_and_approve("hostile-package-cache")


if __name__ == "__main__":
    unittest.main()
