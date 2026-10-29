"""Transactions check their own bytes and write safely without workflow gates."""

import base64
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class ApplyTests(unittest.TestCase):
    def fixture(self, root):
        from support import Context, digest

        ctx = Context.synthetic(root, "hs-knowledge-apply")
        ctx.catalog = {"test_fixture_root": str(root.resolve())}
        root.joinpath(".isolated-knowledge-fixture").write_text(
            "HIMATE_SYNTHETIC_FIXTURE_V2", encoding="utf-8"
        )
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
        proof = ctx.record(
            "content_review", "op", status="passed", view_digest=view["digest"],
            author_id="fixture-author", reviewer_id="fixture-reviewer",
            independent_context=True, findings=[], verification_tier="independent_agent_review",
        )
        ctx.save(".build/operations/op/content-review.json", proof)
        request = {
            "operation_id": "op",
            "view_ref": ".build/operations/op/view.json",
            "proof_ref": ".build/operations/op/content-review.json",
            "content_review_ref": ".build/operations/op/content-review.json",
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

    def test_silent_target_write_failure_never_reports_committed_and_can_recover(self):
        from transaction import execute, atomic_bytes
        from support import Blocked
        from unittest.mock import patch

        for relative in ("knowledge/create.md", "knowledge/update.md"):
            for recovery in ("resume", "rollback"):
                with self.subTest(path=relative, recovery=recovery), tempfile.TemporaryDirectory() as tmp:
                    ctx, request = self.fixture(pathlib.Path(tmp))
                    target = ctx.path(relative)

                    def silently_skip(path, raw):
                        if path != target:
                            return atomic_bytes(path, raw)

                    with patch("transaction.atomic_bytes", side_effect=silently_skip):
                        with self.assertRaisesRegex(Blocked, "verification failed"):
                            execute(ctx, request)
                    journal = ctx.read(".build/operations/op/transaction/journal.json")
                    self.assertEqual(journal["status"], "recovery_required")
                    failed = next(row for row in journal["entries"] if row["path"] == relative)
                    self.assertTrue(failed["attempted"])
                    self.assertFalse(failed["installed"])
                    self.assertFalse(ctx.path(".build/operations/op/transaction/apply-result.json").exists())
                    result = execute(ctx, {"operation_id": "op"}, recovery)
                    self.assertEqual(result["transaction_status"], "committed" if recovery == "resume" else "rolled_back")
                    self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"updated" if recovery == "resume" else b"old")
                    self.assertEqual(ctx.path("knowledge/create.md").exists(), recovery == "resume")

    def test_silent_delete_failure_never_reports_committed(self):
        from transaction import execute
        from support import Blocked
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            target = ctx.path("knowledge/delete.md")
            original_unlink = pathlib.Path.unlink

            def silently_skip(path, *args, **kwargs):
                if path != target:
                    return original_unlink(path, *args, **kwargs)

            with patch.object(pathlib.Path, "unlink", silently_skip):
                with self.assertRaisesRegex(Blocked, "verification failed"):
                    execute(ctx, request)
            journal = ctx.read(".build/operations/op/transaction/journal.json")
            self.assertEqual(journal["status"], "recovery_required")
            self.assertFalse(journal["entries"][-1]["installed"])
            self.assertFalse(ctx.path(".build/operations/op/transaction/apply-result.json").exists())
            execute(ctx, {"operation_id": "op"}, "resume")
            self.assertFalse(target.exists())

    def test_commit_rechecks_all_targets_after_individual_installation(self):
        from transaction import execute, save_journal
        from support import Blocked
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            changed = False

            def drift_after_last_install(context, journal):
                nonlocal changed
                save_journal(context, journal)
                if not changed and all(row["installed"] for row in journal["entries"]):
                    changed = True
                    ctx.path("knowledge/update.md").write_bytes(b"external")

            with patch("transaction.save_journal", side_effect=drift_after_last_install):
                with self.assertRaisesRegex(Blocked, "verification failed"):
                    execute(ctx, request)
            self.assertTrue(changed)
            self.assertEqual(ctx.read(".build/operations/op/transaction/journal.json")["status"], "recovery_required")
            self.assertFalse(ctx.path(".build/operations/op/transaction/apply-result.json").exists())
            for recovery in ("resume", "rollback"):
                with self.assertRaises(Blocked):
                    execute(ctx, {"operation_id": "op"}, recovery)
            self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"external")

    def test_recovery_reconciles_install_marker_from_actual_bytes(self):
        from transaction import execute, atomic_bytes
        from support import Blocked
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))

            def interrupt_after_write(path, raw):
                atomic_bytes(path, raw)
                if path == ctx.path("knowledge/create.md"):
                    raise OSError("synthetic interruption after replacement")

            with patch("transaction.atomic_bytes", side_effect=interrupt_after_write):
                with self.assertRaises(Blocked):
                    execute(ctx, request)
            self.assertFalse(ctx.read(".build/operations/op/transaction/journal.json")["entries"][0]["installed"])
            execute(ctx, {"operation_id": "op"}, "resume")
            self.assertTrue(all(row["installed"] for row in ctx.read(".build/operations/op/transaction/journal.json")["entries"]))

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

    def test_silent_rollback_restore_failure_never_reports_rolled_back(self):
        from transaction import execute, atomic_bytes
        from support import Blocked
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 2})
            target = ctx.path("knowledge/update.md")

            def silently_skip(path, raw):
                if path != target:
                    return atomic_bytes(path, raw)

            with patch("transaction.atomic_bytes", side_effect=silently_skip):
                with self.assertRaisesRegex(Blocked, "verification failed"):
                    execute(ctx, {"operation_id": "op"}, "rollback")
            self.assertEqual(ctx.read(".build/operations/op/transaction/journal.json")["status"], "recovery_required")
            self.assertEqual(target.read_bytes(), b"updated")
            result = execute(ctx, {"operation_id": "op"}, "rollback")
            self.assertEqual(result["transaction_status"], "rolled_back")
            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse(ctx.path("knowledge/create.md").exists())

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

    def test_document_admission_needs_no_human_adapter_or_event(self):
        from transaction import execute
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            request.pop("proof_ref")
            request.pop("content_review_ref")
            result = execute(ctx, request)
            self.assertEqual(result["transaction_status"], "committed")
            self.assertNotIn("review_trust", ctx.catalog)
            self.assertFalse(ctx.path("logs/host-events").exists())
            journal = ctx.read(".build/operations/op/transaction/journal.json")
            self.assertNotIn("proof_ref", journal)
            self.assertNotIn("content_review_ref", journal)

    def test_optional_review_identity_is_not_an_apply_gate(self):
        from transaction import execute
        from support import canonical, seal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            proof = ctx.read(request["proof_ref"])
            proof["reviewer_id"] = proof["author_id"]
            ctx.path(request["proof_ref"]).write_bytes(canonical(seal(proof)))
            self.assertEqual(execute(ctx, request)["transaction_status"], "committed")
            result = ctx.read(".build/operations/op/transaction/apply-result.json")
            self.assertEqual(result["verification_tier"], "transaction_bytes_only")

    def test_optional_review_status_does_not_certify_apply(self):
        from transaction import execute
        from support import canonical, seal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            proof = ctx.read(request["proof_ref"])
            proof.update(record_kind="manual_review", status="approved")
            ctx.path(request["proof_ref"]).write_bytes(canonical(seal(proof)))
            self.assertEqual(execute(ctx, request)["transaction_status"], "committed")
            result = ctx.read(".build/operations/op/transaction/apply-result.json")
            self.assertEqual(result["verification_tier"], "transaction_bytes_only")

    def test_changed_document_view_invalidates_review(self):
        from transaction import execute
        from support import Invalid, canonical, seal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            proof = ctx.read(request["proof_ref"])
            proof["view_digest"] = "f" * 64
            ctx.path(request["proof_ref"]).write_bytes(canonical(seal(proof)))
            with self.assertRaises(Invalid):
                execute(ctx, request)
            self.assertFalse(ctx.path("knowledge/create.md").exists())

    def test_unused_workflow_proof_set_is_not_an_apply_gate(self):
        from transaction import execute
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            self.assertEqual(execute(ctx, {**request, "proof_set": {}})["transaction_status"], "committed")

    def test_optional_review_does_not_require_plan_author_chain(self):
        from transaction_v3 import validate_content_review
        from support import seal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            view = ctx.read(request["view_ref"])
            plan = ctx.record("semantic_plan", "op", author_id="fixture-author", scan_digest="a" * 64,
                              card_actions=[{"author_id": "second-author"}])
            ctx.save(".build/operations/op/semantic-plan.json", plan)
            view = seal({**view, "semantic_plan_ref": ".build/operations/op/semantic-plan.json",
                         "semantic_plan_digest": plan["digest"]})
            review = ctx.record("content_review", "op", status="passed", view_digest=view["digest"],
                                author_id="fixture-author", reviewer_id="second-author",
                                independent_context="separate", findings=[], plan_digest=plan["digest"],
                                semantic_plan_ref=view["semantic_plan_ref"], scan_digest=plan["scan_digest"])
            self.assertEqual(validate_content_review(ctx, view, review), review)

    def mixed_fixture(self, root):
        from support import canonical, seal
        ctx, request = self.fixture(root)
        view = seal({**ctx.read(request["view_ref"]), "review_mode": "mixed"})
        ctx.path(request["view_ref"]).write_bytes(canonical(view))
        review = seal({**ctx.read(request["content_review_ref"]), "view_digest": view["digest"]})
        ctx.path(request["content_review_ref"]).write_bytes(canonical(review))
        proof = ctx.record("local_check", "op", status="passed", mode="local", view_digest=view["digest"],
                           claims=[{"status": "supported", "evidence": ["fixture-code"]}])
        ctx.save("logs/operations/op/code-proof.json", proof)
        return ctx, {**request, "proof_ref": "logs/operations/op/code-proof.json"}

    def test_mixed_view_does_not_require_a_separate_full_view_review_gate(self):
        from transaction import execute
        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.mixed_fixture(pathlib.Path(tmp))
            request.pop("content_review_ref")
            self.assertEqual(execute(ctx, request)["transaction_status"], "committed")

    def test_safe_recovery_does_not_depend_on_optional_upstream_reports(self):
        from transaction import execute
        from support import Blocked
        for action in ("resume", "rollback"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                ctx, request = self.mixed_fixture(pathlib.Path(tmp))
                with self.assertRaises(Blocked):
                    execute(ctx, {**request, "fault_after": 1})
                journal = ctx.read(".build/operations/op/transaction/journal.json")
                captured = (journal["proof_digest"], journal["content_review_digest"])
                self.assertEqual(journal["content_review_ref"], request["content_review_ref"])
                ctx.path(request["content_review_ref"]).write_bytes(b"corrupt optional review")
                ctx.path(request["proof_ref"]).unlink()
                result = execute(ctx, {"operation_id": "op"}, action)
                self.assertEqual(result["transaction_status"], "committed" if action == "resume" else "rolled_back")
                saved = ctx.read(".build/operations/op/transaction/journal.json")
                self.assertEqual((saved["proof_digest"], saved["content_review_digest"]), captured)
                self.assertEqual(ctx.path("knowledge/update.md").read_bytes(), b"updated" if action == "resume" else b"old")

    def test_resealed_journal_cannot_authorize_raw_writes(self):
        from transaction import execute
        from support import Blocked, Invalid, canonical, seal

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp))
            with self.assertRaises(Blocked):
                execute(ctx, {**request, "fault_after": 1}, "run")
            journal = ctx.read(".build/operations/op/transaction/journal.json")
            journal["entries"][0]["path"] = "docs-raw/specs/original.md"
            ctx.path(".build/operations/op/transaction/journal.json").write_bytes(
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
