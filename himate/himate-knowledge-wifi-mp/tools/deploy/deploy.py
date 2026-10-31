"""Install dependencies and capabilities, then copy project entry templates."""

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


def regular_file(path, *, required=False):
    """Do not follow an entry-file link when reading templates or overwriting."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise ValueError(f"Required distribution file is missing: {path}") from None
        return False
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Entry must be a regular file, not a link or directory: {path}")
    return True


def installation_directory(value, default, label, non_interactive):
    if value is None:
        answer = "" if non_interactive else input(f"{label} [{default}]: ").strip()
        value = Path(answer) if answer else default
    return value.expanduser().resolve()


def overwrite_entry(path, non_interactive):
    if non_interactive:
        return True
    while True:
        answer = input(f"Overwrite {path}? [Y/n]: ").strip().casefold()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Enter y or n; press Enter to overwrite.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Knowledge package containing runtime, skills, workflows and entry templates")
    parser.add_argument("--skills-root", type=Path, help="OpenFlow Skill installation directory")
    parser.add_argument("--cac-skills-root", type=Path, help="CAC Skill installation directory")
    parser.add_argument("--workflows-root", type=Path, help="OpenFlow Workflow template installation directory")
    parser.add_argument("--python", default=sys.executable, help="Python environment receiving pip dependencies")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Use default directories and overwrite existing project entry files without prompting")
    args = parser.parse_args(argv)
    source = args.source_root.expanduser().resolve()
    try:
        targets = (
            ("OpenFlow Skills", source / "skills", installation_directory(
                args.skills_root, Path.home() / ".openflow/config/skills", "OpenFlow Skill directory",
                args.non_interactive), "SKILL.md"),
            ("CAC Skills", source / "skills", installation_directory(
                args.cac_skills_root, Path.home() / ".cac/skills", "CAC Skill directory",
                args.non_interactive), "SKILL.md"),
            ("OpenFlow Workflow templates", source / "workflows", installation_directory(
                args.workflows_root, Path.home() / ".openflow/config/workflow-templates",
                "OpenFlow Workflow template directory", args.non_interactive), "workflow.yaml"),
        )
        requirements = source / "runtime/requirements.lock.txt"
        regular_file(requirements, required=True)
        # The manifest root is a filesystem relationship, not a Git checkout.
        project_root = (source / "../..").resolve()
        entries = []
        for original, name in (("config.yml", "config.yml"), ("AGENTS-code-root.md", "AGENTS.md")):
            template, target = source / original, project_root / name
            regular_file(template, required=True)
            exists = regular_file(target)
            entries.append((template, target, not exists or overwrite_entry(target, args.non_interactive)))

        source_roots = [source]
        copied, packages_to_copy = [], {}
        for label, packages, destination, marker in targets:
            count = 0
            for package in sorted(packages.iterdir()):
                if package.is_dir() and (package / marker).is_file():
                    target = replacement_target(destination, package.name, source_roots)
                    if any(root.is_relative_to(target) for _, _, root, _ in targets):
                        raise ValueError(f"Package target contains an installation directory: {target}")
                    if target in packages_to_copy and packages_to_copy[target][0] != package:
                        raise ValueError(f"Different capability packages share one target: {target}")
                    packages_to_copy[target] = (package, destination)
                    count += 1
            copied.append((label, count, destination))

        # Install first: dependency failure must leave old capabilities intact.
        subprocess.run([args.python, "-m", "pip", "install", "-r", str(requirements)], check=True)
        print(f"Installed runtime dependencies with {args.python}")

        removed = 0
        for target, (_, destination) in packages_to_copy.items():
            replacement_target(destination, target.name, source_roots)
            if target.is_dir():
                shutil.rmtree(target)
                removed += 1
            elif target.exists():
                target.unlink()
                removed += 1
        print(f"Removed {removed} existing packages")

        for target, (package, _) in packages_to_copy.items():
            shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for template, target, replace in entries:
            if replace:
                regular_file(target)
                shutil.copy2(template, target)
                print(f"Copied {template.name} to {target}")
            else:
                print(f"Kept existing {target}")
    except (OSError, ValueError, EOFError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    for label, count, destination in copied:
        print(f"Copied {count} {label} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
