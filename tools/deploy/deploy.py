"""Copy knowledge Skills and install runtime dependencies with the chosen Python."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--skills-root", type=Path, default=Path.home() / ".openflow/config/skills")
    parser.add_argument("--python", default=sys.executable, help="Python environment receiving pip dependencies")
    args = parser.parse_args(argv)
    source = args.source_root.expanduser().resolve()
    destination = args.skills_root.expanduser().resolve()
    packages = source / "skills/common/knowledge"
    requirements = source / "himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt"
    try:
        # Active packages own instructions and references. Existing unrelated
        # target directories stay untouched; there is no migration or mirror.
        copied = []
        for package in sorted(packages.iterdir()):
            if package.is_dir() and (package / "SKILL.md").is_file():
                shutil.copytree(package, destination / package.name, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                copied.append(package.name)
        subprocess.run([args.python, "-m", "pip", "install", "-r", str(requirements)], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Copied {len(copied)} Skills to {destination}")
    print(f"Installed runtime dependencies with {args.python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
