"""This Skill's protocol boundary; sibling implementations are never imported."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.abc
import importlib.util
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath

import yaml


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
                for p in current.iterdir()
                if p.name.casefold() == part.casefold()
            ]
            if aliases and part not in aliases:
                raise NodeError(
                    "CASE_ALIAS", "Existing path uses different case", relative
                )
        current = current / part
        if current.is_symlink() or (
            hasattr(current, "is_junction") and current.is_junction()
        ):
            raise NodeError("UNSAFE_PATH", "Linked path is not permitted", relative)
        if not current.resolve().is_relative_to(root):
            raise NodeError("UNSAFE_PATH", "Path escaped knowledge root", relative)
    return current


def fixed_bytes(root, ref, prefixes=None):
    path = safe(root, ref, prefixes)
    data = Path(native_path(path)).read_bytes()
    if Path(native_path(safe(root, ref, prefixes))).read_bytes() != data:
        raise NodeError("INPUT_CHANGED", "Referenced input changed", ref)
    return data


def native_path(value):
    text = str(Path(value).absolute())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return (
            "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        )
    return text


def write_bytes(root, ref, data, *, immutable=True):
    path = safe(root, ref, [".build", "logs", "artifacts/indexes"])
    path.parent.mkdir(parents=True, exist_ok=True)
    safe(root, ref)
    if immutable and path.exists():
        if Path(native_path(path)).read_bytes() != data:
            raise NodeError(
                "OPERATION_CONFLICT", "Immutable artifact already differs", ref
            )
        return
    fd, temporary = tempfile.mkstemp(prefix=".node-", dir=path.parent)
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
        "records.py",
        "indexing.py",
        "checks.py",
    ):
        if "governance/contracts/" + name not in verified:
            raise NodeError(
                "UNPINNED_DOMAIN_CODE", "Domain program is not digest-locked", name
            )
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
            for name in ("validation", "knowledge", "source_resources", "records", "indexing", "checks"):
                importlib.import_module(namespace + "." + name)
        finally:
            sys.meta_path.remove(finder)
    modules = {
        name: sys.modules[namespace + "." + name]
        for name in ("validation", "knowledge", "source_resources", "records", "indexing", "checks")
    }
    rules = modules["validation"].load_rules(root, expected)
    for ref, data in verified.items():
        if safe(root, ref).read_bytes() != data:
            raise NodeError("RULES_CHANGED", "Rules changed while loading", ref)
    return modules, rules


class Context:
    def __init__(self, args, request, package):
        self.args, self.request, self.package = args, request, package
        self.root = Path(args.knowledge_root).resolve(strict=True)
        self.modules, self.rules = domain(self.root, args.rules_digest)
        validate_runtime(package)
        self.tool = tool_identity(package)
        self.operation = identifier(request.get("operation_id"))
        self.base = ".build/operations/" + self.operation

    def seal(self, value, kind):
        record = {
            "schema_version": "2.0",
            "record_kind": kind,
            "operation_id": self.operation,
            "rules_digest": self.args.rules_digest,
            "tool_identity": self.tool,
            **value,
        }
        result = self.modules["records"].seal(record)
        self.modules["validation"].validate_shape(kind, result, self.rules)
        return result

    def save(self, ref, record):
        write_bytes(self.root, ref, canonical(record))
        return ref

    def record(self, ref, kind=None):
        allowed = {
            "index_manifest": ["artifacts/indexes"],
            "generation": ["artifacts/indexes"],
            "project_context": [".build/project-context", ".build/operations", "logs"],
        }.get(
            kind,
            [".build/operations", "logs"]
            if kind
            else [
                ".build/operations",
                ".build/project-context",
                "logs",
                "artifacts/indexes",
            ],
        )
        data = fixed_bytes(self.root, ref, allowed)
        value = json.loads(data, object_pairs_hook=unique)
        self.modules["records"].verify(value)
        self.modules["validation"].validate_shape(
            value.get("record_kind", "record"), value, self.rules
        )
        if value.get("rules_digest") != self.args.rules_digest:
            raise NodeError(
                "STALE_RULES", "Referenced record uses different rules", ref
            )
        if kind and value.get("record_kind") != kind:
            raise NodeError(
                "WRONG_RECORD_KIND", "Referenced record has wrong kind", ref
            )
        return value

    def call(self, name, request, action=None):
        if not self.args.catalog:
            raise NodeError(
                "MISSING_CATALOG",
                "Installed catalog required for sibling capability",
                name,
                blocked=True,
            )
        catalog = read_json(self.args.catalog)
        entry = catalog.get("skills", {}).get(name)
        if catalog.get("schema_version") != "2.0" or not entry:
            raise NodeError(
                "MISSING_CAPABILITY",
                "Skill missing from installed catalog",
                name,
                blocked=True,
            )
        package = Path(entry["root"]).resolve(strict=True)
        if entry.get("entry") != "scripts/cli.py":
            raise NodeError(
                "INVALID_CATALOG_ENTRY",
                "Catalog must name the fixed public scripts/cli.py entry",
                name,
            )
        if package_digest(package) != entry.get("package_digest"):
            raise NodeError(
                "PACKAGE_DIGEST_MISMATCH", "Installed Skill differs from catalog", name
            )
        cli = safe(package, entry["entry"])
        interpreter = Path(entry["python"])
        if not interpreter.is_absolute() or not interpreter.is_file():
            raise NodeError(
                "MISSING_RUNTIME", "Catalog interpreter unavailable", name, blocked=True
            )
        call = self.base + "/calls/" + uuid.uuid4().hex
        incoming, outgoing = call + "/request.json", call + "/response.json"
        write_bytes(self.root, incoming, canonical(request))
        argv = [
            str(interpreter),
            str(cli),
            "--input",
            str(safe(self.root, incoming)),
            "--output",
            str(safe(self.root, outgoing)),
            "--knowledge-root",
            str(self.root),
            "--rules-digest",
            self.args.rules_digest,
            "--catalog",
            self.args.catalog,
        ]
        if action:
            argv += ["--action", action]
        result = subprocess.run(argv, capture_output=True, timeout=120, check=False)
        response = read_json(safe(self.root, outgoing))
        if response.get("digest") != digest(
            {key: value for key, value in response.items() if key != "digest"}
        ):
            raise NodeError(
                "SIBLING_RESULT_CHANGED",
                "Response envelope digest is missing or invalid",
                name,
            )
        if (
            response.get("schema_version") != "2.0"
            or response.get("record_kind") != "result"
            or response.get("rules_digest") != self.args.rules_digest
            or response.get("tool_identity", {}).get("package_digest")
            != entry["package_digest"]
        ):
            raise NodeError(
                "SIBLING_IDENTITY_MISMATCH",
                "Response does not bind the pinned public Skill",
                name,
            )
        if package_digest(package) != entry["package_digest"]:
            raise NodeError(
                "PACKAGE_CHANGED", "Sibling package changed during invocation", name
            )
        if result.returncode or response.get("status") != "ok":
            issue = next(iter(response.get("diagnostics", [])), {})
            raise NodeError(
                issue.get("code", "SIBLING_BLOCKED"),
                issue.get("message", "Sibling prerequisite blocked"),
                name,
                blocked=response.get("status") == "blocked",
            )
        return response


def run(handler, package):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest", required=True)
    parser.add_argument("--catalog")
    parser.add_argument("--action")
    args = parser.parse_args()
    identity = tool_identity(package)
    envelope = {
        "schema_version": "2.0",
        "record_kind": "result",
        "status": "error",
        "phase": "invalid",
        "data": {},
        "diagnostics": [],
        "tool_identity": identity,
        "rules_digest": args.rules_digest,
    }
    code = 2
    try:
        request = read_json(args.input)
        workflow = request.get("workflow")
        if "workflow" in request:
            if not isinstance(workflow, dict) or any(
                key not in workflow for key in ("run_id", "node_id", "attempt_id")
            ):
                raise NodeError(
                    "INVALID_WORKFLOW",
                    "Explicit workflow needs run, node and attempt IDs",
                )
            pieces = [
                identifier(workflow[key]) for key in ("run_id", "node_id", "attempt_id")
            ]
        context = Context(args, request, package)
        data, phase = handler(context)
        envelope.update(status="ok", phase=phase, data=data)
        workflow = request.get("workflow")
        if workflow:
            pieces = [
                identifier(workflow[k]) for k in ("run_id", "node_id", "attempt_id")
            ]
            ref = (
                "logs/workflows/"
                + pieces[0]
                + "/nodes/"
                + "/".join(pieces[1:])
                + "/result.json"
            )
            references = set()
            for key, value in data.items():
                if key.endswith("_ref") and isinstance(value, str):
                    references.add(value)
                elif key.endswith("_refs") and isinstance(value, list):
                    references.update(item for item in value if isinstance(item, str))
            artifact_digests = {
                item: sha(
                    fixed_bytes(
                        context.root, item, [".build", "logs", "artifacts/indexes"]
                    )
                )
                for item in sorted(references)
            }
            manifest = context.seal(
                {
                    "workflow": workflow,
                    "artifact_digests": artifact_digests,
                    "phase": phase,
                    "result": data,
                    "request_digest": digest(request),
                    "result_digest": digest(data),
                },
                "workflow_manifest",
            )
            context.save(ref, manifest)
            markdown = (
                "# Node result\n\n```json\n" + canonical(manifest).decode() + "\n```\n"
            )
            write_bytes(context.root, ref[:-5] + ".md", markdown.encode())
            for item, expected in artifact_digests.items():
                if (
                    sha(
                        fixed_bytes(
                            context.root, item, [".build", "logs", "artifacts/indexes"]
                        )
                    )
                    != expected
                ):
                    raise NodeError(
                        "ARTIFACT_CHANGED",
                        "Returned file changed during workflow manifest publication",
                        item,
                    )
            envelope["data"]["artifact_manifest_ref"] = ref[:-5] + ".md"
        code = 0
    except Exception as exc:
        blocked = getattr(exc, "blocked", False)
        envelope.update(
            status="blocked" if blocked else "error",
            phase="blocked" if blocked else "invalid",
            diagnostics=[
                {
                    "code": getattr(exc, "code", "INVALID_INPUT"),
                    "message": getattr(exc, "message", str(exc)),
                    "path": str(getattr(exc, "path", "")),
                }
            ],
        )
        code = 3 if blocked else 2
    output = Path(args.output).absolute()
    root = Path(args.knowledge_root).resolve()
    if root.exists() and output.is_relative_to(root):
        safe(root, output.relative_to(root).as_posix(), [".build", "logs"])
    output.parent.mkdir(parents=True, exist_ok=True)
    envelope["digest"] = digest(
        {key: value for key, value in envelope.items() if key != "digest"}
    )
    output.write_bytes(canonical(envelope))
    return code
