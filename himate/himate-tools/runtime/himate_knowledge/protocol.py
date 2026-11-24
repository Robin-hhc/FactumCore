"""Verify executable rules and return small command responses."""

from __future__ import annotations

import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import re
import stat
import sys


RULE_ROOT = "runtime/governance"
RULE_CONTRACT_PREFIX = RULE_ROOT + "/contracts/"
RULE_SCHEMA_PREFIX = RULE_ROOT + "/schemas/"
FRAMEWORK_LOCK = RULE_ROOT + "/framework.lock.yaml"
RULE_SUBTREES = tuple(RULE_ROOT + "/" + name for name in ("contracts", "schemas", "specs", "templates"))
# Include transitive dependencies of the public CLI actions: verification
# must catch a missing registration before starting a business command.
REQUIRED_RULE_FILES = {
    RULE_CONTRACT_PREFIX + name + ".py"
    for name in ("__init__", "cards_v3", "catalog", "citation_versions", "document_parser", "indexing",
                 "ingest", "intake", "knowledge", "library", "maintenance", "markdown_images", "panel", "pdf_pictures",
                 "pdf_text", "raw_materials", "runtime", "source_read", "source_resources", "staging",
                 "validation", "workspace_config")
} | {
    RULE_SCHEMA_PREFIX + name
    for name in ("profiles.yaml", "registries.yaml", "workspace.schema.json", "frontmatter.schema.json",
                 "sources.schema.json", "records.schema.json")
}


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
        pairs = [(loader.construct_object(key, deep=deep), loader.construct_object(value, deep=deep))
                 for key, value in node.value]
        if any(not isinstance(key, str) for key, _ in pairs):
            raise NodeError("INVALID_INPUT", "Expected string mapping keys")
        return unique(pairs)

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


def relative_to_existing_root(path, root):
    """Recognize an existing root even through filesystem aliases such as WSL/DrvFS case."""
    if path.is_relative_to(root):
        return path.relative_to(root)
    for candidate in (path, *path.parents):
        try:
            if candidate.samefile(root):
                return path.relative_to(candidate)
        except (FileNotFoundError, NotADirectoryError):
            continue
    return None


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


