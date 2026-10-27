"""Validate node packages, the complete ingest and read-only audit Workflows.

Local structural checks do not prove host triggering,
knowledge semantics or CI permissions. Manual Skill calls do not require a
workflow engine or its source checkout.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat

import yaml


SKILLS = ('hs-knowledge-explore',
 'hs-knowledge-source-capture',
 'hs-knowledge-change-plan',
 'hs-knowledge-view-materialize',
 'hs-knowledge-governance-handoff',
 'hs-knowledge-candidate-inspect',
 'hs-knowledge-local-check',
 'hs-knowledge-candidate-revise',
 'hs-knowledge-apply',
 'hs-knowledge-recover',
 'hs-knowledge-index-build',
 'hs-knowledge-query-regression',
 'hs-knowledge-publish-handoff',
 'hs-knowledge-merge-check',
 'hs-knowledge-maintain',
 'hs-knowledge-query',
 'hs-knowledge-source-scan',
 'hs-knowledge-lint')
INSTRUCTION_SKILLS = ('hs-codegraph-setup',)
ARTIFACT_SCOPE = {'hs-knowledge-explore': ([], []),
 'hs-knowledge-source-capture': ([], []),
 'hs-knowledge-change-plan': (['plan_change'], ['planned']),
 'hs-knowledge-view-materialize': (['materialize_view'], ['ready']),
 'hs-knowledge-governance-handoff': ([], []),
 'hs-knowledge-candidate-inspect': (['inspect_candidate'],
                                    ['manual_ready', 'mixed_ready', 'code_ready', 'recovery_required']),
 'hs-knowledge-local-check': (['local_check'], ['code_passed', 'needs_revision']),
 'hs-knowledge-candidate-revise': (['revise_candidate'], ['ready', 'deferred']),
 'hs-knowledge-apply': (['apply_view'], ['applied', 'record_only']),
 'hs-knowledge-recover': (['recover_transaction'], ['recovered', 'record_only']),
 'hs-knowledge-index-build': (['rebuild_index'], ['built']),
 'hs-knowledge-query-regression': (['query_regression'], ['checked']),
 'hs-knowledge-publish-handoff': ([], []),
 'hs-knowledge-merge-check': ([], []),
 'hs-knowledge-maintain': ([], []),
 'hs-knowledge-query': ([], []),
 'hs-knowledge-source-scan': (['scan_sources'], ['scanned']),
 'hs-knowledge-lint': (['lint_preflight', 'lint_view'], ['passed'])}
EXTRA_ARTIFACT_SCOPE = {'hs-knowledge-source-scan': {'prepare-result.yaml': (['prepare_material'], ['prepared']),
                              'record-result.yaml': (['record_ingest'], ['recorded'])},
 'hs-knowledge-change-plan': {'review-result.yaml': (['review_plan', 'review_content'],
                                                     ['reviewed'])},
 'hs-knowledge-publish-handoff': {'submission-result.yaml': ([], [])},
 'hs-knowledge-maintain': {'audit-result.yaml': (['audit_references'], ['reported'])}}
EXTRA_ARTIFACT_IDS = {
    ('hs-knowledge-maintain', 'audit-result.yaml'): 'hs-knowledge-code-reference-audit',
}
OWNERS = {'review_plan': 'reviewer',
 'review_content': 'reviewer',
 'lint_preflight': 'reviewer',
 'local_check': 'reviewer',
 'lint_view': 'reviewer',
 'query_regression': 'reviewer',
 'check_formal': 'reviewer',
 'audit_references': 'reviewer'}
NODE_SKILLS = {'scan_sources': 'hs-knowledge-source-scan',
 'prepare_material': 'hs-knowledge-source-scan',
 'plan_change': 'hs-knowledge-change-plan',
 'review_plan': 'hs-knowledge-change-plan',
 'materialize_view': 'hs-knowledge-view-materialize',
 'review_content': 'hs-knowledge-change-plan',
 'lint_preflight': 'hs-knowledge-lint',
 'inspect_candidate': 'hs-knowledge-candidate-inspect',
 'local_check': 'hs-knowledge-local-check',
 'revise_candidate': 'hs-knowledge-candidate-revise',
 'lint_view': 'hs-knowledge-lint',
 'record_ingest': 'hs-knowledge-source-scan',
 'apply_view': 'hs-knowledge-apply',
 'recover_transaction': 'hs-knowledge-recover',
 'rebuild_index': 'hs-knowledge-index-build',
 'query_regression': 'hs-knowledge-query-regression',
 'check_formal': 'hs-knowledge-lint',
 'audit_references': 'hs-knowledge-maintain'}
WORKFLOW_ENTRIES = {
    'hs-knowledge-ingest': ('scan_sources', 'hs-knowledge-source-scan'),
    'hs-knowledge-lint': ('check_formal', 'hs-knowledge-lint'),
}
# Exact contracts for the existing ingest graph and the separate read-only graph.
# Template identity is independent of Skill identity, even when names match.
EDGES = {
    'hs-knowledge-ingest': {
        'scan_sources': {'scanned': 'prepare_material', 'unchanged': '__end__',
                         'resume': 'review_content', 'recover': 'recover_transaction',
                         'resume_index': 'rebuild_index', 'resume_queries': 'query_regression'},
        'prepare_material': {'prepared': 'plan_change'},
        'plan_change': {'planned': 'review_plan', 'needs_material': 'prepare_material'},
        'review_plan': {'reviewed': 'materialize_view', 'record_only': 'record_ingest',
                        'needs_material': 'prepare_material', 'needs_revision': 'plan_change'},
        'materialize_view': {'ready': 'review_content', 'stale': 'prepare_material'},
        'review_content': {'reviewed': 'lint_preflight', 'needs_material': 'prepare_material',
                           'needs_plan': 'plan_change', 'needs_revision': 'revise_candidate'},
        'lint_preflight': {'passed': 'inspect_candidate', 'needs_material': 'prepare_material',
                           'needs_plan': 'plan_change', 'needs_revision': 'revise_candidate'},
        'inspect_candidate': {'manual_ready': 'lint_view', 'mixed_ready': 'local_check',
                              'code_ready': 'local_check', 'recovery_required': 'recover_transaction',
                              'needs_revision': 'revise_candidate'},
        'local_check': {'code_passed': 'lint_view', 'needs_revision': 'revise_candidate'},
        'revise_candidate': {'ready': 'review_content', 'needs_material': 'prepare_material',
                             'needs_plan': 'plan_change', 'deferred': 'record_ingest'},
        'lint_view': {'passed': 'record_ingest', 'needs_material': 'prepare_material',
                      'needs_plan': 'plan_change', 'needs_revision': 'revise_candidate'},
        'record_ingest': {'recorded': 'apply_view', 'needs_record': 'record_ingest'},
        'apply_view': {'applied': 'rebuild_index', 'record_only': '__end__',
                       'recovery_required': 'recover_transaction', 'stale': 'prepare_material'},
        'recover_transaction': {'recovered': 'rebuild_index', 'record_only': '__end__',
                                'rolled_back': 'prepare_material'},
        'rebuild_index': {'built': 'query_regression', 'content_error': 'prepare_material'},
        'query_regression': {'checked': '__end__', 'content_error': 'prepare_material'},
    },
    'hs-knowledge-lint': {
        'check_formal': {'checked': 'audit_references'},
        'audit_references': {'reported': '__end__'},
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


def no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (
            os.path.lexists(part)
            and getattr(part.lstat(), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError(f"LINKED_PATH: {part}")


def instruction_files(package):
    """Read an instruction-only package for static checks, without executing it."""
    no_links(package)
    suffixes = {".md", ".txt", ".yaml", ".yml", ".json", ".toml"}
    files = {}
    for path in sorted(package.rglob("*")):
        relative = path.relative_to(package)
        no_links(path)
        if any(part.startswith(".") or part.lower() == "config.local.yml"
               or Path(part).stem.lower() in {"credentials", "secrets"}
               for part in relative.parts):
            raise ValueError(f"UNPUBLISHABLE_PACKAGE_FILE: {relative}")
        if relative.as_posix() != "SKILL.md" and (
            relative.parts[0] != "references"
            or path.is_file() and path.suffix.lower() not in suffixes
        ):
            raise ValueError(f"UNPUBLISHABLE_INSTRUCTION_FILE: {relative}")
        if not path.is_file():
            continue
        data = path.read_bytes()
        if re.search(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----", data):
            raise ValueError(f"PRIVATE_KEY_IN_PACKAGE: {relative}")
        if "\x00" in data.decode("utf-8"):
            raise ValueError(f"NON_TEXT_INSTRUCTION_FILE: {relative}")
        files[relative.as_posix()] = data
    if "SKILL.md" not in files:
        raise ValueError(f"INCOMPLETE_PACKAGE: {package.name}: SKILL.md")
    for reference in re.findall(r"\]\((references/[^\s)]+)\)", files["SKILL.md"].decode("utf-8")):
        if reference.split("#", 1)[0] not in files:
            raise ValueError(f"INVALID_INSTRUCTION_REFERENCE: {reference}")
    return files


def validate(root):
    root = Path(root).resolve(strict=True)
    errors = []
    artifacts = set()
    # Instruction packages have a text-only boundary; node requirements below
    # remain unchanged. No material from the inspected packages is run.
    for skill in INSTRUCTION_SKILLS:
        package = root / "skills/common/knowledge" / skill
        try:
            files = instruction_files(package)
            text = files["SKILL.md"].decode("utf-8")
            match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
            metadata = yaml.load(match[1], Loader=UniqueLoader) if match else None
            if (not isinstance(metadata, dict) or metadata.get("name") != skill
                    or not isinstance(metadata.get("description"), str)
                    or not metadata["description"].strip()):
                errors.append(f"{skill}: missing or inconsistent Skill identity")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{skill}: {exc}")
    for skill in SKILLS:
        package = root / "skills/common/knowledge" / skill
        try:
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
            if expected_nodes and actual_nodes != expected_nodes:
                errors.append(f"{skill}: artifact node scope mismatch")
            if expected_exits and not set(expected_exits).issubset(actual_exits):
                errors.append(f"{skill}: missing artifact exit obligations")
            legal_exits = {
                exit_id
                for edges in EDGES.values()
                for node_id, transitions in edges.items()
                if node_id in expected_nodes
                for exit_id in transitions
            }
            if expected_nodes and not set(actual_exits).issubset(legal_exits):
                errors.append(f"{skill}: artifact refers to nonexistent exit")
        except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
            errors.append(f"{skill}: {exc}")
    # Native OpenFlow contracts are scoped per node. A multi-node contract's
    # required exits must exist on every node, not just in their union.
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
