"""Public-CLI recovery delegation tests; no private transaction imports."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class RecoverTests(unittest.TestCase):
    def test_missing_installed_apply_is_blocked(self):
        from recover import recover
        from support import Blocked, Context
        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context.synthetic(pathlib.Path(tmp), "hs-knowledge-recover")
            with self.assertRaises(Blocked):
                recover(ctx, {"operation_id": "op"}, "inspect")

    def test_package_change_is_rejected_before_process_start(self):
        from recover import recover
        from support import Invalid, Context, package_digest
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            ctx = Context.synthetic(root, "hs-knowledge-recover")
            package = root / "installed/hs-knowledge-apply"
            package.joinpath("scripts").mkdir(parents=True)
            entry = package / "scripts/cli.py"
            entry.write_text("raise AssertionError('must not execute')", encoding="utf-8")
            ctx.catalog = {"skills": {"hs-knowledge-apply": {"root": str(package), "entry": "scripts/cli.py", "python": sys.executable, "package_digest": package_digest(package)}}}
            entry.write_text("raise AssertionError('changed')", encoding="utf-8")
            with self.assertRaises(Invalid):
                recover(ctx, {"operation_id": "op"}, "rollback")


if __name__ == "__main__":
    unittest.main()
