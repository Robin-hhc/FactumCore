"""Static package and Workflow source checks, independent of a workflow engine."""

import importlib.util
from pathlib import Path
import shutil

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / "himate/himate-knowledge-wifi-mp/evals/validate_design.py"


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
            "references/results/templates/result.md": "# Result\n",
            "references/results/writing-guide.md": "# Writing\n",
            "references/results/review-guide.md": "# Review\n",
        }
        contract = {
            "id": module.PRIMARY_ARTIFACT_IDS.get(skill, skill + "-result"),
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
    for relative in ("knowledge.py", "knowledge.sh", "knowledge.cmd", "runtime/manifest.json",
                     "runtime/requirements.lock.txt", "runtime/himate_knowledge/__init__.py",
                     "runtime/himate_knowledge/cli.py"):
        path = root / "himate/himate-knowledge-wifi-mp" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic repository runtime\n", encoding="utf-8")
    return root


def test_instruction_sources_do_not_need_private_scripts_tests_or_locks(tmp_path):
    module = validator_module()
    assert module.validate(fixture_packages(tmp_path / "fixture")) == []


@pytest.mark.parametrize("resource", ["scripts/cli.py", "tests/test_hidden.py", "requirements.lock.txt"])
def test_instruction_sources_reject_executable_or_test_ownership(tmp_path, resource):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "skills/common/knowledge/hs-knowledge-query" / resource
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic wrong owner", encoding="utf-8")
    assert any("Skill source owns implementation" in error for error in module.validate(source))


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
@pytest.mark.parametrize("markers", [(), ("__start__",), ("__end__",), ("__start__", "__end__")])
def test_layout_accepts_optional_canvas_endpoints(tmp_path, workflow, markers):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge" / workflow / "layouts.yaml"
    layout = yaml.safe_load(path.read_bytes())
    coordinates = layout["canvas"]["nodes"]
    for marker in ("__start__", "__end__"):
        coordinates.pop(marker, None)
    for marker in markers:
        coordinates[marker] = {"x": 0, "y": 0}
    path.write_text(yaml.safe_dump(layout), encoding="utf-8")
    assert module.validate(source) == []


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
def test_layout_rejects_unknown_canvas_nodes(tmp_path, workflow):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge" / workflow / "layouts.yaml"
    layout = yaml.safe_load(path.read_bytes())
    layout["canvas"]["nodes"]["unexpected_canvas_node"] = {"x": 0, "y": 0}
    path.write_text(yaml.safe_dump(layout), encoding="utf-8")
    assert any(workflow + ": layout identity/node set mismatch" == error
               for error in module.validate(source))


def test_public_capabilities_separate_review_and_each_patrol_task():
    assert set(validator_module().SKILLS) == {
        "hs-knowledge-source",
        "hs-knowledge-change-plan", "hs-knowledge-view-materialize", "hs-knowledge-review",
        "hs-knowledge-record", "hs-knowledge-apply", "hs-knowledge-query", "hs-knowledge-maintain",
        "hs-knowledge-patrol-sync", "hs-knowledge-patrol-plan",
        "hs-knowledge-patrol-reindex", "hs-knowledge-patrol-complete",
    }


def test_removed_explore_skill_cannot_reappear_as_an_active_package(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-explore"
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text(
        "---\nname: hs-knowledge-explore\ndescription: old routing skill\n---\n# Old router\n",
        encoding="utf-8",
    )
    assert any("active Skill set mismatch" in error and "hs-knowledge-explore" in error
               for error in module.validate(source))


@pytest.mark.parametrize("node_id", ["sync_workspace", "plan_patrol", "refresh_index", "complete_patrol"])
def test_patrol_node_cannot_reload_general_maintenance_context(tmp_path, node_id):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    next(row for row in value["nodes"] if row["id"] == node_id)["skill"] = "hs-knowledge-maintain"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert f"hs-knowledge-lint.{node_id}: wrong Skill/owner/type" in module.validate(source)


@pytest.mark.parametrize("skill", ["patrol-sync", "patrol-plan", "patrol-reindex", "patrol-complete"])
def test_each_patrol_result_is_scoped_only_to_its_own_node_and_exits(tmp_path, skill):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / f"skills/common/knowledge/hs-knowledge-{skill}/artifacts/result.yaml"
    value = yaml.safe_load(path.read_bytes())
    value["applies_to"]["node_ids"].append("prepare_sources")
    value["required_on"]["exit_ids"].append("prepared")
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    errors = module.validate(source)
    assert f"hs-knowledge-{skill}: artifact node scope mismatch" in errors
    assert f"hs-knowledge-{skill}: artifact exit obligations mismatch" in errors


def test_review_keeps_the_existing_host_identity_and_rejects_old_skill_package(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-review"
    contract = yaml.safe_load((package / "artifacts/result.yaml").read_bytes())
    assert contract["id"] == "hs-knowledge-lint-result"
    shutil.copytree(package, package.with_name("hs-knowledge-lint"))
    assert any("active Skill set mismatch" in error and "hs-knowledge-lint" in error
               for error in module.validate(source))


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
def test_record_node_cannot_load_the_source_preparation_skill(tmp_path, workflow):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge" / workflow / "workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    node = next(row for row in value["nodes"] if row["id"] == "record_ingest")
    node["skill"] = "hs-knowledge-source"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert f"{workflow}.record_ingest: wrong Skill/owner/type" in module.validate(source)


@pytest.mark.parametrize("field,value,diagnostic", [
    ("id", "hs-knowledge-record-result", "artifact ID must be globally unique and exact"),
    ("applies_to", {"node_ids": ["prepare_sources"]}, "artifact node scope mismatch"),
    ("required_on", {"exit_ids": ["prepared"]}, "artifact exit obligations mismatch"),
])
def test_record_report_keeps_its_exact_host_identity_and_p6_scope(tmp_path, field, value, diagnostic):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "skills/common/knowledge/hs-knowledge-record/artifacts/result.yaml"
    contract = yaml.safe_load(path.read_bytes())
    contract[field] = value
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert "hs-knowledge-record: " + diagnostic in module.validate(source)


def test_source_package_cannot_keep_a_second_p6_report_declaration(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package_root = source / "skills/common/knowledge"
    old = package_root / "hs-knowledge-source/artifacts/record-result.yaml"
    shutil.copyfile(package_root / "hs-knowledge-record/artifacts/result.yaml", old)
    assert "hs-knowledge-source: exact artifact contract set mismatch" in module.validate(source)


@pytest.mark.parametrize("name", ["hs-knowledge-candidate-revise", "hs-knowledge-source-scan", "hs-knowledge-source-prepare"])
def test_active_old_skill_is_rejected_but_empty_historical_directory_is_not(tmp_path, name):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge" / name
    package.mkdir()
    assert module.validate(source) == []
    (package / "SKILL.md").write_text("# Active legacy package\n", encoding="utf-8")
    assert any("active Skill set mismatch" in error and name in error
               for error in module.validate(source))


def test_ingest_stays_complete_beside_the_governance_lint_template():
    ingest = yaml.safe_load(
        (
            ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
        ).read_bytes()
    )
    nodes = {n["id"]: n for n in ingest["nodes"]}
    assert ingest["entry_node"] == "prepare_sources"
    assert "bind_project" not in nodes and "governance_handoff" not in nodes
    assert (ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml").is_file()
    assert not any(node["type"] == "gate" for node in nodes.values())
    assert not {"prepare_confirmation", "final_view_user_gate", "record_confirmation"} & nodes.keys()
    assert list(nodes) == ["prepare_sources", "plan_change",
                           "materialize_view", "lint_view", "record_ingest", "apply_view"]
    assert [(key, node["owner"]) for key, node in nodes.items()] == [
        ("prepare_sources", "coder"),
        ("plan_change", "coder"), ("materialize_view", "coder"),
        ("lint_view", "reviewer"), ("record_ingest", "coder"), ("apply_view", "coder"),
    ]
    assert "verify_merge" not in nodes and "maintain_knowledge" not in nodes
    assert nodes["lint_view"]["skill"] == "hs-knowledge-review"
    assert nodes["prepare_sources"]["skill"] == "hs-knowledge-source"
    assert nodes["record_ingest"]["skill"] == "hs-knowledge-record"
    assert {e["id"]: e["target"] for e in nodes["record_ingest"]["exits"]}["recorded"] == "apply_view"
    routes = {edge["id"]: edge["target"] for edge in nodes["prepare_sources"]["exits"]}
    assert routes == {"prepared": "plan_change", "unchanged": "__end__"}
    assert "knowledge.py source" in nodes["prepare_sources"]["prompt"]
    assert "prepare" in nodes["prepare_sources"]["prompt"]
    assert "record" in nodes["record_ingest"]["prompt"]
    for identity in ("plan_change", "materialize_view", "lint_view"):
        assert {edge["id"]: edge["target"] for edge in nodes[identity]["exits"]}["needs_material"] == "prepare_sources"
    assert "proof_set" not in nodes["apply_view"]["prompt"]


def test_lint_workflow_filters_changes_then_reuses_ingest_without_nested_workflows():
    workflow = yaml.safe_load(
        (ROOT / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml").read_bytes()
    )
    assert workflow["entry_node"] == "sync_workspace"
    assert workflow["entry"] == {"skill": "hs-knowledge-patrol-sync"}
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert list(nodes) == ["sync_workspace", "plan_patrol", "prepare_sources", "plan_change",
                           "materialize_view", "lint_view", "record_ingest", "apply_view",
                           "refresh_index", "complete_patrol"]
    assert {e["id"]: e["target"] for e in nodes["plan_patrol"]["exits"]} == {
        "needs_ingest": "prepare_sources", "needs_index": "refresh_index",
        "unchanged": "complete_patrol", "blocked": "__end__",
    }
    assert {e["id"]: e["target"] for e in nodes["apply_view"]["exits"]} == {
        "completed": "complete_patrol", "recorded": "complete_patrol"}
    assert "patrol sync" in nodes["sync_workspace"]["prompt"]
    assert "patrol plan" in nodes["plan_patrol"]["prompt"]
    assert "source_request" in nodes["prepare_sources"]["prompt"]
    assert "prepare" in nodes["prepare_sources"]["prompt"]
    assert "patrol complete" in nodes["complete_patrol"]["prompt"]
    assert {node: nodes[node]["skill"] for node in (
        "sync_workspace", "plan_patrol", "refresh_index", "complete_patrol"
    )} == {
        "sync_workspace": "hs-knowledge-patrol-sync",
        "plan_patrol": "hs-knowledge-patrol-plan",
        "refresh_index": "hs-knowledge-patrol-reindex",
        "complete_patrol": "hs-knowledge-patrol-complete",
    }
    assert all(node["skill"] != "hs-knowledge-maintain" for node in nodes.values())
    ingest = yaml.safe_load((ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml").read_bytes())
    original = {node["id"]: node for node in ingest["nodes"]}
    for identity in ("plan_change", "materialize_view", "lint_view", "record_ingest"):
        assert nodes[identity] == original[identity]
    assert nodes["apply_view"]["prompt"] == original["apply_view"]["prompt"]
    assert nodes["lint_view"]["owner"] == "reviewer"
    assert all(not any(key in node for key in ("workflow", "runner", "run")) for node in nodes.values())


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
        / "himate/himate-knowledge-wifi-mp/runtime/himate_knowledge/stages/apply/cli.py"
    ).is_file()


def test_public_mixed_candidate_keeps_classification_and_routes_to_independent_p5(tmp_path):
    from support.stages import source as fixture
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
    assert (reviewer["skill"], reviewer["owner"]) == ("hs-knowledge-review", "reviewer")


def test_design_validation_checks_package_contracts_and_owners(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    assert module.validate(source) == []
    contract_path = (
        source
        / "skills/common/knowledge/hs-knowledge-source/artifacts/result.yaml"
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
    ("name: hs-knowledge-source\ndescription: ''", "missing or inconsistent Skill identity"),
    ("name: hs-knowledge-source\nname: duplicate\ndescription: fixture", "duplicate YAML key"),
])
def test_node_skill_rejects_invalid_metadata(tmp_path, metadata, diagnostic):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "skills/common/knowledge/hs-knowledge-source/SKILL.md"
    path.write_text("---\n" + metadata + "\n---\n# Fixture\n", encoding="utf-8")
    assert any("hs-knowledge-source" in error and diagnostic in error
               for error in module.validate(source))


def test_node_skill_requires_entry_document(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    (source / "skills/common/knowledge/hs-knowledge-source/SKILL.md").unlink()
    assert any("hs-knowledge-source" in error and "SKILL.md" in error
               for error in module.validate(source))


def test_instruction_skill_does_not_require_a_private_cli(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-query"
    assert not (package / "scripts").exists()
    assert not (package / "tests").exists()
    assert not list(package.glob("requirements*.txt"))
    assert not any("hs-knowledge-query: missing scripts/" in error
                   or "hs-knowledge-query: missing requirements" in error
                   for error in module.validate(source))


def test_repository_execution_entry_is_required(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    (source / "himate/himate-knowledge-wifi-mp/knowledge.py").unlink()
    assert any("repository runtime: missing knowledge.py" in error for error in module.validate(source))


def test_missing_reference_or_wrong_artifact_exit_is_rejected(tmp_path):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    package = source / "skills/common/knowledge/hs-knowledge-apply/artifacts"
    guide = package.parent / "references/results/review-guide.md"
    guide.unlink()
    assert any("review_guide" in error for error in module.validate(source))
    guide.write_text("# Review\n", encoding="utf-8")
    contract = yaml.safe_load((package / "result.yaml").read_bytes())
    contract["required_on"]["exit_ids"] = ["made_up_success"]
    (package / "result.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert any("exit" in error.lower() for error in module.validate(source))


@pytest.mark.parametrize("mutation", ["stale_prepare", "unscoped_old_node", "extra_exit", "missing_failure_report"])
def test_artifact_contracts_reject_retired_scope_and_missing_real_obligations(tmp_path, mutation):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    if mutation == "stale_prepare":
        package = source / "skills/common/knowledge/hs-knowledge-source/artifacts"
        shutil.copyfile(package / "result.yaml", package / "prepare-result.yaml")
        assert any("exact artifact contract set mismatch" in error for error in module.validate(source))
        return
    skill = "hs-knowledge-query" if mutation == "unscoped_old_node" else "hs-knowledge-review"
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
    ("prepare_sources", "prepared", "lint_view"),
    ("plan_change", "needs_material", "prepare_material"),
    ("materialize_view", "ready", "record_ingest"),
    ("lint_view", "needs_material", "scan_sources"),
    ("lint_view", "needs_revision", "plan_change"),
    ("record_ingest", "recorded", "__end__"),
])
def test_six_node_graph_rejects_skipped_review_wrong_reentry_and_retired_nodes(tmp_path, node_id, exit_id, target):
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
    ("wrong_skill", "wrong Skill/owner/type"),
    ("skip_completion", "unsafe or missing transition"),
    ("cross_template", "unsafe or missing transition"),
    ("extra_writer", "complete node set/uniqueness mismatch"),
    ("external_runner", "unsupported runtime field"),
    ("child_workflow", "unsupported runtime field"),
])
def test_governance_lint_workflow_rejects_shortcuts_and_external_calls(tmp_path, mutation, expected):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    workflow = yaml.safe_load(path.read_bytes())
    sync, plan = workflow["nodes"][:2]
    if mutation == "wrong_entry":
        workflow["entry_node"] = "plan_patrol"
    elif mutation == "wrong_skill":
        plan["skill"] = "hs-knowledge-apply"
    elif mutation == "skip_completion":
        apply = next(node for node in workflow["nodes"] if node["id"] == "apply_view")
        apply["exits"][0]["target"] = "__end__"
    elif mutation == "cross_template":
        plan["exits"][0]["target"] = "hs-knowledge-ingest:prepare_sources"
    elif mutation == "extra_writer":
        workflow["nodes"].append({"id": "apply", "type": "skill", "owner": "coder",
                                  "skill": "hs-knowledge-apply", "prompt": "write", "exits": []})
    elif mutation == "external_runner":
        plan["runner"] = "python external.py"
    elif mutation == "child_workflow":
        plan["workflow"] = "hs-knowledge-ingest"
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
def test_ingest_rejects_implicit_history_resume_from_preparation(tmp_path, exit_id):
    module = validator_module()
    source = fixture_packages(tmp_path / "fixture")
    path = source / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    workflow = yaml.safe_load(path.read_bytes())
    node = next(item for item in workflow["nodes"] if item["id"] == "prepare_sources")
    node["exits"].append({"id": exit_id, "label": "old history", "condition": "old fact", "target": "apply_view"})
    path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
    assert any(".prepare_sources: unsafe or missing transition" in error for error in module.validate(source))
