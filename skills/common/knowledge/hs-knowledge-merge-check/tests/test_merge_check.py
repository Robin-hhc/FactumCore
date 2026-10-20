import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class MergeCheckTests(unittest.TestCase):
    def fixture(self, root, review_mode):
        from support import Context, digest

        ctx = Context.synthetic(root, "hs-knowledge-merge-check")
        ctx.save(
            ".build/operations/op/view.json",
            ctx.record(
                "final_view",
                "op",
                review_mode=review_mode,
                writes=[
                    {
                        "path": "knowledge/index.md",
                        "expected_old_digest": None,
                        "final_digest": digest(b"new"),
                        "bytes_b64": "bmV3",
                    }
                ],
                deletes=[],
            ),
        )
        return ctx, {"operation_id": "op", "view_ref": ".build/operations/op/view.json"}

    def test_missing_code_engine_does_not_claim_ci_pass(self):
        from merge import merge_check
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp), "code_gate")
            with self.assertRaises(Blocked):
                merge_check(ctx, request)

    def test_document_view_is_exempt(self):
        from merge import merge_check
        from support import Invalid

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp), "manual_document")
            with self.assertRaises(Invalid):
                merge_check(ctx, request)


if __name__ == "__main__":
    unittest.main()
