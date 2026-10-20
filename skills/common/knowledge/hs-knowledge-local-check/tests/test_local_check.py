"""Code gates never turn missing inputs or zero findings into support."""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class LocalCheckTests(unittest.TestCase):
    def view(self, ctx, mode):
        from support import digest

        value = ctx.record(
            "final_view",
            "op",
            review_mode=mode,
            writes=[
                {
                    "path": "knowledge/index.md",
                    "expected_old_digest": None,
                    "final_digest": digest(b"new"),
                    "bytes_b64": "bmV3",
                }
            ],
            deletes=[],
        )
        ctx.save(".build/operations/op/view.json", value)
        return {"operation_id": "op", "view_ref": ".build/operations/op/view.json"}

    def test_unknown_code_is_incomplete_not_passed(self):
        from check import local_check
        from support import Context

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-local-check")
            result = local_check(ctx, self.view(ctx, "code_gate"), "run")
            proof = ctx.read(result["local_check_ref"])
            self.assertEqual(proof["status"], "incomplete")
            self.assertFalse(result.get("proof_verified", False))

    def test_pure_document_rejects_code_gate(self):
        from check import local_check
        from support import Context, Invalid

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-local-check")
            with self.assertRaises(Invalid):
                local_check(ctx, self.view(ctx, "manual_document"), "run")


if __name__ == "__main__":
    unittest.main()
