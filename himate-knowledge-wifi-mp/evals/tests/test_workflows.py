"""Static package and Workflow source checks, independent of a workflow engine."""

import importlib.util
from pathlib import Path
import shutil

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "himate-knowledge-wifi-mp/evals/validate_design.py"


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
            extra = {**contract, "id": module.EXTRA_ARTIFACT_IDS.get((skill, name), skill + "-" + name[:-5]),
                     "applies_to": {"node_ids": mapping[0]}, "required_on": {"exit_ids": mapping[1]}}
            files["artifacts/" + name] = yaml.safe_dump(extra)
        for relative, data in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
    shutil.copytree(ROOT / "workflows", root / "workflows")
    return root


def test_ingest_stays_complete_beside_the_read_only_lint_template():
    ingest = yaml.safe_load(
        (
            ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
        ).read_bytes()
    )
    nodes = {n["id"]: n for n in ingest["nodes"]}
    assert ingest["entry_node"] == "scan_sources"
    assert "bind_project" not in nodes and "governance_handoff" not in nodes
    assert (ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml").is_file()
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
    assert "保留历史卡输入" in nodes["apply_view"]["prompt"]
    assert "proof_set" not in nodes["apply_view"]["prompt"]


def test_lint_workflow_is_two_read_only_skills_with_a_report_exit():
    workflow = yaml.safe_load(
        (ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml").read_bytes()
    )
    assert workflow["entry_node"] == "check_formal"
    assert workflow["entry"] == {"skill": "hs-knowledge-lint"}
    nodes = workflow["nodes"]
    assert [(node["id"], node["type"], node["owner"], node["skill"]) for node in nodes] == [
        ("check_formal", "skill", "reviewer", "hs-knowledge-lint"),
        ("audit_references", "skill", "reviewer", "hs-knowledge-maintain"),
    ]
    assert [{edge["id"]: edge["target"] for edge in node["exits"]} for node in nodes] == [
        {"checked": "audit_references"}, {"reported": "__end__"},
    ]
    # A report can be complete as an artifact while retaining failed checks.
    assert "failed" in nodes[0]["exits"][0]["condition"]
    assert "incomplete" in nodes[0]["exits"][0]["condition"]
    assert "audit-references" in nodes[1]["prompt"]


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


@pytest.mark.parametrize("metadata,diagnostic", [
    ("name: wrong\ndescription: fixture", "missing or inconsistent Skill identity"),
    ("name: hs-knowledge-explore\ndescription: ''", "missing or inconsistent Skill identity"),
    ("name: hs-knowledge-explore\nname: duplicate\ndescription: fixture", "duplicate YAML key"),
])
def test_node_skill_rejects_invalid_metadata(tmp_path, metadata, diagnostic):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "skills/common/knowledge/hs-knowledge-explore/SKILL.md"
    path.write_text("---\n" + metadata + "\n---\n# Fixture\n", encoding="utf-8")
    assert any("hs-knowledge-explore" in error and diagnostic in error
               for error in module.validate(source))


def test_node_skill_requires_entry_document(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    (source / "skills/common/knowledge/hs-knowledge-explore/SKILL.md").unlink()
    assert any("hs-knowledge-explore" in error and "SKILL.md" in error
               for error in module.validate(source))


def test_node_skill_requires_cli(tmp_path):
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


@pytest.mark.parametrize("mutation, expected", [
    ("wrong_entry", "invalid template identity/entry"),
    ("write_skill", "wrong Skill/owner/type"),
    ("skip_audit", "unsafe or missing transition"),
    ("cross_template", "unsafe or missing transition"),
    ("extra_writer", "complete node set/uniqueness mismatch"),
    ("external_runner", "unsupported runtime field"),
    ("child_workflow", "unsupported runtime field"),
])
def test_read_only_lint_workflow_rejects_writers_shortcuts_and_external_calls(tmp_path, mutation, expected):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    workflow = yaml.safe_load(path.read_bytes())
    check, audit = workflow["nodes"]
    if mutation == "wrong_entry":
        workflow["entry_node"] = "audit_references"
    elif mutation == "write_skill":
        audit["skill"] = "hs-knowledge-apply"
    elif mutation == "skip_audit":
        check["exits"][0]["target"] = "__end__"
    elif mutation == "cross_template":
        check["exits"][0]["target"] = "hs-knowledge-ingest:scan_sources"
    elif mutation == "extra_writer":
        workflow["nodes"].append({"id": "apply", "type": "skill", "owner": "coder",
                                  "skill": "hs-knowledge-apply", "prompt": "write", "exits": []})
    elif mutation == "external_runner":
        audit["runner"] = "python external.py"
    elif mutation == "child_workflow":
        audit["workflow"] = "hs-knowledge-ingest"
    path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    assert any(expected in error for error in module.validate(source))


@pytest.mark.parametrize("mutation", ["wrong_id", "wrong_scope", "optional"])
def test_audit_report_contract_keeps_its_exact_identity_scope_and_obligation(tmp_path, mutation):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "skills/common/knowledge/hs-knowledge-maintain/artifacts/audit-result.yaml"
    contract = yaml.safe_load(path.read_bytes())
    assert contract["id"] == "hs-knowledge-code-reference-audit"
    if mutation == "wrong_id":
        contract["id"] = "hs-knowledge-maintain-result"
    elif mutation == "wrong_scope":
        contract["applies_to"]["node_ids"] = ["check_formal"]
    elif mutation == "optional":
        contract["required"] = False
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert any("hs-knowledge-maintain/audit-result.yaml" in error for error in module.validate(source))


def test_cross_template_edge_and_apply_after_index_failure_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    doc = yaml.safe_load(path.read_bytes())
    node = next(n for n in doc["nodes"] if n["id"] == "query_regression")
    next(e for e in node["exits"] if e["id"] == "content_error")["target"] = "apply_view"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert any("transition" in e.lower() for e in module.validate(source))
