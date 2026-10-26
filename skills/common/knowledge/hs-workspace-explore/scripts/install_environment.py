"""Prepare locked dependencies and a private catalog with existing Python.

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
    """Union the real package locks, rejecting aliases with conflicting pins."""
    pins = {}
    for identity in catalog.SKILLS:
        files = catalog.package_files(source / "skills/common/knowledge" / identity)
        for name, version in catalog.dependencies(files).items():
            normalized = re.sub(r"[-_.]+", "-", name).lower()
            if normalized in pins and pins[normalized] != version:
                raise catalog.InstallError(f"CONFLICTING_DEPENDENCY_LOCKS: {normalized}")
            pins[normalized] = version
    return dict(sorted(pins.items()))


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


def prepare(source, destination, *, wheelhouse=None, index_url=None):
    if sys.version_info[:2] not in {(3, 11), (3, 12)}:
        raise catalog.InstallError("PYTHON_VERSION: use existing Python 3.11 (3.12 is also supported)")
    for name in ("PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON"):
        if os.environ.get(name):
            raise catalog.InstallError(f"PIP_DESTINATION_OVERRIDE: unset {name} before private installation")
    source = catalog.absolute(str(source))
    destination = catalog.absolute(str(destination), exists=False)
    if destination.exists():
        raise catalog.InstallError("DESTINATION_EXISTS: select a new directory; existing installations are preserved")
    if source == destination or source in destination.parents or destination in source.parents:
        raise catalog.InstallError("DESTINATION_OVERLAPS_SOURCE: runtime must be outside the project")
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
    config = source / "config.yml"
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
    installed = destination / "capabilities"
    catalog_path = catalog.install(source, installed, python, config)
    report = {
        "status": "installed",
        "installation": str(destination / "installation.json"),
        "python": str(python),
        "python_version": sys.version.split()[0],
        "catalog": str(catalog_path),
        "workspace_registry": str(installed / "workspace-registry.json"),
        "skills": str(installed / "config/skills"),
        "workflows": str(installed / "config/workflow-templates"),
        "requirements": str(lock),
        "runtime_packages": pins,
        "next_step": "Register these skills/workflows and this Python interpreter with your internal Agent.",
    }
    (destination / "installation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[5]))
    parser.add_argument("--destination", help="new private directory outside the source project")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--wheelhouse", help="offline wheel directory for this OS, CPU and Python")
    sources.add_argument("--index-url", help="internal pip index; otherwise uses existing pip configuration")
    args = parser.parse_args()
    source = Path(args.source_root).absolute()
    destination = Path(args.destination).absolute() if args.destination else default_destination(source)
    try:
        report = prepare(source, destination, wheelhouse=args.wheelhouse, index_url=args.index_url)
    except (catalog.InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        # CalledProcessError includes the command, potentially containing a private
        # index URL. Print the stage failure only; pip supplies its own diagnostics.
        if isinstance(exc, subprocess.CalledProcessError):
            print(f"INSTALL_FAILED: subprocess exit {exc.returncode}; no completed installation was published", file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        print(f"Installation directory: {destination}. A failed private directory can be inspected; rerun with a new directory.", file=sys.stderr)
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
