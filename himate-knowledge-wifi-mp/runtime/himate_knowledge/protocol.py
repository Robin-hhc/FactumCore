"""Shared command protocol; operations call only verified domain functions."""

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
import stat
import sys
import tempfile
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


def write_bytes(root, ref, data, *, immutable=True):
    path = safe(root, ref, [".build", "logs"])
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


_RUNTIME_OBSERVATION = None


def set_runtime_observation(files, root):
    """Bind a trusted bootstrap's exact compiled inputs for this process only.

    The verified entrypoint supplies this through Python, never request JSON.
    A defensive copy prevents later caller mutation from changing identity.
    """
    global _RUNTIME_OBSERVATION
    if not isinstance(files, dict) or not files:
        raise NodeError("INVALID_RUNTIME_OBSERVATION", "Runtime input observation is empty")
    frozen = {}
    for reference, fingerprint in files.items():
        if (not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference
                or reference.startswith("/") or str(PurePosixPath(reference)) != reference
                or any(part in {".", ".."} for part in PurePosixPath(reference).parts)
                or not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)):
            raise NodeError("INVALID_RUNTIME_OBSERVATION", "Runtime input observation is invalid", reference)
        frozen[reference] = fingerprint
    _RUNTIME_OBSERVATION = (Path(root).resolve(strict=True), frozen)


def _runtime_observation():
    if _RUNTIME_OBSERVATION is None:
        package = sys.modules.get(__package__)
        snapshot = getattr(package, "_runtime_files_snapshot", None)
        root = getattr(package, "_runtime_root", None)
        if snapshot is not None and root is not None:
            set_runtime_observation(snapshot, root)
    return _RUNTIME_OBSERVATION


def runtime_files(runtime_root=None):
    """Hash actual repository runtime inputs, excluding manifest self-reference.

    Keys are relative to ``runtime/`` so the deployment manifest and operation
    identity describe the same bytes. Entrypoint digests are pinned separately
    by the runtime manifest; installed Python dependencies retain their lock.
    """
    root = Path(runtime_root) if runtime_root is not None else Path(__file__).resolve().parents[1]
    root = root.resolve(strict=True)
    observed = _runtime_observation()
    if observed is not None and root == observed[0]:
        return dict(observed[1])
    files = {}
    candidates = [root / "requirements.lock.txt"]
    package = root / "himate_knowledge"
    candidates.extend(package.rglob("*.py"))
    candidates.extend(package.rglob("requirements.lock.txt"))
    for path in sorted(set(candidates)):
        if not path.is_file() or "__pycache__" in path.parts or "tests" in path.relative_to(root).parts:
            continue
        current = root
        for part in path.relative_to(root).parts:
            current = current / part
            if current.is_symlink() or (os.path.lexists(current) and
                    getattr(current.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise NodeError("UNTRUSTED_PACKAGE", "Runtime contains a linked input", path)
        files[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return files


def runtime_digest(runtime_root=None):
    return digest(runtime_files(runtime_root))


def _stage_name(package):
    root = Path(package).resolve(strict=True)
    if root.parent.name == "stages" and root.parent.parent.name == "himate_knowledge":
        return "hs-knowledge-" + root.name.replace("_", "-")
    return None


def package_digest(root):
    root = Path(root).resolve(strict=True)
    logical = _stage_name(root)
    if logical:
        # The shared protocol and dispatch code execute alongside each stage.
        # Never attribute repository execution to old installed Skill bytes.
        return digest({"stage": logical, "runtime_files": runtime_files(root.parents[2])})
    # Historical catalog verification still needs its original package rules.
    files = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        rel = file.relative_to(root)
        if "__pycache__" in rel.parts or "tests" in rel.parts:
            continue
        if (rel.as_posix() == "SKILL.md" or rel.parts[0] in {"scripts", "references", "artifacts"}
                or (len(rel.parts) == 1 and file.name.startswith("requirements") and file.name.endswith(".txt"))):
            if file.is_symlink():
                raise NodeError("UNTRUSTED_PACKAGE", "Package contains a linked file", rel)
            files[rel.as_posix()] = sha(file.read_bytes())
    return digest(files)


def tool_identity(package):
    package = Path(package).resolve(strict=True)
    lock = package / "requirements.lock.txt"
    logical = _stage_name(package)
    if logical:
        runtime_root = package.parents[2]
        files = runtime_files(runtime_root)
        lock_ref = lock.relative_to(runtime_root).as_posix()
        return {"skill": logical, "executor": "knowledge-cli", "runtime": platform.python_version(),
                "package_digest": digest({"stage": logical, "runtime_files": files}),
                "runtime_digest": digest(files), "requirements_digest": files.get(lock_ref)}
    return {"skill": package.name, "package_digest": package_digest(package),
            "runtime": platform.python_version(),
            "requirements_digest": sha(lock.read_bytes()) if lock.exists() else None}


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


def Context(args, request, package):
    root = Path(args.knowledge_root).resolve(strict=True)
    args.rules_digest = args.rules_digest or sha(safe(root, "governance/framework.lock.yaml").read_bytes())
    modules, rules = domain(root, args.rules_digest)
    validate_runtime(package)
    return modules["runtime"].OperationContext(root, request, modules=modules, rules=rules,
                                               tool=tool_identity(package), rules_digest=args.rules_digest,
                                               action=args.action, package=package, catalog=args.catalog)


def run(handler, package, *, owned_io=False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--knowledge-root", required=True)
    parser.add_argument("--rules-digest")
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
    output = Path(args.output).absolute()
    root = Path(args.knowledge_root).resolve()
    output_allowed = not owned_io or not output.is_relative_to(root)
    try:
        request = read_json(args.input)
        if owned_io and output.is_relative_to(root):
            safe(root, output.relative_to(root).as_posix(), [".build/operations/" + identifier(request.get("operation_id"))])
        output_allowed = True
        context = Context(args, request, package)
        if owned_io:
            incoming = Path(args.input).absolute()
            if incoming.is_relative_to(context.root):
                relative = incoming.relative_to(context.root).as_posix()
                if relative.startswith(context.operation_root + "/"):
                    context.register_owned(relative, incoming.read_bytes())
        data, phase = handler(context)
        envelope.update(status="ok", phase=phase, data=data)
        code = 0
    except Exception as exc:
        blocked = getattr(exc, "blocked", False)
        envelope.update(
            status="blocked" if blocked else "error",
            phase="blocked" if blocked else "invalid",
            data=dict(getattr(exc, "data", {}) or {}),
            diagnostics=[
                {
                    "code": getattr(exc, "code", "INVALID_INPUT"),
                    "message": getattr(exc, "message", str(exc)),
                    "path": str(getattr(exc, "path", "")),
                }
            ],
        )
        code = 3 if blocked else 2
    envelope["rules_digest"] = args.rules_digest
    if not output_allowed:
        print(json.dumps(envelope, ensure_ascii=True))
        return code
    if not owned_io and root.exists() and output.is_relative_to(root):
        safe(root, output.relative_to(root).as_posix(), [".build", "logs"])
    output.parent.mkdir(parents=True, exist_ok=True)
    envelope["digest"] = digest(
        {key: value for key, value in envelope.items() if key != "digest"}
    )
    output.write_bytes(canonical(envelope))
    if owned_io and "context" in locals() and output.is_relative_to(root):
        context.register_owned(output.relative_to(root).as_posix(), canonical(envelope))
    return code
