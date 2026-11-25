"""Instruction packaging and the five-step graph, independent of host runtime."""

from __future__ import annotations

import importlib.util
import shutil

import pytest
import yaml

from support.contracts import CAPABILITIES_ROOT, TOOL_ROOT


def validator_module():
    path = TOOL_ROOT / "evals/validate_design.py"
    spec = importlib.util.spec_from_file_location("workflow_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def distribution(tmp_path):
    capabilities = tmp_path / "himate-skills"
    for name in ("skills", "workflows"):
        shutil.copytree(CAPABILITIES_ROOT / name, capabilities / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for relative in ("knowledge.py", "runtime/manifest.json",
                     "runtime/requirements.lock.txt", "runtime/himate_knowledge/__init__.py",
                     "runtime/himate_knowledge/cli.py"):
        path = tmp_path / "himate-tools" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic runtime placeholder\n", encoding="utf-8")
    return capabilities


def validate_distribution(capabilities):
    return validator_module().validate(capabilities.with_name("himate-tools"))


def workflow_nodes(workflow):
    graph = yaml.safe_load((CAPABILITIES_ROOT / "workflows" / workflow / "workflow.yaml").read_bytes())
    return {node["id"]: node for node in graph["nodes"]}


def follow(nodes, start, exits):
    current, trace = start, []
    for exit_id in exits:
        trace.append(current)
        choices = {edge["id"]: edge["target"] for edge in nodes[current]["exits"]}
        current = choices[exit_id]
    return trace, current


def test_current_distribution_is_structurally_valid():
    assert validator_module().validate(TOOL_ROOT, CAPABILITIES_ROOT) == []


@pytest.mark.parametrize("skill,operation", [
    ("source", "ingest_scan"),
    ("review", "ingest_check"),
    ("apply", "ingest_commit"),
    ("view-materialize", "source_register"),
    ("patrol-sync", "patrol_sync"),
    ("patrol-plan", "patrol_plan"),
    ("patrol-prepare", "maintain_prepare"),
    ("patrol-review", "maintain_check"),
    ("patrol-apply", "maintain_commit"),
    ("patrol-reindex", "patrol_reindex"),
    ("patrol-complete", "patrol_complete"),
    ("query", "search"),
    ("maintain", "maintain_audit"),
])
def test_assigned_skills_name_their_harness_independent_mcp_operation(skill, operation):
    instruction = CAPABILITIES_ROOT / "skills" / f"hs-knowledge-{skill}" / "SKILL.md"
    body = instruction.read_text(encoding="utf-8")
    assert f"`knowledge_{operation}`" in body
    assert "`hs-knowledge-setup`" in body
    assert "OpenFlow" not in body


@pytest.mark.parametrize(("workflow", "first_node"), [
    ("hs-knowledge-ingest", "prepare_sources"), ("hs-knowledge-lint", "sync_workspace"),
])
def test_workflow_bootstraps_on_the_bound_execution_end(workflow, first_node):
    prompt = workflow_nodes(workflow)[first_node]["prompt"]
    assert "`knowledge_doctor`" in prompt
    assert "--knowledge-root" in prompt
    assert "data.runtime_version" in prompt
    assert "hs-knowledge-setup" in prompt
    assert "OpenFlow" not in prompt


def test_five_steps_keep_decision_writing_and_independent_review_separate():
    graph = yaml.safe_load((CAPABILITIES_ROOT / "workflows/hs-knowledge-ingest/workflow.yaml").read_bytes())
    nodes = {row["id"]: row for row in graph["nodes"]}
    assert list(nodes) == ["prepare_sources", "plan_change", "materialize_view", "lint_view", "apply_view"]
    assert [row["owner"] for row in nodes.values()] == ["coder", "coder", "coder", "reviewer", "coder"]
    assert {row["id"]: row["target"] for row in nodes["plan_change"]["exits"]}["content_planned"] == "materialize_view"
    assert {row["id"]: row["target"] for row in nodes["lint_view"]["exits"]} == {
        "passed": "apply_view", "needs_plan": "plan_change", "needs_revision": "materialize_view",
    }


def test_ingest_completed_batch_returns_to_scan_before_normal_completion():
    graph = yaml.safe_load((CAPABILITIES_ROOT / "workflows/hs-knowledge-ingest/workflow.yaml").read_bytes())
    edges = {row["id"]: {edge["id"]: edge["target"] for edge in row["exits"]}
             for row in graph["nodes"]}
    assert edges["apply_view"] == {
        "completed": "prepare_sources", "needs_revision": "materialize_view",
        "retry": "apply_view", "failed": "__end__",
    }
    assert edges["prepare_sources"] == {
        "prepared": "plan_change", "next_upload_source": "prepare_sources",
        "unchanged": "__end__", "blocked": "__end__",
    }
    assert edges["plan_change"]["deferred"] == "__end__"


def test_patrol_reselects_after_completed_or_already_completed_selected_source():
    graph = yaml.safe_load((CAPABILITIES_ROOT / "workflows/hs-knowledge-lint/workflow.yaml").read_bytes())
    edges = {row["id"]: {edge["id"]: edge["target"] for edge in row["exits"]}
             for row in graph["nodes"]}
    assert edges["apply_view"] == {
        "completed": "plan_patrol", "needs_revision": "materialize_view",
        "retry": "apply_view", "failed": "complete_patrol",
    }
    assert edges["prepare_sources"]["unchanged"] == "plan_patrol"
    assert edges["prepare_sources"]["blocked"] == "complete_patrol"
    assert edges["plan_patrol"]["needs_ingest"] == "prepare_sources"
    assert edges["plan_patrol"]["unchanged"] == "complete_patrol"
    assert edges["plan_change"]["deferred"] == "complete_patrol"


def test_patrol_routes_documents_and_existing_card_maintenance_before_authoring():
    nodes = workflow_nodes("hs-knowledge-lint")
    decisions = {edge["id"]: edge["target"] for edge in nodes["plan_patrol"]["exits"]}
    assert decisions == {
        "needs_ingest": "prepare_sources", "needs_maintenance": "prepare_maintenance",
        "needs_reindex": "refresh_index", "unchanged": "complete_patrol", "blocked": "complete_patrol",
    }
    document_trace, document_end = follow(nodes, "plan_patrol", [
        "needs_ingest", "prepared", "content_planned", "ready", "passed", "completed",
    ])
    assert document_trace == [
        "plan_patrol", "prepare_sources", "plan_change", "materialize_view", "lint_view", "apply_view",
    ]
    assert document_end == "plan_patrol"
    maintenance_trace, maintenance_end = follow(nodes, "plan_patrol", [
        "needs_maintenance", "prepared", "ready", "passed", "completed",
    ])
    assert maintenance_trace == [
        "plan_patrol", "prepare_maintenance", "repair_cards", "review_maintenance", "apply_maintenance",
    ]
    assert maintenance_end == "plan_patrol"
    assert not set(document_trace[1:]) & set(maintenance_trace[1:])
    assert [nodes[node]["owner"] for node in maintenance_trace[1:]] == ["coder", "coder", "reviewer", "coder"]


def test_maintenance_revisions_and_input_refresh_stay_in_the_maintenance_branch():
    nodes = workflow_nodes("hs-knowledge-lint")
    trace, target = follow(nodes, "review_maintenance", ["needs_revision", "ready", "passed"])
    assert trace == ["review_maintenance", "repair_cards", "review_maintenance"]
    assert target == "apply_maintenance"
    for start in ("repair_cards", "review_maintenance", "apply_maintenance"):
        trace, target = follow(nodes, start, ["needs_preparation", "prepared"])
        assert trace == [start, "prepare_maintenance"]
        assert target == "repair_cards"
    trace, target = follow(nodes, "review_maintenance", ["deferred", "completed"])
    assert trace == ["review_maintenance", "complete_patrol"]
    assert target == "__end__"


@pytest.mark.parametrize("workflow,publish,failed", [
    ("hs-knowledge-ingest", "apply_view", "__end__"),
    ("hs-knowledge-lint", "apply_view", "complete_patrol"),
    ("hs-knowledge-lint", "apply_maintenance", "complete_patrol"),
])
def test_publication_retries_the_same_batch_and_unknown_state_stops(workflow, publish, failed):
    nodes = workflow_nodes(workflow)
    trace, target = follow(nodes, publish, ["retry", "retry", "failed"])
    assert trace == [publish, publish, publish]
    assert target == failed


def test_index_refresh_returns_to_selection_before_summary():
    nodes = workflow_nodes("hs-knowledge-lint")
    trace, target = follow(nodes, "plan_patrol", ["needs_reindex", "reindexed", "unchanged", "completed"])
    assert trace == ["plan_patrol", "refresh_index", "plan_patrol", "complete_patrol"]
    assert target == "__end__"


@pytest.mark.parametrize("workflow,node_id,exit_id,wrong_target", [
    ("hs-knowledge-ingest", "apply_view", "completed", "__end__"),
    ("hs-knowledge-ingest", "apply_view", "needs_revision", "prepare_sources"),
    ("hs-knowledge-ingest", "prepare_sources", "next_upload_source", "__end__"),
    ("hs-knowledge-ingest", "plan_change", "deferred", "prepare_sources"),
    ("hs-knowledge-lint", "apply_view", "completed", "prepare_sources"),
    ("hs-knowledge-lint", "apply_view", "needs_revision", "plan_patrol"),
    ("hs-knowledge-lint", "prepare_sources", "unchanged", "complete_patrol"),
    ("hs-knowledge-lint", "plan_change", "deferred", "plan_patrol"),
    ("hs-knowledge-lint", "plan_patrol", "needs_maintenance", "prepare_sources"),
    ("hs-knowledge-lint", "review_maintenance", "needs_revision", "materialize_view"),
    ("hs-knowledge-lint", "review_maintenance", "deferred", "prepare_maintenance"),
    ("hs-knowledge-lint", "apply_maintenance", "retry", "prepare_maintenance"),
    ("hs-knowledge-lint", "apply_maintenance", "completed", "complete_patrol"),
    ("hs-knowledge-lint", "apply_maintenance", "failed", "plan_patrol"),
    ("hs-knowledge-ingest", "apply_view", "retry", "prepare_sources"),
    ("hs-knowledge-ingest", "apply_view", "failed", "prepare_sources"),
])
def test_loop_boundaries_cannot_terminate_early_or_repeat_blocked_sources(
        distribution, workflow, node_id, exit_id, wrong_target):
    path = distribution / "workflows" / workflow / "workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    node = next(row for row in value["nodes"] if row["id"] == node_id)
    next(edge for edge in node["exits"] if edge["id"] == exit_id)["target"] = wrong_target
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any(node_id + ": unsafe or missing transition" in error
               for error in validate_distribution(distribution))


@pytest.mark.parametrize("skill", ["record", "explore", "lint"])
def test_retired_skills_cannot_reappear_as_active_packages(distribution, skill):
    package = distribution / "skills" / ("hs-knowledge-" + skill)
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text("---\nname: retired\ndescription: old capability\n---\n", encoding="utf-8")
    assert any("active Skill set mismatch" in error for error in validate_distribution(distribution))


@pytest.mark.parametrize("resource", ["scripts/cli.py", "tests/test_hidden.py", "requirements.lock.txt"])
def test_skill_packages_do_not_own_execution_or_test_code(distribution, resource):
    path = distribution / "skills/hs-knowledge-query" / resource
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic wrong owner", encoding="utf-8")
    assert any("Skill source owns implementation" in error for error in validate_distribution(distribution))


def test_setup_skill_requires_its_launcher_and_rejects_extra_scripts(distribution):
    package = distribution / "skills/hs-knowledge-setup"
    (package / "scripts/setup.cjs").unlink()
    (package / "scripts/extra.cjs").write_text("synthetic wrong owner", encoding="utf-8")
    errors = validate_distribution(distribution)
    assert "hs-knowledge-setup: missing setup launcher scripts/setup.cjs" in errors
    assert "hs-knowledge-setup: Skill source owns implementation, tests or dependency locks" in errors


def test_authoring_template_links_resolve_within_the_skill_package(distribution):
    package = distribution / "skills/hs-knowledge-view-materialize"
    (package / "references/templates/entity.md").unlink()
    assert any("unavailable local reference templates/entity.md" in error
               for error in validate_distribution(distribution))


@pytest.mark.parametrize("workflow,node_id", [
    ("hs-knowledge-ingest", "lint_view"),
    ("hs-knowledge-lint", "lint_view"),
    ("hs-knowledge-lint", "review_maintenance"),
])
def test_review_cannot_run_as_the_author(distribution, workflow, node_id):
    path = distribution / "workflows" / workflow / "workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    next(row for row in value["nodes"] if row["id"] == node_id)["owner"] = "coder"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any(node_id + ": wrong Skill/owner/type" in error for error in validate_distribution(distribution))


@pytest.mark.parametrize("node_id", [
    "sync_workspace", "plan_patrol", "prepare_maintenance", "repair_cards",
    "review_maintenance", "apply_maintenance", "refresh_index", "complete_patrol",
])
def test_each_patrol_step_has_its_own_narrow_skill(distribution, node_id):
    path = distribution / "workflows/hs-knowledge-lint/workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    next(row for row in value["nodes"] if row["id"] == node_id)["skill"] = "hs-knowledge-maintain"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any(node_id + ": wrong Skill/owner/type" in error for error in validate_distribution(distribution))


def test_review_revisions_return_to_the_correct_author_step(distribution):
    path = distribution / "workflows/hs-knowledge-ingest/workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    review = next(row for row in value["nodes"] if row["id"] == "lint_view")
    next(row for row in review["exits"] if row["id"] == "needs_revision")["target"] = "prepare_sources"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any("lint_view: unsafe or missing transition" in error for error in validate_distribution(distribution))


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
def test_canvas_cannot_contain_a_retired_record_node(distribution, workflow):
    path = distribution / "workflows" / workflow / "layouts.yaml"
    value = yaml.safe_load(path.read_bytes())
    value["canvas"]["nodes"]["record_ingest"] = {"x": 0, "y": 0}
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any("layout identity/node set mismatch" in error for error in validate_distribution(distribution))
