import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        import merge as module
        from support import Blocked

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp), "code_gate")
            with patch.object(module, "__file__", str(pathlib.Path(tmp) / "skills/hs-knowledge-merge-check/scripts/merge.py")):
                with self.assertRaises(Blocked):
                    module.merge_check(ctx, request)

    def test_manual_merge_calls_business_checker_without_catalog_or_workflow_gate(self):
        import merge as module
        from support import atomic_bytes, canonical

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            ctx, request = self.fixture(base, "code_gate")
            package = base / "skills/hs-knowledge-local-check/scripts"
            package.mkdir(parents=True)
            (package / "cli.py").write_text("# installed checker", encoding="utf-8")
            atomic_bytes(ctx.path("governance/sources.lock.yaml"), b"resources: []\n")
            calls = []

            def execute(command, **kwargs):
                calls.append(command)
                view = ctx.read(request["view_ref"])
                proof = ctx.record("merge_check", "op", mode="merge", status="failed", view_digest=view["digest"], claims=[], gaps=["business failure"])
                proof_ref = ".build/operations/op/checked.json"
                ctx.save(proof_ref, proof)
                response = ctx.record("result", "op", status="ok", data={"mode": "merge", "merge_check_ref": proof_ref})
                output = pathlib.Path(command[command.index("--output") + 1])
                atomic_bytes(output, canonical(response))
                return type("Completed", (), {"returncode": 0})()

            with patch.object(module, "__file__", str(base / "skills/hs-knowledge-merge-check/scripts/merge.py")), \
                    patch.object(module.subprocess, "run", execute):
                result = module.merge_check(ctx, {**request, "workflow": "harness metadata"})
            self.assertEqual(calls[0][0], sys.executable)
            self.assertNotIn("--catalog", calls[0])
            self.assertEqual(result["check_status"], "failed")

    def test_document_view_is_exempt(self):
        from merge import merge_check
        from support import Invalid

        with tempfile.TemporaryDirectory() as tmp:
            ctx, request = self.fixture(pathlib.Path(tmp), "manual_document")
            with self.assertRaises(Invalid):
                merge_check(ctx, request)


if __name__ == "__main__":
    unittest.main()
