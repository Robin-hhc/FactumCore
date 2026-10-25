"""Validate the approved node packages and the complete ingest Workflow.

Local structural checks do not prove host triggering, human authentication,
knowledge semantics or CI permissions. --openflow-source additionally executes
the actual pinned upstream loader against an explicit isolated installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import yaml


SKILLS = ('hs-workspace-explore',
 'hs-knowledge-source-capture',
 'hs-knowledge-change-plan',
 'hs-knowledge-view-materialize',
 'hs-knowledge-governance-handoff',
 'hs-knowledge-candidate-inspect',
 'hs-knowledge-confirmation-prepare',
 'hs-knowledge-confirmation-record',
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
ARTIFACT_SCOPE = {'hs-workspace-explore': ([], []),
 'hs-knowledge-source-capture': ([], []),
 'hs-knowledge-change-plan': (['plan_change'], ['planned']),
 'hs-knowledge-view-materialize': (['materialize_view'], ['ready']),
 'hs-knowledge-governance-handoff': ([], []),
 'hs-knowledge-candidate-inspect': (['inspect_candidate'],
                                    ['manual_ready',
                                     'mixed_ready',
                                     'code_ready',
                                     'recovery_required']),
 'hs-knowledge-confirmation-prepare': (['prepare_confirmation'], ['await_user']),
 'hs-knowledge-confirmation-record': (['record_confirmation'], ['accepted', 'mixed_ready']),
 'hs-knowledge-local-check': (['local_check'], ['code_passed', 'needs_revision']),
 'hs-knowledge-candidate-revise': (['revise_candidate'], ['ready', 'deferred']),
 'hs-knowledge-apply': (['apply_view'], ['applied', 'record_only']),
 'hs-knowledge-recover': (['recover_transaction'], ['recovered', 'record_only']),
 'hs-knowledge-index-build': (['rebuild_index'], ['built']),
 'hs-knowledge-query-regression': (['query_regression'], ['checked']),
 'hs-knowledge-publish-handoff': (['publish_handoff'], ['ready_to_publish']),
 'hs-knowledge-merge-check': ([], []),
 'hs-knowledge-maintain': ([], []),
 'hs-knowledge-query': ([], []),
 'hs-knowledge-source-scan': (['scan_sources'], ['scanned']),
 'hs-knowledge-lint': (['lint_preflight', 'lint_view'], ['passed'])}
EXTRA_ARTIFACT_SCOPE = {'hs-knowledge-source-scan': {'prepare-result.yaml': (['prepare_material'], ['prepared']),
                              'record-result.yaml': (['record_ingest'], ['recorded'])},
 'hs-knowledge-change-plan': {'review-result.yaml': (['review_plan', 'review_content'],
                                                     ['reviewed'])},
 'hs-knowledge-publish-handoff': {'submission-result.yaml': (['submit_batch'], ['submitted'])}}
OWNERS = {'review_plan': 'reviewer',
 'review_content': 'reviewer',
 'lint_preflight': 'reviewer',
 'final_view_user_gate': 'user',
 'local_check': 'reviewer',
 'lint_view': 'reviewer',
 'query_regression': 'reviewer'}
NODE_SKILLS = {'scan_sources': 'hs-knowledge-source-scan',
 'prepare_material': 'hs-knowledge-source-scan',
 'plan_change': 'hs-knowledge-change-plan',
 'review_plan': 'hs-knowledge-change-plan',
 'materialize_view': 'hs-knowledge-view-materialize',
 'review_content': 'hs-knowledge-change-plan',
 'lint_preflight': 'hs-knowledge-lint',
 'inspect_candidate': 'hs-knowledge-candidate-inspect',
 'prepare_confirmation': 'hs-knowledge-confirmation-prepare',
 'record_confirmation': 'hs-knowledge-confirmation-record',
 'local_check': 'hs-knowledge-local-check',
 'revise_candidate': 'hs-knowledge-candidate-revise',
 'lint_view': 'hs-knowledge-lint',
 'record_ingest': 'hs-knowledge-source-scan',
 'apply_view': 'hs-knowledge-apply',
 'recover_transaction': 'hs-knowledge-recover',
 'rebuild_index': 'hs-knowledge-index-build',
 'query_regression': 'hs-knowledge-query-regression',
 'publish_handoff': 'hs-knowledge-publish-handoff',
 'submit_batch': 'hs-knowledge-publish-handoff'}
EDGES = {'hs-knowledge-ingest': {'scan_sources': {'scanned': 'prepare_material',
                                          'unchanged': 'record_ingest',
                                          'resume': 'inspect_candidate',
                                          'recover': 'recover_transaction',
                                          'blocked': '__end__'},
                         'prepare_material': {'prepared': 'plan_change', 'blocked': '__end__'},
                         'plan_change': {'planned': 'review_plan',
                                         'needs_material': 'prepare_material',
                                         'blocked': '__end__'},
                         'review_plan': {'reviewed': 'materialize_view',
                                         'record_only': 'record_ingest',
                                         'needs_material': 'prepare_material',
                                         'needs_revision': 'plan_change',
                                         'blocked': '__end__'},
                         'materialize_view': {'ready': 'review_content',
                                              'stale': 'prepare_material',
                                              'blocked': '__end__'},
                         'review_content': {'reviewed': 'lint_preflight',
                                            'needs_material': 'prepare_material',
                                            'needs_plan': 'plan_change',
                                            'needs_revision': 'revise_candidate',
                                            'blocked': '__end__'},
                         'lint_preflight': {'passed': 'inspect_candidate',
                                            'needs_material': 'prepare_material',
                                            'needs_plan': 'plan_change',
                                            'needs_revision': 'revise_candidate',
                                            'blocked': '__end__'},
                         'inspect_candidate': {'manual_ready': 'prepare_confirmation',
                                               'mixed_ready': 'prepare_confirmation',
                                               'code_ready': 'local_check',
                                               'recovery_required': 'recover_transaction',
                                               'needs_revision': 'revise_candidate',
                                               'blocked': '__end__'},
                         'prepare_confirmation': {'await_user': 'final_view_user_gate',
                                                  'stale': 'inspect_candidate',
                                                  'blocked': '__end__'},
                         'final_view_user_gate': {'on_pass': 'record_confirmation',
                                                  'on_fail': 'revise_candidate'},
                         'record_confirmation': {'accepted': 'lint_view',
                                                 'mixed_ready': 'local_check',
                                                 'stale': 'prepare_confirmation',
                                                 'partial': 'revise_candidate',
                                                 'awaiting_confirmation': '__end__',
                                                 'blocked': '__end__'},
                         'local_check': {'code_passed': 'lint_view',
                                         'needs_revision': 'revise_candidate',
                                         'blocked': '__end__'},
                         'revise_candidate': {'ready': 'review_content',
                                              'needs_material': 'prepare_material',
                                              'needs_plan': 'plan_change',
                                              'deferred': 'record_ingest',
                                              'blocked': '__end__'},
                         'lint_view': {'passed': 'record_ingest',
                                       'needs_material': 'prepare_material',
                                       'needs_plan': 'plan_change',
                                       'needs_revision': 'revise_candidate',
                                       'blocked': '__end__'},
                         'record_ingest': {'recorded': 'apply_view',
                                           'needs_record': 'record_ingest',
                                           'blocked': '__end__'},
                         'apply_view': {'applied': 'rebuild_index',
                                        'record_only': 'publish_handoff',
                                        'recovery_required': 'recover_transaction',
                                        'stale': 'prepare_material',
                                        'blocked': '__end__'},
                         'recover_transaction': {'recovered': 'rebuild_index',
                                                 'record_only': 'publish_handoff',
                                                 'rolled_back': 'prepare_material',
                                                 'blocked': '__end__'},
                         'rebuild_index': {'built': 'query_regression',
                                           'content_error': 'plan_change',
                                           'blocked': '__end__'},
                         'query_regression': {'checked': 'publish_handoff',
                                              'content_error': 'plan_change',
                                              'blocked': '__end__'},
                         'publish_handoff': {'ready_to_publish': 'submit_batch',
                                             'blocked': '__end__'},
                         'submit_batch': {'submitted': '__end__',
                                          'pending_submission': '__end__',
                                          'blocked': '__end__'}}}
OPENFLOW_REVISION = "1901a463efca222542a4634d7ce50c7b244b2bab"
# Exact bytes retrieved from the upstream revision, including transitive local
# imports of the real loader. No copied or invented replacement validator.
OPENFLOW_HASHES = {
    "skill-artifact-loader.js": "ac79387629fa4e7673fa637dfd3c4add14d9cd3b7abe9d4e8c2d1fc4ce8e5222",
    "skill-registry.js": "9c2055579a8a375258c41926f89bec8768a65b10148c03863a86262e409a292e",
    "built-ins.js": "59326a7c81f1fadf2771873a99feb6bb1784a4356887b4478fa376b57209580b",
    "skill-default-loading.js": "4696076bb56375988ff71ac4245956c3f5689f28426a94ec2eb4f84761c84e61",
    "workflow-resource-registry.js": "69dfa921a9a6059bdd48a270777d11d3111ee933dd0afdde7bf8940fdf2f744c",
    "workflow-template-layout-loader.js": "a4aeee79c5a13fc3f4da4b182090a0c9bba78115439fb89fabc1357814f0b251",
    "workflow-template-loader.js": "d4934348acbe1a86f90ac96adaaa02393a22e5f1f2617918f113511ca75c73f2",
    "workflow-template-health.js": "e4f370bd5067b6eb783035f61ab78a736f7a2b9c79e9f1a46861658a50b0017d",
    "workflow-template-validator.js": "50b4e6e12b9e8534ec337a047deebcdba988aac346c9ff6916813e783dac9d10",
    "workflow-skill-bindings.js": "306e0ec593ecaec8b7c13745961cd25d404a7769a46b62af2e339198542818dc",
    "built-in-overrides.js": "fe6a36dd46e88a15601d8763c5ab2c46c48cd92b8a2c3252e93f83dad0f1b405",
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
    for skill in SKILLS:
        package = root / "aiotbot-knowledge-wifi-mp/skills/common/knowledge" / skill
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
        package = root / "aiotbot-knowledge-wifi-mp/skills/common/knowledge" / skill
        for name, (expected_nodes, expected_exits) in contracts.items():
            try:
                contract = load(package / "artifacts" / name)
                identity = skill + "-" + name[:-5]
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
            package = root / "aiotbot-knowledge-wifi-mp/workflows/common/knowledge" / identity
            doc = load(package / "workflow.yaml")
            if (
                doc.get("version"),
                doc.get("id"),
                doc.get("kind"),
                doc.get("entry_node"),
            ) != (1, identity, "custom", "scan_sources") or doc.get("entry") != {
                "skill": "hs-knowledge-source-scan"
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
                if node_id == "final_view_user_gate":
                    if (
                        node.get("type") != "gate"
                        or node.get("owner") != "user"
                        or "skill" in node
                    ):
                        errors.append(f"{identity}: real user gate required")
                    transitions = {
                        "on_pass": node.get("on_pass"),
                        "on_fail": node.get("on_fail"),
                    }
                else:
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
                    )
                ):
                    errors.append(f"{identity}.{node_id}: unsupported runtime field")
            visited, pending = set(), ["scan_sources"]
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


def validate_openflow(upstream, installed):
    """Run actual upstream registry, artifact, Workflow and layout loaders."""
    upstream = Path(upstream).resolve(strict=True)
    installed = Path(installed).resolve(strict=True)
    for name, expected in OPENFLOW_HASHES.items():
        path = upstream / "src/config" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"OpenFlow source differs from {OPENFLOW_REVISION}: {name}"
            )
    script = r"""
