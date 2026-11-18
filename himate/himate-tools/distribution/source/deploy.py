"""Install HiMate Skills and Workflow templates for OpenFlow and CAC."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import stat
import sys


def within(path, base):
    if path.is_relative_to(base):
        return True
    if not base.exists():
        return False
    return any(candidate.exists() and candidate.samefile(base) for candidate in (path, *path.parents))


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
    if any(within(target, root) or within(root, target) for root in source_roots):
        raise ValueError(f"Package target overlaps distribution sources: {target}")
    return target


def installation_directory(value, default, label, non_interactive):
    if value is None:
        answer = "" if non_interactive else input(f"{label} [{default}]: ").strip()
        value = Path(answer) if answer else default
    return value.expanduser().resolve()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Base directory used to locate the adjacent himate-skills package")
    parser.add_argument("--capabilities-root", type=Path,
                        help="Capability package containing skills and workflows (default: adjacent himate-skills)")
    parser.add_argument("--skills-root", type=Path, help="OpenFlow Skill installation directory")
    parser.add_argument("--cac-skills-root", type=Path, help="CAC Skill installation directory")
    parser.add_argument("--workflows-root", type=Path, help="OpenFlow Workflow template installation directory")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Use default installation directories without prompting")
    args = parser.parse_args(argv)
    source = args.source_root.expanduser().resolve()
    try:
        adjacent = source.parent / "himate-skills"
        capabilities = args.capabilities_root or (adjacent if adjacent.exists() else source)
        capabilities = capabilities.expanduser().resolve()
        skills, workflows = capabilities / "skills", capabilities / "workflows"
        if not skills.is_dir() or not workflows.is_dir():
            raise ValueError(f"Skills and workflows are missing at {capabilities}. "
                             "Place himate-skills beside the tool package or specify --capabilities-root.")
        source_roots = [source, capabilities]
        targets = (
            ("OpenFlow Skills", skills, installation_directory(
                args.skills_root, Path.home() / ".openflow/config/skills", "OpenFlow Skill directory",
                args.non_interactive), "SKILL.md"),
            ("CAC Skills", skills, installation_directory(
                args.cac_skills_root, Path.home() / ".cac/skills", "CAC Skill directory",
                args.non_interactive), "SKILL.md"),
            ("OpenFlow Workflow templates", workflows, installation_directory(
                args.workflows_root, Path.home() / ".openflow/config/workflow-templates",
                "OpenFlow Workflow template directory", args.non_interactive), "workflow.yaml"),
        )
        copied, packages_to_copy = [], {}
        for label, packages, destination, marker in targets:
            count = 0
            for package in sorted(packages.iterdir()):
                if package.is_dir() and (package / marker).is_file():
                    target = replacement_target(destination, package.name, source_roots)
                    if any(within(root, target) for _, _, root, _ in targets):
                        raise ValueError(f"Package target contains an installation directory: {target}")
                    if target in packages_to_copy and packages_to_copy[target][0] != package:
                        raise ValueError(f"Different capability packages share one target: {target}")
                    packages_to_copy[target] = (package, destination)
                    count += 1
            copied.append((label, count, destination))

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
    except (OSError, ValueError, EOFError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    for label, count, destination in copied:
        print(f"Copied {count} {label} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
