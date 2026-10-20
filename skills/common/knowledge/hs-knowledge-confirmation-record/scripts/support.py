"""Package-local protocol support. No sibling private imports."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import platform
import re
import subprocess
import sys
import tempfile
import time
import types


class Invalid(ValueError):
    code = "invalid_input"


class Blocked(Invalid):
    code = "awaiting_prerequisite"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


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
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative or relative.startswith("/"):
        raise Invalid("expected knowledge-root relative POSIX path")
    parts = relative.split("/")
    reserved = {"con", "prn", "aux", "nul"} | {"com" + str(n) for n in range(1, 10)} | {"lpt" + str(n) for n in range(1, 10)}
    if any(p in ("", ".", "..") or p.rstrip(". ") != p or p.split(".")[0].lower() in reserved for p in parts):
        raise Invalid("unsafe path component")
    if prefixes and not any(relative == p or relative.startswith(p.rstrip("/") + "/") for p in prefixes):
        raise Invalid("path is outside its prescribed subtree")
    root = pathlib.Path(root).resolve()
    current = root
    for part in parts:
        if current.exists():
            aliases = [entry.name for entry in current.iterdir() if entry.name.casefold() == part.casefold()]
            if aliases and aliases != [part]:
                raise Invalid("case alias is not permitted")
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
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
        if not p.is_file() or "__pycache__" in p.parts or "tests" in p.relative_to(root).parts:
            continue
        if rel == "SKILL.md" or rel.startswith(("scripts/", "references/", "artifacts/")) or (p.name.startswith("requirements") and p.suffix == ".txt"):
            entries[rel] = digest(p.read_bytes())
    return digest(entries)


def identity(root):
    root = pathlib.Path(root)
    lock = root / "requirements.lock.txt"
    return {"skill": root.name, "package_digest": package_digest(root), "runtime": platform.python_version(), "requirements_digest": digest(lock.read_bytes())}


def atomic_bytes(path, content):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".atomic-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
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
        self.path = safe_path(root, "logs/operations/.writer.lock")

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
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
    def __init__(self, root, rules_digest, tool_identity, catalog=None, domain=None, rules=None):
        self.root = pathlib.Path(root).resolve()
        self.rules_digest = rules_digest
        self.identity = tool_identity
        self.catalog = catalog or {}
        self.domain = domain
        self.rules = rules

    @classmethod
    def synthetic(cls, root, skill):
        """Explicit dependency-injection seam for unit tests, never used by CLI."""
        return cls(root, "0" * 64, {"skill": skill, "package_digest": "0" * 64, "runtime": platform.python_version(), "requirements_digest": "0" * 64})

    def path(self, relative, prefixes=None):
        result = safe_path(self.root, relative, prefixes)
        if self.domain:
            self.domain.safe_path(self.root, relative, prefixes)
        return result

    def read(self, relative):
        value = json.loads(self.path(relative).read_text(encoding="utf-8"))
        verify(value)
        if value.get("rules_digest") != self.rules_digest:
            raise Invalid("record rules identity mismatch")
        if self.domain:
            self.domain.validate_shape(value.get("record_kind", "record"), value, self.rules)
        return value

    def save(self, relative, record, immutable=True):
        path = self.path(relative, (".build/operations", "logs"))
        record = seal(record)
        if self.domain:
            self.domain.validate_shape(record.get("record_kind", "record"), record, self.rules)
        content = canonical(record) + b"\n"
        if immutable:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                sync_directory(path.parent)
            except FileExistsError:
                if path.read_bytes() != content:
                    raise Blocked("immutable record already exists with different bytes")
        else:
            atomic_bytes(path, content)
        return relative

    def record(self, kind, operation_id, **fields):
        return seal({"schema_version": "2.0", "record_kind": kind, "operation_id": operation_id, "rules_digest": self.rules_digest, "tool_identity": self.identity, **fields})

    def operation(self, request):
        op = request.get("operation_id")
        if not isinstance(op, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", op):
            raise Invalid("invalid operation_id")
        return op


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
    for row in view.get("writes", []) + view.get("deletes", []):
        path = row.get("path")
        ctx.path(path, ("knowledge", "governance/sources.lock.yaml", "index.md"))
        if path.casefold() in paths:
            raise Invalid("duplicate write/delete path")
        paths.add(path.casefold())
        old = row.get("expected_old_digest")
        if old is not None and (not isinstance(old, str) or not re.fullmatch(r"[0-9a-f]{64}", old)):
            raise Invalid("invalid expected-old digest")
    for row in view.get("writes", []):
        try:
            content = base64.b64decode(row["bytes_b64"], validate=True)
        except (ValueError, KeyError) as exc:
            raise Invalid("invalid final bytes") from exc
        if digest(content) != row.get("final_digest"):
            raise Invalid("final byte digest mismatch")
    if not view.get("writes") and not view.get("deletes"):
        raise Invalid("empty final view")
    return view


def authenticated_event(ctx, display, event):
    adapter_id = event.get("adapter_id")
    trust = ctx.catalog.get("review_trust", {}).get("adapters", {}).get(adapter_id)
    if not trust:
        raise Blocked("awaiting authenticated human adapter")
    if trust.get("synthetic"):
        fixture = trust.get("fixture_root")
        marker = ctx.root / ".isolated-knowledge-fixture"
        if not fixture or pathlib.Path(fixture).resolve() != ctx.root or not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "AIOTBOT_SYNTHETIC_FIXTURE_V2":
            raise Blocked("synthetic adapter requires explicitly isolated fixture root")
    payload = event.get("payload")
    if not isinstance(payload, dict) or event.get("record_kind") != "host_event" or event.get("schema_version") != "2.0":
        raise Invalid("invalid authenticated host event")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(trust["public_key_b64"], validate=True))
        key.verify(base64.b64decode(event["signature_b64"], validate=True), canonical(payload))
    except Exception as exc:
        raise Invalid("host event signature invalid") from exc
    expected = {"display_digest": display["digest"], "view_digest": display["view_digest"], "challenge": display["challenge"]}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise Invalid("host event exact-view binding mismatch")
    if payload.get("actor_type") != "human" or not isinstance(payload.get("actor_id"), str) or not payload["actor_id"].strip():
        raise Blocked("event does not attest a real human actor")
    if payload.get("decision") not in ("approve", "reject"):
        raise Blocked("human decision absent")
    now = time.time()
    issued = payload.get("issued_at")
    if not isinstance(issued, (int, float)) or isinstance(issued, bool) or not math.isfinite(issued) or issued < display["created_at"] - 1 or issued > now + 60 or now > display["expires_at"]:
        raise Blocked("human event expired or predates display")
    return "synthetic_host" if trust.get("synthetic") else "authenticated_host"


def load_context(args, package_root):
    root = pathlib.Path(args.knowledge_root).resolve()
    lock = safe_path(root, "governance/framework.lock.yaml")
    if digest(lock.read_bytes()) != args.rules_digest:
        raise Invalid("framework lock digest mismatch")
    import yaml
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        value = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in value:
                raise Invalid("duplicate YAML key")
            value[key] = loader.construct_object(value_node, deep=deep)
        return value
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    document = yaml.load(lock.read_bytes(), Loader=UniqueLoader)
    files = document.get("files", {})
    validation_path = None
    for item in files.values():
        if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
            raise Invalid("invalid framework file manifest")
        target = safe_path(root, item["path"], ("governance",))
        if digest(target.read_bytes()) != item["sha256"]:
            raise Invalid("framework file digest mismatch")
        if item["path"] == "governance/contracts/validation.py":
            validation_path = target
    if validation_path is None:
        raise Invalid("validation program is not pinned")
    package_name = "_aiot_domain_" + args.rules_digest[:16]
    package = types.ModuleType(package_name)
    package.__path__ = [str(validation_path.parent)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(package_name + ".validation", validation_path)
    domain = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = domain
    spec.loader.exec_module(domain)
    rules = domain.load_rules(root, args.rules_digest)
    catalog = json.loads(pathlib.Path(args.catalog).read_text(encoding="utf-8")) if args.catalog else {}
    if catalog and catalog.get("schema_version") != "2.0":
        raise Invalid("invalid installed catalog version")
    return Context(root, args.rules_digest, identity(package_root), catalog, domain, rules)


def run_cli(handler, package_root):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest", required=True)
    parser.add_argument("--catalog")
    parser.add_argument("--action", default="run")
    args = parser.parse_args()
    tool = identity(package_root)
    try:
        ctx = load_context(args, package_root)
        request = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
        data = handler(ctx, request, args.action)
        result = {"status": "ok", "phase": data.pop("phase", "completed"), "data": data, "diagnostics": []}
        code = 0
    except Blocked as exc:
        result = {"status": "blocked", "phase": "awaiting", "data": {}, "diagnostics": [{"code": exc.code, "message": str(exc)}]}
        code = 3
    except Exception as exc:
        result = {"status": "error", "phase": "invalid", "data": {}, "diagnostics": [{"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}]}
        code = 2
    result = seal({"schema_version": "2.0", "record_kind": "result", "rules_digest": args.rules_digest, "tool_identity": tool, **result})
    output = pathlib.Path(args.output).resolve()
    try:
        root = pathlib.Path(args.knowledge_root).resolve()
        rel = output.relative_to(root).as_posix()
        safe_path(root, rel, (".build/operations", "logs"))
        if output.exists() and output.read_bytes() != canonical(result) + b"\n":
            raise Invalid("response path already exists; use a new attempt output")
        atomic_bytes(output, canonical(result) + b"\n")
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    return code
