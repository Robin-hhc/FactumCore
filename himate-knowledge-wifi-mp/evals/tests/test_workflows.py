"""Workflow source checks and optional pinned upstream-loader integration."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "himate-knowledge-wifi-mp/evals/validate_design.py"
INSTALLER = (
    ROOT / "himate-knowledge-wifi-mp/tools/deploy/install_catalog.py"
)


def validator_module():
    spec = importlib.util.spec_from_file_location("workflow_validation", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_packages(root):
    module = validator_module()
    for skill in module.SKILLS:
        package = root / "skills/common/knowledge" / skill
        mapping = module.ARTIFACT_SCOPE[skill]
        files = {
            "SKILL.md": f"---\nname: {skill}\ndescription: isolated synthetic contract fixture\n---\n# fixture\n",
            "scripts/cli.py": "# fixture\n",
            "scripts/support.py": "# fixture\n",
            "tests/test_cli.py": "# fixture\n",
            "requirements.lock.txt": "# fixture\n",
            "requirements-dev.lock.txt": "# fixture\n",
            "artifacts/templates/result.md": "# Result\n",
            "artifacts/writing-guide.md": "# Writing\n",
            "artifacts/review-guide.md": "# Review\n",
        }
        contract = {
            "id": skill + "-result",
            "title": skill,
            "required": True,
            "template": "templates/result.md",
            "writing_guide": "writing-guide.md",
            "review_guide": "review-guide.md",
            "default_location": {"kind": "markdown_file"},
            "applies_to": {"node_ids": mapping[0]},
            "required_on": {"exit_ids": mapping[1]},
        }
        files["artifacts/result.yaml"] = yaml.safe_dump(contract)
        for name, mapping in module.EXTRA_ARTIFACT_SCOPE.get(skill, {}).items():
            extra = {**contract, "id": skill + "-" + name[:-5],
                     "applies_to": {"node_ids": mapping[0]}, "required_on": {"exit_ids": mapping[1]}}
            files["artifacts/" + name] = yaml.safe_dump(extra)
        for relative, data in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
    for skill in module.INSTRUCTION_SKILLS:
        package = root / "skills/common/knowledge" / skill
        (package / "references").mkdir(parents=True)
        (package / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: isolated setup fixture\n---\n"
            "Read [commands](references/codegraph.md).\n", encoding="utf-8")
        (package / "references/codegraph.md").write_text(
            "# Setup fixture\nNo host settings are modified.\n", encoding="utf-8")
    shutil.copytree(ROOT / "workflows", root / "workflows")
    return root


def test_ingest_is_one_complete_workflow_without_project_binding_or_lint_template():
    ingest = yaml.safe_load(
        (
            ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
        ).read_bytes()
    )
    nodes = {n["id"]: n for n in ingest["nodes"]}
    assert ingest["entry_node"] == "scan_sources"
    assert "bind_project" not in nodes and "governance_handoff" not in nodes
    assert not (ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml").exists()
    assert not any(node["type"] == "gate" for node in nodes.values())
    assert not {"prepare_confirmation", "final_view_user_gate", "record_confirmation"} & nodes.keys()
    assert nodes["review_content"]["owner"] == "reviewer"
    assert "verify_merge" not in nodes and "maintain_knowledge" not in nodes
    assert nodes["lint_view"]["skill"] == "hs-knowledge-lint"
    assert nodes["record_ingest"]["skill"] == "hs-knowledge-source-scan"
    assert {e["id"]: e["target"] for e in nodes["record_ingest"]["exits"]}["recorded"] == "apply_view"
    routes = {edge["id"]: edge["target"] for edge in nodes["inspect_candidate"]["exits"]}
    assert routes["manual_ready"] == "lint_view"
    assert routes["mixed_ready"] == routes["code_ready"] == "local_check"
    assert "content_review_ref" in nodes["apply_view"]["prompt"]
    assert "proof_set" not in nodes["apply_view"]["prompt"]


def test_ingest_finishes_locally_without_repository_submission():
    """Content and record-only success stop before optional human publishing."""
    workflow = yaml.safe_load(
        (
            ROOT
            / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
        ).read_bytes()
    )
    nodes = {node["id"]: node for node in workflow["nodes"]}

    def destination(node_id, exit_id):
        return next(
            edge["target"]
            for edge in nodes[node_id]["exits"]
            if edge["id"] == exit_id
        )

    assert destination("apply_view", "applied") == "rebuild_index"
    assert destination("rebuild_index", "built") == "query_regression"
    assert destination("query_regression", "checked") == "__end__"
    assert destination("apply_view", "record_only") == "__end__"
    assert destination("recover_transaction", "record_only") == "__end__"
    assert "publish_handoff" not in nodes
    assert "submit_batch" not in nodes
    assert not any(
        node.get("skill") == "hs-knowledge-publish-handoff"
        for node in workflow["nodes"]
    )
    # The independent tool remains available after the local Workflow completes.
    assert (
        ROOT
        / "skills/common/knowledge/hs-knowledge-publish-handoff/scripts/cli.py"
    ).is_file()


def test_public_mixed_candidate_routes_to_code_check_without_human_confirmation(tmp_path):
    fixture_path = ROOT / "skills/common/knowledge/hs-knowledge-source-scan/tests/conftest.py"
    spec = importlib.util.spec_from_file_location("workflow_mixed_public_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = fixture.Harness(tmp_path)
    bundle_ref, bundle = harness.capture("mixed-route")
    document = harness.write(".build/candidates/document.md", harness.card("document", bundle))
    code = harness.write(".build/candidates/code.md", harness.card("code", bundle).replace(b"review_mode: manual_document", b"review_mode: code_gate"))
    plan = harness.run("change-plan", {"operation_id": "mixed-route", "bundle_ref": bundle_ref, "decisions": [
        {"candidate_id": "document", "decision": "create", "reason": "Synthetic routing document", "card_inputs": [document]},
        {"candidate_id": "code", "decision": "create", "reason": "Synthetic routing code", "card_inputs": [code]},
    ]})
    view = harness.run("view-materialize", {"operation_id": "mixed-route", "plan_ref": plan["data"]["plan_ref"]})
    inspected = harness.run("candidate-inspect", {"operation_id": "mixed-route", "view_ref": view["data"]["view_ref"]})
    assert inspected["phase"] == "mixed_ready"
    workflow = yaml.safe_load((ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml").read_bytes())
    node = next(item for item in workflow["nodes"] if item["id"] == "inspect_candidate")
    assert {edge["id"]: edge["target"] for edge in node["exits"]}.get(inspected["phase"]) == "local_check"


def test_design_validation_checks_package_contracts_and_owners(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    assert module.validate(source) == []
    contract_path = (
        source
        / "skills/common/knowledge/hs-knowledge-source-capture/artifacts/result.yaml"
    )
    contract = yaml.safe_load(contract_path.read_bytes())
    contract["default_location"]["path"] = "node-result.md"
    contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert module.validate(source) == []  # a standard default path is legal
    workflow = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    document = yaml.safe_load(workflow.read_bytes())
    next(n for n in document["nodes"] if n["id"] == "review_content")["owner"] = "coder"
    workflow.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert any("review_content: wrong Skill/owner/type" in error for error in module.validate(source))


def test_instruction_skill_has_no_node_contract_but_keeps_strict_metadata(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-codegraph-setup"
    assert not (package / "scripts").exists() and not (package / "artifacts").exists()
    assert module.validate(source) == []
    (package / "SKILL.md").write_text(
        "---\nname: hs-codegraph-setup\nname: duplicate\ndescription: fixture\n---\n", encoding="utf-8")
    assert any("hs-codegraph-setup" in error for error in module.validate(source))


def test_instruction_skill_rejects_missing_reference_and_executable_content(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-codegraph-setup"
    reference = package / "references/codegraph.md"
    reference.unlink()
    assert any("INVALID_INSTRUCTION_REFERENCE" in error for error in module.validate(source))
    reference.write_text("# Commands\n", encoding="utf-8")
    (package / "references/setup.py").write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    assert any("UNPUBLISHABLE_INSTRUCTION_FILE" in error for error in module.validate(source))


def test_instruction_exception_does_not_relax_node_cli_requirements(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    (source / "skills/common/knowledge/hs-knowledge-query/scripts/cli.py").unlink()
    assert any("hs-knowledge-query: missing scripts/cli.py" in error for error in module.validate(source))


def test_missing_reference_or_wrong_artifact_exit_is_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-apply/artifacts"
    (package / "review-guide.md").unlink()
    assert any("review_guide" in error for error in module.validate(source))
    (package / "review-guide.md").write_text("# Review\n", encoding="utf-8")
    contract = yaml.safe_load((package / "result.yaml").read_bytes())
    contract["required_on"]["exit_ids"] = ["made_up_success"]
    (package / "result.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert any("exit" in error.lower() for error in module.validate(source))


def test_cross_template_edge_and_apply_after_index_failure_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    doc = yaml.safe_load(path.read_bytes())
    node = next(n for n in doc["nodes"] if n["id"] == "query_regression")
    next(e for e in node["exits"] if e["id"] == "blocked")["target"] = "apply_view"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert any("transition" in e.lower() for e in module.validate(source))


def test_real_pinned_openflow_loader(tmp_path):
    upstream = os.environ.get("FACTUM_OPENFLOW_SOURCE")
    if not upstream:
        pytest.skip(
            "set FACTUM_OPENFLOW_SOURCE to verified OpenFlow@1901a4 checkout for upstream integration"
        )
    source = fixture_packages(tmp_path / "fixture")
    destination = tmp_path / "installed"
    installed = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--source-root",
            str(source),
            "--destination",
            str(destination),
            "--python",
            sys.executable,
        ],
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr
    result = validator_module().validate_openflow(Path(upstream), destination)
    assert result["workflow_ids"] == ["hs-knowledge-ingest"]
    assert result["skill_count"] == 19
    assert result["contract_count"] == 22


