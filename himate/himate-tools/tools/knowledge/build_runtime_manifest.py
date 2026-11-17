"""Explicit developer operation: freeze the tool's CLI bytes before validation.

Normal commands and acceptance tests never regenerate an invalid manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build(root, version="1.0.0"):
    root = Path(root).resolve(strict=True)
    runtime = root / "runtime"
    files = {}
    for path in sorted(runtime.rglob("*")):
        relative = path.relative_to(runtime)
        if "__pycache__" in relative.parts:
            continue
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Linked runtime paths cannot be frozen: " + relative.as_posix())
        if path.is_file() and (path.suffix == ".py" or path.name.endswith(".lock.txt")):
            files[relative.as_posix()] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    entrypoint = root / "knowledge.py"
    if entrypoint.is_symlink() or not entrypoint.is_file():
        raise ValueError("Missing regular entrypoint: knowledge.py")
    entries = {"knowledge.py": {"sha256": hashlib.sha256(entrypoint.read_bytes()).hexdigest()}}
    reference = "governance/framework.lock.yaml"
    path = root / reference
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing regular framework lock: " + reference)
    assets = {reference: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    value = {"schema_version": "1.1", "version": version, "files": files,
             "entrypoints": entries, "assets": assets}
    output = runtime / "manifest.json"
    output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", "--knowledge-root", dest="tool_root", type=Path, required=True)
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()
    manifest = build(args.tool_root, args.version)
    print(json.dumps({"version": manifest["version"], "files": len(manifest["files"]),
                      "entrypoints": len(manifest["entrypoints"])}))
