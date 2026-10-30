"""Agent review records over isolated Git fixtures; no real Target QA."""

import base64
import importlib.util as _fixture_importlib
from pathlib import Path as _FixturePath
import json
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import time
import unittest

import yaml

import importlib.util as _repository_importlib
from pathlib import Path as _RepositoryPath
_repository_spec = _repository_importlib.spec_from_file_location(
    "test_public_code_gate_repository_runtime_fixture",
    _RepositoryPath(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py",
)
_repository_fixture = _repository_importlib.module_from_spec(_repository_spec)
_repository_spec.loader.exec_module(_repository_fixture)

SKILLS = _repository_fixture.ROOT / "skills/common/knowledge"
_fixture_root = _FixturePath(__file__).resolve().parents[5]
_fixture_spec = _fixture_importlib.spec_from_file_location("lint_contract_fixture", _fixture_root / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py")
_fixture_lib = _fixture_importlib.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_lib)
legacy = _fixture_lib.module("legacy_runtime")
engine = _fixture_lib.module("code_review")

canonical, digest, package_digest, seal = legacy.canonical, legacy.digest, legacy.package_digest, legacy.seal
_pipeline_spec = _fixture_importlib.spec_from_file_location("lint_pipeline_fixture", _fixture_root / "himate/himate-knowledge-wifi-mp/evals/support/pipeline.py")
_pipeline = _fixture_importlib.module_from_spec(_pipeline_spec)
_pipeline_spec.loader.exec_module(_pipeline)


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
        self._fixture_scratch = scratch.resolve(strict=True)
        self.workspace = pathlib.Path(tempfile.mkdtemp(prefix="code-gate-", dir=str(self._fixture_scratch))).resolve(strict=True)
        self._fixture_target = self.workspace
        self.addCleanup(self.cleanup_fixture)
        self.root = self.workspace / "himate-knowledge-wifi-mp"
        shutil.copytree(
            domain,
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        _repository_fixture.copy_runtime(self.root)
        empty_dbox = self.workspace / "empty-dbox"
        empty_dbox.mkdir()
        local = self.root / "docs-raw/sources/dbox.local.yml"
        local.parent.mkdir(parents=True)
        local.write_text(yaml.safe_dump({"schema_version": "1.0", "path": str(empty_dbox)}), encoding="utf-8")
        self.root.joinpath(".isolated-knowledge-fixture").write_text(
            "HIMATE_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
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
        # These tests intentionally retain the legacy contract. The production
        # entry no longer asks users to maintain six Target declarations.
        config = {
            "schema_version": "2.0", "workspace_id": "isolated-code-review",
            "knowledge_roots": {"wifi": self.root.name},
            "repos": [], "architecture": [{"binding_id": "wifi-main", "repo_id": "wifi-code",
                "module_root": ".", "knowledge_domain": "wifi", "override_nested": False}],
            "wiki_entities": {}, "symbol_aliases": {},
            "targets": [{"target_id": chip + "-" + side, "chip": chip, "side": side,
                "source_bindings": [], "module_roots": [], "build_profile": None,
                "required_features": [], "protocol_versions": []}
                for chip in ("chip12", "chip08", "chip07c") for side in ("host", "device")],
            "pairs": [{"pairing_id": chip + "-host-device", "host_target": chip + "-host",
                "device_target": chip + "-device", "compatibility_policy": "unknown"}
                for chip in ("chip12", "chip08", "chip07c")],
            "query": {"default_channel": "local", "allowed_channels": ["local", "shared"]},
        }
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
            ("logs/evidence/objects/" + digest(self.source) + ".bin", self.source),
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
                    "recovery": {"method": "evidence_object",
                                 "path": "logs/evidence/objects/" + digest(self.source) + ".bin"},
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
        meta["sources"][0]["code_ref"] = {
            "kind": "function", "name": "fixture_wifi_ready", "scope": [],
            "parameter_types": [], "role": "definition",
        }
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
        navigation = b"[Fixture code](fixture-code-flow.md)\n"
        writes.append({"path": "knowledge/flows/index.md", "expected_old_digest": None,
                       "final_digest": digest(navigation), "bytes_b64": base64.b64encode(navigation).decode()})
        self.view = self.record(
            "final_view",
            review_mode="code_gate",
            context_ref=self.context_ref,
            writes=writes,
            deletes=[],
            source_refs=source_lock["snapshots"],
            source_set_digest=digest(source_lock["snapshots"]),
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
        if self.view.get("plan_ref", "").endswith("/fixture-plan.json"):
            operation = self.view["operation_id"]
            self.view["plan_ref"] = f".build/operations/{operation}/fixture-plan.json"
            plan = self.record("change_plan", bundle_ref=".build/operations/op/fixture-bundle.json",
                               operation_id=operation,
                               bundle_digest="0" * 64, candidate_ids=["fixture"], decisions=[],
                               writes=self.view["writes"], deletes=self.view.get("deletes", []),
                               baseline={}, review_mode=self.view["review_mode"])
            self.save(self.view["plan_ref"], plan)
            self.view = seal({**self.view, "plan_digest": plan["digest"]})
            self.save(self.view_ref, self.view)
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
        self, skill="hs-knowledge-local-check", action="run", request=None, expected=0,
        use_catalog=True,
    ):
        self.counter += 1
        request = request or {
            "operation_id": "op",
            "view_ref": self.view_ref,
            "context_ref": self.context_ref,
            "semantic_report_ref": self.report_ref,
        }
        if skill == "hs-knowledge-apply" and action == "run":
            config = self.workspace / "config.yml"
            request.setdefault("check_inputs", {"code_checkout": {"configuration": str(config),
                "config_digest": digest(config.read_bytes()),
                "repos": {"wifi-code": {"root": str(self.code), "commit": self.head}}}})
        slug, request, action = _pipeline.target_call(skill.removeprefix("hs-"), request, action)
        skill = "hs-" + slug
        inp, out = (
            f".build/operations/{request['operation_id']}/request-{self.counter}.json",
            f".build/operations/{request['operation_id']}/response-{self.counter}.json",
        )
        self.save(inp, request)
        completed = subprocess.run(
            [
                *_repository_fixture.stage_command(skill, self.root),
                "--input",
                str(self.root / inp),
                "--output",
                str(self.root / out),
                "--knowledge-root",
                str(self.root),
                "--rules-digest",
                self.rules_digest,
                "--action",
                action,
            ] + (["--catalog", str(self.catalog_path)] if use_catalog else []),
            capture_output=True,
            check=False,
            timeout=60,
        )
        response = json.loads((self.root / out).read_text(encoding="utf-8"))
        if skill == "hs-knowledge-lint":
            if expected == 3:
                expected = 2  # Explicit 0/1/2 lint protocol replaces old transport 3.
            elif expected == 0 and response.get("status") == "ok":
                expected = {"passed": 0, "failed": 1, "incomplete": 2}.get(response.get("data", {}).get("check_status"), 0)
        self.assertEqual(completed.returncode, expected, (completed.stderr, response))
        return response


    def prepare_committed_code_publication(self):
        """Actual capture-code through same-generation query, with fixture trust."""
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
        scanned = self.invoke("hs-knowledge-source", "scan", {"operation_id": "op"})
        scan_ref = scanned["data"]["scan_ref"]
        scan = json.loads((self.root / scan_ref).read_bytes())
        self.assertEqual(scan["units"], [])
        affected = scan["current_context"]["affected_claims"]
        self.assertTrue(any(row["card_id"] == "fixture-code-flow" and row["claim_id"] == "c1" for row in affected))
        prepared = self.invoke("hs-knowledge-source", "prepare", {"operation_id": "op", "scan_ref": scan_ref,
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
        # Byte production belongs to P3; the independent legacy-run/index
        # portion below deliberately tests those standalone public purposes.
        materialized = self.invoke("hs-knowledge-view-materialize", request={"operation_id": "op", "v3_required": True,
            "semantic_plan_ref": semantic_ref, "material_ref": material_ref,
            "bundle_ref": material["bundle_ref"], "context_ref": self.context_ref,
            "decisions": [{"candidate_id": "fixture-code", "decision": "update", "reason": "Actual code result changed",
                           "card_inputs": [draft_ref]}]})
        self.view_ref = materialized["data"]["view_ref"]
        self.view = json.loads((self.root / self.view_ref).read_bytes())
        reviewed = self.invoke("hs-knowledge-lint", "record-review", {"operation_id": "op", "semantic_plan_ref": semantic_ref,
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
        self.assertEqual(refused["data"]["check_status"], "passed")
        self.save(self.report_ref, independent_report)
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        inputs = {"code_checkout": {"configuration": str(self.workspace / "config.yml"), "config_digest": context["config_digest"],
                                    "repos": {"wifi-code": {"root": str(self.code), "commit": self.head}}}}
        linted = self.invoke("hs-knowledge-lint", "review", request={
            "operation_id": "op", "view_ref": self.view_ref, "semantic_plan_ref": semantic_ref,
            "sampled_unit_ids": maintenance_ids, "unreviewed_unit_ids": [],
            "reason": "Read the complete candidate and its exact committed code evidence", "findings": [],
            "inputs": inputs, "code_review": {"context_ref": self.context_ref,
                                               "semantic_report_ref": self.report_ref}})
        self.assertEqual(linted["status"], "passed")
        self.assertEqual(linted["code_review"]["check_status"], "passed")
        lint_ref = str(pathlib.Path(linted["data"]["report_ref"]).relative_to(self.root)).replace("\\", "/")
        recorded = self.invoke("hs-knowledge-source", "record", {"operation_id": "op", "scan_ref": scan_ref,
            "semantic_plan_ref": semantic_ref, "view_ref": self.view_ref, "lint_ref": lint_ref,
            "disposition_preview_ref": self.view["disposition_preview_ref"]})
        applied = self.invoke("hs-knowledge-apply", request={"operation_id": "op", "v3_required": True, "view_ref": self.view_ref,
            "proof_ref": checked["data"]["local_check_ref"], "content_review_ref": reviewed["data"]["content_review_ref"],
            "lint_report_ref": lint_ref, "check_inputs": inputs, "ingest_record_ref": recorded["data"]["ingest_record_ref"]})
        self.assertEqual(applied["phase"], "committed")
        applied_record = json.loads((self.root / "logs/ingest/op.yaml").read_bytes())
        self.assertNotIn("acceptance", applied_record)
        self.assertEqual(applied_record["progress"]["apply"]["status"], "applied")
        semantic = json.loads((self.root / semantic_ref).read_bytes())
        self.assertEqual(applied_record["maintenance_dispositions"], semantic["maintenance_units"])
        built = self.invoke("hs-knowledge-index-build", "build", {"operation_id": "op"})["data"]
        generation = built["generation_ref"]
        regression = self.invoke("hs-knowledge-query-regression", request={"operation_id": "op", "v3_required": True,
            "apply_result_ref": applied["data"]["apply_result_ref"], "generation_ref": generation,
            "expected_active": built["expected_active"]})
        self.assertEqual(regression["phase"], "checked")
        self.assertTrue(regression["data"]["passed"])


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


if __name__ == "__main__":
    unittest.main()
