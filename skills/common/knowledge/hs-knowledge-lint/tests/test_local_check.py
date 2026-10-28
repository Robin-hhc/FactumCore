"""Code gates never turn missing inputs or zero findings into support."""

import pathlib
import tempfile
import unittest
from unittest.mock import patch

import importlib.util as _fixture_importlib
from pathlib import Path as _FixturePath
_fixture_root = _FixturePath(__file__).resolve().parents[5]
_fixture_spec = _fixture_importlib.spec_from_file_location("lint_contract_fixture", _fixture_root / "himate-knowledge-wifi-mp/evals/contract_test_support.py")
_fixture_lib = _fixture_importlib.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_lib)
legacy = _fixture_lib.module("legacy_runtime")
engine = _fixture_lib.module("code_review")



class LocalCheckTests(unittest.TestCase):
    def view(self, ctx, mode):
        digest = legacy.digest

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
        local_check = engine.local_check
        Context = legacy.Context

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-lint")
            result = local_check(ctx, self.view(ctx, "code_gate"), "run")
            proof = ctx.read(result["local_check_ref"])
            self.assertEqual(proof["status"], "incomplete")
            self.assertFalse(result.get("proof_verified", False))

    def test_pure_document_rejects_code_gate(self):
        local_check = engine.local_check
        Context, Invalid = legacy.Context, legacy.Invalid

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-lint")
            with self.assertRaises(Invalid):
                local_check(ctx, self.view(ctx, "manual_document"), "run")

    def test_object_read_disables_partial_clone_lazy_fetch(self):
        git_read = engine.git_read
        import subprocess

        with patch.object(engine.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout=b"fixture")
            self.assertEqual(
                git_read(pathlib.Path("."), ["cat-file", "blob", "HEAD:source"]),
                b"fixture",
            )
            self.assertEqual(run.call_args.kwargs["env"].get("GIT_NO_LAZY_FETCH"), "1")


if __name__ == "__main__":
    unittest.main()
