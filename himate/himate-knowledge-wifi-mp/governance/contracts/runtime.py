"""Shared operation data and IO. Importing never reads business files."""

from __future__ import annotations

import hashlib
import importlib
import importlib.abc
import importlib.util
import importlib.metadata
import json
import os
import platform
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath

import yaml


class NodeError(ValueError):
    def __init__(self, code, message, path="", *, blocked=False, data=None):
        super().__init__(message)
        self.data = dict(data or {})
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


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NodeError("DUPLICATE_KEY", "Duplicate object key", key)
        result[key] = value
    return result


def read_json(path):
    raw = Path(path).read_bytes()
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique,
        parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)),
    )
    if not isinstance(value, dict):
        raise NodeError("INVALID_INPUT", "Expected a JSON object", path)
    if Path(path).read_bytes() != raw:
        raise NodeError("INPUT_CHANGED", "JSON input changed while reading", path)
    return value


class UniqueLoader(yaml.SafeLoader):
    pass


def yaml_mapping(loader, node, deep=False):
    return unique(
        [
            (
                loader.construct_object(k, deep=deep),
                loader.construct_object(v, deep=deep),
            )
            for k, v in node.value
        ]
    )


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, yaml_mapping
)


def load_yaml(data):
    value = yaml.load(data.decode("utf-8-sig"), Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise NodeError("INVALID_INPUT", "Expected a YAML object")
    canonical(value)
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value
    ):
        raise NodeError("INVALID_ID", "Expected a safe identifier", value)
    return value


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


