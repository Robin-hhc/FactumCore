"""Package-local protocol support. No sibling private imports."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import platform
import re
import stat
import tempfile


class Invalid(ValueError):
    code = "invalid_input"


class Blocked(Invalid):
    code = "awaiting_prerequisite"


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise Invalid("duplicate JSON key")
            result[key] = item
        return result

    def nonfinite(value):
        raise Invalid("nonfinite JSON value: " + value)

    return json.loads(value, object_pairs_hook=pairs, parse_constant=nonfinite)


def digest(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical(value)
    ).hexdigest()


def seal(record):
    result = dict(record)
    result.pop("digest", None)
    result["digest"] = digest(result)
    return result


def verify(record):
    if not isinstance(record, dict):
        raise Invalid("record must be an object")
    payload = dict(record)
    expected = payload.pop("digest", None)
    if expected != digest(payload):
        raise Invalid("record digest mismatch")
    if record.get("schema_version") != "2.0":
        raise Invalid("unsupported protocol version")
    return record


def safe_path(root, relative, prefixes=None):
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or ":" in relative
        or relative.startswith("/")
    ):
        raise Invalid("expected knowledge-root relative POSIX path")
    parts = relative.split("/")
    reserved = (
        {"con", "prn", "aux", "nul"}
        | {"com" + str(n) for n in range(1, 10)}
        | {"lpt" + str(n) for n in range(1, 10)}
    )
    if any(
        p in ("", ".", "..")
        or p.rstrip(". ") != p
        or p.split(".")[0].lower() in reserved
        or any(ord(c) < 32 or c in '<>"|?*' for c in p)
        for p in parts
    ):
        raise Invalid("unsafe path component")
    if prefixes and not any(
        relative == p or relative.startswith(p.rstrip("/") + "/") for p in prefixes
    ):
        raise Invalid("path is outside its prescribed subtree")
    root = pathlib.Path(root).resolve()
    current = root
    for part in parts:
        if current.exists():
            aliases = [
                entry.name
                for entry in pathlib.Path(native_path(current)).iterdir()
                if entry.name.casefold() == part.casefold()
            ]
            if aliases and aliases != [part]:
                raise Invalid("case alias is not permitted")
        current = current / part
        if current.is_symlink() or (
            os.path.lexists(current)
            and getattr(current.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise Invalid("symlink or junction is not permitted")
        try:
            current.resolve().relative_to(root)
        except ValueError as exc:
            raise Invalid("path escapes knowledge root") from exc
    return current


def package_digest(root):
    entries = {}
    for p in pathlib.Path(root).rglob("*"):
        rel = p.relative_to(root).as_posix()
        if (
            not p.is_file()
            or "__pycache__" in p.parts
            or "tests" in p.relative_to(root).parts
        ):
            continue
        if (
            rel == "SKILL.md"
            or rel.startswith(("scripts/", "references/", "artifacts/"))
            or (p.name.startswith("requirements") and p.suffix == ".txt")
        ):
            entries[rel] = digest(pathlib.Path(native_path(p)).read_bytes())
    return digest(entries)


def identity(root):
    root = pathlib.Path(root)
    lock = root / "requirements.lock.txt"
    return {
        "skill": root.name,
        "package_digest": package_digest(root),
        "runtime": platform.python_version(),
        "requirements_digest": digest(pathlib.Path(native_path(lock)).read_bytes()),
    }


def native_path(value):
    text = str(pathlib.Path(value).absolute())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return (
            "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        )
    return text


def atomic_bytes(path, content):
    path = pathlib.Path(path)
    pathlib.Path(native_path(path.parent)).mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".atomic-", dir=native_path(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(native_path(temporary), native_path(path))
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_directory(path):
    if os.name != "nt":
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class WriterLock:
    def __init__(self, root):
        self.path = safe_path(root, ".build/runtime/writer.lock")

    def __enter__(self):
        pathlib.Path(native_path(self.path.parent)).mkdir(parents=True, exist_ok=True)
        self.stream = pathlib.Path(native_path(self.path)).open("a+b")
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b"\0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise Blocked("knowledge writer lock is held") from exc
        return self

    def __exit__(self, *_):
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream, fcntl.LOCK_UN)
        finally:
            self.stream.close()


class Context:
    def __init__(
        self, root, rules_digest, tool_identity, catalog=None, domain=None, rules=None
    ):
        self.root = pathlib.Path(root).resolve()
        self.rules_digest = rules_digest
        self.identity = tool_identity
        self.catalog = catalog or {}
        self.catalog_path = None
        self.domain = domain
        self.rules = rules

    @classmethod
    def synthetic(cls, root, skill):
        """Explicit dependency-injection seam for unit tests, never used by CLI."""
        return cls(
            root,
            "0" * 64,
            {
                "skill": skill,
                "package_digest": "0" * 64,
                "runtime": platform.python_version(),
                "requirements_digest": "0" * 64,
            },
        )

    def path(self, relative, prefixes=None):
        result = safe_path(self.root, relative, prefixes)
        if self.domain:
            self.domain.safe_path(self.root, relative, prefixes)
        return result

    def read(self, relative):
        value = strict_json(pathlib.Path(native_path(self.path(relative))).read_text(encoding="utf-8"))
        verify(value)
        if value.get("rules_digest") != self.rules_digest:
            raise Invalid("record rules identity mismatch")
        if self.domain:
            self.domain.validate_shape(
                value.get("record_kind", "record"), value, self.rules
            )
        return value

    def publish(self, relative, content):
        path = self.path(relative, (".build/operations", "logs"))
        pathlib.Path(native_path(path.parent)).mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".record-", dir=native_path(path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self.path(relative, (".build/operations", "logs"))
            try:
                os.link(temporary, native_path(path))
                sync_directory(path.parent)
            except FileExistsError:
                if pathlib.Path(native_path(path)).read_bytes() != content:
                    raise Blocked(
                        "immutable artifact already exists with different bytes"
                    )
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return relative

    def save(self, relative, record, immutable=True):
        path = self.path(relative, (".build/operations", "logs"))
        record = seal(record)
        if self.domain:
            self.domain.validate_shape(
                record.get("record_kind", "record"), record, self.rules
            )
        content = canonical(record) + b"\n"
        if immutable:
            self.publish(relative, content)
        else:
            atomic_bytes(path, content)
        return relative

    def record(self, kind, operation_id, **fields):
        return seal(
            {
                "schema_version": "2.0",
                "record_kind": kind,
                "operation_id": operation_id,
                "rules_digest": self.rules_digest,
                "tool_identity": self.identity,
                **fields,
            }
        )

    def operation(self, request):
        from .runtime import identifier
        try:
            return identifier(request.get("operation_id"))
        except ValueError as exc:
            raise Invalid("invalid operation_id") from exc


def checked_view(ctx, request):
    op = ctx.operation(request)
    ref = request.get("view_ref")
    if not isinstance(ref, str):
        raise Invalid("view_ref required")
    ctx.path(ref, (f".build/operations/{op}",))
    view = ctx.read(ref)
    if view.get("record_kind") != "final_view" or view.get("operation_id") != op:
        raise Invalid("final view identity mismatch")
    paths = set()
    if any(
        row.get("path") == "governance/sources.lock.yaml"
        for row in view.get("deletes", [])
    ):
        raise Invalid("source registry cannot be deleted by a knowledge transaction")
    for row in view.get("writes", []) + view.get("deletes", []):
        path = row.get("path")
        ctx.path(path, ("knowledge", "governance/sources.lock.yaml", "index.md"))
        if path.casefold() in paths:
            raise Invalid("duplicate write/delete path")
        paths.add(path.casefold())
        old = row.get("expected_old_digest")
        if old is not None and (
            not isinstance(old, str) or not re.fullmatch(r"[0-9a-f]{64}", old)
        ):
            raise Invalid("invalid expected-old digest")
    for row in view.get("writes", []):
        try:
            content = base64.b64decode(row["bytes_b64"], validate=True)
        except (ValueError, KeyError) as exc:
            raise Invalid("invalid final bytes") from exc
        if digest(content) != row.get("final_digest"):
            raise Invalid("final byte digest mismatch")
    if not view.get("writes") and not view.get("deletes"):
        if not (view.get("review_mode") == "record_only" and view.get("batch_kind") == "record_only" and view.get("ingest_record_ref")):
            raise Invalid("empty final view")
    return view
