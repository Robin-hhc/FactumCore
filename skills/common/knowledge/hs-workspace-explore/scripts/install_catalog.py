"""Explicit, non-overwriting private installation of the approved capability set.

Run with the interpreter/environment intended for the installed Skills. This
script never installs dependencies, loads domain Python, or writes global state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


SKILLS = ("hs-workspace-explore",) + tuple(
    "hs-knowledge-" + name
    for name in (
        "source-capture",
        "change-plan",
        "view-materialize",
        "governance-handoff",
        "candidate-inspect",
        "local-check",
        "candidate-revise",
        "apply",
        "recover",
        "index-build",
        "query-regression",
        "publish-handoff",
        "merge-check",
        "maintain",
        "query",
        "source-scan",
        "lint",
    )
)
WORKFLOWS = ("hs-knowledge-ingest",)
COMMANDS = {
    "ingest": {"kind": "workflow", "target": "hs-knowledge-ingest", "entry_node": "scan_sources"},
    "lint": {"kind": "skill", "target": "hs-knowledge-lint"},
    "query": {"kind": "skill", "target": "hs-knowledge-query"},
    "status": {"kind": "skill", "target": "hs-knowledge-source-scan", "action": "status"},
    "index rebuild": {"kind": "skill", "target": "hs-knowledge-index-build"},
    "recover": {"kind": "skill", "target": "hs-knowledge-recover"},
}
REQUIRED = (
    "SKILL.md",
    "scripts/cli.py",
    "scripts/support.py",
    "requirements.lock.txt",
    "requirements-dev.lock.txt",
    "artifacts/result.yaml",
    "artifacts/templates/result.md",
    "artifacts/writing-guide.md",
    "artifacts/review-guide.md",
)
IGNORED = {"__pycache__", ".pytest_cache", ".ruff_cache"}
DIRECTORIES = {"scripts", "references", "artifacts", "tests"}
SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".sh", ".ps1"}


class InstallError(ValueError):
    pass


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


def public_bytes(data, relative):
    if re.search(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----", data):
        raise InstallError(f"PRIVATE_KEY_IN_PACKAGE: {relative}")
    return data


def no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (
            os.path.lexists(part)
            and getattr(part.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise InstallError(f"LINKED_PATH: {part}")


def absolute(value, *, exists=True):
    path = Path(value)
    if not path.is_absolute():
        raise InstallError("ABSOLUTE_PATH_REQUIRED")
    no_links(path)
    return path.resolve(strict=exists)


def package_files(package):
    no_links(package)
    files = {}
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(package)
        if any(p in IGNORED for p in rel.parts) or path.suffix == ".pyc":
            continue
        no_links(path)
        if not path.is_file():
            continue
        if rel.as_posix() == "SKILL.md" or (
            len(rel.parts) == 1
            and re.fullmatch(r"requirements(?:-dev)?\.lock\.txt", path.name)
        ):
            files[rel.as_posix()] = public_bytes(path.read_bytes(), rel)
        elif rel.parts[0] in DIRECTORIES:
            if path.suffix.lower() not in SUFFIXES or any(
                p.startswith(".")
                or p.lower() in {"credentials", "secrets", "config.local.yml"}
                or Path(p).stem.lower() in {"credentials", "secrets"}
                for p in rel.parts
            ):
                raise InstallError(f"UNPUBLISHABLE_PACKAGE_FILE: {rel}")
            files[rel.as_posix()] = public_bytes(path.read_bytes(), rel)
    missing = set(REQUIRED) - files.keys()
    if not any(ref.startswith("tests/test") and ref.endswith(".py") for ref in files):
        missing.add("tests/test*.py")
    if missing:
        raise InstallError(f"INCOMPLETE_PACKAGE: {package.name}: {sorted(missing)}")
    names = re.findall(
        r"^name:\s*['\"]?([^'\"\r\n]+)['\"]?\s*$",
        files["SKILL.md"].decode("utf-8"),
        re.MULTILINE,
    )
    if names != [package.name]:
        raise InstallError(f"SKILL_ID_MISMATCH: {package.name}")
    return files


def package_digest(files):
    # Same canonical tree as every node's public support.package_digest.
    return sha(
        canonical(
            {
                ref: sha(data)
                for ref, data in files.items()
                if "tests" not in Path(ref).parts
            }
        )
    )


def dependencies(files):
    pins = {}
    for line in files["requirements.lock.txt"].decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise InstallError("INVALID_DEPENDENCY_LOCK: exact pins required")
        name, version = match.groups()
        pins[name] = version
    return pins


def validate_interpreter(python, pins):
    code = (
        "import importlib.metadata as m,json,sys; "
        "pins=json.loads(sys.argv[1]); "
        "print(json.dumps({k:m.version(k) for k in pins}))"
    )
    result = subprocess.run(
        [str(python), "-I", "-c", code, json.dumps(pins)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise InstallError(
            "DEPENDENCY_UNAVAILABLE: selected interpreter lacks a locked runtime"
        )
    if json.loads(result.stdout) != pins:
        raise InstallError("DEPENDENCY_VERSION_MISMATCH")


def parse_yaml_data(python, documents):
    # Parse data with the selected locked runtime. No source-root Python or
    # package initialization is ever imported. Duplicate YAML keys are invalid.
    code = """import json,sys,yaml
