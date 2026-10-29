"""Real public CLIs + copied 2.0 domain and independent synthetic review.

Set HIMATE_TEST_GOVERNANCE when running outside the monorepo. No private
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
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "hs-knowledge-apply/scripts"))
from support import canonical, digest, package_digest, seal  # noqa: E402 - isolated package test seam
_p7_spec = importlib.util.spec_from_file_location("public_governance_p7_helpers", pathlib.Path(__file__).with_name("p7_test_helpers.py"))
_p7_helpers = importlib.util.module_from_spec(_p7_spec)
_p7_spec.loader.exec_module(_p7_helpers)
map_call = _p7_helpers.map_call


class PublicGovernanceTests(unittest.TestCase):
    def record_only_request(self, operation):
        common = {"schema_version": "2.0", "operation_id": operation, "rules_digest": self.rules_digest,
                  "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
                                    "runtime": "fixture", "requirements_digest": "0" * 64}}
        scan = seal({**common, "record_kind": "source_inventory", "scope": ["docs-raw/specs"],
                     "full_scan": True, "complete": False,
                     "units": [{"unit_id": "u1", "path": "docs-raw/specs/missing.md", "source_id": "source",
                                "observed_fingerprint": None, "previous_fingerprint": None, "change": "read_failed",
                                "read_error": "unreadable", "progress": "blocked"}]})
        record = seal({**common, "record_kind": "ingest_record", "record_id": operation,
                       "target_path": "logs/ingest/" + operation + ".yaml", "batch_kind": "record_only",
                       "scan_ref": ".build/operations/" + operation + "/scan.json", "scan_digest": scan["digest"],
                       "inventory": scan, "progress": {}, "dispositions": [{"unit_id": "u1", "action": "failed",
                       "reason": "unreadable", "observed_fingerprint": None, "adopted_fingerprint": None,
                       "progress": "blocked", "card_refs": [], "claim_refs": []}]})
        parent = self.root / ".build/operations" / operation
        parent.mkdir(parents=True)
        (parent / "record.yaml").write_bytes(canonical(record))
        return {"operation_id": operation, "v3_required": True, "ingest_record_ref": ".build/operations/" + operation + "/record.yaml"}

    def save_foreign_journal(self, **changes):
        record = seal({"schema_version": "2.0", "record_kind": "transaction_journal", "operation_id": "legacy",
                       "rules_digest": "a" * 64, "tool_identity": {"skill": "hs-knowledge-apply", "package_digest": "0" * 64,
                       "runtime": "fixture", "requirements_digest": "0" * 64}, "status": "committed", "entries": [],
                       "view_ref": ".build/operations/legacy/view.json", "view_digest": "1" * 64,
                       "proof_ref": "logs/operations/legacy/proof.json", "proof_digest": "2" * 64, **changes})
        path = self.root / "logs/operations/legacy/journal.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(record))
        return path

    def test_new_record_only_batch_skips_only_unrelated_old_terminal_liveness(self):
        for status in ("committed", "rolled_back"):
            with self.subTest(status=status):
                old = self.save_foreign_journal(status=status)
                before = old.read_bytes()
                request = self.record_only_request("facts-" + status.replace("_", "-"))
                result = self.invoke("hs-knowledge-apply", request)
                self.assertEqual(result["phase"], "committed")
                self.assertEqual(old.read_bytes(), before)
                self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_old_rules_nonterminal_journal_keeps_the_writer_barrier(self):
        for number, status in enumerate(("prepared", "installing", "recovery_required", "unknown-terminal")):
            with self.subTest(status=status):
                old = self.save_foreign_journal(status=status)
                before = old.read_bytes()
                request = self.record_only_request("pending-facts-" + str(number))
                result = self.invoke("hs-knowledge-apply", request, expected=3)
                self.assertIn("requires recovery", result["diagnostics"][0]["message"])
                self.assertFalse((self.root / "logs/ingest" / (request["operation_id"] + ".yaml")).exists())
                self.assertEqual(old.read_bytes(), before)

    def test_old_terminal_journal_requires_valid_seal_supported_schema_and_identity(self):
        variants = [("seal", {}), ("schema", {"schema_version": "3.0"}),
                    ("operation", {"operation_id": "different-directory"}),
                    ("kind", {"record_kind": "apply_result"}), ("rules", {"rules_digest": "unknown"}),
                    ("shape", {"entries": {}})]
        for name, changes in variants:
            with self.subTest(name=name):
                old = self.save_foreign_journal(**changes)
                if name == "seal":
                    value = json.loads(old.read_bytes())
                    value["digest"] = "0" * 64
                    old.write_bytes(canonical(value))
                before = old.read_bytes()
                request = self.record_only_request("bad-old-" + name)
                result = self.invoke("hs-knowledge-apply", request, expected=2)
                self.assertEqual(result["phase"], "invalid")
                self.assertFalse((self.root / "logs/ingest" / (request["operation_id"] + ".yaml")).exists())
                self.assertEqual(old.read_bytes(), before)

    def test_same_operation_old_rules_journal_cannot_be_read_or_resumed_under_new_rules(self):
        old = self.save_foreign_journal()
        before = old.read_bytes()
        request = self.record_only_request("legacy")
        for action in ("run", "inspect", "resume", "rollback"):
            with self.subTest(action=action):
                result = self.invoke("hs-knowledge-apply", request, action=action, expected=2)
                self.assertIn("record rules identity mismatch", result["diagnostics"][0]["message"])
                self.assertEqual(old.read_bytes(), before)
        self.assertFalse((self.root / "logs/ingest/legacy.yaml").exists())

    def test_apply_does_not_certify_optional_review_authorship(self):
        request = self.prepare_reviewed("new-forged-proof")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        proof_path = self.root / request["proof_ref"]
        proof = json.loads(proof_path.read_bytes())
        proof["reviewer_id"] = proof["author_id"]
        proof_path.write_bytes(canonical(seal(proof)))
        result = self.invoke("hs-knowledge-apply", request)
        applied = json.loads((self.root / result["data"]["apply_result_ref"]).read_bytes())
        self.assertEqual(applied["verification_tier"], "fixed_business_checks")
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_old_terminal_journal_does_not_accept_an_old_rules_current_proof(self):
        request = self.prepare_reviewed("new-old-proof")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        proof_path = self.root / request["proof_ref"]
        proof = json.loads(proof_path.read_bytes())
        proof["rules_digest"] = "a" * 64
        proof_path.write_bytes(canonical(seal(proof)))
        result = self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertIn("record rules identity mismatch", result["diagnostics"][0]["message"])
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_old_terminal_journal_does_not_accept_an_invalid_new_view(self):
        request = self.prepare_reviewed("new-invalid-view")
        old = self.save_foreign_journal()
        frozen = old.read_bytes()
        view_path = self.root / request["view_ref"]
        view = json.loads(view_path.read_bytes())
        view["operation_id"] = "other-view-owner"
        view_path.write_bytes(canonical(seal(view)))
        result = self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertIn("view identity", result["diagnostics"][0]["message"])
        self.assertEqual(old.read_bytes(), frozen)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")

    def test_handoff_describes_files_without_a_target_query_pass_gate(self):
        request = self.prepare_reviewed("gate")
        applied = self.invoke("hs-knowledge-apply", request)
        result = self.invoke("hs-knowledge-publish-handoff", {"operation_id": "gate", "v3_required": True,
                             "apply_result_ref": applied["data"]["apply_result_ref"]})
        self.assertEqual(result["phase"], "ready_to_submit")
        handoff = json.loads((self.root / result["data"]["publish_handoff_ref"]).read_bytes())
        self.assertEqual(handoff["commit_files"], ["knowledge/index.md"])
        self.assertNotIn("verification_tier", handoff)

    def test_record_only_batch_applies_shared_failure_fact_without_card_writes(self):
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
        configured = os.environ.get("HIMATE_TEST_GOVERNANCE")
        domain = (
            pathlib.Path(configured)
            if configured
            else pathlib.Path(__file__).resolve().parents[5]
            / "himate-knowledge-wifi-mp/governance"
        )
        if not domain.joinpath("contracts/validation.py").is_file():
            self.skipTest("2.0 domain fixture path not supplied")
        scratch = pathlib.Path(
            os.environ.get("HIMATE_TEST_TMP", tempfile.gettempdir())
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
            "HIMATE_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
        )
        self.root.joinpath("knowledge").mkdir()
        self.root.joinpath("knowledge/index.md").write_bytes(b"old navigation")
        self.counter = 0
        self.catalog = {
            "schema_version": "2.0", "skills": {}, "test_fixture_root": str(self.root.resolve()),
        }
        for name in (
            "hs-knowledge-source-prepare",
            "hs-knowledge-apply",
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
        skill, action = map_call(skill, action)
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

    def prepare_reviewed(self, op, include_card=False, workflow=None):
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
            # Construct actual legacy formal evidence explicitly; the capture
            # CLI now stages these bytes and cannot act as publication setup.
            for entry in bundle["staged_objects"]:
                raw = (self.root / entry["stage_ref"]).read_bytes()
                self.assertEqual(digest(raw), entry["sha256"])
                self.assertEqual(len(raw), entry["bytes"])
                target = self.root / entry["final_ref"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
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
        if include_card:
            navigation = b"[Synthetic flow](fixture-flow.md)\n"
            writes.append({"path": "knowledge/flows/index.md", "expected_old_digest": None,
                           "final_digest": digest(navigation), "bytes_b64": base64.b64encode(navigation).decode()})
        plan_ref = f".build/operations/{op}/synthetic-plan.json"
        plan = seal({"schema_version": "2.0", "record_kind": "change_plan", "operation_id": op,
                     "rules_digest": self.rules_digest, "tool_identity": view["tool_identity"],
                     "bundle_ref": view.get("bundle_ref", f".build/operations/{op}/synthetic-bundle.json"),
                     "bundle_digest": bundle["digest"] if include_card else "0" * 64,
                     "candidate_ids": [], "decisions": [], "author_id": "fixture-author",
                     "writes": writes, "deletes": [], "baseline": {row["path"]: row["expected_old_digest"] for row in writes},
                     "review_mode": "manual_document"})
        (self.root / plan_ref).parent.mkdir(parents=True, exist_ok=True)
        (self.root / plan_ref).write_bytes(canonical(plan))
        view = seal({**view, "writes": writes, "plan_ref": plan_ref, "plan_digest": plan["digest"],
                     "source_set_digest": digest(view["source_refs"]),
                     "baseline_digest": digest({"files": plan["baseline"]})})
        ref = f".build/operations/{op}/view.json"
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(view))
        review = seal({"schema_version": "2.0", "record_kind": "content_review", "operation_id": op,
                       "rules_digest": self.rules_digest, "tool_identity": view["tool_identity"],
                       "status": "passed", "view_digest": view["digest"],
                       "plan_ref": plan_ref, "plan_digest": plan["digest"],
                       "author_id": "fixture-author", "reviewer_id": "fixture-reviewer",
                       "independent_context": "separate-fixture-context", "findings": [],
                       "verification_tier": "declared_independent_content_review"})
        review_ref = f".build/operations/{op}/content-review.json"
        (self.root / review_ref).write_bytes(canonical(review))
        return {"operation_id": op, "view_ref": ref, "proof_ref": review_ref,
                "content_review_ref": review_ref}

    def test_optional_review_does_not_require_an_upstream_plan_chain(self):
        request = self.prepare_reviewed("missing-plan-binding")
        path = self.root / request["content_review_ref"]
        review = json.loads(path.read_bytes())
        review.pop("plan_ref")
        path.write_bytes(canonical(seal(review)))
        self.invoke("hs-knowledge-apply", request)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_non_v3_document_runs_full_checks_before_admission(self):
        request = self.prepare_reviewed("invalid-full-view")
        view_path = self.root / request["view_ref"]
        view = json.loads(view_path.read_bytes())
        raw = b"[Broken navigation](absent.md)\n"
        view["writes"][0].update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        plan_path = self.root / view["plan_ref"]
        plan = json.loads(plan_path.read_bytes())
        plan["writes"] = view["writes"]
        plan = seal(plan)
        plan_path.write_bytes(canonical(plan))
        view["plan_digest"] = plan["digest"]
        view = seal(view)
        view_path.write_bytes(canonical(view))
        review_path = self.root / request["content_review_ref"]
        review = json.loads(review_path.read_bytes())
        review.update(view_digest=view["digest"], plan_digest=plan["digest"])
        review_path.write_bytes(canonical(seal(review)))
        request.pop("proof_ref")
        request.pop("content_review_ref")
        result = self.invoke("hs-knowledge-apply", request, expected=3)
        self.assertIn("full-view checks", result["diagnostics"][0]["message"])
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / ".build/operations/invalid-full-view/transaction/journal.json").exists())

    def test_non_v3_document_requires_exact_source_recovery_before_first_write(self):
        request = self.prepare_reviewed("unrecoverable", include_card=True)
        (self.root / self.fixture_original_ref).write_bytes(b"altered original")
        self.invoke("hs-knowledge-apply", request, expected=3)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / "knowledge/flows/fixture-flow.md").exists())

    def test_workflow_metadata_does_not_create_skill_handoff_manifests(self):
        workflow = {"run_id": "fixture-run", "node_id": "apply_view", "attempt_id": "first"}
        request = self.prepare_reviewed("workflow")
        applied = self.invoke("hs-knowledge-apply", {**request, "workflow": workflow})
        manifest_path = self.root / "logs/workflows/fixture-run/nodes/apply_view/first/result.json"
        self.assertFalse(manifest_path.exists())
        self.assertNotIn("artifact_manifest_ref", applied["data"])
        result_ref = applied["data"]["apply_result_ref"]
        self.assertEqual(json.loads((self.root / result_ref).read_bytes())["status"], "committed")

    def test_public_review_apply_verify_publish(self):
        request = self.prepare_reviewed("public")
        applied = self.invoke("hs-knowledge-apply", request)
        self.assertEqual(
            self.root.joinpath("knowledge/index.md").read_bytes(), b"new navigation"
        )
        # A committed transaction remains verifiable from its own exact bytes
        # even after optional upstream review material has disappeared.
        (self.root / request["proof_ref"]).unlink()
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
        self.assertNotIn("verification_tier", record)
        self.assertEqual(record["write_manifest"], [{"path": "knowledge/index.md", "sha256": digest(b"new navigation")}])

    def test_public_recover_delegates_to_single_apply_engine(self):
        request = self.prepare_reviewed("recover")
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

    def test_workflow_metadata_is_ignored_by_apply(self):
        request = self.prepare_reviewed("workflow-metadata")
        request.pop("proof_ref")
        request.pop("content_review_ref")
        for workflow in ({"attempt_id": "partial"}, {}, None, []):
            result = self.invoke("hs-knowledge-apply", {**request, "workflow": workflow})
            self.assertEqual(result["data"]["transaction_status"], "committed")
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"new navigation")

    def test_manual_card_apply_needs_no_upstream_proofs(self):
        request = self.prepare_reviewed("manual-card", include_card=True)
        request.pop("proof_ref")
        request.pop("content_review_ref")
        result = self.invoke("hs-knowledge-apply", request)
        applied = json.loads((self.root / result["data"]["apply_result_ref"]).read_bytes())
        self.assertEqual(applied["verification_tier"], "fixed_business_checks")
        self.assertNotIn("proof_ref", applied)
        self.assertNotIn("proof_digest", applied)
        self.assertTrue((self.root / "knowledge/flows/fixture-flow.md").is_file())

    def test_manual_apply_still_rejects_malformed_card_before_writing(self):
        request = self.prepare_reviewed("manual-bad-card", include_card=True)
        request.pop("proof_ref")
        request.pop("content_review_ref")
        path = self.root / request["view_ref"]
        view = json.loads(path.read_bytes())
        for row in view["writes"]:
            if row["path"] == "knowledge/flows/fixture-flow.md":
                raw = b"# Missing required card frontmatter\n"
                row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        path.write_bytes(canonical(seal(view)))
        self.invoke("hs-knowledge-apply", request, expected=2)
        self.assertEqual((self.root / "knowledge/index.md").read_bytes(), b"old navigation")
        self.assertFalse((self.root / "knowledge/flows/fixture-flow.md").exists())
        self.assertFalse((self.root / ".build/operations/manual-bad-card/transaction/journal.json").exists())

    def test_card_eligibility_ignores_unrelated_navigation_and_source_append(self):
        request = self.prepare_reviewed("card", include_card=True)
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
        request = self.prepare_reviewed("hostile-cache")
        self.invoke("hs-knowledge-apply", request)

    def test_own_support_and_business_pyc_are_never_executed(self):
        name = "hs-knowledge-apply"
        copied = self.root / "isolated-installed" / name
        shutil.copytree(
            SKILLS / name, copied, ignore=shutil.ignore_patterns("__pycache__")
        )
        for module in ("support", "transaction"):
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
        request = self.prepare_reviewed("hostile-package-cache")
        self.invoke("hs-knowledge-apply", request)


if __name__ == "__main__":
    unittest.main()
