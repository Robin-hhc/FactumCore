"""Validate instruction packages, five-step ingest and serial lint Workflows.

Local structural checks do not prove host triggering,
knowledge semantics or CI permissions. Manual Skill calls do not require a
workflow engine or its source checkout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import yaml


SKILLS = tuple("hs-knowledge-" + name for name in (
    "source", "change-plan", "view-materialize", "review", "apply", "query", "maintain",
    "patrol-sync", "patrol-plan", "patrol-reindex", "patrol-complete",
))
OWNERS = {"lint_view": "reviewer"}
NODE_SKILLS = {
    "prepare_sources": "hs-knowledge-source",
    "plan_change": "hs-knowledge-change-plan",
    "materialize_view": "hs-knowledge-view-materialize",
    "lint_view": "hs-knowledge-review",
    "apply_view": "hs-knowledge-apply",
    "sync_workspace": "hs-knowledge-patrol-sync",
    "plan_patrol": "hs-knowledge-patrol-plan",
    "refresh_index": "hs-knowledge-patrol-reindex",
    "complete_patrol": "hs-knowledge-patrol-complete",
}
WORKFLOW_ENTRIES = {
    "hs-knowledge-ingest": ("prepare_sources", "hs-knowledge-source"),
    "hs-knowledge-lint": ("sync_workspace", "hs-knowledge-patrol-sync"),
}
EDGES = {
    "hs-knowledge-ingest": {
        "prepare_sources": {"prepared": "plan_change", "unchanged": "__end__"},
        "plan_change": {"content_planned": "materialize_view", "deferred": "__end__"},
        "materialize_view": {"ready": "lint_view", "needs_plan": "plan_change"},
        "lint_view": {"passed": "apply_view", "needs_plan": "plan_change", "needs_revision": "materialize_view"},
        "apply_view": {"completed": "__end__"},
    },
    "hs-knowledge-lint": {
        "sync_workspace": {"synced": "plan_patrol", "skipped": "plan_patrol"},
        "plan_patrol": {"needs_ingest": "prepare_sources", "needs_reindex": "refresh_index", "unchanged": "complete_patrol"},
        "prepare_sources": {"prepared": "plan_change", "unchanged": "complete_patrol"},
        "plan_change": {"content_planned": "materialize_view", "deferred": "complete_patrol"},
        "materialize_view": {"ready": "lint_view", "needs_plan": "plan_change"},
        "lint_view": {"passed": "apply_view", "needs_plan": "plan_change", "needs_revision": "materialize_view"},
        "apply_view": {"completed": "plan_patrol"},
        "refresh_index": {"reindexed": "complete_patrol"},
        "complete_patrol": {"completed": "__end__"},
    },
}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def load(path):
    value = yaml.load(path.read_bytes(), Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise ValueError(f"mapping required: {path}")
    return value


def validate(root):
    root = Path(root).resolve(strict=True)
    errors = []
    knowledge_root = root / "himate/himate-knowledge-wifi-mp"
    for ref in ("knowledge.py", "knowledge.sh", "knowledge.cmd", "runtime/manifest.json",
                "runtime/requirements.lock.txt", "runtime/himate_knowledge/__init__.py",
                "runtime/himate_knowledge/cli.py"):
        if not (knowledge_root / ref).is_file():
            errors.append(f"repository runtime: missing {ref}")
    package_root = root / "skills/common/knowledge"
    # A leftover historical directory is not an installed Skill. A package with
    # SKILL.md is active and must belong to the exact final public capability set.
    active_skills = {path.name for path in package_root.glob("*")
                     if path.is_dir() and (path / "SKILL.md").is_file()}
    if active_skills != set(SKILLS):
        errors.append(
            "active Skill set mismatch: missing=" + repr(sorted(set(SKILLS) - active_skills))
            + ", unexpected=" + repr(sorted(active_skills - set(SKILLS)))
        )
    for skill in SKILLS:
        package = package_root / skill
        try:
            forbidden = [path for path in package.rglob("*") if path.is_file()
                         and "__pycache__" not in path.parts
                         and (path.relative_to(package).parts[0] in {"scripts", "tests"}
                              or path.name.startswith("requirements")
                              or path.suffix == ".py")]
            if forbidden:
                errors.append(f"{skill}: Skill source owns implementation, tests or dependency locks")
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            metadata = yaml.load(frontmatter.group(1), Loader=UniqueLoader) if frontmatter else {}
            if not isinstance(metadata, dict) or metadata.get("name") != skill or not metadata.get("description"):
                errors.append(f"{skill}: missing or inconsistent Skill identity")
            for reference in re.findall(r"\]\((references/[^)#]+)(?:#[^)]*)?\)", text):
                target = package / reference
                if ".." in Path(reference).parts or not target.is_file():
                    errors.append(f"{skill}: missing business reference {reference}")
        except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
            errors.append(f"{skill}: {exc}")
    for identity, expected in EDGES.items():
        try:
            package = root / "workflows/common/knowledge" / identity
            doc = load(package / "workflow.yaml")
            entry_node, entry_skill = WORKFLOW_ENTRIES[identity]
            if (
                doc.get("version"),
                doc.get("id"),
                doc.get("kind"),
                doc.get("entry_node"),
            ) != (1, identity, "custom", entry_node) or doc.get("entry") != {
                "skill": entry_skill
            }:
                errors.append(f"{identity}: invalid template identity/entry")
            nodes = doc.get("nodes", [])
            by_id = {n["id"]: n for n in nodes}
            if set(by_id) != set(expected) or len(by_id) != len(nodes):
                errors.append(f"{identity}: complete node set/uniqueness mismatch")
            for node_id, node in by_id.items():
                if node_id not in expected:
                    continue
                owner = OWNERS.get(node_id, "coder")
                if (
                    node.get("type") != "skill"
                    or node.get("owner") != owner
                    or node.get("skill") != NODE_SKILLS[node_id]
                ):
                    errors.append(f"{identity}.{node_id}: wrong Skill/owner/type")
                transitions = {e["id"]: e["target"] for e in node.get("exits", [])}
                if len(transitions) != len(node.get("exits", [])):
                    errors.append(f"{identity}.{node_id}: duplicate exits")
                if transitions != expected[node_id]:
                    errors.append(f"{identity}.{node_id}: unsafe or missing transition")
                if not node.get("prompt"):
                    errors.append(
                        f"{identity}.{node_id}: missing execution constraints"
                    )
                if any(
                    field in node
                    for field in (
                        "run",
                        "runner",
                        "inputs",
                        "outputs",
                        "retry",
                        "timeout",
                        "workflow",
                        "workflow_id",
                        "subworkflow",
                        "call",
                    )
                ):
                    errors.append(f"{identity}.{node_id}: unsupported runtime field")
            visited, pending = set(), [entry_node]
            while pending:
                current = pending.pop()
                if current in visited or current == "__end__":
                    continue
                visited.add(current)
                pending.extend(expected.get(current, {}).values())
            if visited != set(by_id):
                errors.append(f"{identity}: unreachable node")
            layout = load(package / "layouts.yaml")
            coordinates = layout.get("canvas", {}).get("nodes", {})
            # The canvas may position its start/end glyphs independently of
            # executable nodes. Every real node is still required; other IDs
            # remain invalid, and endpoint coordinates use the same checks.
            executable_coordinates = set(coordinates) - {"__start__", "__end__"}
            if layout.get("template_id") != identity or executable_coordinates != set(by_id):
                errors.append(f"{identity}: layout identity/node set mismatch")
            for node_id, xy in coordinates.items():
                if set(xy) != {"x", "y"} or not all(
                    isinstance(v, (int, float)) for v in xy.values()
                ):
                    errors.append(f"{identity}.{node_id}: invalid layout coordinates")
        except (OSError, ValueError, KeyError, AttributeError, yaml.YAMLError) as exc:
            errors.append(f"{identity}: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    args = parser.parse_args()
    errors = validate(args.source_root)
    report = {
        "status": "invalid" if errors else "static_valid",
        "errors": errors,
        "limitations": ["Not real host/CI/permission or semantic acceptance."],
    }
    if errors:
        report["status"] = "invalid"
    print(json.dumps(report, ensure_ascii=True))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