def native_path(value):
    text = str(Path(value).absolute())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return (
            "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        )
    return text


def fixed_bytes(root, ref, prefixes=None):
    path = safe(root, ref, prefixes)
    data = Path(native_path(path)).read_bytes()
    if Path(native_path(safe(root, ref, prefixes))).read_bytes() != data:
        raise NodeError("INPUT_CHANGED", "Referenced input changed", ref)
    return data


def transaction_journals(root):
    """Writer-only safety inventory, including pre-upgrade transaction journals.

    This is a write barrier, never an ingest discovery or recovery input.
    """
    root = Path(root).resolve(strict=True)
    refs = []
    for prefix, pattern in ((".build/operations", "*/transaction/journal.json"),
                            ("logs/operations", "*/journal.json")):
        directory = safe(root, prefix)
        if directory.exists():
            for path in Path(native_path(directory)).glob(pattern):
                # Build refs from known layouts, not platform extended paths.
                owner = path.parent.parent.name if prefix.startswith(".build/") else path.parent.name
                ref = prefix + "/" + owner + ("/transaction/journal.json" if prefix.startswith(".build/") else "/journal.json")
                safe(root, ref, [prefix])
                refs.append((ref, owner))
    return sorted(refs)


def _write_bytes(root, ref, data, prefixes, *, immutable=True):
    path = safe(root, ref, prefixes)
    Path(native_path(path.parent)).mkdir(parents=True, exist_ok=True)
    safe(root, ref)
    if immutable and path.exists():
        if Path(native_path(path)).read_bytes() != data:
            raise NodeError(
                "OPERATION_CONFLICT", "Immutable artifact already differs", ref
            )
        return
    fd, temporary = tempfile.mkstemp(prefix=".node-", dir=native_path(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe(root, ref)
        if immutable:
            # link is create-if-absent, unlike replace; concurrent attempts cannot overwrite.
            try:
                os.link(native_path(temporary), native_path(path))
            except FileExistsError:
                if Path(native_path(path)).read_bytes() != data:
                    raise NodeError(
                        "OPERATION_CONFLICT", "Concurrent artifact differs", ref
                    )
        else:
            os.replace(native_path(temporary), native_path(path))
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)



def write_bytes(root, ref, data, *, immutable=True):
    return _write_bytes(root, ref, data, [".build", "logs"], immutable=immutable)


def write_index_bytes(root, ref, data, *, immutable=True):
    return _write_bytes(root, ref, data, ["artifacts/indexes"], immutable=immutable)


def package_digest(root):
    root = Path(root).resolve(strict=True)
    files = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        rel = file.relative_to(root)
        if "__pycache__" in rel.parts or "tests" in rel.parts:
            continue
        if (
            rel.as_posix() == "SKILL.md"
            or rel.parts[0] in {"scripts", "references", "artifacts"}
            or (
                len(rel.parts) == 1
                and file.name.startswith("requirements")
                and file.name.endswith(".txt")
            )
        ):
            if file.is_symlink():
                raise NodeError(
                    "UNTRUSTED_PACKAGE", "Package contains a linked file", rel
                )
            files[rel.as_posix()] = sha(file.read_bytes())
    return digest(files)


def tool_identity(package):
    lock = package / "requirements.lock.txt"
    return {
        "skill": package.name,
        "package_digest": package_digest(package),
        "runtime": platform.python_version(),
        "requirements_digest": sha(lock.read_bytes()) if lock.exists() else None,
    }


def validate_runtime(package):
    lock = package / "requirements.lock.txt"
    if not lock.is_file():
        raise NodeError(
            "MISSING_RUNTIME_LOCK", "Skill dependency lock is unavailable", blocked=True
        )
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise NodeError(
                "INVALID_RUNTIME_LOCK", "Expected exact dependency pins", line
            )
        name, expected = match.groups()
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise NodeError(
                "MISSING_RUNTIME",
                "Required installed dependency is absent",
                name,
                blocked=True,
            ) from exc
        if actual != expected:
            raise NodeError(
                "INCOMPATIBLE_RUNTIME",
                "Installed dependency differs from lock",
                name,
                blocked=True,
            )



class OperationContext:
    """One operation over already verified rules; no nested Skill process."""

    def __init__(self, root, request, *, modules, rules, tool, rules_digest,
                 action=None, package=None, catalog=None):
        from types import SimpleNamespace
        self.root = Path(root).resolve(strict=True)
        self.request, self.modules, self.rules = request, modules, rules
        self.tool, self.package = tool, Path(package) if package else None
        self.operation = identifier(request.get("operation_id"))
        self.operation_root = ".build/operations/" + self.operation
        self.base = self.operation_root
        self.args = SimpleNamespace(knowledge_root=str(self.root), rules_digest=rules_digest,
                                    action=action, catalog=catalog)

    def seal(self, value, kind):
        record = {"schema_version": "2.0", "record_kind": kind,
                  "operation_id": self.operation, "rules_digest": self.args.rules_digest,
                  "tool_identity": self.tool, **value}
        result = self.modules["records"].seal(record)
        self.modules["validation"].validate_shape(kind, result, self.rules)
        return result

    def save(self, ref, record):
        writer = write_index_bytes if ref.startswith("artifacts/indexes/") else write_bytes
        raw = canonical(record)
        writer(self.root, ref, raw)
        if ref.startswith(self.operation_root + "/"):
            self.register_owned(ref, raw)
        return ref

    def owned_files(self):
        """Read this operation's explicit write ledger, never enumerate a directory."""
        reference = self.operation_root + "/owned-files.json"
        if not safe(self.root, reference).exists():
            return []
        ledger = self.record(reference, "artifact_manifest")
        if (ledger.get("purpose") != "operation_owned_files"
                or ledger.get("operation_id") != self.operation
                or not isinstance(ledger.get("files"), list)):
            raise NodeError("INVALID_OWNERSHIP", "Ownership ledger has another identity", reference)
        files = {}
        for item in ledger["files"]:
            if not isinstance(item, dict):
                raise NodeError("INVALID_OWNERSHIP", "An owned file must be an object", reference)
            row = dict(item)
            path = row.get("path")
            safe(self.root, path, [self.operation_root])
            if (path == reference or row.get("owner_operation_id") != self.operation
                    or not isinstance(row.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                    or type(row.get("bytes")) is not int or row["bytes"] < 0
                    or path in files):
                raise NodeError("INVALID_OWNERSHIP", "Invalid owned file identity", path)
            files[path] = row
        return [files[path] for path in sorted(files)]

    def register_owned(self, ref, raw):
        """Register actual bytes written or explicitly adopted within this operation."""
        safe(self.root, ref, [self.operation_root])
        reference = self.operation_root + "/owned-files.json"
        if ref == reference:
            return ref
        if not isinstance(raw, bytes) or fixed_bytes(self.root, ref) != raw:
            raise NodeError("OWNED_FILE_CHANGED", "Owned bytes differ from the observed file", ref)
        previous = fixed_bytes(self.root, reference) if safe(self.root, reference).exists() else None
        files = {row["path"]: row for row in self.owned_files()}
        observed = {"path": ref, "sha256": sha(raw), "bytes": len(raw),
                    "owner_operation_id": self.operation}
        if files.get(ref) == observed:
            return ref
        files[ref] = observed
        ledger = self.seal({"purpose": "operation_owned_files",
                            "files": [files[path] for path in sorted(files)]}, "artifact_manifest")
        current = fixed_bytes(self.root, reference) if safe(self.root, reference).exists() else None
        if current != previous:
            raise NodeError("OWNERSHIP_CHANGED", "Ownership changed during registration", reference)
        write_bytes(self.root, reference, canonical(ledger), immutable=False)
        return ref

    def record(self, ref, kind=None):
        allowed = {"index_manifest": ["artifacts/indexes"],
                   "generation": ["artifacts/indexes"],
                   "project_context": [".build/project-context", ".build/operations", "logs"]}.get(
                       kind, [".build/operations", "logs"] if kind else
                       [".build/operations", ".build/project-context", "logs", "artifacts/indexes"])
        value = json.loads(fixed_bytes(self.root, ref, allowed), object_pairs_hook=unique)
        self.modules["records"].verify(value)
        self.modules["validation"].validate_shape(value.get("record_kind", "record"), value, self.rules)
        if value.get("rules_digest") != self.args.rules_digest:
            raise NodeError("STALE_RULES", "Referenced record uses different rules", ref)
        if kind and value.get("record_kind") != kind:
            raise NodeError("WRONG_RECORD_KIND", "Referenced record has wrong kind", ref)
        return value


def fork_context(ctx, request=None, operation_id=None, action=None):
    """Share verified rules, but retain each action's real immutable operation."""
    payload = dict(ctx.request if request is None else request)
    if operation_id is not None:
        payload["operation_id"] = operation_id
    elif "operation_id" not in payload:
        payload["operation_id"] = ctx.operation
    return OperationContext(ctx.root, payload, modules=ctx.modules, rules=ctx.rules,
                            tool=ctx.tool, rules_digest=ctx.args.rules_digest,
                            action=ctx.args.action if action is None else action,
                            package=getattr(ctx, "package", None),
                            catalog=getattr(ctx.args, "catalog", None))
