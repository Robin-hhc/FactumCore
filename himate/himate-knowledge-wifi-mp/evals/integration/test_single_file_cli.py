"""Public single-file entry points using an isolated synthetic knowledge root."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture
def knowledge(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/knowledge-test"
    root.mkdir(parents=True)
    for directory in ("runtime", "governance"):
        shutil.copytree(SOURCE / directory, root / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv"))
    for name in ("knowledge.py", "knowledge.sh", "knowledge.cmd"):
        shutil.copyfile(SOURCE / name, root / name)
    (root / "governance/sources.lock.yaml").write_text(
        "schema_version: '2.0'\nresources: []\nsnapshots: []\n", encoding="utf-8",
    )
    (project / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: synthetic\n"
        "knowledge_roots:\n  wifi: himate/knowledge-test\ncode_root: main\nmodules: []\n",
        encoding="utf-8",
    )
    (root / "docs-raw/specs").mkdir(parents=True)
    (root / "knowledge").mkdir()
    return root


def invoke(root, *arguments):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-B", str(root / "knowledge.py"), *arguments, "--json"],
        cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=60,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, json.loads(result.stdout)


def test_ingest_scan_returns_one_document_without_legacy_operation_request(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# A\nA new bounded conclusion.\n", encoding="utf-8")
    (knowledge / "docs-raw/specs/b.md").write_text("# B\nAnother conclusion.\n", encoding="utf-8")
    status, report = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, report
    assert report["phase"] == "prepared"
    assert report["data"]["source"]["path"] == "docs-raw/specs/a.md"
    assert report["data"]["source"]["doc_id"]
    assert report["data"]["affected_cards"] == []
    assert (knowledge / report["data"]["task_ref"]).is_file()
    assert not list((knowledge / "knowledge").rglob("*.md"))


def test_formal_check_needs_no_private_ingest_or_review_ticket(knowledge):
    status, report = invoke(knowledge, "lint")
    assert status == 0, report
    assert report["phase"] == "passed"
    assert report["data"]["findings"] == []
    assert report["data"]["review_required"] is True
    assert not (knowledge / ".build").exists()


def test_formal_check_reports_invalid_frontmatter_as_a_finding(knowledge):
    (knowledge / "knowledge/bad.md").write_text("---\nid: missing-references\n---\n# Broken\n", encoding="utf-8")
    status, report = invoke(knowledge, "lint")
    assert status == 1, report
    assert report["phase"] == "failed"
    assert report["data"]["findings"]
    assert not (knowledge / ".build").exists()


def test_public_p4_blocks_a_misplaced_card_and_p5_copies_the_corrected_path(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# Reply\n\nWait for a reply.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, scanned
    identity = scanned["data"]["source"]["doc_id"]
    (knowledge / ".build/plan.md").write_text(
        "---\ncards:\n- id: waiting\n  path: knowledge/rules/waiting.md\n---\n"
        "Keep this documented rule under rules.\n", encoding="utf-8")
    misplaced = knowledge / ".build/cards/waiting.md"
    misplaced.write_text(
        "---\nid: waiting\ndoc_ref:\n- doc_id: " + identity
        + "\n  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Waiting\n\nWait for a reply.\n",
        encoding="utf-8")
    expected = misplaced.read_bytes()

    status, report = invoke(knowledge, "ingest", "check")

    assert status == 1, report
    assert report["phase"] == "failed"
    finding = next(item for item in report["data"]["findings"] if item["code"] == "PLAN_CARD_MISMATCH")
    assert finding["card_id"] == "waiting"
    assert finding["expected_path"] == "knowledge/rules/waiting.md"
    assert finding["actual_path"] == "knowledge/waiting.md"
    assert not (knowledge / "knowledge/waiting.md").exists()
    assert not (knowledge / "knowledge/rules/waiting.md").exists()
    corrected = misplaced.parent / "rules/waiting.md"
    corrected.parent.mkdir()
    misplaced.rename(corrected)
    status, report = invoke(knowledge, "ingest", "check")
    assert status == 0, report
    assert report["phase"] == "passed"
    status, report = invoke(knowledge, "ingest", "commit")
    assert status == 0, report
    assert report["phase"] == "completed"
    assert (knowledge / "knowledge/rules/waiting.md").read_bytes() == expected
    assert not (knowledge / "knowledge/waiting.md").exists()
    assert not (knowledge / ".build").exists()


@pytest.mark.parametrize("arguments,output", [
    (("search", "fresh"), ".build/task.json"),
    (("query", "fresh"), ".build/task.json"),
    (("query", "search", "fresh"), ".build/task.json"),
    (("read", "formal"), ".build/task.json"),
    (("query", "read", "formal"), ".build/task.json"),
    (("search", "fresh"), "artifacts/query/../../.build/task.json"),
    (("query", "fresh"), "artifacts/knowledge.sqlite"),
    (("read", "formal"), "artifacts/query/../knowledge.sqlite"),
])
def test_query_output_cannot_overwrite_ingest_or_database(knowledge, arguments, output):
    (knowledge / "docs-raw/specs/a.md").write_text("# A\n\nA fresh conclusion.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    identity = scanned["data"]["source"]["doc_id"]
    (knowledge / "knowledge/formal.md").write_text(
        "---\nid: formal\ndoc_ref:\n- doc_id: " + identity
        + "\n  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Formal\nA fresh conclusion.\n",
        encoding="utf-8",
    )
    before = {p.relative_to(knowledge).as_posix(): p.read_bytes()
              for p in knowledge.rglob("*") if p.is_file()}
    status, report = invoke(knowledge, *arguments, "--output", output)
    assert status == 2, report
    assert report["status"] == "error"
    assert report["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_WORKSPACE"
    assert {p.relative_to(knowledge).as_posix(): p.read_bytes()
            for p in knowledge.rglob("*") if p.is_file()} == before


def test_query_can_save_its_actual_response_in_query_artifacts(knowledge):
    status, report = invoke(knowledge, "search", "fresh", "--output", "artifacts/query/answer.json")
    assert status == 0, report
    assert json.loads((knowledge / "artifacts/query/answer.json").read_bytes()) == report
    assert not (knowledge / ".build").exists()


@pytest.mark.parametrize("invalid_card,expected", [(False, 0), (True, 1)])
def test_fixed_ci_uses_trusted_rules_without_loading_candidate_programs(knowledge, tmp_path, invalid_card, expected):
    marker = tmp_path / "candidate-program-executed"
    (knowledge / "governance/contracts/ingest.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n", encoding="utf-8",
    )
    if invalid_card:
        (knowledge / "knowledge/bad.md").write_text("---\nid: missing-references\n---\n# Broken\n", encoding="utf-8")
    output = tmp_path / "ci-report.json"
    result = subprocess.run([
        sys.executable, "-B", str(SOURCE / "check.py"), "--trusted-root", str(SOURCE),
        "--candidate-root", str(knowledge), "--rules-digest",
        hashlib.sha256((SOURCE / "governance/framework.lock.yaml").read_bytes()).hexdigest(),
        "--commit", "a" * 40, "--output", str(output),
    ], cwd=knowledge, capture_output=True, encoding="utf-8", timeout=60)
    assert result.returncode == expected, result.stdout + result.stderr
    report = json.loads(output.read_bytes())
    assert report["status"] == ("failed" if invalid_card else "passed")
    assert bool(report["findings"]) is invalid_card
    assert report["commit"] == "a" * 40
    assert not marker.exists()
