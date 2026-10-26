"""Public-CLI recovery delegation tests; no private transaction imports."""

import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))


class RecoverTests(unittest.TestCase):
    def test_long_existing_attempt_input_is_preserved_before_delegation(self):
        from recover import recover
        from support import Blocked, Context, atomic_bytes, native_path, package_digest

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            prefix = "knowledge-"
            root = base / (prefix + "k" * (130 - len(str(base / prefix))))
            root.mkdir()
            ctx = Context.synthetic(root, "hs-knowledge-recover")
            package = base / "installed/hs-knowledge-apply"
            package.joinpath("scripts").mkdir(parents=True)
            package.joinpath("scripts/cli.py").write_text(
                "raise AssertionError('immutable input must be checked before delegation')", encoding="utf-8"
            )
            ctx.catalog = {"skills": {"hs-knowledge-apply": {
                "root": str(package), "entry": "scripts/cli.py", "python": sys.executable,
                "package_digest": package_digest(package),
            }}}
            ctx.catalog_path = str(base / "catalog.json")
            base.joinpath("catalog.json").write_text("{}", encoding="utf-8")
            operation = "operation-" + "x" * 70
            request_ref = f".build/operations/{operation}/recover-inspect-standalone-request.json"
            path = ctx.path(request_ref)
            self.assertGreater(len(str(path)), 260)
            original = b"pre-existing immutable attempt with different input\n"
            atomic_bytes(path, original)

            try:
                with self.assertRaisesRegex(Blocked, "recovery attempt input changed"):
                    recover(ctx, {"operation_id": operation}, "inspect")
                self.assertEqual(pathlib.Path(native_path(path)).read_bytes(), original)
            finally:
                self.assertTrue(root.resolve().is_relative_to(base.resolve()))
                self.assertNotEqual(root.resolve(), base.resolve())
                shutil.rmtree(native_path(root))

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
            entry.write_text(
                "raise AssertionError('must not execute')", encoding="utf-8"
            )
            ctx.catalog = {
                "skills": {
                    "hs-knowledge-apply": {
                        "root": str(package),
                        "entry": "scripts/cli.py",
                        "python": sys.executable,
                        "package_digest": package_digest(package),
                    }
                }
            }
            entry.write_text("raise AssertionError('changed')", encoding="utf-8")
            with self.assertRaises(Invalid):
                recover(ctx, {"operation_id": "op"}, "rollback")


if __name__ == "__main__":
    unittest.main()
