"""Real public CLIs + copied 2.0 domain and independent synthetic review.

Set HIMATE_TEST_GOVERNANCE when running outside the monorepo. No private
cross-Skill imports, real source documents, gold or installed host are used.
"""

import base64
import json
import importlib.util
import marshal as marshal
import os
import pathlib
import shutil
import subprocess
import struct as struct
import sys
import tempfile
import unittest

_repository_spec = importlib.util.spec_from_file_location(
    "test_public_governance_repository_runtime_fixture",
    pathlib.Path(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py",
)
_repository_fixture = importlib.util.module_from_spec(_repository_spec)
_repository_spec.loader.exec_module(_repository_fixture)
_apply_support = _repository_fixture.runtime_module("stages.apply.support")
canonical, digest, seal = _apply_support.canonical, _apply_support.digest, _apply_support.seal
_p7_spec = importlib.util.spec_from_file_location("public_governance_p7_helpers", pathlib.Path(__file__).with_name("apply_helpers.py"))
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


    def setUp(self):
        configured = os.environ.get("HIMATE_TEST_GOVERNANCE")
        domain = (
            pathlib.Path(configured)
            if configured
            else pathlib.Path(__file__).resolve().parents[5]
            / "himate/himate-knowledge-wifi-mp/governance"
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
        _repository_fixture.copy_runtime(self.root)
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
                str(self.root / "knowledge.py"),
                skill.removeprefix("hs-knowledge-"),
                "--json",
                "--input",
                str(inp),
                "--output",
                str(out),
                "--knowledge-root",
                str(self.root),
                "--rules-digest",
                self.rules_digest,
                *(["--catalog", str(self.catalog_path)] if "fault_after" in request else []),
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


if __name__ == "__main__":
    unittest.main()
