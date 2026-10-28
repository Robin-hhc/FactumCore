"""Lint's JSON transport works with a restricted stdout encoding."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SKILLS = DOMAIN.parent / "skills/common/knowledge"


def invoke(root, output, *, skills=SKILLS, request=None, action=None):
    command = [sys.executable, str(skills / "hs-knowledge-lint/scripts/cli.py"),
               "--knowledge-root", str(root), "--output", str(output)]
    if request is not None:
        incoming = output.with_suffix(".input.json")
        incoming.write_text(json.dumps(request, ensure_ascii=True), encoding="utf-8")
        command += ["--input", str(incoming)]
    if action is not None:
        command += ["--action", action]
    environment = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    return subprocess.run(command, env=environment, capture_output=True, timeout=90)


def assert_same_report(completed, output, expected_status, expected_exit):
    persisted = output.read_bytes()
    report = json.loads(persisted)
    assert report["status"] == expected_status
    # The persisted canonical UTF-8 report retains the original Unicode.
    assert "中文报告".encode("utf-8") in persisted
    assert completed.returncode == expected_exit, completed.stdout + completed.stderr
    assert json.loads(completed.stdout.decode("ascii")) == report
    assert completed.stderr == b""


@pytest.mark.parametrize(("invalid_card", "status", "code"), [(False, "passed", 0), (True, "failed", 1)])
def test_formal_lint_json_stdout_matches_utf8_file_under_cp1252(tmp_path, invalid_card, status, code):
    root = tmp_path / "root"
    shutil.copytree(DOMAIN / "governance", root / "governance")
    if invalid_card:
        (root / "knowledge").mkdir()
        (root / "knowledge/bad.md").write_text("---\nbad: true\n---\n# Invalid\n", encoding="utf-8")
    output = tmp_path / "中文报告.json"
    completed = invoke(root, output)
    assert_same_report(completed, output, status, code)


def test_review_lint_json_stdout_matches_utf8_file_under_cp1252(tmp_path):
    fixture_spec = importlib.util.spec_from_file_location("unicode_output_pipeline", DOMAIN / "evals/pipeline_harness.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    pipeline = fixture.Pipeline(tmp_path / "pipeline")
    bundle_ref, bundle = pipeline.capture("unicode-review", b"# Source\nCapture marker is a documented rule.\n")
    view_ref = pipeline.view("unicode-review", bundle_ref, "unicode-rule", pipeline.card("unicode-rule", bundle))
    view = pipeline.record(view_ref)
    semantic = pipeline.record(view["semantic_plan_ref"])
    units = semantic["units"] + semantic.get("maintenance_units", [])
    request = {"operation_id": "unicode-review", "view_ref": view_ref,
               "semantic_plan_ref": view["semantic_plan_ref"], "reviewer_id": "fixture-independent-reader",
               "independent_context": "fresh-fixture-context", "sampled_unit_ids": [row["unit_id"] for row in units],
               "unreviewed_unit_ids": [], "reason": "独立复核完整范围", "findings": [],
               "inputs": {"historical_card_objects": {}}}
    output = tmp_path / "中文报告.json"
    completed = invoke(pipeline.root, output, skills=pipeline.skills, request=request, action="review")
    assert_same_report(completed, output, "passed", 0)


@pytest.mark.parametrize(("invalid_card", "status", "code"), [(False, "passed", 0), (True, "failed", 1)])
def test_protected_ci_json_stdout_matches_utf8_file_under_cp1252(tmp_path, invalid_card, status, code):
    import hashlib

    trusted = tmp_path / "trusted"
    candidate = tmp_path / "中文报告候选库"
    shutil.copytree(DOMAIN / "governance", trusted / "governance")
    (candidate / "governance").mkdir(parents=True)
    shutil.copyfile(trusted / "governance/sources.lock.yaml", candidate / "governance/sources.lock.yaml")
    if invalid_card:
        (candidate / "knowledge").mkdir()
        (candidate / "knowledge/无效知识卡.md").write_text("---\nbad: true\n---\n# Invalid\n", encoding="utf-8")
    output = tmp_path / "ci-report.json"
    rules_digest = hashlib.sha256((trusted / "governance/framework.lock.yaml").read_bytes()).hexdigest()
    command = [sys.executable, str(DOMAIN / "check.py"), "--trusted-root", str(trusted),
               "--candidate-root", str(candidate), "--rules-digest", rules_digest,
               "--commit", "fixture-unicode-candidate", "--output", str(output)]
    completed = subprocess.run(command, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
                               capture_output=True, timeout=90)
    assert_same_report(completed, output, status, code)
    report = json.loads(output.read_bytes())
    assert report["mode"] == "ci"
    if invalid_card:
        assert any(finding["path"] == "knowledge/无效知识卡.md" for finding in report["findings"])
