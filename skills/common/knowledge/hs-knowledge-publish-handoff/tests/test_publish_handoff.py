import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class PublishTests(unittest.TestCase):
    def test_manual_view_is_checked_directly_without_apply_or_query_receipts(self):
        from publish import publish_handoff
        from support import Context, atomic_bytes, digest

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            ctx = Context.synthetic(root, "hs-knowledge-publish-handoff")
            content = b"exact selected contents\n"
            atomic_bytes(ctx.path("knowledge/card.md"), content)
            ctx.save(".build/operations/op/view.json", ctx.record(
                "final_view", "op", review_mode="manual_document", v3_required=True,
                writes=[{"path": "knowledge/card.md", "final_digest": digest(content),
                         "bytes_b64": "ZXhhY3Qgc2VsZWN0ZWQgY29udGVudHMK", "expected_old_digest": None}], deletes=[]))
            result = publish_handoff(ctx, {"operation_id": "op", "view_ref": ".build/operations/op/view.json"})
            self.assertEqual(result["commit_files"], ["knowledge/card.md"])
            handoff = ctx.read(result["publish_handoff_ref"])
            self.assertFalse(handoff["remote_push_verified"])
            self.assertFalse(handoff["git_merge_verified"])
            self.assertNotIn("apply_result_ref", handoff)
            self.assertNotIn("query_report_ref", handoff)

    def test_changed_selected_bytes_are_still_rejected(self):
        from publish import publish_handoff
        from support import Blocked, Context, atomic_bytes, digest

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-publish-handoff")
            atomic_bytes(ctx.path("knowledge/card.md"), b"changed\n")
            ctx.save(".build/operations/op/view.json", ctx.record(
                "final_view", "op", review_mode="manual_document",
                writes=[{"path": "knowledge/card.md", "final_digest": digest(b"new"),
                         "bytes_b64": "bmV3", "expected_old_digest": None}], deletes=[]))
            with self.assertRaisesRegex(Blocked, "differs from the selected final bytes"):
                publish_handoff(ctx, {"operation_id": "op", "view_ref": ".build/operations/op/view.json"})

    def test_agent_record_alone_cannot_claim_published(self):
        from publish import publish_handoff
        from support import Context, Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-publish-handoff")
            record = ctx.record(
                "apply_result", "op", status="committed", view_digest="a" * 64
            )
            ctx.save("logs/operations/op/apply-result.json", record)
            with self.assertRaises(Blocked):
                publish_handoff(
                    ctx,
                    {
                        "operation_id": "op",
                        "apply_result_ref": "logs/operations/op/apply-result.json",
                    },
                )


if __name__ == "__main__":
    unittest.main()
