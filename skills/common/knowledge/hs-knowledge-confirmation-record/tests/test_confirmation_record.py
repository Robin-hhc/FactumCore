"""Signed synthetic-host tests; not real-human acceptance."""
import base64
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class ConfirmationRecordTests(unittest.TestCase):
    def fixture(self, root):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from support import Context, canonical
        key = Ed25519PrivateKey.generate()
        ctx = Context.synthetic(root, "hs-knowledge-confirmation-record")
        root.joinpath(".isolated-knowledge-fixture").write_text("AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8")
        ctx.catalog = {"review_trust": {"adapters": {"fixture": {"synthetic": True, "fixture_root": str(root), "public_key_b64": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}}}}
        view = ctx.record("final_view", "op", review_mode="manual_document", writes=[{"path": "knowledge/a.md", "expected_old_digest": None, "final_digest": "11507a0e2f5e69d5dfa40a62a1bd7b6ee57e6bcd85c67c9b8431b36fff21c437", "bytes_b64": "bmV3"}], deletes=[])
        ctx.save(".build/operations/op/view.json", view)
        display = ctx.record("confirmation_display", "op", view_ref=".build/operations/op/view.json", view_digest=view["digest"], writes=view["writes"], deletes=[], challenge="challenge", created_at=time.time() - 1, expires_at=time.time() + 100)
        ctx.save(".build/operations/op/confirmation-display.json", display)
        payload = {"actor_type": "human", "actor_id": "synthetic-reviewer", "decision": "approve", "display_digest": display["digest"], "view_digest": display["view_digest"], "challenge": display["challenge"], "issued_at": time.time()}
        event = {"schema_version": "2.0", "record_kind": "host_event", "adapter_id": "fixture", "payload": payload, "signature_b64": base64.b64encode(key.sign(canonical(payload))).decode()}
        path = root / ".build/operations/op/host-event.json"
        path.write_bytes(canonical(event))
        return ctx, display, event, key

    def test_signed_fixture_is_recorded_with_test_tier(self):
        from confirmation import record_confirmation
        with tempfile.TemporaryDirectory() as tmp:
            ctx, display, _, _ = self.fixture(pathlib.Path(tmp))
            result = record_confirmation(ctx, {"operation_id": "op", "display_ref": ".build/operations/op/confirmation-display.json", "host_event_ref": ".build/operations/op/host-event.json"})
            proof = ctx.read(result["manual_review_ref"])
            self.assertEqual(proof["verification_tier"], "synthetic_host")
            self.assertEqual(proof["status"], "approved")
            self.assertEqual(proof["display_digest"], display["digest"])

    def test_tampered_actor_or_view_is_rejected(self):
        from confirmation import record_confirmation
        from support import Invalid, canonical
        with tempfile.TemporaryDirectory() as tmp:
            ctx, _, event, _ = self.fixture(pathlib.Path(tmp))
            event["payload"]["view_digest"] = "b" * 64
            ctx.path(".build/operations/op/host-event.json").write_bytes(canonical(event))
            with self.assertRaises(Invalid):
                record_confirmation(ctx, {"operation_id": "op", "display_ref": ".build/operations/op/confirmation-display.json", "host_event_ref": ".build/operations/op/host-event.json"})

    def test_absent_host_is_awaiting(self):
        from confirmation import record_confirmation
        from support import Blocked
        with tempfile.TemporaryDirectory() as tmp:
            ctx, _, _, _ = self.fixture(pathlib.Path(tmp))
            ctx.catalog = {}
            with self.assertRaises(Blocked):
                record_confirmation(ctx, {"operation_id": "op", "display_ref": ".build/operations/op/confirmation-display.json"})

    def test_synthetic_adapter_cannot_escape_fixture(self):
        from confirmation import record_confirmation
        from support import Blocked
        with tempfile.TemporaryDirectory() as tmp:
            ctx, _, _, _ = self.fixture(pathlib.Path(tmp))
            ctx.path(".isolated-knowledge-fixture").unlink()
            with self.assertRaises(Blocked):
                record_confirmation(ctx, {"operation_id": "op", "display_ref": ".build/operations/op/confirmation-display.json", "host_event_ref": ".build/operations/op/host-event.json"})


if __name__ == "__main__":
    unittest.main()
