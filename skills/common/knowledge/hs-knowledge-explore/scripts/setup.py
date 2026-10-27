"""Prepare the current global Python and read the project's knowledge entry.

No virtual environment, catalog, registry or machine binding is created.
Optional SSH connection data lives in this Skill's own config.env; the Agent
and its harness perform the connection and execution checks.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys


SKILL = Path(__file__).absolute().parents[1]


def read_pins(path):
    pins = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise ValueError("Invalid dependency lock line")
        pins[match[1]] = match[2]
    return pins


def missing_packages(pins):
    missing = []
    for name, expected in pins.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            missing.append({"name": name, "required": expected, "installed": actual})
    return missing


def connection_entry():
    path = SKILL / "config.env"
    if not path.is_file():
        return None
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    if values.get("EXECUTION_MODE", "ssh") == "local" or not values.get("SSH_HOST"):
        return None
    # These are connection hints, never a shell script or executed command.
    keys = ("SSH_HOST", "SSH_USER", "SSH_PORT", "SSH_IDENTITY_FILE", "REMOTE_PROJECT_ROOT", "PYTHON")
    return {"config": str(path), **{key: values[key] for key in keys if values.get(key)}}


def project_entry(config):
    import yaml

    try:
        value = yaml.safe_load(config.read_bytes())
    except yaml.YAMLError as exc:
        raise ValueError("Cannot read config.yml as YAML: " + str(exc)) from exc
    if not isinstance(value, dict):
        raise ValueError("config.yml must contain a project mapping")
    roots = value.get("knowledge_roots")
    knowledge = roots.get("wifi") if isinstance(roots, dict) else None
    if not isinstance(knowledge, str) or not knowledge:
        raise ValueError("Set knowledge_roots.wifi in config.yml")
    return {"workspace_config": str(config), "project_root": str(config.parent),
            "knowledge_root": str((config.parent / knowledge).resolve()),
            "code_root": value.get("code_root"), "modules": value.get("modules", [])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", default="config.yml")
    parser.add_argument("--local", action="store_true", help="run on the actual execution host, bypassing SSH hints")
    parser.add_argument("--check-only", action="store_true", help="report missing dependencies without installing")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--wheelhouse", help="offline wheels for this global Python and operating system")
    sources.add_argument("--index-url", help="explicit package index; otherwise use the existing pip configuration")
    args = parser.parse_args(argv)
    try:
        ssh = None if args.local else connection_entry()
        if ssh:
            print(json.dumps({"status": "ssh_entry", "ssh": ssh,
                "next_step": "Use the harness SSH connection, then run setup --local with the server config.yml and global Python."},
                ensure_ascii=False, indent=2))
            return 0
        config = Path(args.workspace_config).expanduser().absolute()
        if not config.is_file():
            raise ValueError("Provide the actual project config.yml with --workspace-config")
        lock = SKILL / "requirements.lock.txt"
        pins = read_pins(lock)
        missing = missing_packages(pins)
        installed = False
        if missing and args.check_only:
            print(json.dumps({"status": "missing_dependencies", "python": sys.executable,
                              "missing": missing}, ensure_ascii=False, indent=2))
            return 2
        if missing:
            command = [sys.executable, "-m", "pip", "--disable-pip-version-check", "--no-cache-dir",
                       "install", "--no-user", "--only-binary=:all:", "-r", str(lock)]
            if args.wheelhouse:
                command += ["--no-index", "--find-links", str(Path(args.wheelhouse).expanduser().absolute())]
            elif args.index_url:
                command += ["--index-url", args.index_url]
            subprocess.run(command, check=True, stdout=sys.stderr)
            installed = True
            missing = missing_packages(pins)
            if missing:
                raise ValueError("Dependency installation did not complete for the current Python")
        report = {"status": "ready", "python": sys.executable,
                  "dependencies": "installed" if installed else "already_available", **project_entry(config)}
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        message = ("Dependency installation failed with exit " + str(exc.returncode)
                   if isinstance(exc, subprocess.CalledProcessError) else str(exc))
        print(json.dumps({"status": "failed", "diagnostics": [message]}, ensure_ascii=False))
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
