"""Locate the Python environment used by the manifest-verified CLI."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


def managed_home(tool_root: Path) -> Path:
    try:
        installation = json.loads((tool_root / ".install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        installation = None
    if isinstance(installation, dict) and installation.get("package") == "@himate/knowledge-cli":
        return tool_root
    return Path.home() / ".himate" / "knowledge"


def managed_python(tool_root: Path) -> Path:
    venv = managed_home(tool_root) / ".venv"
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def selected_python(tool_root: Path, *, explicit_venv: bool = True) -> Path | None:
    current_python = Path(sys.executable)
    if explicit_venv:
        if sys.prefix != sys.base_prefix:
            return current_python
        # Python 3.10–3.12 does not set the venv prefix when explicitly run with -S.
        if sys.flags.no_site and (current_python.parent.parent / "pyvenv.cfg").is_file():
            return current_python

    python = managed_python(tool_root)
    directory = python.parent.parent
    try:
        metadata = directory.lstat()
    except OSError:
        return None
    if (not stat.S_ISDIR(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        return None
    if not python.is_file() or not (directory / "pyvenv.cfg").is_file():
        return None

    # Keep the invoked path lexical so that POSIX Python reads this venv's configuration.
    try:
        probe = subprocess.run(
            [str(python), "-I", "-B", "-c", "import sys; sys.exit(not ("
             "sys.prefix != sys.base_prefix and (3, 10) <= sys.version_info[:2] <= (3, 12)))"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return python if probe.returncode == 0 else None
