"""Transaction mechanism tests with authenticated synthetic fixture consent."""

import base64
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class ApplyTests(unittest.TestCase):
    def fixture(self, root):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from support import Context, canonical, digest

        ctx = Context.synthetic(root, "hs-knowledge-apply")
        root.joinpath(".isolated-knowledge-fixture").write_text(
            "AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
        )
        key = Ed25519PrivateKey.generate()
        ctx.catalog = {
            "review_trust": {
                "adapters": {
                    "fixture": {
                        "synthetic": True,
                        "fixture_root": str(root),
                        "public_key_b64": base64.b64encode(
                            key.public_key().public_bytes(
                                Encoding.Raw, PublicFormat.Raw
                            )
                        ).decode(),
                    }
                }
            }
        }
        (root / "knowledge").mkdir()
        (root / "knowledge/update.md").write_bytes(b"old")
        (root / "knowledge/delete.md").write_bytes(b"delete")
        writes = [
            {
                "path": "knowledge/create.md",
                "expected_old_digest": None,
                "final_digest": digest(b"created"),
                "bytes_b64": base64.b64encode(b"created").decode(),
            },
            {
                "path": "knowledge/update.md",
                "expected_old_digest": digest(b"old"),
                "final_digest": digest(b"updated"),
                "bytes_b64": base64.b64encode(b"updated").decode(),
            },
        ]
        view = ctx.record(
            "final_view",
            "op",
            review_mode="manual_document",
            writes=writes,
            deletes=[
                {
                    "path": "knowledge/delete.md",
                    "expected_old_digest": digest(b"delete"),
                }
            ],
            source_refs=[],
        )
        ctx.save(".build/operations/op/view.json", view)
        display = ctx.record(
            "confirmation_display",
            "op",
            view_ref=".build/operations/op/view.json",
            view_digest=view["digest"],
            writes=writes,
            deletes=view["deletes"],
            challenge="challenge",
            created_at=time.time() - 1,
            expires_at=time.time() + 100,
        )
        ctx.save(".build/operations/op/display.json", display)
        payload = {
            "actor_type": "human",
            "actor_id": "fixture-human",
            "decision": "approve",
            "display_digest": display["digest"],
            "view_digest": view["digest"],
            "challenge": display["challenge"],
            "issued_at": time.time(),
        }
        event = {
            "schema_version": "2.0",
            "record_kind": "host_event",
            "adapter_id": "fixture",
            "payload": payload,
            "signature_b64": base64.b64encode(key.sign(canonical(payload))).decode(),
        }
        proof = ctx.record(
            "manual_review",
            "op",
            status="approved",
            view_digest=view["digest"],
            display_ref=".build/operations/op/display.json",
            display_digest=display["digest"],
            host_event=event,
            verification_tier="synthetic_host",
        )
        ctx.save("logs/operations/op/manual-review.json", proof)
        request = {
            "operation_id": "op",
            "view_ref": ".build/operations/op/view.json",
            "proof_ref": "logs/operations/op/manual-review.json",
        }
        return ctx, request

    def test_multi_write_delete_commit_and_idempotent_reentry(self):
        from transaction import execute

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            result = execute(ctx, request, "run")
            self.assertEqual(ctx.path("knowledge/create.md").read_bytes(), b"created")
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"updated")
            self.assertFalse(ctx.path("knowledge/delete.md").exists())
            ctx.path("knowledge/update.md").write_bytes(b"external-later")
            self.assertEqual(execute(ctx, request, "run"), result)
            self.assertEqual(
                ctx.path("knowledge/update.md").read_bytes(), b"external-later"
            )

    def test_complete_cas_blocks_before_first_write(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            ctx.path("knowledge/delete.md").write_bytes(b"external")
            with self.assertRaises(Blocked):
                execute(ctx, request, "run")
            self.assertFalse(ctx.path("knowledge/create.md").exists())
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"old")

    def test_failure_then_resume(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 1}, "run")
            state = execute(ctx, {"operation_id": "op"}, "inspect")
            self.assertEqual(state["transaction_status"], "recovery_required")
            execute(ctx, {"operation_id": "op"}, "resume")
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"updated")
            self.assertFalse(ctx.path("knowledge/delete.md").exists())

    def test_failure_then_rollback_restores_old_bytes(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 2}, "run")
            execute(ctx, {"operation_id": "op"}, "rollback")
            self.assertFalse(ctx.path("knowledge/create.md").exists())
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"old")
            self.assertEqual(ctx.path("knowledge/delete.md").read_bytes(), b"delete")

    def test_recovery_preserves_external_edit(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 1}, "run")
            ctx.path("knowledge/create.md").write_bytes(b"external")
            for action in ("resume", "rollback"):
                with self.assertRaises(Blocked):
                    execute(ctx, {"operation_id": "op"}, action)
            self.assertEqual(ctx.path("knowledge/create.md").read_bytes(), b"external")

    def test_resealed_fake_consent_is_not_approval(self):
        from transaction import execute
        from support import Invalid, canonical, seal

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            proof = ctx.read(request["proof_ref"])
            proof["host_event"]["payload"]["actor_id"] = "forged"
            ctx.path(request["proof_ref"]).write_bytes(canonical(seal(proof)))
            with self.assertRaises(Invalid):
                execute(ctx, request, "run")
            self.assertFalse(ctx.path("knowledge/create.md").exists())

    def test_resealed_journal_cannot_authorize_raw_writes(self):
        from transaction import execute
        from support import Blocked, Invalid, canonical, seal

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 1}, "run")
            journal = ctx.read("logs/operations/op/journal.json")
            journal["entries"][0]["path"] = "docs-raw/specs/original.md"
            ctx.path("logs/operations/op/journal.json").write_bytes(
                canonical(seal(journal))
            )
            with self.assertRaises(Invalid):
                execute(ctx, {"operation_id": "op"}, "rollback")
            self.assertEqual(ctx.path("knowledge/create.md").read_bytes(), b"created")

    def test_cooperative_writer_lock_is_exclusive(self):
        from support import WriterLock, Blocked

        with tempfile.TemporaryDirectory() as tmp:
            with WriterLock(pathlib.Path(tmp)):
                with self.assertRaises(Blocked):
                    with WriterLock(pathlib.Path(tmp)):
                        self.fail("second writer acquired the domain lock")

    def test_other_interrupted_operation_blocks_new_apply(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            journal = ctx.record(
                "transaction_journal", "other", status="recovery_required", entries=[]
            )
            ctx.save("logs/operations/other/journal.json", journal)
            with self.assertRaises(Blocked):
                execute(ctx, request, "run")
            self.assertFalse(ctx.path("knowledge/create.md").exists())

    def test_unrelated_old_rules_terminal_journal_does_not_authorize_or_block_new_review(self):
        from transaction import execute
        from support import seal

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            old = seal({**ctx.record("transaction_journal", "legacy", status="committed", entries=[],
                view_ref=".build/operations/legacy/view.json", view_digest="1" * 64,
                proof_ref="logs/operations/legacy/proof.json", proof_digest="2" * 64), "rules_digest": "a" * 64})
            ctx.save("logs/operations/legacy/journal.json", old)
            frozen = ctx.path("logs/operations/legacy/journal.json").read_bytes()
            result = execute(ctx, request, "run")
            self.assertEqual(result["transaction_status"], "committed")
            self.assertEqual(ctx.path("knowledge/create.md").read_bytes(), b"created")
            self.assertEqual(ctx.path("logs/operations/legacy/journal.json").read_bytes(), frozen)

    def test_committed_reentry_is_read_only_during_another_recovery(self):
        from transaction import execute

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            original = execute(ctx, request, "run")
            ctx.save(
                "logs/operations/other/journal.json",
                ctx.record(
                    "transaction_journal",
                    "other",
                    status="recovery_required",
                    entries=[],
                ),
            )
            self.assertEqual(execute(ctx, request, "run"), original)

    def test_rollback_preserves_external_final_bytes_on_unattempted_target(self):
        from transaction import execute
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 1}, "run")
            ctx.path("knowledge/update.md").write_bytes(b"updated")
            with self.assertRaises(Blocked):
                execute(ctx, {"operation_id": "op"}, "rollback")
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"updated")
            self.assertEqual(ctx.path("knowledge/create.md").read_bytes(), b"created")

    def test_interrupted_immutable_publish_never_leaves_partial_record(self):
        from support import Context
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-apply")
            record = ctx.record("apply_result", "op", status="committed")
            ref = "logs/operations/op/atomic-test.json"
            with patch(
                "support.os.link",
                side_effect=RuntimeError("synthetic hard interruption before publish"),
            ):
                with self.assertRaises(RuntimeError):
                    ctx.save(ref, record)
            self.assertFalse(ctx.path(ref).exists())
            ctx.save(ref, record)
            self.assertEqual(ctx.read(ref)["status"], "committed")


if __name__ == "__main__":
    unittest.main()
