"""Public recovery delegation uses sibling Skills and the current interpreter."""

import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class RecoverTests(unittest.TestCase):
    def test_manual_recovery_ignores_workflow_and_preserves_existing_records(self):
        import recover as module
        from support import Context, atomic_bytes, canonical, native_path

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            root = base / ("knowledge-" + "k" * max(1, 130 - len(str(base / "knowledge-"))))
            root.mkdir()
            ctx = Context.synthetic(root, "hs-knowledge-recover")
            package = base / "skills/hs-knowledge-apply"
            package.joinpath("scripts").mkdir(parents=True)
            package.joinpath("scripts/cli.py").write_text("# installed entry", encoding="utf-8")
            operation = "operation-" + "x" * 70
            old = ctx.path(f".build/operations/{operation}/recover-inspect-standalone-request.json")
            original = b"earlier manual attempt\n"
            atomic_bytes(old, original)
            calls = []

            def execute(command, **kwargs):
                calls.append(command)
                output = pathlib.Path(command[command.index("--output") + 1])
                result = ctx.record("result", operation, tool_identity={"skill": "hs-knowledge-apply"},
                                    status="ok", phase="inspected", data={"transaction_status": "absent"}, diagnostics=[])
                atomic_bytes(output, canonical(result))
                return type("Completed", (), {"returncode": 0})()

            try:
                with patch.object(module, "__file__", str(base / "skills/hs-knowledge-recover/scripts/recover.py")), \
                        patch.object(module.subprocess, "run", execute):
                    result = module.recover(ctx, {"operation_id": operation, "workflow": "owned by harness"}, "inspect")
                self.assertEqual(calls[0][0], sys.executable)
                self.assertNotIn("--catalog", calls[0])
                self.assertEqual(result["transaction_status"], "absent")
                self.assertEqual(pathlib.Path(native_path(old)).read_bytes(), original)
                self.assertFalse((root / "logs/workflows").exists())
            finally:
                self.assertTrue(root.resolve().is_relative_to(base.resolve()))
                shutil.rmtree(native_path(root))

    def test_missing_installed_apply_is_blocked_without_catalog_requirement(self):
        import recover as module
        from support import Blocked, Context

        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-recover")
            with patch.object(module, "__file__", str(pathlib.Path(tmp) / "skills/hs-knowledge-recover/scripts/recover.py")):
                with self.assertRaisesRegex(Blocked, "installed apply Skill is unavailable"):
                    module.recover(ctx, {"operation_id": "op"}, "inspect")


if __name__ == "__main__":
    unittest.main()
