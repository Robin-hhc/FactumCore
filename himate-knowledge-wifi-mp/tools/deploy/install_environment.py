"""Prepare a knowledge-owned runtime, optionally registering final Agent packages.

Uses the machine's pip configuration by default. --wheelhouse is strictly offline;
--index-url explicitly selects the company's package index. No system packages,
Python installation, host registration, service, or knowledge ingestion is changed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from urllib.parse import urlsplit

import install_catalog as catalog


def runtime_pins(source):
    """Read the knowledge-owned lock; installed Skills may live anywhere."""
    source = Path(source).absolute()
    # Bootstrap must work before PyYAML exists. Prefer this tool's explicit
    # knowledge root over any unrelated flat sibling; registration later
    # checks its actual project mapping with the newly locked runtime.
    own_domain = Path(__file__).absolute().parents[2]
    if source == own_domain or source in own_domain.parents:
        lock = own_domain / "tools/deploy/requirements.runtime.lock.txt"
    else:
        lock = source / "himate-knowledge-wifi-mp/tools/deploy/requirements.runtime.lock.txt"
        if not lock.is_file():
            lock = source / "tools/deploy/requirements.runtime.lock.txt"
    catalog.no_links(lock)
    if not lock.is_file():
        raise catalog.InstallError("RUNTIME_LOCK_MISSING")
    pins = {}
    for name, version in catalog.dependencies({"requirements.lock.txt": lock.read_bytes()}).items():
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in pins and pins[normalized] != version:
            raise catalog.InstallError(f"CONFLICTING_DEPENDENCY_LOCKS: {normalized}")
        pins[normalized] = version
    if not pins:
        raise catalog.InstallError("EMPTY_RUNTIME_LOCK")
    return dict(sorted(pins.items()))


def project_source(knowledge_root):
    """Bootstrap discovery only; registration later validates the exact mapping."""
    domain = Path(knowledge_root).absolute()
    catalog.no_links(domain)
    candidates = [parent / "config.yml" for parent in domain.parents if (parent / "config.yml").is_file()]
    for config in candidates:
        catalog.no_links(config)
    if len(candidates) != 1:
        raise catalog.InstallError("WORKSPACE_CONFIG_REQUIRED: supply --workspace-config for missing or ambiguous project roots")
    return candidates[0].parent


def default_destination(source):
    workspace = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.home() / ".factumcore" / workspace / f"{stamp}-{uuid.uuid4().hex[:8]}"


def run(command, label):
    print(label, flush=True)
    # Do not echo commands: a package index may be supplied through private config.
    subprocess.run(command, check=True)


def validate_pip_destination(python):
    """Keep index/auth configuration, reject options that redirect installation.

    Capture the output because it can contain private index credentials. Inspect
    only option names, and never echo configuration values.
    """
    result = subprocess.run(
        [str(python), "-m", "pip", "config", "list"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise catalog.InstallError("PIP_CONFIG_UNREADABLE: check the machine's pip configuration")
    for line in result.stdout.splitlines():
        key, separator, _ = line.partition("=")
        option = key.rsplit(".", 1)[-1].replace("_", "-").lower()
        if separator and option in {"target", "prefix", "root", "python"}:
            raise catalog.InstallError(f"PIP_DESTINATION_OVERRIDE: remove {key} before private installation")


def prepare(source, destination, *, wheelhouse=None, index_url=None,
            skills_root=None, workflows_root=None, workspace_config=None):
    if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12)}:
        raise catalog.InstallError("PYTHON_VERSION: use existing Python 3.10-3.12")
    for name in ("PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON"):
        if os.environ.get(name):
            raise catalog.InstallError(f"PIP_DESTINATION_OVERRIDE: unset {name} before private installation")
    source = catalog.absolute(str(source))
    destination = catalog.absolute(str(destination), exists=False)
    if destination.exists():
        raise catalog.InstallError("DESTINATION_EXISTS: select a new directory; existing installations are preserved")
    if source == destination or source in destination.parents or destination in source.parents:
        raise catalog.InstallError("DESTINATION_OVERLAPS_SOURCE: runtime must be outside the project")
    if bool(skills_root) != bool(workflows_root):
        raise catalog.InstallError("CAPABILITY_ROOTS_REQUIRED: supply both skills-root and workflows-root")
    if skills_root:
        skills_root = catalog.absolute(str(Path(skills_root).absolute()))
        workflows_root = catalog.absolute(str(Path(workflows_root).absolute()))
        if any(destination == path or path in destination.parents or destination in path.parents
               for path in (skills_root, workflows_root)):
            raise catalog.InstallError("DESTINATION_OVERLAPS_SOURCE")
    if wheelhouse and index_url:
        raise catalog.InstallError("Choose either --wheelhouse or --index-url")
    if wheelhouse:
        wheelhouse = catalog.absolute(str(Path(wheelhouse).absolute()))
        if not wheelhouse.is_dir():
            raise catalog.InstallError("WHEELHOUSE_NOT_DIRECTORY")
    if index_url:
        parsed = urlsplit(index_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise catalog.InstallError("INDEX_URL: provide an HTTP(S) package index")
        if parsed.username or parsed.password:
            raise catalog.InstallError("INDEX_CREDENTIALS: configure authentication in pip, not command arguments")
    pins = runtime_pins(source)
    config = catalog.absolute(str(Path(workspace_config).absolute())) if workspace_config else source / "config.yml"
    if config.parent != source:
        raise catalog.InstallError("WORKSPACE_CONFIG_MISMATCH: source-root must be the config directory")
    catalog.no_links(config)
    if not config.is_file():
        raise catalog.InstallError("WORKSPACE_CONFIG_MISSING")
    destination.mkdir(parents=True, mode=0o700)
    catalog.no_links(destination)
    lock = destination / "requirements.runtime.lock.txt"
    lock.write_text("".join(f"{name}=={version}\n" for name, version in pins.items()), encoding="utf-8")
    venv = destination / "venv"
    # The catalog intentionally rejects symlinked interpreters on either OS.
    run([sys.executable, "-I", "-m", "venv", "--copies", str(venv)], "Creating private virtual environment...")
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    validate_pip_destination(python)
    command = [str(python), "-m", "pip", "--disable-pip-version-check", "install", "--no-user", "--prefix", str(venv),
               "--only-binary=:all:", "-r", str(lock)]
    if wheelhouse:
        command.extend(["--no-index", "--find-links", str(wheelhouse)])
    elif index_url:
        command.extend(["--index-url", index_url])
    run(command, f"Installing {len(pins)} locked runtime packages...")
    run([str(python), "-m", "pip", "--disable-pip-version-check", "check"], "Checking dependency consistency...")
    catalog.validate_interpreter(python, pins)
    catalog_path = None
    own_domain = Path(__file__).absolute().parents[2]
    registry = None
    if source == own_domain or source in own_domain.parents:
        _, registry = catalog.workspace_registration(config, python, expected_root=own_domain)
    if skills_root:
        installed = destination / "registration"
        catalog_path = catalog.install(source, installed, python, config,
                                       skills_root=skills_root, workflows_root=workflows_root,
                                       register_existing=True)
        registry_path = installed / "workspace-registry.json"
    else:
        if registry is None:
            _, registry = catalog.workspace_registration(config, python)
        registry_path = destination / "workspace-registry.json"
        registry_path.write_bytes(catalog.canonical(registry) + b"\n")
    report = {
        "status": "installed" if catalog_path else "runtime_ready",
        "installation": str(destination / "installation.json"),
        "python": str(python),
        "python_version": sys.version.split()[0],
        "catalog": str(catalog_path) if catalog_path else None,
        "workspace_registry": str(registry_path),
        "skills": str(skills_root) if skills_root else None,
        "workflows": str(workflows_root) if workflows_root else None,
        "requirements": str(lock),
        "runtime_packages": pins,
        "next_step": ("Use this catalog and Python with the Agent's registered capability directories."
                      if catalog_path else "Move capabilities into their final Agent directories, then run install_catalog.py --register-existing with this Python."),
    }
    (destination / "installation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", help="project directory containing the workspace config")
    parser.add_argument("--workspace-config", help="explicit actual config path; resolves nested deployment without guessing")
    parser.add_argument("--destination", help="new private directory outside the source project")
    parser.add_argument("--skills-root", help="final Agent directory containing the hs-* Skill packages")
    parser.add_argument("--workflows-root", help="final Agent directory containing hs-knowledge-ingest")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--wheelhouse", help="offline wheel directory for this OS, CPU and Python")
    sources.add_argument("--index-url", help="internal pip index; otherwise uses existing pip configuration")
    args = parser.parse_args()
    try:
        source = (Path(args.source_root).absolute() if args.source_root else
                  Path(args.workspace_config).absolute().parent if args.workspace_config else
                  project_source(Path(__file__).absolute().parents[2]))
        destination = Path(args.destination).absolute() if args.destination else default_destination(source)
        report = prepare(source, destination, wheelhouse=args.wheelhouse, index_url=args.index_url,
                         skills_root=args.skills_root, workflows_root=args.workflows_root,
                         workspace_config=args.workspace_config)
    except (catalog.InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        # CalledProcessError includes the command, potentially containing a private
        # index URL. Print the stage failure only; pip supplies its own diagnostics.
        if isinstance(exc, subprocess.CalledProcessError):
            print(f"INSTALL_FAILED: subprocess exit {exc.returncode}; no completed installation was published", file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        if "destination" in locals():
            print(f"Installation directory: {destination}. A failed private directory can be inspected; rerun with a new directory.", file=sys.stderr)
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
