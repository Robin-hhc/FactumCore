"""Agent review records over isolated Git fixtures; no real Target QA."""

import base64
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import yaml

SKILLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "hs-knowledge-local-check/scripts"))
from support import canonical, digest, package_digest, seal  # noqa: E402 - isolated package test seam


class PublicCodeGateTests(unittest.TestCase):
    def cleanup_fixture(self):
        target = self.workspace.resolve(strict=True)
        if (target != self._fixture_target or target.parent != self._fixture_scratch
                or not target.name.startswith("code-gate-")):
            raise RuntimeError("Fixture cleanup target escaped its explicit scratch root")
        native = str(target)
        if os.name == "nt" and not native.startswith("\\\\?\\"):
            native = "\\\\?\\UNC\\" + native[2:] if native.startswith("\\\\") else "\\\\?\\" + native
        native_target = pathlib.Path(native).resolve(strict=True)

        def remove_readonly(function, filename, exc_info):
            error = exc_info[1]
            candidate = pathlib.Path(filename).resolve(strict=True)
            if (not isinstance(error, PermissionError) or function not in {os.unlink, os.rmdir}
                    or not candidate.is_relative_to(native_target)):
                raise error
            # Git's own fixture objects can have the Windows read-only flag.
            # Clear it only inside the verified fixture and retry; errors remain
            # failures rather than being discarded by ignore_errors.
            os.chmod(filename, stat.S_IREAD | stat.S_IWRITE)
            function(filename)

        shutil.rmtree(native, onerror=remove_readonly)
        if os.path.exists(native):
            raise RuntimeError("Fixture cleanup left files in the verified target")

    def test_cleanup_rejects_changed_target_outside_its_scratch_root(self):
        owned = self.workspace
        with tempfile.TemporaryDirectory(prefix="cleanup-control-", dir=str(self._fixture_scratch.parent)) as control:
            try:
                # Even a future guard regression can touch only this empty,
                # separately owned control directory, never the scratch root.
                self.workspace = pathlib.Path(control)
                with self.assertRaisesRegex(RuntimeError, "escaped"):
                    self.cleanup_fixture()
            finally:
                self.workspace = owned

    def test_committed_code_capture_reaches_v3_apply_index_and_target_queries(self):
        """Actual capture-code through same-generation query, with fixture trust."""
        framework_path = self.root / "governance/framework.lock.yaml"
        framework = yaml.safe_load(framework_path.read_bytes())
        for entry in framework["files"].values():
            entry["sha256"] = digest((self.root / entry["path"]).read_bytes())
        framework_path.write_text(yaml.safe_dump(framework, sort_keys=False), encoding="utf-8")
        self.rules_digest = digest(framework_path.read_bytes())
        for package in SKILLS.iterdir():
            if (package / "scripts/cli.py").is_file():
                self.catalog["skills"][package.name] = {"root": str(package), "entry": "scripts/cli.py",
                                                        "python": sys.executable, "package_digest": package_digest(package)}
        self.catalog_path.write_bytes(canonical(self.catalog))
        old_card = base64.b64decode(self.view["writes"][0]["bytes_b64"])
        card_path = self.root / "knowledge/concepts/flows/fixture-code-flow.md"
        card_path.parent.mkdir(parents=True)
        card_path.write_bytes(old_card)
        old_registry = base64.b64decode(self.view["writes"][1]["bytes_b64"])
        (self.root / "governance/sources.lock.yaml").write_bytes(old_registry)
        # The code changes in a real Git commit; only the declared Target/build
        # facts and semantic signature use the explicit synthetic fixture tier.
        self.source = b"int fixture_wifi_ready(void) { return 2; }\n"
        (self.code / "src/wifi.c").write_bytes(self.source)
        self.git("add", "--", "src/wifi.c")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "second code revision")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.update(rules_digest=self.rules_digest, state="context_loaded", workspace_root=str(self.workspace),
                       config_path=str(self.workspace / "config.yml"))
        context["repos"]["wifi-code"].update(head=self.head, files={"src/wifi.c": digest(self.source)})
        context["target"]["revision"] = self.head
        context["build_evidence"]["source_revision"] = self.head
        self.save(self.context_ref, seal(context))
        captured = self.invoke("hs-knowledge-source-capture", request={"operation_id": "code-source", "kind": "code",
            "repo_id": "wifi-code", "relative_path": "src/wifi.c", "source_id": "fixture-code", "context_ref": self.context_ref})
        code_bundle_ref = captured["data"]["bundle_ref"]
        code_bundle = json.loads((self.root / code_bundle_ref).read_bytes())
        snapshot = code_bundle["snapshots"][0]
        self.assertEqual(snapshot["recovery"], {"kind": "git", "method": "git", "repo_id": "wifi-code",
                                              "commit": self.head, "path": "src/wifi.c", "status": "available"})
        self.assertFalse(snapshot["code_identity"]["checked_file_dirty"])
        scanned = self.invoke("hs-knowledge-source-scan", "scan", {"operation_id": "op"})
        scan_ref = scanned["data"]["scan_ref"]
        scan = json.loads((self.root / scan_ref).read_bytes())
        self.assertEqual(scan["units"], [])
        affected = scan["current_context"]["affected_claims"]
        self.assertTrue(any(row["card_id"] == "fixture-code-flow" and row["claim_id"] == "c1" for row in affected))
        prepared = self.invoke("hs-knowledge-source-scan", "prepare", {"operation_id": "op", "scan_ref": scan_ref,
            "code_bundle_refs": [{"bundle_ref": code_bundle_ref, "bundle_digest": code_bundle["digest"]}]})
        material_ref = prepared["data"]["material_ref"]
        material = json.loads((self.root / material_ref).read_bytes())
        maintenance = list({(row["card_id"], row["claim_id"]): {
            "unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"], "card_id": row["card_id"],
            "claim_id": row["claim_id"], "outcome": "content", "reason": "Actual committed function result changed"} for row in affected}.values())
        maintenance_ids = [row["unit_id"] for row in maintenance]
        planned = self.invoke("hs-knowledge-change-plan", "plan", {"operation_id": "op", "scan_ref": scan_ref,
            "material_ref": material_ref, "author_id": "fixture-author", "units": [], "maintenance_units": maintenance,
            "claim_changes": [{"unit_ids": maintenance_ids, "card_id": "fixture-code-flow", "claim_id": "c1", "action": "update",
                               "before": "returns one", "after": "returns two", "conditions": "chip12-host fixture-build",
                               "evidence": [{"snapshot_id": snapshot["snapshot_id"], "locator": "src/wifi.c:L1"}],
                               "preserved": "Function and Target identity", "reason": "Read the actual changed function"}],
            "card_actions": [{"card_id": "fixture-code-flow", "decision": "update", "author_id": "fixture-author",
                              "unit_ids": maintenance_ids, "reason": "Same function and knowledge responsibility"}],
            "target_queries": [{"id": "fixture-ready", "query": "Fixture", "required": ["fixture-code-flow"],
                                "expected_claim_ids": ["fixture-code-flow#c1"], "purpose": "implementation", "context": context["target"]}]})
        semantic_ref = planned["data"]["semantic_plan_ref"]
        _, front, body = old_card.decode().split("---", 2)
        meta = yaml.safe_load(front)
        meta["scope"]["contexts"][0]["revision"] = self.head
        meta["sources"][0].update(snapshot_id=snapshot["snapshot_id"], locator={"kind": "lines", "start": 1, "end": 1,
                                                                            "repo_id": "wifi-code", "path": "src/wifi.c"})
        draft = ("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---" + body.replace("returns one", "returns two")).encode()
        draft_ref = ".build/candidates/fixture-code-flow.md"
        (self.root / draft_ref).parent.mkdir(parents=True)
        (self.root / draft_ref).write_bytes(draft)
        final_plan = self.invoke("hs-knowledge-change-plan", request={"operation_id": "op", "v3_required": True,
            "semantic_plan_ref": semantic_ref, "bundle_ref": material["bundle_ref"], "context_ref": self.context_ref,
            "decisions": [{"candidate_id": "fixture-code", "decision": "update", "reason": "Actual code result changed",
                           "card_inputs": [draft_ref]}]})["data"]["plan_ref"]
        self.view_ref = self.invoke("hs-knowledge-view-materialize", request={"operation_id": "op", "plan_ref": final_plan})["data"]["view_ref"]
        self.view = json.loads((self.root / self.view_ref).read_bytes())
        reviewed = self.invoke("hs-knowledge-change-plan", "review", {"operation_id": "op", "semantic_plan_ref": semantic_ref,
            "view_ref": self.view_ref, "reviewer_id": "fixture-independent", "independent_context": "new-fixture-review",
            "sampled_unit_ids": maintenance_ids, "unreviewed_unit_ids": [], "reason": "Committed implementation Claim needs independent review", "findings": []})
        self.evidence = [{"card_id": "fixture-code-flow", "claim_id": "c1", "status": "supported", "evidence": [
            {"source_id": "fixture-code", "snapshot_id": snapshot["snapshot_id"], "locator": meta["sources"][0]["locator"], "sha256": digest(self.source)}]}]
        self.sign_report("local")
        independent_report = json.loads((self.root / self.report_ref).read_bytes())
        author_report = json.loads(json.dumps(independent_report))
        author_report["reviewer_id"] = "fixture-author"
        self.save(self.report_ref, author_report)
        refused = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
            "semantic_report_ref": self.report_ref,
            "workflow": {"run_id": "v3-author-check", "node_id": "local_check", "attempt_id": "same-author"}})
        self.assertEqual(refused["data"]["check_status"], "incomplete")
        self.save(self.report_ref, independent_report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        inputs = {"code_checkout": {"configuration": str(self.workspace / "config.yml"), "config_digest": context["config_digest"],
                                    "repos": {"wifi-code": {"root": str(self.code), "commit": self.head}}}}
        linted = self.invoke("hs-knowledge-lint", request={"operation_id": "op", "view_ref": self.view_ref, "inputs": inputs})
        self.assertEqual(linted["status"], "passed")
        lint_ref = str(pathlib.Path(linted["data"]["report_ref"]).relative_to(self.root)).replace("\\", "/")
        recorded = self.invoke("hs-knowledge-source-scan", "record", {"operation_id": "op", "scan_ref": scan_ref,
            "semantic_plan_ref": semantic_ref, "view_ref": self.view_ref, "lint_ref": lint_ref, "dispositions": []})
        applied = self.invoke("hs-knowledge-apply", request={"operation_id": "op", "v3_required": True, "view_ref": self.view_ref,
            "proof_ref": checked["data"]["local_check_ref"], "content_review_ref": reviewed["data"]["content_review_ref"],
            "lint_report_ref": lint_ref, "check_inputs": inputs, "ingest_record_ref": recorded["data"]["ingest_record_ref"]})
        self.assertEqual(applied["phase"], "committed")
        applied_record = json.loads((self.root / "logs/ingest/op.yaml").read_bytes())
        self.assertEqual(applied_record["acceptance"]["config_digest"], context["config_digest"])
        self.assertEqual(applied_record["maintenance_dispositions"], maintenance)
        generation = self.invoke("hs-knowledge-index-build", "build", {"operation_id": "op"})["data"]["generation_ref"]
        regression = self.invoke("hs-knowledge-query-regression", request={"operation_id": "op", "v3_required": True,
            "apply_result_ref": applied["data"]["apply_result_ref"], "generation_ref": generation})
        self.assertEqual(regression["phase"], "checked")
        self.assertTrue(regression["data"]["passed"])

    def test_mixed_view_requires_authenticated_human_and_code_proofs(self):
        # Only this copied fixture is repinned during concurrent rule development.
        lock_path = self.root / "governance/framework.lock.yaml"
        framework = yaml.safe_load(lock_path.read_bytes())
        for entry in framework["files"].values():
            entry["sha256"] = digest((self.root / entry["path"]).read_bytes())
        lock_path.write_text(yaml.safe_dump(framework, sort_keys=False), encoding="utf-8")
        self.rules_digest = digest(lock_path.read_bytes())
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["rules_digest"] = self.rules_digest
        self.save(self.context_ref, seal(context))
        original = base64.b64decode(self.view["writes"][0]["bytes_b64"]).decode()
        _, front, body = original.split("---", 2)
        meta = yaml.safe_load(front)
        meta.update(id="fixture-document", title="Fixture document", review_mode="manual_document",
                    scope={"applicability": "unknown", "contexts": []})
        meta["sources"] = [{"evidence_ref": "doc", "source_id": "fixture-document", "snapshot_id": "document-v1",
                            "locator": {"kind": "lines", "start": 1, "end": 1}}]
        meta["claims"][0].update(evidence_kind="design", usage="guidance", context_ids=[], source_refs=["doc"], verification_requirements=[])
        document = ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body.replace("The fixture function returns one.", "Synthetic document requirement.")).encode()
        raw = b"Synthetic document requirement.\n"
        for ref in ("docs-raw/specs/document.md", "logs/evidence/document.bin"):
            path = self.root / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        registry = json.loads(base64.b64decode(self.view["writes"][1]["bytes_b64"]))
        registry["resources"].append({"source_id": "fixture-document", "kind": "raw", "path": "docs-raw/specs/document.md"})
        registry["snapshots"].append({"source_id": "fixture-document", "snapshot_id": "document-v1", "sha256": digest(raw),
                                     "bytes": len(raw), "recovery": {"path": "logs/evidence/document.bin"}})
        registry_bytes = canonical(registry)
        (self.root / "governance/sources.lock.yaml").write_bytes(registry_bytes)
        self.view["writes"][1].update(expected_old_digest=digest(registry_bytes), final_digest=digest(registry_bytes),
                                      bytes_b64=base64.b64encode(registry_bytes).decode())
        self.view["writes"].append({"path": "knowledge/flows/fixture-document.md", "expected_old_digest": None,
                                     "final_digest": digest(document), "bytes_b64": base64.b64encode(document).decode()})
        self.view.update(rules_digest=self.rules_digest, review_mode="mixed",
                         review_requirements={"manual_document": ["knowledge/flows/fixture-document.md"], "code_gate": ["knowledge/flows/fixture-code-flow.md"]},
                         baseline_digest=digest({"files": {r["path"]: r["expected_old_digest"] for r in self.view["writes"]}}))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        for name in ("hs-knowledge-source-capture", "hs-knowledge-confirmation-prepare", "hs-knowledge-confirmation-record"):
            package = SKILLS / name
            self.catalog["skills"][name] = {"root": str(package), "entry": "scripts/cli.py", "python": sys.executable,
                                               "package_digest": package_digest(package)}
        self.catalog["review_trust"] = {"adapters": {"fixture": self.catalog["semantic_reviewers"]["fixture"]}}
        self.catalog_path.write_bytes(canonical(self.catalog))
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        code_proof = checked["data"]["local_check_ref"]
        self.invoke("hs-knowledge-apply", request={"operation_id": "op", "view_ref": self.view_ref,
                    "proof_set": {"code_gate": code_proof}}, expected=2)
        prepared = self.invoke("hs-knowledge-confirmation-prepare", request={"operation_id": "op", "view_ref": self.view_ref})
        display_ref = prepared["data"]["display_ref"]
        display = json.loads((self.root / display_ref).read_bytes())
        payload = {"actor_type": "human", "actor_id": "fixture-human", "decision": "approve", "issued_at": time.time(),
                   "view_digest": self.view["digest"], "display_digest": display["digest"], "challenge": display["challenge"]}
        self.save(".build/operations/op/human-event.json", {"schema_version": "2.0", "record_kind": "host_event",
                    "adapter_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(self.key.sign(canonical(payload))).decode()})
        approved = self.invoke("hs-knowledge-confirmation-record", request={"operation_id": "op", "display_ref": display_ref,
                                "host_event_ref": ".build/operations/op/human-event.json"})
        applied = self.invoke("hs-knowledge-apply", request={"operation_id": "op", "view_ref": self.view_ref,
                              "proof_set": {"manual_document": approved["data"]["manual_review_ref"], "code_gate": code_proof}})
        self.assertEqual(applied["phase"], "committed")

    def setUp(self):
        configured = os.environ.get("AIOTBOT_TEST_GOVERNANCE")
        domain = (
            pathlib.Path(configured)
            if configured
            else pathlib.Path(__file__).resolve().parents[5]
            / "aiotbot-knowledge-wifi-mp/governance"
        )
        if not domain.joinpath("contracts/validation.py").is_file():
            self.skipTest("2.0 domain fixture path not supplied")
        scratch = pathlib.Path(
            os.environ.get("AIOTBOT_TEST_TMP", tempfile.gettempdir())
        )
        scratch.mkdir(parents=True, exist_ok=True)
        self._fixture_scratch = scratch.resolve(strict=True)
        self.workspace = pathlib.Path(tempfile.mkdtemp(prefix="code-gate-", dir=str(self._fixture_scratch))).resolve(strict=True)
        self._fixture_target = self.workspace
        self.addCleanup(self.cleanup_fixture)
        self.root = self.workspace / "aiotbot-knowledge-wifi-mp"
        shutil.copytree(
            domain,
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.root.joinpath(".isolated-knowledge-fixture").write_text(
            "AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
        )
        self.rules_digest = digest(
            (self.root / "governance/framework.lock.yaml").read_bytes()
        )
        self.code = self.workspace / "code"
        self.code.mkdir()
        self.git("init", "--initial-branch=main", "-q")
        self.git("remote", "add", "origin", "synthetic-wifi-code")
        self.code.joinpath("src").mkdir()
        self.source = b"int fixture_wifi_ready(void) { return 1; }\n"
        self.code.joinpath("src/wifi.c").write_bytes(self.source)
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture",
        )
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        config = yaml.safe_load(domain.parents[1].joinpath("config.yml").read_bytes())
        config["repos"] = [
            {
                "repo_id": "wifi-code",
                "kind": "git",
                "root": str(self.code),
                "expected_identity": "synthetic-wifi-code",
            }
        ]
        for target in config["targets"]:
            target.update(
                source_bindings=["fixture-code"],
                module_roots=["src"],
                build_profile="fixture-build",
                required_features=["WIFI_ON"],
                protocol_versions=["fixture-v1"],
            )
        policy = {
            "allowed_ref": "refs/heads/main",
            "repo_roots": {"wifi-code": str(self.code)},
        }
        config["code_policy"] = policy
        config_raw = yaml.safe_dump(
            config, allow_unicode=True, sort_keys=False
        ).encode()
        self.workspace.joinpath("config.yml").write_bytes(config_raw)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        self.key = Ed25519PrivateKey.generate()
        self.catalog = {
            "schema_version": "2.0",
            "skills": {},
            "code_policy": policy,
            "semantic_reviewers": {
                "fixture": {
                    "synthetic": True,
                    "fixture_root": str(self.root),
                    "public_key_b64": base64.b64encode(
                        self.key.public_key().public_bytes(
                            Encoding.Raw, PublicFormat.Raw
                        )
                    ).decode(),
                }
            },
        }
        for name in (
            "hs-knowledge-local-check",
            "hs-knowledge-apply",
            "hs-knowledge-merge-check",
        ):
            package = SKILLS / name
            self.catalog["skills"][name] = {
                "root": str(package),
                "entry": "scripts/cli.py",
                "python": sys.executable,
                "package_digest": package_digest(package),
            }
        self.catalog_path = self.workspace / "trusted-catalog.json"
        self.catalog_path.write_bytes(canonical(self.catalog))
        self.counter = 0
        self.tool = {
            "skill": "hs-fixture-producer",
            "package_digest": "0" * 64,
            "runtime": "fixture",
            "requirements_digest": "0" * 64,
        }
        for rel, data in (
            ("logs/evidence/code.bin", self.source),
            ("logs/evidence/build.bin", b"synthetic fixture build only\n"),
        ):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        locator = {
            "kind": "lines",
            "start": 1,
            "end": 1,
            "repo_id": "wifi-code",
            "path": "src/wifi.c",
        }
        source_lock = {
            "schema_version": "2.0",
            "resources": [
                {
                    "source_id": "fixture-code",
                    "kind": "code",
                    "repo_id": "wifi-code",
                    "path": "src/wifi.c",
                }
            ],
            "snapshots": [
                {
                    "source_id": "fixture-code",
                    "snapshot_id": "fixture-code-snapshot",
                    "sha256": digest(self.source),
                    "bytes": len(self.source),
                    "recovery": {"path": "logs/evidence/code.bin"},
                }
            ],
        }
        scope = {
            "context_id": "chip12-host-build",
            "target_id": "chip12-host",
            "chip": "chip12",
            "side": "host",
            "build_profile": "fixture-build",
            "features_all": ["WIFI_ON"],
            "features_none": [],
            "protocol_versions": ["fixture-v1"],
            "revision_policy": "revalidate",
            "revision": self.head,
        }
        card_text = (self.root / "governance/templates/flow.md").read_text(
            encoding="utf-8"
        )
        for key, value in {
            "card_id": "fixture-code-flow",
            "title": "Fixture code",
            "summary": "Synthetic code check",
            "owner": "fixture",
            "evidence_ref": "e1",
            "source_id": "fixture-code",
            "snapshot_id": "fixture-code-snapshot",
            "claim_id": "c1",
            "claim_text": "The fixture function returns one.",
        }.items():
            card_text = card_text.replace("{{" + key + "}}", value)
        _, front, body = card_text.split("---", 2)
        meta = yaml.safe_load(front)
        meta.update(
            lifecycle="stable",
            review_mode="code_gate",
            scope={"applicability": "constrained", "contexts": [scope]},
        )
        meta["sources"][0]["locator"] = locator
        meta["claims"][0].update(
            evidence_kind="implementation",
            usage="current",
            context_ids=[scope["context_id"]],
            verification_requirements=["semantic-support"],
        )
        card = (
            "---\n"
            + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
            + "---"
            + body
        ).encode()
        context = self.record(
            "project_context",
            state="loaded",
            workspace_id=config["workspace_id"],
            knowledge_root=str(self.root),
            entries=[],
            config_digest=digest(config_raw),
            repos={
                "wifi-code": {
                    "root": str(self.code),
                    "identity": "synthetic-wifi-code",
                    "head": self.head,
                    "dirty": False,
                    "files": {"src/wifi.c": digest(self.source)},
                }
            },
            target={
                "target_id": "chip12-host",
                "chip": "chip12",
                "side": "host",
                "build_profile": "fixture-build",
                "features": ["WIFI_ON"],
                "protocol_versions": ["fixture-v1"],
                "revision": self.head,
            },
            build_evidence={
                "profile": "fixture-build",
                "source_revision": self.head,
                "macro_digest": digest(["WIFI_ON"]),
                "artifacts": [
                    {
                        "path": "logs/evidence/build.bin",
                        "sha256": digest(b"synthetic fixture build only\n"),
                    }
                ],
            },
        )
        self.context_ref = ".build/operations/op/context.json"
        self.save(self.context_ref, context)
        source_raw = canonical(source_lock)
        writes = [
            {
                "path": "knowledge/flows/fixture-code-flow.md",
                "expected_old_digest": None,
                "final_digest": digest(card),
                "bytes_b64": base64.b64encode(card).decode(),
            },
            {
                "path": "governance/sources.lock.yaml",
                "expected_old_digest": digest(
                    (self.root / "governance/sources.lock.yaml").read_bytes()
                ),
                "final_digest": digest(source_raw),
                "bytes_b64": base64.b64encode(source_raw).decode(),
            },
        ]
        self.view = self.record(
            "final_view",
            review_mode="code_gate",
            context_ref=self.context_ref,
            writes=writes,
            deletes=[],
            source_refs=[],
            plan_ref=".build/operations/op/fixture-plan.json",
            plan_digest="0" * 64,
            baseline_digest=digest(
                {"files": {row["path"]: row["expected_old_digest"] for row in writes}}
            ),
        )
        self.view_ref = ".build/operations/op/view.json"
        self.save(self.view_ref, self.view)
        self.evidence = [
            {
                "card_id": "fixture-code-flow",
                "claim_id": "c1",
                "status": "supported",
                "evidence": [
                    {
                        "source_id": "fixture-code",
                        "snapshot_id": "fixture-code-snapshot",
                        "locator": locator,
                        "sha256": digest(self.source),
                    }
                ],
            }
        ]
        self.report_ref = ".build/operations/op/semantic-report.json"
        self.sign_report("local")

    def git(self, *arguments):
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=" + os.devnull,
                "-C",
                str(self.code),
                *arguments,
            ],
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def record(self, kind, **fields):
        return seal(
            {
                "schema_version": "2.0",
                "record_kind": kind,
                "operation_id": "op",
                "rules_digest": self.rules_digest,
                "tool_identity": self.tool,
                **fields,
            }
        )

    def save(self, ref, value):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value))

    def sign_report(self, mode):
        """Compatibility helper name; Agent review records no longer need a key."""
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        author = "fixture"
        if self.view.get("semantic_plan_ref"):
            author = json.loads((self.root / self.view["semantic_plan_ref"]).read_bytes())["author_id"]
        evidence = json.loads(json.dumps(self.evidence))
        for row in evidence:
            row.setdefault("reason", "Read the exact source and conditions supporting this Claim.")
        payload = {
            "author_id": author,
            "independent_context": "fixture-independent-code-reading-context",
            "findings": [],
            "view_digest": self.view["digest"],
            "context_digest": context["digest"],
            "mode": mode,
            "claims": evidence,
            "issued_at": time.time(),
        }
        self.save(
            self.report_ref,
            {
                "schema_version": "2.0",
                "record_kind": "semantic_review",
                "reviewer_id": "fixture-independent-reviewer",
                "payload": payload,
            },
        )

    def invoke(
        self, skill="hs-knowledge-local-check", action="run", request=None, expected=0
    ):
        self.counter += 1
        request = request or {
            "operation_id": "op",
            "view_ref": self.view_ref,
            "context_ref": self.context_ref,
            "semantic_report_ref": self.report_ref,
        }
        inp, out = (
            f".build/operations/op/request-{self.counter}.json",
            f".build/operations/op/response-{self.counter}.json",
        )
        self.save(inp, request)
        completed = subprocess.run(
            [
                sys.executable,
                str(SKILLS / skill / "scripts/cli.py"),
                "--input",
                str(self.root / inp),
                "--output",
                str(self.root / out),
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
        response = json.loads((self.root / out).read_text(encoding="utf-8"))
        self.assertEqual(completed.returncode, expected, (completed.stderr, response))
        return response

    def test_signed_positive_support_then_apply_and_verify(self):
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        request = {
            "operation_id": "op",
            "view_ref": self.view_ref,
            "proof_ref": checked["data"]["local_check_ref"],
        }
        verified = self.invoke(action="verify-proof", request=request)
        self.assertTrue(verified["data"]["proof_verified"])
        before = self.code.joinpath("src/wifi.c").read_bytes()
        applied = self.invoke(skill="hs-knowledge-apply", request=request)
        self.assertEqual(applied["data"]["transaction_status"], "committed")
        self.assertEqual(self.code.joinpath("src/wifi.c").read_bytes(), before)

    def test_independent_agent_review_needs_no_registered_key_or_signature(self):
        self.catalog.pop("semantic_reviewers", None)
        self.catalog_path.write_bytes(canonical(self.catalog))
        report = json.loads((self.root / self.report_ref).read_bytes())
        report.pop("signature_b64", None)
        report["reviewer_id"] = "fixture-independent-reviewer"
        report["payload"].update(author_id="fixture", independent_context="fresh-code-reading-context", findings=[])
        report["payload"]["claims"][0]["reason"] = "Read the exact function body and verified its return value."
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        proof = json.loads((self.root / checked["data"]["local_check_ref"]).read_bytes())
        self.assertEqual(proof["verification_tier"], "agent_content_review")

    def test_agent_review_rejects_missing_independence_and_unresolved_content(self):
        self.catalog.pop("semantic_reviewers", None)
        self.catalog_path.write_bytes(canonical(self.catalog))
        baseline = json.loads((self.root / self.report_ref).read_bytes())
        baseline.pop("signature_b64", None)
        baseline["reviewer_id"] = "fixture-independent-reviewer"
        baseline["payload"].update(author_id="fixture", independent_context="fresh-context", findings=[])
        baseline["payload"]["claims"][0]["reason"] = "Read the actual return statement."
        for defect, message in (("author", "author"), ("author_type", "author"), ("self_review", "author"),
                                ("context", "independent"), ("findings", "findings"),
                                ("reason", "reason")):
            with self.subTest(defect=defect):
                report = json.loads(json.dumps(baseline))
                if defect == "author":
                    report["payload"]["author_id"] = "unrelated-author"
                elif defect == "author_type":
                    report["payload"]["author_id"] = {"unexpected": "object"}
                elif defect == "self_review":
                    report["reviewer_id"] = "fixture"
                elif defect == "context":
                    report["payload"]["independent_context"] = ""
                elif defect == "findings":
                    report["payload"]["findings"] = [{"reason": "Unresolved source contradiction"}]
                else:
                    report["payload"]["claims"][0]["reason"] = ""
                self.save(self.report_ref, report)
                result = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
                    "semantic_report_ref": self.report_ref,
                    "workflow": {"run_id": "review-guards", "node_id": "local_check", "attempt_id": defect}})
                self.assertIn(result["data"]["check_status"], {"incomplete", "failed"})
                record = json.loads((self.root / result["data"]["local_check_ref"]).read_bytes())
                self.assertIn(message, " ".join(record["gaps"]))

    def test_owner_of_another_card_in_the_mixed_view_is_not_an_independent_reviewer(self):
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata.update(id="fixture-document", owner="document-author", review_mode="manual_document")
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        document_path = "knowledge/flows/fixture-document.md"
        self.view["writes"].append({"path": document_path, "expected_old_digest": None,
            "final_digest": digest(raw), "bytes_b64": base64.b64encode(raw).decode()})
        self.view.update(review_mode="mixed", review_requirements={
            "code_gate": [row["path"]], "manual_document": [document_path]},
            baseline_digest=digest({"files": {item["path"]: item["expected_old_digest"] for item in self.view["writes"]}}))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        report = json.loads((self.root / self.report_ref).read_bytes())
        report["reviewer_id"] = "document-author"
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_legacy_report_missing_review_metadata_requires_a_new_review(self):
        report = json.loads((self.root / self.report_ref).read_bytes())
        report["payload"].pop("author_id")
        report["signature_b64"] = "legacy-signature-is-not-an-author-declaration"
        self.save(self.report_ref, report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")
        record = json.loads((self.root / checked["data"]["local_check_ref"]).read_bytes())
        self.assertIn("author_id", " ".join(record["gaps"]))

    def source_analysis_view(self, usage="historical", with_target=False):
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["scope"] = {"applicability": "unknown", "contexts": []}
        metadata["claims"][0].update(usage=usage, context_ids=[])
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        context = json.loads((self.root / self.context_ref).read_bytes())
        if not with_target:
            context["target"] = None
        context.pop("build_evidence", None)
        self.save(self.context_ref, seal(context))
        self.sign_report("local")

    def test_source_analysis_without_target_or_build_is_admitted_and_reverified(self):
        self.source_analysis_view()
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        proof_ref = checked["data"]["local_check_ref"]
        proof = json.loads((self.root / proof_ref).read_bytes())
        self.assertEqual(proof["code_identity"]["basis"], "source")
        self.assertIsNone(proof["code_identity"]["target"])
        request = {"operation_id": "op", "view_ref": self.view_ref, "proof_ref": proof_ref}
        applied = self.invoke(skill="hs-knowledge-apply", request=request)
        self.assertEqual(applied["data"]["transaction_status"], "committed")
        verified = self.invoke(action="verify-proof", request={**request, "purpose": "historical"})
        self.assertTrue(verified["data"]["proof_verified"])
        self.code.joinpath("src/wifi.c").write_bytes(b"changed source\n")
        self.invoke(action="verify-proof", request=request, expected=3)

    def test_source_analysis_with_registered_target_does_not_require_build_artifacts(self):
        self.source_analysis_view(usage="guidance", with_target=True)
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_current_static_source_claim_does_not_require_build_artifacts(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_current_static_source_still_requires_target_conditions(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        context["target"].pop("features")
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_current_static_source_still_requires_actual_target_code_mapping(self):
        config_path = self.workspace / "config.yml"
        config = yaml.safe_load(config_path.read_bytes())
        config["targets"][0].update(module_roots=[], source_bindings=[])
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        context = json.loads((self.root / self.context_ref).read_bytes())
        context.pop("build_evidence")
        context["config_digest"] = digest(config_path.read_bytes())
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_build_requirement_needs_signed_per_claim_artifact_support(self):
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["semantic-support", "build-support"]
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_signed_build_and_runtime_artifacts_are_checked_without_running_builds(self):
        runtime_ref = "logs/evidence/runtime.log"
        runtime = b"synthetic fixture runtime observation only\n"
        (self.root / runtime_ref).write_bytes(runtime)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"]["artifacts"].append({"path": runtime_ref, "sha256": digest(runtime)})
        self.save(self.context_ref, seal(context))
        row = self.view["writes"][0]
        _, front, body = base64.b64decode(row["bytes_b64"]).decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["claims"][0]["verification_requirements"] = ["build-support", "runtime-support"]
        raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        row.update(bytes_b64=base64.b64encode(raw).decode(), final_digest=digest(raw))
        self.view = seal(self.view)
        self.save(self.view_ref, self.view)
        self.evidence[0]["verification_evidence"] = [
            {"requirement": "build-support", "path": "logs/evidence/build.bin",
             "sha256": digest(b"synthetic fixture build only\n")},
            {"requirement": "runtime-support", "path": runtime_ref, "sha256": digest(runtime)},
        ]
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")
        (self.root / "logs/evidence/build.bin").write_bytes(b"changed build evidence\n")
        checked = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref,
            "semantic_report_ref": self.report_ref,
            "workflow": {"run_id": "artifact-check", "node_id": "local_check", "attempt_id": "changed-artifact"}})
        self.assertEqual(checked["data"]["check_status"], "incomplete")

    def test_current_claim_cannot_use_source_analysis_admission(self):
        self.source_analysis_view(usage="current")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_source_analysis_does_not_ignore_supplied_broken_build_evidence(self):
        self.source_analysis_view(with_target=True)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"] = {"artifacts": []}
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_source_analysis_checks_conditions_of_a_supplied_build(self):
        original = json.loads((self.root / self.context_ref).read_bytes())
        self.source_analysis_view(with_target=True)
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["build_evidence"] = original["build_evidence"]
        context["target"]["features"] = []
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_code_gate_rechecks_authorized_git_with_a_different_owner(self):
        # Only ownership is simulated; Git objects, signatures and public calls
        # retain the existing explicitly synthetic fixture tier.
        with patch.dict(os.environ, {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}):
            checked = self.invoke()
            self.assertEqual(checked["data"]["check_status"], "passed")
            verified = self.invoke(action="verify-proof", request={"operation_id": "op", "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"]})
            self.assertTrue(verified["data"]["proof_verified"])

    def test_missing_signed_support_stays_incomplete(self):
        result = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref})
        self.assertEqual(result["data"]["check_status"], "incomplete")

    def test_official_context_receipt_state_and_location_are_supported(self):
        context = json.loads((self.root / self.context_ref).read_bytes())
        context["state"] = "context_loaded"
        self.context_ref = ".build/project-context/fixture.json"
        self.save(self.context_ref, seal(context))
        self.sign_report("local")
        self.assertEqual(self.invoke()["data"]["check_status"], "passed")

    def test_actual_git_origin_must_match_registered_identity(self):
        self.git("remote", "set-url", "origin", "different-fixture-repository")
        self.assertEqual(self.invoke()["data"]["check_status"], "incomplete")

    def test_interrupted_apply_can_roll_back_after_code_revision_changes(self):
        self.catalog["review_trust"] = {
            "adapters": {"fixture": {"synthetic": True, "fixture_root": str(self.root)}}
        }
        self.catalog_path.write_bytes(canonical(self.catalog))
        checked = self.invoke()
        before_lock = (self.root / "governance/sources.lock.yaml").read_bytes()
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
                "fault_after": 1,
            },
            expected=3,
        )
        self.assertTrue((self.root / "knowledge/flows/fixture-code-flow.md").is_file())
        self.code.joinpath("src/wifi.c").write_bytes(b"changed latest fixture code\n")
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "changed during recovery",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            action="resume",
            request={"operation_id": "op"},
            expected=3,
        )
        recovered = self.invoke(
            skill="hs-knowledge-apply",
            action="rollback",
            request={"operation_id": "op"},
        )
        self.assertEqual(recovered["data"]["transaction_status"], "rolled_back")
        self.assertFalse((self.root / "knowledge/flows/fixture-code-flow.md").exists())
        self.assertEqual(
            (self.root / "governance/sources.lock.yaml").read_bytes(), before_lock
        )

    def test_tampered_signed_support_fails(self):
        report = json.loads((self.root / self.report_ref).read_text(encoding="utf-8"))
        report["payload"]["claims"][0]["status"] = "unsupported"
        self.save(self.report_ref, report)
        self.assertEqual(self.invoke()["data"]["check_status"], "failed")

    def test_latest_merge_ref_invalidates_stale_context_without_repairs(self):
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "new latest",
        )
        view_before = (self.root / self.view_ref).read_bytes()
        lock_before = (self.root / "governance/sources.lock.yaml").read_bytes()
        self.assertEqual(
            self.invoke(action="merge")["data"]["check_status"], "incomplete"
        )
        self.assertEqual((self.root / self.view_ref).read_bytes(), view_before)
        self.assertEqual(
            (self.root / "governance/sources.lock.yaml").read_bytes(), lock_before
        )

    def test_changed_latest_code_can_pass_with_independent_signed_check_snapshot(self):
        checked = self.invoke()
        applied = self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
            },
        )
        card_path = "knowledge/flows/fixture-code-flow.md"
        card_digest = digest((self.root / card_path).read_bytes())
        newer = b"/* a harmless fixture comment */\n" + self.source
        self.code.joinpath("src/wifi.c").write_bytes(newer)
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "latest fixture comment",
        )
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["repos"]["wifi-code"].update(
            head=latest, files={"src/wifi.c": digest(newer)}
        )
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.context_ref = ".build/operations/op/latest-context.json"
        self.save(self.context_ref, seal(context))
        self.evidence[0]["evidence"][0]["checked_snapshot"] = {
            "repo_id": "wifi-code",
            "path": "src/wifi.c",
            "sha256": digest(newer),
            "snapshot_id": "latest-check-snapshot",
            "locator": {"kind": "lines", "start": 2, "end": 2},
            "commit": latest,
            "bytes": len(newer),
        }
        self.report_ref = ".build/operations/op/latest-report.json"
        self.sign_report("merge")
        frozen = {
            ref: (self.root / ref).read_bytes()
            for ref in (
                self.view_ref,
                "governance/sources.lock.yaml",
                "logs/evidence/code.bin",
            )
        }
        result = self.invoke(skill="hs-knowledge-merge-check")
        self.assertEqual(result["data"]["check_status"], "passed")
        for ref, raw in frozen.items():
            self.assertEqual((self.root / ref).read_bytes(), raw)
        self.assertEqual(
            (
                self.root / ("logs/evidence/checked-code/" + digest(newer) + ".bin")
            ).read_bytes(),
            newer,
        )
        qualification = {
            "operation_id": "op",
            "apply_result_ref": applied["data"]["apply_result_ref"],
            "current_code_proof_ref": result["data"]["merge_check_ref"],
            "card_path": card_path,
            "card_digest": card_digest,
        }
        current = self.invoke(
            skill="hs-knowledge-apply", action="verify-result", request=qualification
        )
        self.assertEqual(
            current["data"]["eligible_files"],
            [{"path": card_path, "sha256": card_digest}],
        )
        self.code.joinpath("src/wifi.c").write_bytes(b"/* another change */\n" + newer)
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "a later unchecked commit",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request=qualification,
            expected=3,
        )
        (self.root / card_path).write_bytes(b"a later working-tree replacement")
        history = self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request={**qualification, "purpose": "historical"},
        )
        self.assertEqual(history["data"]["eligible_files"], [])
        self.assertEqual(
            history["data"]["historical_files"],
            [{"path": card_path, "sha256": card_digest}],
        )

    def test_historical_purpose_cannot_bypass_current_apply_gate(self):
        checked = self.invoke()
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "changed before apply",
        )
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
                "purpose": "historical",
            },
            expected=3,
        )
        self.assertFalse((self.root / "knowledge/flows/fixture-code-flow.md").exists())

    def test_signed_retirement_applies_without_claiming_obsolete_code_is_current(self):
        checked = self.invoke()
        self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "op",
                "view_ref": self.view_ref,
                "proof_ref": checked["data"]["local_check_ref"],
            },
        )
        card_path = "knowledge/flows/fixture-code-flow.md"
        old_card = (self.root / card_path).read_bytes()
        self.code.joinpath("src/wifi.c").write_bytes(
            b"int fixture_wifi_ready(void) { return 2; }\n"
        )
        self.git("add", "src/wifi.c")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "obsolete fixture behavior",
        )
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["operation_id"] = "retire"
        context["repos"]["wifi-code"].update(
            head=latest,
            files={"src/wifi.c": digest(self.code.joinpath("src/wifi.c").read_bytes())},
        )
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.context_ref = ".build/operations/retire/context.json"
        self.save(self.context_ref, seal(context))
        _, front, body = old_card.decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata.update(
            lifecycle="deprecated",
            replacement=[],
            deprecation_reason="Fixture implementation no longer returns one",
        )
        tombstone = (
            "---\n"
            + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + "---"
            + body
        ).encode()
        self.assertTrue(tombstone.endswith(body.encode()))
        writes = [
            {
                "path": card_path,
                "expected_old_digest": digest(old_card),
                "final_digest": digest(tombstone),
                "bytes_b64": base64.b64encode(tombstone).decode(),
            }
        ]
        view = dict(self.view)
        view.update(
            operation_id="retire",
            writes=writes,
            context_ref=self.context_ref,
            baseline_digest=digest({"files": {card_path: digest(old_card)}}),
        )
        self.view = seal(view)
        self.view_ref = ".build/operations/retire/view.json"
        self.save(self.view_ref, self.view)
        self.evidence[0].update(
            status="retired", reason=metadata["deprecation_reason"], replacement=[]
        )
        self.report_ref = ".build/operations/retire/semantic-report.json"
        self.sign_report("local")
        request = {
            "operation_id": "retire",
            "view_ref": self.view_ref,
            "semantic_report_ref": self.report_ref,
        }
        retired = self.invoke(request=request)
        self.assertEqual(retired["data"]["check_status"], "passed")
        proof_ref = retired["data"]["local_check_ref"]
        proof = json.loads((self.root / proof_ref).read_text(encoding="utf-8"))
        self.assertEqual(proof["claims"][0]["status"], "retired")
        applied = self.invoke(
            skill="hs-knowledge-apply",
            request={
                "operation_id": "retire",
                "view_ref": self.view_ref,
                "proof_ref": proof_ref,
            },
        )
        self.assertEqual((self.root / card_path).read_bytes(), tombstone)
        qualified = self.invoke(
            skill="hs-knowledge-apply",
            action="verify-result",
            request={
                "operation_id": "retire",
                "apply_result_ref": applied["data"]["apply_result_ref"],
            },
        )
        self.assertEqual(qualified["data"]["eligible_files"], [])
        self.assertEqual(
            qualified["data"]["historical_files"],
            [{"path": card_path, "sha256": digest(tombstone)}],
        )


if __name__ == "__main__":
    unittest.main()