const path=require('path'); const root=process.argv[1], installed=process.argv[2];
const registry=require(path.join(root,'src/config/skill-registry')).loadSkillRegistry({projectRoot:installed});
const contracts=require(path.join(root,'src/config/skill-artifact-loader')).loadSkillArtifactContracts(installed);
const loader=require(path.join(root,'src/config/workflow-template-loader'));
const layoutLoader=require(path.join(root,'src/config/workflow-template-layout-loader'));
const workflows=loader.loadWorkflowTemplates(installed);
if(workflows.length!==1||registry.skillIds.length!==20||contracts.length!==24) throw Error('Incomplete packages');
for(const workflow of workflows){
 const layout=layoutLoader.loadWorkflowTemplateLayoutFromPackageDir(path.dirname(workflow.filePath),workflow.id);
 if(layout.template_id!==workflow.id) throw Error('Wrong layout identity');
 const ids=workflow.nodes.map(n=>n.id).sort();
 if(JSON.stringify(Object.keys(layout.canvas.nodes).sort())!==JSON.stringify(ids)) throw Error('Wrong layout nodes');
 if(workflow.nodes.some(n=>!['coder','reviewer','user'].includes(n.owner))) throw Error('Unavailable declared role');
}
console.log(JSON.stringify({workflow_ids:workflows.map(w=>w.id).sort(),skill_count:registry.skillIds.length,
contract_count:contracts.length,role_ids:['coder','reviewer'],role_scope:'synthetic declared roles only; real host roles not verified'}));
"""
    env = dict(os.environ)
    modules = upstream / "validation-deps/node_modules"
    if modules.is_dir():
        env["NODE_PATH"] = str(modules)
    result = subprocess.run(
        ["node", "-e", script, str(upstream), str(installed)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )
    if result.returncode:
        raise ValueError(
            "Pinned OpenFlow loader rejected installation: " + result.stderr
        )
    return {"revision": OPENFLOW_REVISION, **json.loads(result.stdout)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--openflow-source", type=Path)
    parser.add_argument("--installed-root", type=Path)
    args = parser.parse_args()
    errors = validate(args.source_root)
    report = {
        "status": "invalid" if errors else "static_valid",
        "errors": errors,
        "limitations": ["Not real host/human/CI/permission or semantic acceptance."],
    }
    if args.openflow_source:
        if not args.installed_root:
            errors.append("--installed-root required with --openflow-source")
        elif not errors:
            try:
                report["openflow"] = validate_openflow(
                    args.openflow_source, args.installed_root
                )
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
    if errors:
        report["status"] = "invalid"
    print(json.dumps(report, ensure_ascii=True))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
