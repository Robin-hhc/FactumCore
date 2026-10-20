"""Real public CLIs + copied 2.0 domain, synthetic host and navigation only.

Set AIOTBOT_TEST_GOVERNANCE when running outside the monorepo. No private
cross-Skill imports, real source documents, gold or installed host are used.
"""
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

SKILLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "hs-knowledge-apply/scripts"))
from support import canonical, digest, package_digest, seal


class PublicGovernanceTests(unittest.TestCase):
    def setUp(self):
        configured = os.environ.get("AIOTBOT_TEST_GOVERNANCE")
        domain = pathlib.Path(configured) if configured else pathlib.Path(__file__).resolve().parents[5] / "aiotbot-knowledge-wifi/governance"
        if not domain.joinpath("contracts/validation.py").is_file():
            self.skipTest("2.0 domain fixture path not supplied")
        scratch = pathlib.Path(os.environ.get("AIOTBOT_TEST_TMP", tempfile.gettempdir()))
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="governance-cli-", dir=str(scratch))
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        shutil.copytree(domain, self.root / "governance", ignore=shutil.ignore_patterns("__pycache__"))
        self.rules_digest = digest((self.root / "governance/framework.lock.yaml").read_bytes())
        self.root.joinpath(".isolated-knowledge-fixture").write_text("AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8")
        self.root.joinpath("knowledge").mkdir()
        self.root.joinpath("knowledge/index.md").write_bytes(b"old navigation")
        self.counter = 0
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        self.key = Ed25519PrivateKey.generate()
        self.catalog = {"schema_version": "2.0", "skills": {}, "review_trust": {"adapters": {"fixture": {"synthetic": True, "fixture_root": str(self.root), "public_key_b64": base64.b64encode(self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}}}
        for name in ("hs-knowledge-confirmation-prepare", "hs-knowledge-confirmation-record", "hs-knowledge-apply", "hs-knowledge-recover", "hs-knowledge-publish-handoff"):
            package = SKILLS / name
            self.catalog["skills"][name] = {"root": str(package), "entry": "scripts/cli.py", "python": sys.executable, "package_digest": package_digest(package)}
        self.catalog_path = self.root / "installed-catalog.json"
        self.catalog_path.write_bytes(canonical(self.catalog))

    def invoke(self, skill, request, action="run", expected=0):
        self.counter += 1
        parent = self.root / (".build/operations/" + request["operation_id"])
        parent.mkdir(parents=True, exist_ok=True)
        inp = parent / ("request-" + str(self.counter) + ".json")
        out = parent / ("response-" + str(self.counter) + ".json")
        inp.write_bytes(canonical(request))
        completed = subprocess.run([sys.executable, str(SKILLS / skill / "scripts/cli.py"), "--input", str(inp), "--output", str(out), "--knowledge-root", str(self.root), "--rules-digest", self.rules_digest, "--catalog", str(self.catalog_path), "--action", action], capture_output=True, check=False, timeout=60)
        result = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        self.assertEqual(completed.returncode, expected, (completed.stderr.decode(errors="replace"), result))
        return result

    def prepare_and_approve(self, op):
        old = self.root.joinpath("knowledge/index.md").read_bytes()
        row = {"path": "knowledge/index.md", "expected_old_digest": digest(old), "final_digest": digest(b"new navigation"), "bytes_b64": base64.b64encode(b"new navigation").decode()}
        view = seal({"schema_version": "2.0", "record_kind": "final_view", "operation_id": op, "rules_digest": self.rules_digest, "tool_identity": {"skill": "synthetic-materializer"}, "review_mode": "manual_document", "writes": [row], "deletes": [], "source_refs": [], "baseline_digest": digest({"files": {row["path"]: row["expected_old_digest"]}})})
        ref = f".build/operations/{op}/view.json"
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(view))
        prepared = self.invoke("hs-knowledge-confirmation-prepare", {"operation_id": op, "view_ref": ref})
        self.assertEqual(prepared["phase"], "awaiting_human")
        display_ref = prepared["data"]["display_ref"]
        self.invoke("hs-knowledge-confirmation-record", {"operation_id": op, "display_ref": display_ref}, expected=3)
        display = json.loads((self.root / display_ref).read_text(encoding="utf-8"))
        payload = {"actor_type": "human", "actor_id": "synthetic-human", "decision": "approve", "display_digest": display["digest"], "view_digest": display["view_digest"], "challenge": display["challenge"], "issued_at": time.time()}
        event = {"schema_version": "2.0", "record_kind": "host_event", "adapter_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(self.key.sign(canonical(payload))).decode()}
        event_ref = f".build/operations/{op}/host-event.json"
        (self.root / event_ref).write_bytes(canonical(event))
        reviewed = self.invoke("hs-knowledge-confirmation-record", {"operation_id": op, "display_ref": display_ref, "host_event_ref": event_ref})
        return {"operation_id": op, "view_ref": ref, "proof_ref": reviewed["data"]["manual_review_ref"]}

    def test_public_prepare_record_apply_verify_publish(self):
        request = self.prepare_and_approve("public")
        applied = self.invoke("hs-knowledge-apply", request)
        self.assertEqual(self.root.joinpath("knowledge/index.md").read_bytes(), b"new navigation")
        verify_request = {"operation_id": "public", "apply_result_ref": applied["data"]["apply_result_ref"]}
        verified = self.invoke("hs-knowledge-apply", verify_request, action="verify-result")
        self.assertTrue(verified["data"]["result_verified"])
        handoff = self.invoke("hs-knowledge-publish-handoff", verify_request)
        record = json.loads((self.root / handoff["data"]["publish_handoff_ref"]).read_text(encoding="utf-8"))
        self.assertFalse(record["git_merge_verified"])
        self.assertFalse(record["remote_push_verified"])
        self.assertEqual(record["verification_tier"], "synthetic_host")

    def test_public_recover_delegates_to_single_apply_engine(self):
        request = self.prepare_and_approve("recover")
        self.invoke("hs-knowledge-apply", {**request, "fault_after": 1}, expected=3)
        inspected = self.invoke("hs-knowledge-recover", {"operation_id": "recover", "workflow": {"attempt_id": "inspect1"}}, action="inspect")
        self.assertEqual(inspected["data"]["transaction_status"], "recovery_required")
        resumed = self.invoke("hs-knowledge-recover", {"operation_id": "recover", "workflow": {"attempt_id": "resume1"}}, action="resume")
        self.assertEqual(resumed["data"]["transaction_status"], "committed")


if __name__ == "__main__":
    unittest.main()
