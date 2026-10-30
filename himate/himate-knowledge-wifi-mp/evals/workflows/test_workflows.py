"""Instruction packaging and the five-step graph, independent of host runtime."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[4]


def validator_module():
    path = ROOT / "himate/himate-knowledge-wifi-mp/evals/validate_design.py"
    spec = importlib.util.spec_from_file_location("workflow_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def distribution(tmp_path):
    for name in ("skills/common/knowledge", "workflows/common/knowledge"):
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for relative in ("knowledge.py", "knowledge.sh", "knowledge.cmd", "runtime/manifest.json",
                     "runtime/requirements.lock.txt", "runtime/himate_knowledge/__init__.py",
                     "runtime/himate_knowledge/cli.py"):
        path = tmp_path / "himate/himate-knowledge-wifi-mp" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic runtime placeholder\n", encoding="utf-8")
    return tmp_path


def test_current_distribution_is_structurally_valid():
    assert validator_module().validate(ROOT) == []


def test_five_steps_keep_decision_writing_and_independent_review_separate():
    graph = yaml.safe_load((ROOT / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml").read_bytes())
    nodes = {row["id"]: row for row in graph["nodes"]}
    assert list(nodes) == ["prepare_sources", "plan_change", "materialize_view", "lint_view", "apply_view"]
    assert [row["owner"] for row in nodes.values()] == ["coder", "coder", "coder", "reviewer", "coder"]
    assert {row["id"]: row["target"] for row in nodes["plan_change"]["exits"]}["content_planned"] == "materialize_view"
    assert {row["id"]: row["target"] for row in nodes["lint_view"]["exits"]} == {
        "passed": "apply_view", "needs_plan": "plan_change", "needs_revision": "materialize_view",
    }


@pytest.mark.parametrize("skill", ["record", "explore", "lint"])
def test_retired_skills_cannot_reappear_as_active_packages(distribution, skill):
    package = distribution / "skills/common/knowledge" / ("hs-knowledge-" + skill)
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text("---\nname: retired\ndescription: old capability\n---\n", encoding="utf-8")
    assert any("active Skill set mismatch" in error for error in validator_module().validate(distribution))


@pytest.mark.parametrize("resource", ["scripts/cli.py", "tests/test_hidden.py", "requirements.lock.txt"])
def test_skill_packages_do_not_own_execution_or_test_code(distribution, resource):
    path = distribution / "skills/common/knowledge/hs-knowledge-query" / resource
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic wrong owner", encoding="utf-8")
    assert any("Skill source owns implementation" in error for error in validator_module().validate(distribution))


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
def test_review_cannot_run_as_the_author(distribution, workflow):
    path = distribution / "workflows/common/knowledge" / workflow / "workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    next(row for row in value["nodes"] if row["id"] == "lint_view")["owner"] = "coder"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any("lint_view: wrong Skill/owner/type" in error for error in validator_module().validate(distribution))


@pytest.mark.parametrize("node_id", ["sync_workspace", "plan_patrol", "refresh_index", "complete_patrol"])
def test_each_patrol_step_has_its_own_narrow_skill(distribution, node_id):
    path = distribution / "workflows/common/knowledge/hs-knowledge-lint/workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    next(row for row in value["nodes"] if row["id"] == node_id)["skill"] = "hs-knowledge-maintain"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any(node_id + ": wrong Skill/owner/type" in error for error in validator_module().validate(distribution))


def test_review_revisions_return_to_the_correct_author_step(distribution):
    path = distribution / "workflows/common/knowledge/hs-knowledge-ingest/workflow.yaml"
    value = yaml.safe_load(path.read_bytes())
    review = next(row for row in value["nodes"] if row["id"] == "lint_view")
    next(row for row in review["exits"] if row["id"] == "needs_revision")["target"] = "prepare_sources"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any("lint_view: unsafe or missing transition" in error for error in validator_module().validate(distribution))


@pytest.mark.parametrize("workflow", ["hs-knowledge-ingest", "hs-knowledge-lint"])
def test_canvas_cannot_contain_a_retired_record_node(distribution, workflow):
    path = distribution / "workflows/common/knowledge" / workflow / "layouts.yaml"
    value = yaml.safe_load(path.read_bytes())
    value["canvas"]["nodes"]["record_ingest"] = {"x": 0, "y": 0}
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert any("layout identity/node set mismatch" in error for error in validator_module().validate(distribution))
