"""Package-local protocol support. No sibling private imports."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import importlib.abc
import importlib.metadata
import json
import os
import pathlib
import platform
import re
import stat
import sys
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
        op = request.get("operation_id")
        if not isinstance(op, str) or not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", op
        ):
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


def load_context(args, package_root):
    for line in (
        (pathlib.Path(package_root) / "requirements.lock.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise Invalid("runtime lock must contain exact version pins")
        try:
            actual = importlib.metadata.version(match[1])
        except importlib.metadata.PackageNotFoundError as exc:
            raise Blocked("required runtime dependency missing: " + match[1]) from exc
        if actual != match[2]:
            raise Blocked("runtime dependency differs from pinned lock: " + match[1])
    root = pathlib.Path(args.knowledge_root).resolve()
    lock = safe_path(root, "governance/framework.lock.yaml")
    args.rules_digest = args.rules_digest or digest(pathlib.Path(native_path(lock)).read_bytes())
    if digest(pathlib.Path(native_path(lock)).read_bytes()) != args.rules_digest:
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

    UniqueLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping
    )
    document = yaml.load(pathlib.Path(native_path(lock)).read_bytes(), Loader=UniqueLoader)
    files = document.get("files", {})
    verified = {}
    validation_path = None
    for item in files.values():
        if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
            raise Invalid("invalid framework file manifest")
        target = safe_path(root, item["path"], ("governance",))
        raw = pathlib.Path(native_path(target)).read_bytes()
        if digest(raw) != item["sha256"]:
            raise Invalid("framework file digest mismatch")
        if item["path"] in verified:
            raise Invalid("duplicate framework file path")
        verified[item["path"]] = raw
        if item["path"] == "governance/contracts/validation.py":
            validation_path = target
    if validation_path is None:
        raise Invalid("validation program is not pinned")
    contract_names = tuple(sorted(ref[len("governance/contracts/"):-3] for ref in verified
                                      if ref.startswith("governance/contracts/") and ref.endswith(".py")
                                      and "/" not in ref[len("governance/contracts/"):]
                                      and not ref.endswith("/__init__.py")))
    package_name = "_aiot_domain_" + args.rules_digest
    for name in ("__init__", "validation", "knowledge", "source_resources", "records", "indexing", "checks", "indexing", "checks"):
        if "governance/contracts/" + name + ".py" not in verified:
            raise Invalid("domain program is not pinned")

    class PinnedLoader(importlib.abc.Loader):
        def __init__(self, reference):
            self.reference = reference

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            if module.__name__ == package_name:
                module.__path__ = []
            module.__file__ = str(root / self.reference)
            exec(
                compile(verified[self.reference], module.__file__, "exec"),
                module.__dict__,
            )

    class PinnedFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != package_name and not fullname.startswith(package_name + "."):
                return None
            name = (
                "__init__"
                if fullname == package_name
                else fullname[len(package_name) + 1 :]
            )
            reference = "governance/contracts/" + name.replace(".", "/") + ".py"
            if reference not in verified:
                raise ImportError("unlocked domain module: " + fullname)
            return importlib.util.spec_from_loader(
                fullname, PinnedLoader(reference), is_package=fullname == package_name
            )

    finder = PinnedFinder()
    sys.meta_path.insert(0, finder)
    try:
        importlib.import_module(package_name)
        for name in contract_names:
            importlib.import_module(package_name + "." + name)
    finally:
        sys.meta_path.remove(finder)
    domain = sys.modules[package_name + ".validation"]
    rules = domain.load_rules(root, args.rules_digest)
    for reference, raw in verified.items():
        if pathlib.Path(native_path(safe_path(root, reference))).read_bytes() != raw:
            raise Invalid("rules changed while loading")
    catalog = {}
    if args.catalog:
        try:
            catalog = strict_json(pathlib.Path(args.catalog).read_text(encoding="utf-8"))
            if not isinstance(catalog, dict):
                catalog = {}
        except (OSError, ValueError):
            pass
    context = Context(
        root, args.rules_digest, identity(package_root), catalog, domain, rules
    )
    context.modules = {name: sys.modules[package_name + "." + name] for name in contract_names}
    context.catalog_path = (
        str(pathlib.Path(args.catalog).resolve()) if args.catalog else None
    )
    return context



def _batch_transport(ctx, request, incoming, outgoing):
    operation = ctx.modules["runtime"].identifier(request.get("operation_id"))
    allowed = (".build/operations/" + operation,)
    root = ctx.root.resolve()
    for candidate in (incoming, outgoing):
        absolute = pathlib.Path(candidate).absolute()
        resolved = absolute.resolve()
        if absolute.is_relative_to(root):
            relative = absolute.relative_to(root).as_posix()
            ctx.path(relative, allowed)
            if candidate == outgoing:
                slot = relative[len(allowed[0]) + 1:].casefold()
                reserved = {"owned-files.json", "batch-intent.json", "batch-build.json", "batch-complete.json",
                    "view.json", "final-view.json", "plan.json", "preview.json", "summary.json", "revision.json",
                    "disposition-preview.json", "view-summary.json", "capture.json", "scan.json", "inventory.json",
                    "record.json", "ingest-record.json", "material.json"}
                if slot == "transaction" or slot.startswith("transaction/") or slot in reserved:
                    raise Invalid("batch response cannot overwrite a reserved operation protocol slot")
        elif resolved.is_relative_to(root):
            raise Invalid("an aliased knowledge path is not external transport")
    if pathlib.Path(incoming).resolve() == pathlib.Path(outgoing).resolve():
        raise Invalid("batch input and output transport paths must differ")
    return operation


def run_cli(handler, package_root):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest")
    parser.add_argument("--catalog")
    parser.add_argument("--action", default="run")
    args = parser.parse_args()
    tool = identity(package_root)
    output = pathlib.Path(args.output).absolute()
    root = pathlib.Path(args.knowledge_root).resolve()
    output_allowed = args.action != "batch" or (not output.is_relative_to(root) and not output.resolve().is_relative_to(root))
    try:
        ctx = load_context(args, package_root)
        incoming = pathlib.Path(args.input).absolute()
        request_raw = pathlib.Path(native_path(incoming)).read_bytes()
        request = strict_json(request_raw.decode("utf-8"))
        if args.action == "batch":
            operation = _batch_transport(ctx, request, incoming, output)
            output_allowed = True
            # The first batch owns its transport input. Completed/cleanup-only
            # reentry must not recreate the deleted business ownership ledger.
            formal = "logs/publications/" + operation + "/manifest.json"
            completion = None
            if ctx.path(formal).is_file():
                shared = ctx.modules["runtime"].OperationContext(ctx.root, request, modules=ctx.modules,
                    rules=ctx.rules, tool=ctx.identity, rules_digest=ctx.rules_digest)
                completion = ctx.modules["publication"].read_completion(shared)
            if incoming.is_relative_to(ctx.root) and not (completion and completion.get("retrieval", {}).get("complete") is True):
                relative = incoming.relative_to(ctx.root).as_posix()
                from transaction import register_owned
                register_owned(ctx, relative, operation)
        data = handler(ctx, request, args.action)
        result = {
            "status": "ok",
            "phase": data.pop("phase", "completed"),
            "data": data,
            "diagnostics": [],
        }
        code = 0
    except Blocked as exc:
        result = {
            "status": "blocked",
            "phase": "awaiting",
            "data": {},
            "diagnostics": [{"code": exc.code, "message": str(exc)}],
        }
        code = 3
    except Exception as exc:
        result = {
            "status": "error",
            "phase": "invalid",
            "data": {},
            "diagnostics": [
                {"code": getattr(exc, "code", "invalid_input"), "message": str(exc)}
            ],
        }
        code = 2
    result = seal(
        {
            "schema_version": "2.0",
            "record_kind": "result",
            "rules_digest": args.rules_digest,
            "tool_identity": tool,
            **result,
        }
    )
    if not output_allowed:
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
        return code
    try:
        if args.action == "batch" and "ctx" in locals() and "request" in locals():
            _batch_transport(ctx, request, args.input, output)
        elif output.is_relative_to(root):
            rel = output.relative_to(root).as_posix()
            safe_path(root, rel, (".build", "logs"))
        if output.exists() and pathlib.Path(native_path(output)).read_bytes() != canonical(result) + b"\n":
            raise Invalid("response path already exists; use a new output path")
        atomic_bytes(output, canonical(result) + b"\n")
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    return code
