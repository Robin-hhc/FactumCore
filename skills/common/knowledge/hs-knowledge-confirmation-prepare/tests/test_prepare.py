"""Synthetic protocol tests; no real host acceptance is claimed."""

import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class PrepareTests(unittest.TestCase):
    def test_exact_display_and_fresh_challenge(self):
        from support import Context, digest, seal
        from prepare import prepare

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            ctx = Context.synthetic(root, "hs-knowledge-confirmation-prepare")
            view = seal(
                {
                    "schema_version": "2.0",
                    "record_kind": "final_view",
                    "operation_id": "op1",
                    "rules_digest": ctx.rules_digest,
                    "tool_identity": ctx.identity,
                    "review_mode": "manual_document",
                    "source_refs": [],
                    "writes": [
                        {
                            "path": "knowledge/a.md",
                            "expected_old_digest": None,
                            "final_digest": digest(b"new"),
                            "bytes_b64": "bmV3",
                        }
                    ],
                    "deletes": [],
                }
            )
            ctx.save(".build/operations/op1/view.json", view)
            result = prepare(
                ctx,
                {"operation_id": "op1", "view_ref": ".build/operations/op1/view.json"},
            )
            display = ctx.read(result["display_ref"])
            self.assertEqual(display["view_digest"], view["digest"])
            self.assertEqual(display["writes"], view["writes"])
            self.assertGreaterEqual(len(display["challenge"]), 40)
            self.assertEqual(
                prepare(
                    ctx,
                    {
                        "operation_id": "op1",
                        "view_ref": ".build/operations/op1/view.json",
                    },
                ),
                result,
            )

    def test_code_view_is_not_manual(self):
        from support import Context, seal, Blocked
        from prepare import prepare

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(
                pathlib.Path(tmp), "hs-knowledge-confirmation-prepare"
            )
            ctx.save(
                ".build/operations/op/view.json",
                seal(
                    {
                        "schema_version": "2.0",
                        "record_kind": "final_view",
                        "operation_id": "op",
                        "rules_digest": ctx.rules_digest,
                        "tool_identity": ctx.identity,
                        "review_mode": "code_gate",
                        "writes": [
                            {
                                "path": "knowledge/a.md",
                                "expected_old_digest": None,
                                "final_digest": "11507a0e2f5e69d5dfa40a62a1bd7b6ee57e6bcd85c67c9b8431b36fff21c437",
                                "bytes_b64": "bmV3",
                            }
                        ],
                        "deletes": [],
                    }
                ),
            )
            with self.assertRaises(Blocked):
                prepare(
                    ctx,
                    {
                        "operation_id": "op",
                        "view_ref": ".build/operations/op/view.json",
                    },
                )


if __name__ == "__main__":
    unittest.main()
