"""Resolve execution settings and account state."""

import json
import os
from pathlib import Path


PIP_LOCATION_OPTIONS = {"target", "prefix", "root", "python"}


def child_environment():
    ignored = {"PIP_" + option.upper() for option in PIP_LOCATION_OPTIONS}
    ignored.update({"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"})
    return {key: value for key, value in os.environ.items() if key.upper() not in ignored}


def managed_home(tool_root: Path) -> Path:
    try:
        installation = json.loads((tool_root / ".install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        installation = None
    if isinstance(installation, dict) and installation.get("package") == "@himate/knowledge-cli":
        return tool_root
    return Path.home() / ".himate" / "knowledge"
