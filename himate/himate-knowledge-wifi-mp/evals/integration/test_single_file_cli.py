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
import yaml


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


def test_ingest_uses_manifest_config_when_the_package_keeps_its_template(knowledge):
    workspace = knowledge.parents[1]
    template = knowledge / "config.yml"
    template.write_bytes((workspace / "config.yml").read_bytes())
    original = template.read_bytes()
    assert not (workspace / ".git").exists()
    (knowledge / "docs-raw/specs/a.md").write_text("# RX\nDocument in a manifest workspace.\n", encoding="utf-8")

    status, report = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")

    assert status == 0 and report["phase"] == "prepared", report
    assert report["data"]["source"]["path"] == "docs-raw/specs/a.md"
    assert template.read_bytes() == original


def test_no_card_commit_keeps_receipt_under_artifacts_without_creating_logs(knowledge):
    original = knowledge / "docs-raw/specs/a.md"
    original.write_text("# A\n\nAn already covered conclusion.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    (knowledge / ".build/plan.md").write_text(
        "---\ncards: []\n---\nThe source adds no new knowledge after full review.\n", encoding="utf-8")
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0, checked
    request = knowledge / "artifacts/commit-request.json"
    request.write_text(json.dumps({"reason": "Fully reviewed; existing knowledge covers this source."}), encoding="utf-8")

    status, committed = invoke(knowledge, "ingest", "commit", "--input", str(request))

    assert status == 0 and committed["phase"] == "completed", committed
    receipt = knowledge / "artifacts/ingest/latest.json"
    assert receipt.is_file()
    assert json.loads(receipt.read_bytes()) == committed["data"]
    assert not (knowledge / "logs").exists()
    assert not (knowledge / ".build").exists()
    registry = yaml.safe_load((knowledge / "governance/sources.lock.yaml").read_bytes())
    resource = next(row for row in registry["resources"] if row["source_id"] == scanned["data"]["source"]["doc_id"])
    assert resource["processed_hash"] == hashlib.sha256(original.read_bytes()).hexdigest()
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "completed", report
    assert report["data"] == committed["data"]


def test_status_reads_legacy_receipt_without_migration_and_prefers_current_work(knowledge):
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "idle", report
    assert not (knowledge / "logs").exists()
    assert not (knowledge / "artifacts/ingest").exists()

    old = knowledge / "logs/ingest/latest.json"
    old.parent.mkdir(parents=True)
    legacy_bytes = b'{"source_id":"legacy-source","card_ids":[]}\n'
    old.write_bytes(legacy_bytes)
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "completed", report
    assert report["data"]["source_id"] == "legacy-source"
    assert old.read_bytes() == legacy_bytes
    assert not (knowledge / "artifacts/ingest").exists()

    latest = knowledge / "artifacts/ingest/latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text('{"source_id":"new-source","card_ids":[]}', encoding="utf-8")
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["data"]["source_id"] == "new-source", report
    task = knowledge / ".build/task.json"
    task.parent.mkdir()
    task.write_text('{"source":{"source_id":"pending-source"}}', encoding="utf-8")
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "prepared", report
    assert report["data"]["source"]["source_id"] == "pending-source"
    assert old.read_bytes() == legacy_bytes


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


def test_public_three_field_card_is_private_until_commit_then_searchable_without_purpose(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text(
        "# RX design\n\nThe RX design budget is 8 ms; no timing measurement is supplied.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, scanned
    source_id = scanned["data"]["source"]["doc_id"]
    metadata = {"id": "rx-flow", "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 3}], "code_ref": []}
    draft = knowledge / ".build/cards/rx-flow.md"
    draft.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False)
                     + "---\n# RX design budget\n\nrx_budget is 8 ms by design.\n\n"
                     "Timing has not been measured; implementation applicability is unknown.\n", encoding="utf-8")
    (knowledge / ".build/plan.md").write_text(
        "---\ncards:\n- id: rx-flow\n  path: knowledge/rx-flow.md\n---\nCreate the documented design budget.\n", encoding="utf-8")
    expected = draft.read_bytes()
    status, before = invoke(knowledge, "search", "rx_budget")
    assert status == 0 and before["data"]["matches"] == []
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0, checked
    status, committed = invoke(knowledge, "ingest", "commit")
    assert status == 0, committed
    assert (knowledge / "knowledge/rx-flow.md").read_bytes() == expected
    status, result = invoke(knowledge, "query", "rx_budget")
    assert status == 0, result
    hit = result["data"]["matches"][0]
    assert hit["card_id"] == "rx-flow"
    assert set(hit) == {"card_id", "path", "title", "tags", "lifecycle", "score"}
    assert "purpose" not in result["data"]
    status, read = invoke(knowledge, "read", "rx-flow")
    assert status == 0, read
    assert read["data"]["metadata"] == metadata
    assert read["data"]["code_ref"] == []
    assert "not been measured" in read["data"]["body"]
    assert "eligible_claim_ids" not in read["data"]
    assert read["data"]["sources"][0]["processed_hash"] == scanned["data"]["source"]["hash"]


@pytest.mark.parametrize("arguments", [
    ("search", "RX", "--purpose", "current"), ("query", "RX", "--purpose", ""),
    ("read", "absent", "--purpose", "guidance"), ("query", "read", "absent", "--purpose", ""),
])
def test_public_old_purpose_option_reports_migration_before_search(knowledge, arguments):
    status, result = invoke(knowledge, *arguments)
    assert status == 2, result
    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "QUERY_PARAMETERS_REMOVED"
    assert not (knowledge / "artifacts/query").exists()
    assert not (knowledge / ".build").exists()


@pytest.mark.parametrize("extra", [{"purpose": None}, {"purpose": ""}, {"purpose": "current"}, {"context": {}}, {"context": None}])
@pytest.mark.parametrize("command", ["search", "read"])
def test_public_old_json_fields_report_migration_even_when_empty(knowledge, extra, command):
    request = {"query": "RX"} if command == "search" else {"card_id": "absent"}
    request_path = knowledge.parent / "request.json"
    request_path.write_text(json.dumps({**request, **extra}), encoding="utf-8")
    status, result = invoke(knowledge, command, "--input", str(request_path))
    assert status == 2, result
    assert result["diagnostics"][0]["code"] == "QUERY_PARAMETERS_REMOVED"
    assert not (knowledge / "artifacts/query").exists()


def test_public_include_deprecated_flag_adds_retired_cards_without_changing_read_state(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# RX\n\nRX history.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    source_id = scanned["data"]["source"]["doc_id"]
    for identity, lifecycle in (("normal", "stable"), ("old", "deprecated")):
        header = {"id": identity, "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 3}],
                  "code_ref": [], "tags": ["RX"], "lifecycle": lifecycle}
        (knowledge / "knowledge" / (identity + ".md")).write_text(
            "---\n" + yaml.safe_dump(header) + "---\n# RX history\n\nrx_timeout history.\n", encoding="utf-8")
    status, result = invoke(knowledge, "search", "rx_timeout")
    assert status == 0 and [hit["card_id"] for hit in result["data"]["matches"]] == ["normal"]
    status, result = invoke(knowledge, "search", "rx_timeout", "--include-deprecated")
    assert status == 0, result
    assert {hit["card_id"] for hit in result["data"]["matches"]} == {"normal", "old"}
    status, result = invoke(knowledge, "read", "old")
    assert status == 0 and result["data"]["lifecycle"] == "deprecated"
