"""Locate the account's tool state."""

import json
from pathlib import Path


def managed_home(tool_root: Path) -> Path:
    try:
        installation = json.loads((tool_root / ".install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        installation = None
    if isinstance(installation, dict) and installation.get("package") == "@himate/knowledge-cli":
        return tool_root
    return Path.home() / ".himate" / "knowledge"
