# ruff: noqa: E402 - isolate dependency search before importing non-builtin modules.
"""Repository Knowledge entry: execute only the manifest-verified runtime bytes."""

import sys


# A repository is a data location, not a dependency search path. Restrict the
# initial stdlib imports before pathlib/hashlib/yaml can see adjacent files.
def _normalized_boot_path(value):
    value = value.replace("\\", "/").rstrip("/")
    return value.casefold() if sys.platform == "win32" else value


_initial_paths = list(sys.path)
_python_prefixes = tuple(_normalized_boot_path(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix} if p)


def _python_path(value):
    value = _normalized_boot_path(value)
    return any(value == prefix or value.startswith(prefix + "/") for prefix in _python_prefixes)


sys.path[:] = [p for p in _initial_paths if p and _python_path(p)]
import os as _bootstrap_os  # noqa: E402 - load stdlib before admitting execution-host site packages

_entry_directory = _bootstrap_os.path.realpath(_bootstrap_os.path.dirname(__file__))
_blocked_paths = {_bootstrap_os.path.realpath(_bootstrap_os.getcwd()), _entry_directory}
_blocked_paths.update(_bootstrap_os.path.realpath(p) for p in _bootstrap_os.environ.get("PYTHONPATH", "").split(_bootstrap_os.pathsep) if p)
if _initial_paths and _initial_paths[0]:
    _blocked_paths.add(_bootstrap_os.path.realpath(_initial_paths[0]))
_blocked_paths = {_normalized_boot_path(p) for p in _blocked_paths}
_entry_prefix = _normalized_boot_path(_entry_directory)
sys.path[:] = [p for p in _initial_paths if p and (
    _python_path(p) or (
        _normalized_boot_path(_bootstrap_os.path.realpath(p)) not in _blocked_paths
        and not _normalized_boot_path(_bootstrap_os.path.realpath(p)).startswith(_entry_prefix + "/")
    )
)]

import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path, PurePosixPath
import secrets
import tempfile


sys.dont_write_bytecode = True
sys.pycache_prefix = str(Path(tempfile.gettempdir()) / ("knowledge-no-cache-" + secrets.token_hex(16)))
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest field: " + key)
        result[key] = value
    return result


def _file(root, reference):
    if not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference:
        raise ValueError("Invalid runtime path")
    parts = PurePosixPath(reference).parts
    if reference.startswith("/") or "/".join(parts) != reference or any(p in {".", ".."} for p in parts):
        raise ValueError("Invalid runtime path: " + reference)
    path = root
    for part in parts:
        path /= part
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked runtime path: " + reference)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Runtime file unavailable: " + reference)
    return path


def verified_runtime(root):
    runtime = root / "runtime"
    manifest_path = _file(root, "runtime/manifest.json")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_object)
    if manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("version"), str):
        raise ValueError("Unsupported runtime manifest")
    verified = {}
    for category, base in (("entrypoints", root), ("files", runtime)):
        rows = manifest.get(category)
        if not isinstance(rows, dict) or not rows:
            raise ValueError("Incomplete runtime manifest: " + category)
        for reference, row in rows.items():
            if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
                raise ValueError("Invalid runtime manifest row")
            data = _file(base, reference).read_bytes()
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("Runtime digest mismatch: " + reference)
            if category == "files":
                verified[reference] = data
    if not {"knowledge.py", "knowledge.cmd", "knowledge.sh"}.issubset(manifest["entrypoints"]):
        raise ValueError("Runtime entrypoints are incomplete")
    if not {"requirements.lock.txt", "himate_knowledge/__init__.py", "himate_knowledge/cli.py"}.issubset(verified):
        raise ValueError("Runtime implementation is incomplete")
    if manifest_path.read_bytes() != raw:
        raise ValueError("Runtime manifest changed while loading")
    return manifest, verified


class _VerifiedRuntime(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, root, verified):
        self.root, self.verified = root / "runtime", verified

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "himate_knowledge" and not fullname.startswith("himate_knowledge."):
            return None
        reference = fullname.replace(".", "/")
        package = reference + "/__init__.py" in self.verified
        reference += "/__init__.py" if package else ".py"
        if reference not in self.verified:
            raise ImportError("Runtime module is not in its manifest: " + fullname)
        spec = importlib.util.spec_from_loader(fullname, self, is_package=package)
        spec.loader_state = reference
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        reference = module.__spec__.loader_state
        module.__file__ = str(self.root / reference)
        if module.__spec__.submodule_search_locations is not None:
            module.__path__ = []
        exec(compile(self.verified[reference], module.__file__, "exec"), module.__dict__)


def _failure(error):
    value = {"schema_version": "2.0", "record_kind": "result", "status": "error",
             "phase": "invalid", "data": {},
             "diagnostics": [{"code": "RUNTIME_UNAVAILABLE", "message": str(error)}]}
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True)
    # An unverified runtime has no authority to choose a file output policy.
    # Its diagnostic is read-only stdout, including when --output was supplied.
    print(raw)
    return 2


def main():
    root = Path(__file__).resolve().parent
    try:
        if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
            raise ValueError("Knowledge requires Python 3.10, 3.11 or 3.12")
        manifest, verified = verified_runtime(root)
        loader = _VerifiedRuntime(root, verified)
        sys.meta_path.insert(0, loader)
        try:
            import himate_knowledge
            himate_knowledge._runtime_root = root / "runtime"
            himate_knowledge._runtime_files_snapshot = {
                reference: hashlib.sha256(raw).hexdigest() for reference, raw in verified.items()
            }
            from himate_knowledge.cli import main as cli_main
            return cli_main(knowledge_root=root, manifest=manifest)
        finally:
            sys.meta_path.remove(loader)
    except Exception as error:
        return _failure(error)


if __name__ == "__main__":
    raise SystemExit(main())
