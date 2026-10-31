"""Install runtime dependencies, remove old capability packages, then copy new ones."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import stat
import subprocess
import sys


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--skills-root", type=Path, default=Path.home() / ".openflow/config/skills")
    parser.add_argument("--workflows-root", type=Path, default=Path.home() / ".openflow/config/workflow-templates")
    parser.add_argument("--python", default=sys.executable, help="Python environment receiving pip dependencies")
    args = parser.parse_args(argv)
    source = args.source_root.expanduser().resolve()
    targets = (
        ("Skills", source / "skills/common/knowledge", args.skills_root.expanduser().resolve(), "SKILL.md"),
        ("Workflow templates", source / "workflows/common/knowledge",
         args.workflows_root.expanduser().resolve(), "workflow.yaml"),
    )
    requirements = source / "himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt"
    try:
        source_roots = [packages.resolve() for _, packages, _, _ in targets]
        copied, packages_to_copy = [], []
        for label, packages, destination, marker in targets:
            count = 0
            for package in sorted(packages.iterdir()):
                if package.is_dir() and (package / marker).is_file():
                    target = replacement_target(destination, package.name, source_roots)
                    if any(root.is_relative_to(target) for _, _, root, _ in targets):
                        raise ValueError(f"Package target contains an installation directory: {target}")
                    packages_to_copy.append((package, destination, target))
                    count += 1
            copied.append((label, count, destination))

        # Install first: dependency failure must leave old capabilities intact.
        subprocess.run([args.python, "-m", "pip", "install", "-r", str(requirements)], check=True)
        print(f"Installed runtime dependencies with {args.python}")

        removed = 0
        for _, destination, target in packages_to_copy:
            replacement_target(destination, target.name, source_roots)
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1
            elif target.exists():
                target.unlink()
                removed += 1
        print(f"Removed {removed} existing packages")

        for package, _, target in packages_to_copy:
            shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    for label, count, destination in copied:
        print(f"Copied {count} {label} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
