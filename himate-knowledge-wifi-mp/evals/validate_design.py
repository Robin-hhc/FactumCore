"""Validate node packages, the complete ingest and read-only audit Workflows.

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


SKILLS = (
    'hs-knowledge-explore',
    'hs-knowledge-source',
    'hs-knowledge-change-plan',
    'hs-knowledge-view-materialize',
    'hs-knowledge-lint',
    'hs-knowledge-apply',
    'hs-knowledge-query',
    'hs-knowledge-maintain',
)
ARTIFACT_SCOPE = {
    'hs-knowledge-explore': ([], []),
    'hs-knowledge-source': (['prepare_sources'], ['prepared', 'unchanged']),
    'hs-knowledge-change-plan': (['plan_change'], ['content_planned']),
    'hs-knowledge-view-materialize': (['materialize_view'], ['ready']),
    'hs-knowledge-lint': (
        ['lint_view'],
        ['passed', 'needs_material', 'needs_plan', 'needs_revision'],
    ),
    'hs-knowledge-apply': (['apply_view'], ['completed', 'recorded']),
    'hs-knowledge-query': ([], []),
    'hs-knowledge-maintain': (
        ['sync_workspace', 'plan_patrol', 'refresh_index', 'complete_patrol'],
        ['synced', 'skipped', 'needs_ingest', 'needs_index', 'unchanged', 'blocked',
         'indexed', 'completed', 'pending'],
    ),
}
EXTRA_ARTIFACT_SCOPE = {
    'hs-knowledge-source': {'record-result.yaml': (['record_ingest'], ['recorded'])},
    'hs-knowledge-maintain': {'audit-result.yaml': ([], [])},
}
EXTRA_ARTIFACT_IDS = {
    ('hs-knowledge-maintain', 'audit-result.yaml'): 'hs-knowledge-code-reference-audit',
}
OWNERS = {'lint_view': 'reviewer'}
NODE_SKILLS = {'prepare_sources': 'hs-knowledge-source',
 'plan_change': 'hs-knowledge-change-plan',
 'materialize_view': 'hs-knowledge-view-materialize',
 'lint_view': 'hs-knowledge-lint',
 'record_ingest': 'hs-knowledge-source',
 'apply_view': 'hs-knowledge-apply',
 'sync_workspace': 'hs-knowledge-maintain',
 'plan_patrol': 'hs-knowledge-maintain',
 'refresh_index': 'hs-knowledge-maintain',
 'complete_patrol': 'hs-knowledge-maintain'}
WORKFLOW_ENTRIES = {
    'hs-knowledge-ingest': ('prepare_sources', 'hs-knowledge-source'),
    'hs-knowledge-lint': ('sync_workspace', 'hs-knowledge-maintain'),
}
# Exact contracts for ingest and the governance workflow sharing P3-P7.
# Template identity is independent of Skill identity, even when names match.
EDGES = {
    'hs-knowledge-ingest': {
        'prepare_sources': {'prepared': 'plan_change', 'unchanged': '__end__'},
        'plan_change': {'content_planned': 'materialize_view', 'needs_material': 'prepare_sources'},
        'materialize_view': {'ready': 'lint_view', 'needs_material': 'prepare_sources',
                             'needs_plan': 'plan_change'},
        'lint_view': {'passed': 'record_ingest', 'needs_material': 'prepare_sources',
                      'needs_plan': 'plan_change', 'needs_revision': 'materialize_view'},
        'record_ingest': {'recorded': 'apply_view'},
        'apply_view': {'completed': '__end__', 'recorded': '__end__'},
    },
    'hs-knowledge-lint': {
        'sync_workspace': {'synced': 'plan_patrol', 'skipped': 'plan_patrol'},
        'plan_patrol': {'needs_ingest': 'prepare_sources', 'needs_index': 'refresh_index',
                        'unchanged': 'complete_patrol', 'blocked': '__end__'},
        'prepare_sources': {'prepared': 'plan_change'},
        'plan_change': {'content_planned': 'materialize_view', 'needs_material': 'prepare_sources'},
        'materialize_view': {'ready': 'lint_view', 'needs_material': 'prepare_sources',
                             'needs_plan': 'plan_change'},
        'lint_view': {'passed': 'record_ingest', 'needs_material': 'prepare_sources',
                      'needs_plan': 'plan_change', 'needs_revision': 'materialize_view'},
        'record_ingest': {'recorded': 'apply_view'},
        'apply_view': {'completed': 'complete_patrol', 'recorded': 'complete_patrol'},
        'refresh_index': {'indexed': 'complete_patrol'},
        'complete_patrol': {'completed': '__end__', 'pending': '__end__'},
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
    artifacts = set()
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
            expected_contracts = {"result.yaml", *EXTRA_ARTIFACT_SCOPE.get(skill, {})}
            actual_contracts = {path.name for path in (package / "artifacts").glob("*.yaml")}
            if actual_contracts != expected_contracts:
                errors.append(f"{skill}: exact artifact contract set mismatch")
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            metadata = (
                yaml.load(frontmatter.group(1), Loader=UniqueLoader)
                if frontmatter
                else {}
            )
            if metadata.get("name") != skill or not metadata.get("description"):
                errors.append(f"{skill}: missing or inconsistent Skill identity")
            for ref in (
                "scripts/cli.py",
                "scripts/support.py",
                "requirements.lock.txt",
                "requirements-dev.lock.txt",
            ):
                if not (package / ref).is_file():
                    errors.append(f"{skill}: missing {ref}")
            if not any((package / "tests").rglob("test*.py")):
                errors.append(f"{skill}: missing executable tests/test*.py")
            contract = load(package / "artifacts/result.yaml")
            if (
                contract.get("id") != skill + "-result"
                or contract.get("id") in artifacts
            ):
                errors.append(f"{skill}: artifact ID must be globally unique and exact")
            artifacts.add(contract.get("id"))
            if (
                contract.get("required") is not True
                or contract.get("default_location", {}).get("kind") != "markdown_file"
            ):
                errors.append(f"{skill}: required markdown_file artifact expected")
            for field in ("template", "writing_guide", "review_guide"):
                ref = contract.get(field, "")
                parts = Path(ref).parts
                target = package / "artifacts" / ref
                if (
                    not ref
                    or Path(ref).is_absolute()
                    or ".." in parts
                    or "\\" in ref
                    or not target.is_file()
                ):
                    errors.append(f"{skill}: invalid artifact {field} reference")
            expected_nodes, expected_exits = ARTIFACT_SCOPE[skill]
            actual_nodes = contract.get("applies_to", {}).get("node_ids", [])
            actual_exits = contract.get("required_on", {}).get("exit_ids", [])
            if actual_nodes != expected_nodes:
                errors.append(f"{skill}: artifact node scope mismatch")
            if actual_exits != expected_exits:
                errors.append(f"{skill}: artifact exit obligations mismatch")
            legal_exits = {
                exit_id
                for edges in EDGES.values()
                for node_id, transitions in edges.items()
                if node_id in expected_nodes
                for exit_id in transitions
            }
            if not set(actual_exits).issubset(legal_exits):
                errors.append(f"{skill}: artifact refers to nonexistent exit")
        except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
            errors.append(f"{skill}: {exc}")
    # Every native contract uses the real node IDs and exit names. The shared
    # lint report covers P5 exits. The explicit manual audit keeps a separate
    # artifact identity without claiming a removed workflow node obligation.
    for skill, contracts in EXTRA_ARTIFACT_SCOPE.items():
        package = root / "skills/common/knowledge" / skill
        for name, (expected_nodes, expected_exits) in contracts.items():
            try:
                contract = load(package / "artifacts" / name)
                identity = EXTRA_ARTIFACT_IDS.get((skill, name), skill + "-" + name[:-5])
                if contract.get("id") != identity or identity in artifacts:
                    errors.append(f"{skill}/{name}: duplicate or inconsistent artifact identity")
                artifacts.add(identity)
                if contract.get("required") is not True or contract.get("default_location", {}).get("kind") != "markdown_file":
                    errors.append(f"{skill}/{name}: required markdown_file artifact expected")
                if contract.get("applies_to", {}).get("node_ids") != expected_nodes or contract.get("required_on", {}).get("exit_ids") != expected_exits:
                    errors.append(f"{skill}/{name}: artifact scope mismatch")
                for field in ("template", "writing_guide", "review_guide"):
                    ref = contract.get(field, "")
                    if not ref or Path(ref).is_absolute() or ".." in Path(ref).parts or "\\" in ref or not (package / "artifacts" / ref).is_file():
                        errors.append(f"{skill}/{name}: invalid {field} reference")
                for node_id in expected_nodes:
                    exits = next((edges[node_id] for edges in EDGES.values() if node_id in edges), {})
                    if not set(expected_exits).issubset(exits):
                        errors.append(f"{skill}/{name}: nonexistent node exit")
            except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
                errors.append(f"{skill}/{name}: {exc}")
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
            if layout.get("template_id") != identity or set(coordinates) != set(by_id):
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
        "--source-root", type=Path, default=Path(__file__).resolve().parents[2]
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
