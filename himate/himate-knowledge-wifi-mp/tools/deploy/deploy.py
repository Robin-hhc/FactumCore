"""Install dependencies and capabilities, then copy project entry templates."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import stat
import subprocess
import sys


OCR_PREPARE = """from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "governance"))
from contracts.document_parser import OCR_MODEL_FILES, _models, safe_path
from contracts.validation import ContractError


def inspect_tree(directory):
    if directory.exists():
        if not directory.is_dir():
            raise RuntimeError(f"Expected model directory: {directory}")
        for path in directory.rglob("*"):
            safe_path(directory, path.relative_to(directory).as_posix())


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise RuntimeError(f"Duplicate model manifest field: {key}")
        value[key] = item
    return value


def verify_file(path, row):
    if not path.is_file() or path.stat().st_size != row["bytes"]:
        raise RuntimeError(f"Bundled model size mismatch or file missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != row["sha256"]:
        raise RuntimeError(f"Bundled model digest mismatch: {path}")


def install_bundle(options):
    base = safe_path(root, "tools/deploy/models")
    if not base.exists():
        return False
    bundle = safe_path(base, "docling-cpu")
    if not bundle.exists():
        return False
    inspect_tree(base)
    if not bundle.is_dir():
        raise RuntimeError(f"Expected bundled model directory: {bundle}")
    manifest = json.loads(safe_path(base, "manifest.json").read_text(encoding="utf-8"),
                          object_pairs_hook=unique_object)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0"
            or manifest.get("model_set") != "docling-cpu"
            or not isinstance(manifest.get("files"), list) or not manifest["files"]):
        raise RuntimeError("Invalid bundled model manifest")
    rows, identities = {}, set()
    for row in manifest["files"]:
        if not isinstance(row, dict):
            raise RuntimeError("Invalid bundled model entry")
        reference = row.get("path")
        safe_path(bundle, reference)
        if reference.casefold() in identities:
            raise RuntimeError(f"Duplicate bundled model path: {reference}")
        if (type(row.get("bytes")) is not int or row["bytes"] <= 0
                or not isinstance(row.get("sha256"), str)
                or not re.fullmatch("[0-9a-f]{64}", row["sha256"])):
            raise RuntimeError(f"Invalid bundled model size or digest: {reference}")
        identities.add(reference.casefold())
        rows[reference] = row
    if set(rows) != set(OCR_MODEL_FILES):
        raise RuntimeError("Bundled manifest must contain the complete required model set")
    if (type(manifest.get("total_bytes")) is not int
            or manifest["total_bytes"] != sum(row["bytes"] for row in rows.values())):
        raise RuntimeError("Bundled model total size mismatch")
    directory = safe_path(root, options["models_path"], ["artifacts/models"])
    inspect_tree(directory)
    targets = []
    for reference, row in rows.items():
        source = safe_path(bundle, reference)
        target = safe_path(root, options["models_path"] + "/" + reference, [options["models_path"]])
        verify_file(source, row)
        targets.append((source, target, row))
    for source, target, row in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        safe_path(root, target.relative_to(root).as_posix(), [options["models_path"]])
        descriptor, name = tempfile.mkstemp(prefix=".model-", suffix=".tmp", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as destination, source.open("rb") as stream:
                shutil.copyfileobj(stream, destination, length=1024 * 1024)
                destination.flush()
                os.fsync(destination.fileno())
            shutil.copymode(source, temporary)
            verify_file(temporary, row)
            safe_path(root, target.relative_to(root).as_posix(), [options["models_path"]])
            os.replace(temporary, target)
            verify_file(target, row)
        finally:
            temporary.unlink(missing_ok=True)
    _models(root, options)
    print(f"Installed bundled CPU OCR models at {directory}")
    return True


options = {"models_path": "artifacts/models/docling-cpu"}
try:
    directory = _models(root, options)
except ContractError as error:
    if error.code != "PARSER_MODELS_REQUIRED":
        raise
    if install_bundle(options):
        sys.exit(0)
    if sys.argv[2] != "download":
        raise RuntimeError(
            "CPU OCR models are missing or incomplete at " + str(root / options["models_path"])
            + "; preinstall the models offline or explicitly use --download-models. "
            "No model download was attempted.") from error
    directory = safe_path(root, options["models_path"], ["artifacts/models"])
    directory.mkdir(parents=True, exist_ok=True)
    inspect_tree(directory)
    from docling.utils.model_downloader import download_models
    download_models(output_dir=directory, with_layout=True, with_tableformer=True,
                    with_code_formula=False, with_picture_classifier=False,
                    with_rapidocr=True, rapidocr_models=["onnxruntime:ch"], progress=False, force=True)
    directory = _models(root, options)
    print(f"Prepared local CPU OCR models at {directory}")
else:
    print(f"Reused complete local CPU OCR models at {directory}")
"""


def replacement_target(destination, name, source_roots):
    """Limit deletion to a direct package child, without following reparse points."""
    target = destination / name
    if target.resolve().parent != destination:
        raise ValueError(f"Package target escapes its installation directory: {target}")
    try:
        info = target.lstat()
    except FileNotFoundError:
        info = None
    if info and (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError(f"Package target must not be a link or junction: {target}")
    if any(target.is_relative_to(root) or root.is_relative_to(target) for root in source_roots):
        raise ValueError(f"Package target overlaps distribution sources: {target}")
    return target


def regular_file(path, *, required=False):
    """Do not follow an entry-file link when reading templates or overwriting."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise ValueError(f"Required distribution file is missing: {path}") from None
        return False
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Entry must be a regular file, not a link or directory: {path}")
    return True


def installation_directory(value, default, label, non_interactive):
    if value is None:
        answer = "" if non_interactive else input(f"{label} [{default}]: ").strip()
        value = Path(answer) if answer else default
    return value.expanduser().resolve()


def overwrite_entry(path, non_interactive):
    if non_interactive:
        return True
    while True:
        answer = input(f"Overwrite {path}? [Y/n]: ").strip().casefold()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Enter y or n; press Enter to overwrite.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Knowledge package containing runtime, skills, workflows and entry templates")
    parser.add_argument("--skills-root", type=Path, help="OpenFlow Skill installation directory")
    parser.add_argument("--cac-skills-root", type=Path, help="CAC Skill installation directory")
    parser.add_argument("--workflows-root", type=Path, help="OpenFlow Workflow template installation directory")
    parser.add_argument("--python", default=sys.executable, help="Python environment receiving pip dependencies")
    parser.add_argument("--download-models", action="store_true",
                        help="Explicitly allow downloading missing CPU OCR models; otherwise require offline models")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Use default directories and overwrite existing project entry files without prompting")
    args = parser.parse_args(argv)
    source = args.source_root.expanduser().resolve()
    try:
        targets = (
            ("OpenFlow Skills", source / "skills", installation_directory(
                args.skills_root, Path.home() / ".openflow/config/skills", "OpenFlow Skill directory",
                args.non_interactive), "SKILL.md"),
            ("CAC Skills", source / "skills", installation_directory(
                args.cac_skills_root, Path.home() / ".cac/skills", "CAC Skill directory",
                args.non_interactive), "SKILL.md"),
            ("OpenFlow Workflow templates", source / "workflows", installation_directory(
                args.workflows_root, Path.home() / ".openflow/config/workflow-templates",
                "OpenFlow Workflow template directory", args.non_interactive), "workflow.yaml"),
        )
        requirements = source / "runtime/requirements.lock.txt"
        regular_file(requirements, required=True)
        # The manifest root is a filesystem relationship, not a Git checkout.
        project_root = (source / "../..").resolve()
        entries = []
        for original, name in (("config.yml", "config.yml"), ("AGENTS-code-root.md", "AGENTS.md")):
            template, target = source / original, project_root / name
            regular_file(template, required=True)
            exists = regular_file(target)
            entries.append((template, target, not exists or overwrite_entry(target, args.non_interactive)))

        source_roots = [source]
        copied, packages_to_copy = [], {}
        for label, packages, destination, marker in targets:
            count = 0
            for package in sorted(packages.iterdir()):
                if package.is_dir() and (package / marker).is_file():
                    target = replacement_target(destination, package.name, source_roots)
                    if any(root.is_relative_to(target) for _, _, root, _ in targets):
                        raise ValueError(f"Package target contains an installation directory: {target}")
                    if target in packages_to_copy and packages_to_copy[target][0] != package:
                        raise ValueError(f"Different capability packages share one target: {target}")
                    packages_to_copy[target] = (package, destination)
                    count += 1
            copied.append((label, count, destination))

        # Prepare first: dependency or model failure must leave old capabilities intact.
        subprocess.run([args.python, "-m", "pip", "install", "-r", str(requirements)], check=True)
        print(f"Installed runtime dependencies with {args.python}")
        subprocess.run([args.python, "-c", OCR_PREPARE, str(source),
                        "download" if args.download_models else "local"], check=True)

        removed = 0
        for target, (_, destination) in packages_to_copy.items():
            replacement_target(destination, target.name, source_roots)
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1
            elif target.exists():
                target.unlink()
                removed += 1
        print(f"Removed {removed} existing packages")

        for target, (package, _) in packages_to_copy.items():
            shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for template, target, replace in entries:
            if replace:
                regular_file(target)
                shutil.copy2(template, target)
                print(f"Copied {template.name} to {target}")
            else:
                print(f"Kept existing {target}")
    except (OSError, ValueError, EOFError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    for label, count, destination in copied:
        print(f"Copied {count} {label} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
