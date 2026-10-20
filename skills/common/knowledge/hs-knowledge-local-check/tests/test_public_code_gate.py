"""Signed synthetic code protocol in an isolated Git fixture; no real Target QA."""
import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import yaml

SKILLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "hs-knowledge-local-check/scripts"))
from support import canonical, digest, package_digest, seal


class PublicCodeGateTests(unittest.TestCase):
    def setUp(self):
        configured = os.environ.get("AIOTBOT_TEST_GOVERNANCE")
        domain = pathlib.Path(configured) if configured else pathlib.Path(__file__).resolve().parents[5] / "aiotbot-knowledge-wifi/governance"
        if not domain.joinpath("contracts/validation.py").is_file():
            self.skipTest("2.0 domain fixture path not supplied")
        scratch = pathlib.Path(os.environ.get("AIOTBOT_TEST_TMP", tempfile.gettempdir()))
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="code-gate-", dir=str(scratch))
        self.addCleanup(self.tmp.cleanup)
        self.workspace = pathlib.Path(self.tmp.name)
        self.root = self.workspace / "aiotbot-knowledge-wifi"
        shutil.copytree(domain, self.root / "governance", ignore=shutil.ignore_patterns("__pycache__"))
        self.root.joinpath(".isolated-knowledge-fixture").write_text("AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8")
        self.rules_digest = digest((self.root / "governance/framework.lock.yaml").read_bytes())
        self.code = self.workspace / "code"
        self.code.mkdir()
        self.git("init", "--initial-branch=main", "-q")
        self.code.joinpath("src").mkdir()
        self.source = b"int fixture_wifi_ready(void) { return 1; }\n"
        self.code.joinpath("src/wifi.c").write_bytes(self.source)
        self.git("add", "src/wifi.c")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        config = yaml.safe_load(domain.parents[1].joinpath("config.yml").read_bytes())
        config["repos"] = [{"repo_id": "wifi-code", "kind": "git", "root": str(self.code), "expected_identity": "synthetic-wifi-code"}]
        for target in config["targets"]:
            target.update(source_bindings=["fixture-code"], module_roots=["src"], build_profile="fixture-build", required_features=["WIFI_ON"], protocol_versions=["fixture-v1"])
        policy = {"allowed_ref": "refs/heads/main", "repo_roots": {"wifi-code": str(self.code)}}
        config["code_policy"] = policy
        config_raw = yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode()
        self.workspace.joinpath("config.yml").write_bytes(config_raw)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        self.key = Ed25519PrivateKey.generate()
        self.catalog = {"schema_version": "2.0", "skills": {}, "code_policy": policy, "semantic_reviewers": {"fixture": {"synthetic": True, "fixture_root": str(self.root), "public_key_b64": base64.b64encode(self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}}
        for name in ("hs-knowledge-local-check", "hs-knowledge-apply", "hs-knowledge-merge-check"):
            package = SKILLS / name
            self.catalog["skills"][name] = {"root": str(package), "entry": "scripts/cli.py", "python": sys.executable, "package_digest": package_digest(package)}
        self.catalog_path = self.workspace / "trusted-catalog.json"
        self.catalog_path.write_bytes(canonical(self.catalog))
        self.counter = 0
        self.tool = {"skill": "hs-fixture-producer", "package_digest": "0" * 64, "runtime": "fixture", "requirements_digest": "0" * 64}
        for rel, data in (("logs/evidence/code.bin", self.source), ("logs/evidence/build.bin", b"synthetic fixture build only\n")):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        locator = {"kind": "lines", "start": 1, "end": 1, "repo_id": "wifi-code", "path": "src/wifi.c"}
        source_lock = {"schema_version": "2.0", "resources": [{"source_id": "fixture-code", "kind": "code", "repo_id": "wifi-code", "path": "src/wifi.c"}], "snapshots": [{"source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "sha256": digest(self.source), "bytes": len(self.source), "recovery": {"path": "logs/evidence/code.bin"}}]}
        scope = {"context_id": "chip12-host-build", "target_id": "chip12-host", "chip": "chip12", "side": "host", "build_profile": "fixture-build", "features_all": ["WIFI_ON"], "features_none": [], "protocol_versions": ["fixture-v1"], "revision_policy": "revalidate", "revision": self.head}
        card_text = (self.root / "governance/templates/flow.md").read_text(encoding="utf-8")
        for key, value in {"card_id": "fixture-code-flow", "title": "Fixture code", "summary": "Synthetic code check", "owner": "fixture", "evidence_ref": "e1", "source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "claim_id": "c1", "claim_text": "The fixture function returns one."}.items():
            card_text = card_text.replace("{{" + key + "}}", value)
        _, front, body = card_text.split("---", 2)
        meta = yaml.safe_load(front)
        meta.update(lifecycle="stable", review_mode="code_gate", scope={"applicability": "constrained", "contexts": [scope]})
        meta["sources"][0]["locator"] = locator
        meta["claims"][0].update(evidence_kind="implementation", usage="current", context_ids=[scope["context_id"]], verification_requirements=["semantic-support"])
        card = ("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---" + body).encode()
        context = self.record("project_context", state="loaded", workspace_id=config["workspace_id"], knowledge_root=str(self.root), entries=[], config_digest=digest(config_raw), repos={"wifi-code": {"root": str(self.code), "identity": "synthetic-wifi-code", "head": self.head, "dirty": False, "files": {"src/wifi.c": digest(self.source)}}}, target={"target_id": "chip12-host", "chip": "chip12", "side": "host", "build_profile": "fixture-build", "features": ["WIFI_ON"], "protocol_versions": ["fixture-v1"], "revision": self.head}, build_evidence={"profile": "fixture-build", "source_revision": self.head, "macro_digest": digest(["WIFI_ON"]), "artifacts": [{"path": "logs/evidence/build.bin", "sha256": digest(b"synthetic fixture build only\n")}]})
        self.context_ref = ".build/operations/op/context.json"
        self.save(self.context_ref, context)
        source_raw = canonical(source_lock)
        writes = [{"path": "knowledge/flows/fixture-code-flow.md", "expected_old_digest": None, "final_digest": digest(card), "bytes_b64": base64.b64encode(card).decode()}, {"path": "governance/sources.lock.yaml", "expected_old_digest": digest((self.root / "governance/sources.lock.yaml").read_bytes()), "final_digest": digest(source_raw), "bytes_b64": base64.b64encode(source_raw).decode()}]
        self.view = self.record("final_view", review_mode="code_gate", context_ref=self.context_ref, writes=writes, deletes=[], source_refs=[], plan_ref=".build/operations/op/fixture-plan.json", plan_digest="0" * 64, baseline_digest=digest({"files": {row["path"]: row["expected_old_digest"] for row in writes}}))
        self.view_ref = ".build/operations/op/view.json"
        self.save(self.view_ref, self.view)
        self.evidence = [{"card_id": "fixture-code-flow", "claim_id": "c1", "status": "supported", "evidence": [{"source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot", "locator": locator, "sha256": digest(self.source)}]}]
        self.report_ref = ".build/operations/op/semantic-report.json"
        self.sign_report("local")

    def git(self, *arguments):
        result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(self.code), *arguments], capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def record(self, kind, **fields):
        return seal({"schema_version": "2.0", "record_kind": kind, "operation_id": "op", "rules_digest": self.rules_digest, "tool_identity": self.tool, **fields})

    def save(self, ref, value):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value))

    def sign_report(self, mode):
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        payload = {"view_digest": self.view["digest"], "context_digest": context["digest"], "mode": mode, "claims": self.evidence, "issued_at": time.time()}
        self.save(self.report_ref, {"schema_version": "2.0", "record_kind": "semantic_review", "reviewer_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(self.key.sign(canonical(payload))).decode()})

    def invoke(self, skill="hs-knowledge-local-check", action="run", request=None, expected=0):
        self.counter += 1
        request = request or {"operation_id": "op", "view_ref": self.view_ref, "semantic_report_ref": self.report_ref}
        inp, out = f".build/operations/op/request-{self.counter}.json", f".build/operations/op/response-{self.counter}.json"
        self.save(inp, request)
        completed = subprocess.run([sys.executable, str(SKILLS / skill / "scripts/cli.py"), "--input", str(self.root / inp), "--output", str(self.root / out), "--knowledge-root", str(self.root), "--rules-digest", self.rules_digest, "--catalog", str(self.catalog_path), "--action", action], capture_output=True, check=False, timeout=60)
        response = json.loads((self.root / out).read_text(encoding="utf-8"))
        self.assertEqual(completed.returncode, expected, (completed.stderr, response))
        return response

    def test_signed_positive_support_then_apply_and_verify(self):
        checked = self.invoke()
        self.assertEqual(checked["data"]["check_status"], "passed")
        request = {"operation_id": "op", "view_ref": self.view_ref, "proof_ref": checked["data"]["local_check_ref"]}
        verified = self.invoke(action="verify-proof", request=request)
        self.assertTrue(verified["data"]["proof_verified"])
        before = self.code.joinpath("src/wifi.c").read_bytes()
        applied = self.invoke(skill="hs-knowledge-apply", request=request)
        self.assertEqual(applied["data"]["transaction_status"], "committed")
        self.assertEqual(self.code.joinpath("src/wifi.c").read_bytes(), before)

    def test_missing_signed_support_stays_incomplete(self):
        result = self.invoke(request={"operation_id": "op", "view_ref": self.view_ref})
        self.assertEqual(result["data"]["check_status"], "incomplete")

    def test_tampered_signed_support_fails(self):
        report = json.loads((self.root / self.report_ref).read_text(encoding="utf-8"))
        report["payload"]["claims"][0]["status"] = "unsupported"
        self.save(self.report_ref, report)
        self.assertEqual(self.invoke()["data"]["check_status"], "failed")

    def test_latest_merge_ref_invalidates_stale_context_without_repairs(self):
        self.code.joinpath("src/wifi.c").write_bytes(b"int fixture_wifi_ready(void) { return 2; }\n")
        self.git("add", "src/wifi.c")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "new latest")
        view_before = (self.root / self.view_ref).read_bytes()
        lock_before = (self.root / "governance/sources.lock.yaml").read_bytes()
        self.assertEqual(self.invoke(action="merge")["data"]["check_status"], "incomplete")
        self.assertEqual((self.root / self.view_ref).read_bytes(), view_before)
        self.assertEqual((self.root / "governance/sources.lock.yaml").read_bytes(), lock_before)

    def test_changed_latest_code_can_pass_with_independent_signed_check_snapshot(self):
        newer = b"/* a harmless fixture comment */\n" + self.source
        self.code.joinpath("src/wifi.c").write_bytes(newer)
        self.git("add", "src/wifi.c")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "latest fixture comment")
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["repos"]["wifi-code"].update(head=latest, files={"src/wifi.c": digest(newer)})
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.save(self.context_ref, seal(context))
        self.evidence[0]["evidence"][0]["checked_snapshot"] = {"repo_id": "wifi-code", "path": "src/wifi.c", "sha256": digest(newer), "snapshot_id": "latest-check-snapshot", "locator": {"kind": "lines", "start": 2, "end": 2}, "commit": latest, "bytes": len(newer)}
        self.sign_report("merge")
        frozen = {ref: (self.root / ref).read_bytes() for ref in (self.view_ref, "governance/sources.lock.yaml", "logs/evidence/code.bin")}
        result = self.invoke(skill="hs-knowledge-merge-check")
        self.assertEqual(result["data"]["check_status"], "passed")
        for ref, raw in frozen.items():
            self.assertEqual((self.root / ref).read_bytes(), raw)
        self.assertEqual((self.root / ("logs/evidence/checked-code/" + digest(newer) + ".bin")).read_bytes(), newer)

    def test_signed_retirement_applies_without_claiming_obsolete_code_is_current(self):
        checked = self.invoke()
        self.invoke(skill="hs-knowledge-apply", request={"operation_id": "op", "view_ref": self.view_ref, "proof_ref": checked["data"]["local_check_ref"]})
        card_path = "knowledge/flows/fixture-code-flow.md"
        old_card = (self.root / card_path).read_bytes()
        self.code.joinpath("src/wifi.c").write_bytes(b"int fixture_wifi_ready(void) { return 2; }\n")
        self.git("add", "src/wifi.c")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-qm", "obsolete fixture behavior")
        latest = self.git("rev-parse", "HEAD").decode().strip()
        context = json.loads((self.root / self.context_ref).read_text(encoding="utf-8"))
        context["operation_id"] = "retire"
        context["repos"]["wifi-code"].update(head=latest, files={"src/wifi.c": digest(self.code.joinpath("src/wifi.c").read_bytes())})
        context["target"]["revision"] = latest
        context["build_evidence"]["source_revision"] = latest
        self.context_ref = ".build/operations/retire/context.json"
        self.save(self.context_ref, seal(context))
        _, front, body = old_card.decode().split("---", 2)
        metadata = yaml.safe_load(front)
        metadata.update(lifecycle="deprecated", replacement=[], deprecation_reason="Fixture implementation no longer returns one")
        tombstone = ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---" + body).encode()
        self.assertTrue(tombstone.endswith(body.encode()))
        writes = [{"path": card_path, "expected_old_digest": digest(old_card), "final_digest": digest(tombstone), "bytes_b64": base64.b64encode(tombstone).decode()}]
        view = dict(self.view)
        view.update(operation_id="retire", writes=writes, context_ref=self.context_ref, baseline_digest=digest({"files": {card_path: digest(old_card)}}))
        self.view = seal(view)
        self.view_ref = ".build/operations/retire/view.json"
        self.save(self.view_ref, self.view)
        self.evidence[0].update(status="retired", reason=metadata["deprecation_reason"], replacement=[])
        self.report_ref = ".build/operations/retire/semantic-report.json"
        self.sign_report("local")
        request = {"operation_id": "retire", "view_ref": self.view_ref, "semantic_report_ref": self.report_ref}
        retired = self.invoke(request=request)
        self.assertEqual(retired["data"]["check_status"], "passed")
        proof_ref = retired["data"]["local_check_ref"]
        proof = json.loads((self.root / proof_ref).read_text(encoding="utf-8"))
        self.assertEqual(proof["claims"][0]["status"], "retired")
        applied = self.invoke(skill="hs-knowledge-apply", request={"operation_id": "retire", "view_ref": self.view_ref, "proof_ref": proof_ref})
        self.assertEqual((self.root / card_path).read_bytes(), tombstone)
        qualified = self.invoke(skill="hs-knowledge-apply", action="verify-result", request={"operation_id": "retire", "apply_result_ref": applied["data"]["apply_result_ref"]})
        self.assertEqual(qualified["data"]["eligible_files"], [])


if __name__ == "__main__":
    unittest.main()
