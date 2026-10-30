"""Verify executable rules and return small command responses."""

from __future__ import annotations

import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

class NodeError(ValueError):
    def __init__(self, code, message, path="", *, blocked=False):
        super().__init__(message)
        self.code, self.message, self.path, self.blocked = (
            code,
            message,
            str(path),
            blocked,
        )


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(canonical(value))


def envelope(status, phase, data=None, diagnostics=None):
    """One CLI response, without persisted stage or operation identities."""
    return {"schema_version": "2.0", "record_kind": "result", "status": status,
            "phase": phase, "data": data or {}, "diagnostics": diagnostics or []}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NodeError("DUPLICATE_KEY", "Duplicate object key", key)
        result[key] = value
    return result


def load_yaml(data):
    import yaml

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        return unique([(loader.construct_object(key, deep=deep), loader.construct_object(value, deep=deep))
                       for key, value in node.value])

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    value = yaml.load(data.decode("utf-8-sig"), Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise NodeError("INVALID_INPUT", "Expected a YAML object")
    canonical(value)
    return value


def native_path(path):
    text = os.path.abspath(path)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
    return text


def safe(root, relative, prefixes=None):
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or ":" in relative
    ):
        raise NodeError("UNSAFE_PATH", "Expected a relative POSIX path", relative)
    parts = PurePosixPath(relative).parts
    if (
        relative.startswith("/")
        or not parts
        or any(p in {".", ".."} for p in parts)
        or str(PurePosixPath(relative)) != relative
    ):
        raise NodeError("UNSAFE_PATH", "Path traversal or alias", relative)
    if prefixes and not any(
        relative == p.rstrip("/") or relative.startswith(p.rstrip("/") + "/")
        for p in prefixes
    ):
        raise NodeError("UNSAFE_PATH", "Path is outside permitted subtrees", relative)
    root = Path(root).resolve(strict=True)
    current = root
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    for part in parts:
        if (
            part.rstrip(" .") != part
            or part.split(".")[0].upper() in reserved
            or any(ord(c) < 32 or c in '<>"|?*' for c in part)
        ):
            raise NodeError(
                "UNSAFE_PATH", "Reserved or nonportable path component", relative
            )
        if current.exists() and current.is_dir():
            aliases = [
                p.name
                for p in Path(native_path(current)).iterdir()
                if p.name.casefold() == part.casefold()
            ]
            if aliases and part not in aliases:
                raise NodeError(
                    "CASE_ALIAS", "Existing path uses different case", relative
                )
        current = current / part
        if current.is_symlink() or (
            os.path.lexists(current)
            and getattr(current.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise NodeError("UNSAFE_PATH", "Linked path is not permitted", relative)
        if not current.resolve().is_relative_to(root):
            raise NodeError("UNSAFE_PATH", "Path escaped knowledge root", relative)
    return current


def domain(root, expected):
    lock_path = safe(root, "governance/framework.lock.yaml")
    lock_bytes = lock_path.read_bytes()
    if not re.fullmatch("[0-9a-f]{64}", expected or "") or sha(lock_bytes) != expected:
        raise NodeError("RULES_DIGEST_MISMATCH", "Pinned framework-lock bytes differ")
    lock = load_yaml(lock_bytes)
    if lock.get("schema_version") != "2.0":
        raise NodeError("INCOMPATIBLE_RULES", "Node Skills require contract 2.0")
    verified = {}
    for entry in lock.get("files", {}).values():
        path = safe(root, entry["path"])
        data = path.read_bytes()
        if sha(data) != entry["sha256"]:
            raise NodeError(
                "RULE_DIGEST_MISMATCH", "Rule file differs from lock", entry["path"]
            )
        verified[entry["path"]] = data
    for name in (
        "__init__.py",
        "validation.py",
        "knowledge.py",
        "source_resources.py",
        "indexing.py",
        "catalog.py",
        "cards_v3.py",
        "ingest.py",
        "library.py",
    ):
        if "governance/contracts/" + name not in verified:
            raise NodeError(
                "UNPINNED_DOMAIN_CODE", "Domain program is not digest-locked", name
            )
    contract_names = tuple(sorted(ref[len("governance/contracts/"):-3] for ref in verified
                                  if ref.startswith("governance/contracts/") and ref.endswith(".py")
                                  and "/" not in ref[len("governance/contracts/"):]
                                  and not ref.endswith("/__init__.py")))
    namespace = "_hs_domain_" + expected
    if namespace not in sys.modules:

        class PinnedLoader(importlib.abc.Loader):
            def __init__(self, ref):
                self.ref = ref

            def create_module(self, spec):
                return None

            def exec_module(self, module):
                # Compile the exact verified source. Never trust timestamp-valid cached pyc.
                if module.__name__ == namespace:
                    module.__path__ = []
                exec(
                    compile(verified[self.ref], str(root / self.ref), "exec"),
                    module.__dict__,
                )

        class PinnedFinder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname != namespace and not fullname.startswith(namespace + "."):
                    return None
                name = (
                    "__init__"
                    if fullname == namespace
                    else fullname[len(namespace) + 1 :]
                )
                ref = "governance/contracts/" + name.replace(".", "/") + ".py"
                if ref not in verified:
                    raise ImportError("Unpinned domain module: " + fullname)
                return importlib.util.spec_from_loader(
                    fullname, PinnedLoader(ref), is_package=fullname == namespace
                )

        finder = PinnedFinder()
        sys.meta_path.insert(0, finder)
        try:
            importlib.import_module(namespace)
            for name in contract_names:
                importlib.import_module(namespace + "." + name)
        finally:
            sys.meta_path.remove(finder)
    modules = {
        name: sys.modules[namespace + "." + name]
        for name in contract_names
    }
    rules = modules["validation"].load_rules(root, expected)
    for ref, data in verified.items():
        if safe(root, ref).read_bytes() != data:
            raise NodeError("RULES_CHANGED", "Rules changed while loading", ref)
    return modules, rules