def read_regular_bytes(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (
            os.path.lexists(part) and getattr(part.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Linked metadata path is not allowed")
    if not path.is_file():
        raise ValueError("Metadata file is missing or unreadable")
    return path.read_bytes()


@dataclass
class RuleVerification:
    report: dict
    lock_bytes: bytes | None = None
    lock: dict | None = None
    files: dict[str, bytes] = field(default_factory=dict)


def verify_rule_files(tool_root, manifest_digest, *, expected=None, yaml_available=True):
    """Validate the rule lock and capture its bytes without executing any rules."""
    path = tool_root / FRAMEWORK_LOCK
    gaps = []
    report = {"path": str(path), "status": "not_checked", "digest": None,
              "schema_version": None, "contract_family": None, "tool_version": None,
              "files_registered": 0, "files_verified": 0, "gaps": gaps}
    result = RuleVerification(report)

    def gap(code, message, target):
        report["status"] = "blocked"
        gaps.append({"code": code, "message": str(message), "path": str(target),
                     "next_step": "Restore the matching governance framework and lock on this execution host"})

    try:
        result.lock_bytes = read_regular_bytes(safe(tool_root, FRAMEWORK_LOCK))
    except (OSError, ValueError) as error:
        gap("RULE_LOCK_UNAVAILABLE", error, path)
        return result
    report["digest"] = sha(result.lock_bytes)
    if report["digest"] != manifest_digest:
        gap("RULE_LOCK_DIGEST_MISMATCH", "Framework lock differs from the installed runtime manifest", path)
        return result
    if expected is not None and report["digest"] != expected:
        gap("RULES_DIGEST_MISMATCH", "Pinned framework-lock bytes differ", path)
        return result
    if not yaml_available:
        return result
    try:
        result.lock = load_yaml(result.lock_bytes)
    except Exception as error:
        gap("RULE_LOCK_INVALID", "Cannot parse framework lock: " + str(error), path)
        return result

    lock = result.lock
    for key in ("schema_version", "contract_family", "tool_version"):
        value = lock.get(key)
        report[key] = value if isinstance(value, str) else None
    if (report["schema_version"] != "2.0" or report["contract_family"] != "aiot-wifi"
            or not (report["tool_version"] or "").strip()):
        gap("RULE_CONTRACT_UNSUPPORTED", "Expected aiot-wifi contract 2.0 and an explicit tool version", path)
    capabilities = lock.get("capabilities")
    if (not isinstance(capabilities, dict)
            or any(capabilities.get(name) != "1.0" for name in ("checks", "indexing", "ingest_records"))
            or any(capabilities.get(name) not in (None, "1.0") for name in
                   ("workspace_mapping", "code_navigation", "incremental_patrol", "local_dbox"))):
        gap("RULE_CAPABILITY_UNSUPPORTED", "Required rule capabilities are absent or incompatible", path)

    files = lock.get("files")
    if not isinstance(files, dict) or not files:
        gap("RULE_LOCK_INCOMPLETE", "Framework lock has no registered rule files", path)
        return result
    report["files_registered"] = len(files)
    seen = set()
    for row in files.values():
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                or row["path"] in seen):
            gap("RULE_LOCK_INVALID", "Invalid or duplicate registered rule entry", path)
            continue
        reference = row["path"]
        seen.add(reference)
        try:
            target = safe(tool_root, reference, RULE_SUBTREES)
        except (OSError, ValueError) as error:
            gap("RULE_LOCK_INVALID", error, reference)
            continue
        try:
            content = read_regular_bytes(target)
        except (OSError, ValueError) as error:
            gap("RULE_FILE_UNAVAILABLE", error, target)
            continue
        if sha(content) != row["sha256"]:
            gap("RULE_FILE_DIGEST_MISMATCH", "Rule bytes differ from the registered digest", target)
            continue
        result.files[reference] = content
    report["files_verified"] = len(result.files)
    required = REQUIRED_RULE_FILES
    if isinstance(capabilities, dict) and capabilities.get("code_navigation") == "1.0":
        required = required | {RULE_CONTRACT_PREFIX + "code_symbols.py"}
    if required - seen:
        gap("RULE_LOCK_INCOMPLETE", "Required rules are not registered: " + ", ".join(sorted(required - seen)), path)
    try:
        if read_regular_bytes(safe(tool_root, FRAMEWORK_LOCK)) != result.lock_bytes:
            gap("RULE_LOCK_CHANGED", "Framework lock changed during verification", path)
    except (OSError, ValueError) as error:
        gap("RULE_LOCK_CHANGED", error, path)
    if not gaps:
        report["status"] = "verified"
    return result


def domain(tool_root, knowledge_root, manifest_digest, expected=None):
    result = verify_rule_files(tool_root, manifest_digest, expected=expected)
    if result.report["gaps"]:
        error = result.report["gaps"][0]
        raise NodeError(error["code"], error["message"], error["path"])
    verified = result.files
    actual = result.report["digest"]
    contract_names = tuple(sorted(ref[len(RULE_CONTRACT_PREFIX):-3] for ref in verified
                                  if ref.startswith(RULE_CONTRACT_PREFIX) and ref.endswith(".py")
                                  and "/" not in ref[len(RULE_CONTRACT_PREFIX):]
                                  and not ref.endswith("/__init__.py")))
    namespace = "_hs_domain_" + actual
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
                    compile(verified[self.ref], str(tool_root / self.ref), "exec"),
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
                ref = RULE_CONTRACT_PREFIX + name.replace(".", "/") + ".py"
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
    rules = modules["validation"].load_rules(knowledge_root, result.lock, actual, verified)
    for ref, data in verified.items():
        if read_regular_bytes(safe(tool_root, ref, RULE_SUBTREES)) != data:
            raise NodeError("RULES_CHANGED", "Rules changed while loading", ref)
    if read_regular_bytes(safe(tool_root, FRAMEWORK_LOCK)) != result.lock_bytes:
        raise NodeError("RULE_LOCK_CHANGED", "Framework lock changed while loading", tool_root / FRAMEWORK_LOCK)
    return modules, rules
