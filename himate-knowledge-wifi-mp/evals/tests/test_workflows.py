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


def test_final_public_capability_set_is_exactly_nine_skills():
    assert set(validator_module().SKILLS) == {
        "hs-knowledge-explore", "hs-knowledge-source-scan", "hs-knowledge-source-prepare",
        "hs-knowledge-change-plan", "hs-knowledge-view-materialize", "hs-knowledge-lint",
        "hs-knowledge-apply", "hs-knowledge-query", "hs-knowledge-maintain",
    }


def test_active_old_skill_is_rejected_but_empty_historical_directory_is_not(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-candidate-revise"
    package.mkdir()
    assert module.validate(source) == []
    (package / "SKILL.md").write_text("# Active legacy package\n", encoding="utf-8")
    assert any("active Skill set mismatch" in error and "hs-knowledge-candidate-revise" in error
               for error in module.validate(source))


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
    assert list(nodes) == ["scan_sources", "prepare_material", "plan_change",
                           "materialize_view", "lint_view", "record_ingest", "apply_view"]
    assert [(key, node["owner"]) for key, node in nodes.items()] == [
        ("scan_sources", "coder"), ("prepare_material", "coder"),
        ("plan_change", "coder"), ("materialize_view", "coder"),
        ("lint_view", "reviewer"), ("record_ingest", "coder"), ("apply_view", "coder"),
    ]
    assert "verify_merge" not in nodes and "maintain_knowledge" not in nodes
    assert nodes["lint_view"]["skill"] == "hs-knowledge-lint"
    assert nodes["prepare_material"]["skill"] == "hs-knowledge-source-prepare"
    assert nodes["record_ingest"]["skill"] == "hs-knowledge-source-scan"
    assert {e["id"]: e["target"] for e in nodes["record_ingest"]["exits"]}["recorded"] == "apply_view"
    routes = {edge["id"]: edge["target"] for edge in nodes["scan_sources"]["exits"]}
    assert routes == {"scanned": "prepare_material", "unchanged": "__end__"}
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

    assert destination("apply_view", "completed") == "__end__"
    assert destination("apply_view", "recorded") == "__end__"
    assert "publish_handoff" not in nodes
    assert "submit_batch" not in nodes
    assert not any(
        node.get("skill") == "hs-knowledge-publish-handoff"
        for node in workflow["nodes"]
    )
    # The independent tool remains available after the local Workflow completes.
    assert (
        ROOT
        / "skills/common/knowledge/hs-knowledge-apply/scripts/cli.py"
    ).is_file()


def test_public_mixed_candidate_keeps_classification_and_routes_to_independent_p5(tmp_path):
    fixture_path = ROOT / "skills/common/knowledge/hs-knowledge-source-scan/tests/conftest.py"
    spec = importlib.util.spec_from_file_location("workflow_mixed_public_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = fixture.Harness(tmp_path)
    bundle_ref, bundle = harness.capture("mixed-route")
    document = harness.write(".build/candidates/document.md", harness.card("document", bundle))
    code = harness.write(".build/candidates/code.md", harness.card("code", bundle).replace(b"review_mode: manual_document", b"review_mode: code_gate"))
    view = harness.run("view-materialize", {"operation_id": "mixed-route", "bundle_ref": bundle_ref, "decisions": [
        {"candidate_id": "document", "decision": "create", "reason": "Synthetic routing document", "card_inputs": [document]},
        {"candidate_id": "code", "decision": "create", "reason": "Synthetic routing code", "card_inputs": [code]},
    ]})
    inspected = harness.run("view-materialize", {"operation_id": "mixed-route", "view_ref": view["data"]["view_ref"]}, action="describe")
    assert inspected["phase"] == "described"
    assert inspected["data"]["review_mode"] == "mixed"
    assert inspected["data"]["view_digest"] == view["data"]["view_digest"]
    assert harness.record(view["data"]["view_ref"])["review_requirements"] == {
        "manual_document": ["knowledge/rules/document.md"],
        "code_gate": ["knowledge/rules/code.md"],
    }
    workflow = yaml.safe_load((ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml").read_bytes())
    node = next(item for item in workflow["nodes"] if item["id"] == "materialize_view")
    assert {edge["id"]: edge["target"] for edge in node["exits"]}["ready"] == "lint_view"
    reviewer = next(item for item in workflow["nodes"] if item["id"] == "lint_view")
    assert (reviewer["skill"], reviewer["owner"]) == ("hs-knowledge-lint", "reviewer")


def test_design_validation_checks_package_contracts_and_owners(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    assert module.validate(source) == []
    contract_path = (
        source
        / "skills/common/knowledge/hs-knowledge-source-prepare/artifacts/result.yaml"
    )
    contract = yaml.safe_load(contract_path.read_bytes())
    contract["default_location"]["path"] = "node-result.md"
    contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert module.validate(source) == []  # a standard default path is legal
    workflow = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    document = yaml.safe_load(workflow.read_bytes())
    next(n for n in document["nodes"] if n["id"] == "lint_view")["owner"] = "coder"
    workflow.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert any("lint_view: wrong Skill/owner/type" in error for error in module.validate(source))


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


@pytest.mark.parametrize("mutation", ["stale_prepare", "unscoped_old_node", "extra_exit", "missing_failure_report"])
def test_artifact_contracts_reject_retired_scope_and_missing_real_obligations(tmp_path, mutation):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    if mutation == "stale_prepare":
        package = source / "skills/common/knowledge/hs-knowledge-source-scan/artifacts"
        shutil.copyfile(package / "record-result.yaml", package / "prepare-result.yaml")
        assert any("exact artifact contract set mismatch" in error for error in module.validate(source))
        return
    skill = "hs-knowledge-query" if mutation == "unscoped_old_node" else "hs-knowledge-lint"
    path = source / "skills/common/knowledge" / skill / "artifacts/result.yaml"
    contract = yaml.safe_load(path.read_bytes())
    if mutation == "unscoped_old_node":
        contract["applies_to"]["node_ids"] = ["query_regression"]
    elif mutation == "extra_exit":
        contract["required_on"]["exit_ids"].append("reviewed")
    else:
        contract["required_on"]["exit_ids"].remove("needs_material")
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert any(skill in error and "artifact" in error for error in module.validate(source))


@pytest.mark.parametrize("node_id,exit_id,target", [
    ("prepare_material", "source_changed", "plan_change"),
    ("plan_change", "needs_material", "scan_sources"),
    ("materialize_view", "ready", "record_ingest"),
    ("lint_view", "needs_material", "scan_sources"),
    ("lint_view", "needs_revision", "plan_change"),
    ("record_ingest", "recorded", "__end__"),
])
def test_seven_stage_graph_rejects_skipped_review_wrong_reentry_and_full_rescan(tmp_path, node_id, exit_id, target):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    workflow = yaml.safe_load(path.read_bytes())
    node = next(item for item in workflow["nodes"] if item["id"] == node_id)
    next(edge for edge in node["exits"] if edge["id"] == exit_id)["target"] = target
    path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    assert any(f".{node_id}: unsafe or missing transition" in error
               for error in module.validate(source))


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


def test_apply_cannot_restart_materialization_after_its_completion_exit(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    doc = yaml.safe_load(path.read_bytes())
    node = next(n for n in doc["nodes"] if n["id"] == "apply_view")
    next(e for e in node["exits"] if e["id"] == "completed")["target"] = "materialize_view"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert any("transition" in e.lower() for e in module.validate(source))


@pytest.mark.parametrize("exit_id", ["recover", "resume_index", "resume_queries"])
def test_ingest_rejects_implicit_history_resume_from_p1(tmp_path, exit_id):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    workflow = yaml.safe_load(path.read_bytes())
    node = next(item for item in workflow["nodes"] if item["id"] == "scan_sources")
    node["exits"].append({"id": exit_id, "label": "old history", "condition": "old fact", "target": "apply_view"})
    path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    assert any(".scan_sources: unsafe or missing transition" in error for error in module.validate(source))
