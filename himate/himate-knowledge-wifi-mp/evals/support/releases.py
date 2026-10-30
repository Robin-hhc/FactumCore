"""Select an explicit, verified historical audit without reviving current Skills.

Normal acceptance always uses the current repository CLI. The sole historical
adapter is the documented frozen dbox release, selected by a human-supplied
checkout and manifest; its own helper and code execute only after verification.
"""

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys


LEGACY_RELEASE = "f8a84153a1ce4c23082f70d7de55a2c1f65523f8"
KNOWLEDGE = "himate-knowledge-wifi-mp"
CURRENT_KNOWLEDGE = "himate/" + KNOWLEDGE


def _object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate release manifest field: " + str(name))
        result[name] = value
    return result


def _regular(root, reference):
    if not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference:
        raise ValueError("Unsafe release path")
    parts = PurePosixPath(reference).parts
    if reference.startswith("/") or "/".join(parts) != reference or any(p in {".", ".."} for p in parts):
        raise ValueError("Unsafe release path")
    path = root
    for part in parts:
        path /= part
        if path.is_symlink() or path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked release input: " + reference)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("Missing release input: " + reference)
    return path


def _verify(root, path, expected_commit):
    if not path.is_file():
        raise ValueError("An explicit release audit requires its manifest")
    manifest = json.loads(path.read_bytes(), object_pairs_hook=_object)
    if not isinstance(manifest, dict) or manifest.get("commit", manifest.get("baseline")) != expected_commit:
        raise ValueError("Release manifest commit mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Release manifest has no source closure")
    for name, expected in files.items():
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid release digest")
        if hashlib.sha256(_regular(root, name).read_bytes()).hexdigest() != expected:
            raise ValueError("Release source digest mismatch: " + name)
    for relative in ("skills/common/knowledge", KNOWLEDGE + "/evals", KNOWLEDGE + "/governance", KNOWLEDGE + "/runtime"):
        for source in (root / relative).rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            if source.suffix == ".py" or source.name.startswith("requirements") or source.name in {"manifest.json", "framework.lock.yaml"}:
                name = source.relative_to(root).as_posix()
                _regular(root, name)
                if name not in files:
                    raise ValueError("Unmanifested release executable input: " + name)
    return manifest


@dataclass(frozen=True)
class ReleaseSelection:
    root: Path
    layout: str
    helper: Path
    manifest: dict
    explicit: bool
    knowledge_root: Path

    def command(self, knowledge_root, slug, *, skills=None):
        stage = slug.removeprefix("hs-").removeprefix("knowledge-")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", stage):
            raise ValueError("Invalid audit stage")
        if self.layout == "repository_cli":
            return [sys.executable, "-X", "utf8", str(Path(knowledge_root) / "knowledge.py"), stage, "--json"]
        if not self.explicit or self.layout != "legacy_skill" or skills is None:
            raise ValueError("Legacy execution requires an explicit verified release")
        package = "hs-knowledge-" + stage
        prefix = "skills/common/knowledge/" + package + "/"
        entry = prefix + "scripts/cli.py"
        if entry not in self.manifest["files"]:
            raise ValueError("The selected release has no requested stage")
        installed = Path(skills).resolve(strict=True)
        for name, expected in self.manifest["files"].items():
            if name.startswith(prefix) and (name.endswith(".py") or PurePosixPath(name).name.startswith("requirements")):
                path = _regular(installed, name.removeprefix("skills/common/knowledge/"))
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError("Copied release executable differs from its manifest: " + name)
        return [sys.executable, "-X", "utf8", str(installed / package / "scripts/cli.py")]


def select_release(current_root, *, checkout=None, manifest_path=None, expected_commit=LEGACY_RELEASE):
    explicit = checkout is not None
    root = Path(checkout if explicit else current_root).resolve(strict=True)
    manifest = _verify(root, Path(manifest_path) if manifest_path else root.parent / "release-manifest.json", expected_commit) if explicit else {}
    knowledge = KNOWLEDGE if explicit else CURRENT_KNOWLEDGE
    modern = knowledge + "/evals/support/manual.py"
    legacy = KNOWLEDGE + "/evals/tests/test_manual_skills.py"
    if (root / knowledge / "runtime/manifest.json").is_file():
        _regular(root, knowledge + "/knowledge.py")
        helper = _regular(root, modern)
        layout = "repository_cli"
    elif explicit and expected_commit == LEGACY_RELEASE:
        helper = _regular(root, legacy)
        _regular(root, "skills/common/knowledge/hs-knowledge-source/scripts/cli.py")
        layout = "legacy_skill"
    else:
        raise ValueError("The current checkout requires its repository CLI layout")
    if explicit and helper.relative_to(root).as_posix() not in manifest["files"]:
        raise ValueError("Release helper is not in the manifest")
    return ReleaseSelection(root, layout, helper, manifest, explicit, root / knowledge)


def load_manual(selection, namespace):
    suffix = hashlib.sha256(str(selection.root).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(namespace + "_" + suffix, selection.helper)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module