class Unique(yaml.SafeLoader): pass
def mapping(loader,node):
    result={}
    for k,v in node.value:
        key=loader.construct_object(k)
        if key in result: raise ValueError('duplicate YAML key')
        result[key]=loader.construct_object(v)
    return result
Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
sys.stdout.buffer.write(json.dumps({k:yaml.load(v,Loader=Unique) for k,v in json.loads(sys.stdin.buffer.read()).items()},ensure_ascii=False).encode('utf-8'))
"""
    result = subprocess.run(
        [str(python), "-I", "-c", code],
        input=canonical(documents),
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise InstallError("INVALID_YAML_DATA_OR_MISSING_PYYAML")
    return json.loads(result.stdout)


def validate_metadata(python, packages, templates):
    documents = {}
    for identity, files in packages.items():
        text = files["SKILL.md"].decode("utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        if not match:
            raise InstallError(f"MISSING_SKILL_FRONTMATTER: {identity}")
        documents[identity + ":skill"] = match[1]
        documents[identity + ":artifact"] = files["artifacts/result.yaml"].decode(
            "utf-8"
        )
        for ref, data in files.items():
            if ref.startswith("artifacts/") and ref.count("/") == 1 and ref.endswith(".yaml") and ref != "artifacts/result.yaml":
                documents[identity + ":artifact:" + ref] = data.decode("utf-8")
    for identity, files in templates.items():
        for name, data in files.items():
            documents[identity + ":" + name] = data.decode("utf-8")
    parsed = parse_yaml_data(python, documents)
    seen = set()
    for identity, files in packages.items():
        metadata = parsed[identity + ":skill"]
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != identity
            or not isinstance(metadata.get("description"), str)
            or not metadata["description"].strip()
        ):
            raise InstallError(f"INVALID_SKILL_METADATA: {identity}")
        contract = parsed[identity + ":artifact"]
        if (
            not isinstance(contract, dict)
            or contract.get("id") != identity + "-result"
            or contract["id"] in seen
        ):
            raise InstallError(f"INVALID_ARTIFACT_ID: {identity}")
        seen.add(contract["id"])
        location = contract.get("default_location")
        if (
            not isinstance(location, dict)
            or location.get("kind") != "markdown_file"
            or contract.get("required") is not True
        ):
            raise InstallError(f"INVALID_ARTIFACT_CONTRACT: {identity}")
        for field in ("template", "writing_guide", "review_guide"):
            ref = contract.get(field)
            if (
                not isinstance(ref, str)
                or not ref
                or "\\" in ref
                or ":" in ref
                or Path(ref).is_absolute()
                or ".." in Path(ref).parts
                or "artifacts/" + ref not in files
            ):
                raise InstallError(f"INVALID_ARTIFACT_REFERENCE: {identity}:{field}")
        for ref in files:
            if not (ref.startswith("artifacts/") and ref.count("/") == 1 and ref.endswith(".yaml") and ref != "artifacts/result.yaml"):
                continue
            extra = parsed[identity + ":artifact:" + ref]
            if not isinstance(extra, dict) or extra.get("id") != identity + "-" + Path(ref).stem or extra["id"] in seen:
                raise InstallError(f"INVALID_ARTIFACT_ID: {identity}:{ref}")
            seen.add(extra["id"])
            if extra.get("required") is not True or extra.get("default_location", {}).get("kind") != "markdown_file":
                raise InstallError(f"INVALID_ARTIFACT_CONTRACT: {identity}:{ref}")
            for field in ("template", "writing_guide", "review_guide"):
                value = extra.get(field)
                if not isinstance(value, str) or not value or "\\" in value or ":" in value or Path(value).is_absolute() or ".." in Path(value).parts or "artifacts/" + value not in files:
                    raise InstallError(f"INVALID_ARTIFACT_REFERENCE: {identity}:{ref}:{field}")
    for identity in templates:
        workflow = parsed[identity + ":workflow.yaml"]
        layout = parsed[identity + ":layouts.yaml"]
        if (
            not isinstance(workflow, dict)
            or workflow.get("id") != identity
            or workflow.get("version") != 1
            or not workflow.get("nodes")
        ):
            raise InstallError(f"INVALID_WORKFLOW_PACKAGE: {identity}")
        if not isinstance(layout, dict) or layout.get("template_id") != identity:
            raise InstallError(f"INVALID_WORKFLOW_LAYOUT: {identity}")


def workspace_registration(config_path, python):
    if not config_path:
        return {}, {"schema_version": "2.0", "workspaces": []}
    config = absolute(config_path)
    before = config.read_bytes()
    # Safe data parsing only, using the explicit environment; no project imports.
    value = parse_yaml_data(python, {"config": before.decode("utf-8")})["config"]
    if not isinstance(value, dict):
        raise InstallError("INVALID_WORKSPACE_CONFIG")
    identity = value.get("workspace_id", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", identity):
        raise InstallError("INVALID_WORKSPACE_ID")
    if value.get("schema_version") != "2.0" or value.get("knowledge_roots") != {
        "wifi": "aiotbot-knowledge-wifi-mp"
    }:
        raise InstallError("INVALID_WORKSPACE_MAPPING")
    lock = config.parent / "aiotbot-knowledge-wifi-mp/governance/framework.lock.yaml"
    no_links(lock)
    lock_bytes = lock.read_bytes()
    if config.read_bytes() != before or lock.read_bytes() != lock_bytes:
        raise InstallError("WORKSPACE_CHANGED_DURING_INSTALL")
    digest = sha(lock_bytes)
    return {identity: {"config": str(config), "rules_digest": digest}}, {
        "schema_version": "2.0",
        "workspaces": [
            {
                "workspace_id": identity,
                "config_path": str(config),
                "rules_digest": digest,
            }
        ],
    }


def install(source_root, destination, python_path, workspace_config=None):
    source = absolute(source_root)
    destination = absolute(destination, exists=False)
    python = absolute(python_path)
    if not python.is_file():
        raise InstallError("INTERPRETER_NOT_FILE")
    if destination.exists():
        raise InstallError("DESTINATION_EXISTS: choose a new isolated destination")
    if (
        source == destination
        or source in destination.parents
        or destination in source.parents
    ):
        raise InstallError("DESTINATION_OVERLAPS_SOURCE")
    packages = {}
    pins = {}
    for identity in SKILLS:
        files = package_files(source / "skills/common/knowledge" / identity)
        for name, version in dependencies(files).items():
            if name in pins and pins[name] != version:
                raise InstallError("CONFLICTING_DEPENDENCY_LOCKS")
            pins[name] = version
        packages[identity] = files
    templates = {}
    for identity in WORKFLOWS:
        package = source / "workflows/common/knowledge" / identity
        no_links(package)
        templates[identity] = {}
        for name in ("workflow.yaml", "layouts.yaml"):
            path = package / name
            no_links(path)
            templates[identity][name] = public_bytes(path.read_bytes(), path.name)
    validate_interpreter(python, pins)
    validate_metadata(python, packages, templates)
    workspaces, registry = workspace_registration(workspace_config, python)
    destination.parent.mkdir(parents=True, exist_ok=True)
    no_links(destination.parent)
    staging = Path(tempfile.mkdtemp(prefix=".factum-install-", dir=destination.parent))
    try:
        os.chmod(staging, 0o700)
        skills = {}
        manifest = {}
        for identity, files in packages.items():
            relative = Path("config/skills") / identity
            for ref, data in files.items():
                path = staging / relative / ref
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                manifest[(relative / ref).as_posix()] = sha(data)
            skills[identity] = {
                "root": str(destination / relative),
                "entry": "scripts/cli.py",
                "python": str(python),
                "package_digest": package_digest(files),
            }
        for identity, files in templates.items():
            for ref, data in files.items():
                relative = Path("config/workflow-templates") / identity / ref
                path = staging / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                manifest[relative.as_posix()] = sha(data)
        outputs = {
            "catalog.json": {
                "schema_version": "2.0",
                "skills": skills,
                "workspaces": workspaces,
                "commands": COMMANDS,
            },
            "workspace-registry.json": registry,
            "install-manifest.json": {
                "schema_version": "2.0",
                "files": manifest,
                "limitations": [
                    "Installation is not host registration or Workflow runtime acceptance.",
                    "OS access control and full OpenFlow runtime acceptance are external checks.",
                ],
            },
        }
        for name, value in outputs.items():
            path = staging / name
            path.write_bytes(canonical(value) + b"\n")
            os.chmod(path, 0o600)
        if destination.exists():
            raise InstallError("DESTINATION_EXISTS")
        # On Windows rename cannot replace an existing directory; new destinations only.
        staging.rename(destination)
        return destination / "catalog.json"
    finally:
        if staging.exists():
            if (
                staging.resolve().parent != destination.parent
                or not staging.name.startswith(".factum-install-")
            ):
                raise InstallError("UNSAFE_STAGING_CLEANUP")
            no_links(staging)
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--workspace-config")
    args = parser.parse_args()
    try:
        catalog = install(
            args.source_root, args.destination, args.python, args.workspace_config
        )
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps({"status": "installed", "catalog": str(catalog)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
