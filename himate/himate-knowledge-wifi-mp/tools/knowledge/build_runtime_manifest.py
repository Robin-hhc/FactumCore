"""Explicit developer operation: freeze repository CLI bytes before validation.

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
    entries = {}
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing regular entrypoint: " + name)
        entries[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    value = {"schema_version": "1.0", "version": version, "files": files, "entrypoints": entries}
    output = runtime / "manifest.json"
    output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", type=Path, required=True)
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()
    manifest = build(args.knowledge_root, args.version)
    print(json.dumps({"version": manifest["version"], "files": len(manifest["files"]),
                      "entrypoints": len(manifest["entrypoints"])}))
