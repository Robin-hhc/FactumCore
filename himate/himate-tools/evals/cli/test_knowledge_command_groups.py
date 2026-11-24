"""Compare the new command groups with the verified CLI's compatibility paths."""

from hashlib import sha256
import json
from pathlib import Path

import pytest

from cli.test_knowledge_help import run_knowledge
from integration import test_single_file_cli as cli_support


knowledge = cli_support.knowledge
invoke = cli_support.invoke


def test_grouped_help_lists_new_and_compatibility_commands(tmp_path):
    help_result = run_knowledge(tmp_path, "--help")
    assert help_result.returncode == 0, help_result.stderr
    assert all(section in help_result.stdout for section in (
        "Set up the execution environment",
        "Find and read knowledge",
        "Manage raw materials and evidence",
        "Publish knowledge",
        "Maintain the knowledge base",
        "Compatibility commands",
    ))
    for title, actions in (
        ("library", ("overview", "cards", "graph", "search", "read", "view_revision")),
        ("raw", ("list", "path", "save", "mkdir", "rmdir", "categories", "preflight", "save-package")),
        ("ingest", ("scan", "check", "commit", "status")),
        ("maintain", ("audit", "lint", "reindex", "prepare", "check", "commit")),
        ("doctor", ("--environment-only", "--bin-dir")),
        ("setup", ("--json", "--jsonl", "--bin-dir")),
        ("panel", ("raw-list", "intake-save")),
    ):
        result = run_knowledge(tmp_path, "help", title)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert f"knowledge {title}" in result.stdout.splitlines()[0]
        assert all(action in result.stdout for action in actions), (title, result.stdout)


def test_library_group_preserves_all_published_operations(knowledge):
    (knowledge / "docs-raw/specs/airtime.md").write_text("# Airtime\n", encoding="utf-8")
    registration = {"path": "docs-raw/specs/airtime.md", "source_id": "doc-airtime"}
    assert invoke(knowledge, "source", "register", request=registration)[0] == 0
    references = [{"doc_id": "doc-airtime", "line_start": 1, "line_end": 1}]
    cli_support._panel_card(knowledge, "airtime", references, "# Airtime\n\nAirtime rule.\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0
    status, overview = invoke(knowledge, "library", "overview")
    assert status == 0 and overview["data"]["card_count"] == 1, overview
    revision = overview["data"]["view_revision"]

    for action, request in (
        ("overview", {}),
        ("cards", {"limit": 1, "type": "rule"}),
        ("graph", {"scope": "global"}),
        ("search", {"query": "airtime"}),
        ("read", {"card_id": "airtime"}),
    ):
        request = {**request, "view_revision": revision}
        current = invoke(knowledge, "library", action, request=request)
        legacy = invoke(knowledge, "--action", action, "panel", request=request)
        assert current == legacy and current[0] == 0, (action, current, legacy)
        assert current[1]["data"]["view_revision"] == revision, (action, current)

    stale_request = {"card_id": "airtime", "view_revision": "stale"}
    stale = invoke(knowledge, "library", "read", request=stale_request)
    assert stale == invoke(knowledge, "panel", "read", request=stale_request)
    assert stale[0] == 2 and stale[1]["diagnostics"][0]["code"] == "PANEL_REVISION_MISMATCH"
    invalid = invoke(knowledge, "library", "raw-list")
    assert invalid[0] == 2 and invalid[1]["diagnostics"][0]["code"] == "INVALID_ACTION"


def test_raw_group_preserves_list_paths_directory_writes_and_intake(knowledge, tmp_path):
    def matching_read(action, legacy_action, request=None):
        current = invoke(knowledge, "--action", action, "raw", request=request)
        legacy = invoke(knowledge, "panel", legacy_action, request=request)
        assert current == legacy and current[0] == 0, (action, current, legacy)
        return current[1]["data"]

    request = {"path": "specs/test-folder"}
    for command, action, old_action in (
        ("raw", "mkdir", "raw-mkdir"), ("raw", "rmdir", "raw-rmdir"),
        ("panel", "raw-mkdir", "mkdir"), ("panel", "raw-rmdir", "rmdir"),
    ):
        alternate = "panel" if command == "raw" else "raw"
        status, result = invoke(knowledge, command, action, request=request)
        assert status == 0 and result["data"]["path"] == request["path"], result
        assert matching_read("list", "raw-list", {"path": "specs"})["items"] == (
            [{"name": "test-folder", "path": request["path"], "kind": "directory",
              "size": None, "category": True, "empty": True}]
            if action.endswith("mkdir") else []
        )
        # Both directions use the same required-field checks, independent of side effects.
        invalid = {"path": "../escaping"}
        assert invoke(knowledge, command, action, request=invalid) == invoke(
            knowledge, alternate, old_action, request=invalid)

    source = b"# Airtime study\n\nA complete document.\n"
    staged = tmp_path / "staging-package.md"
    staged.write_bytes(source)
    digest = sha256(source).hexdigest()
    direct = {"path": "specs/direct.md", "staged_path": str(staged),
              "expected_size": len(source), "expected_sha256": digest}
    status, saved = invoke(knowledge, "raw", "save", request=direct)
    assert status == 0 and saved["data"]["sha256"] == digest, saved
    error = invoke(knowledge, "raw", "save", request=direct)
    assert error == invoke(knowledge, "panel", "raw-save", request=direct)
    assert error[0] == 2 and error[1]["diagnostics"][0]["code"] == "RAW_TARGET_EXISTS"
    assert Path(matching_read("path", "raw-path", {"path": direct["path"]})["absolute_path"]).read_bytes() == source
    assert [item["id"] for item in matching_read("categories", "intake-categories")["categories"]] == ["specs"]

    staged_file = {"path": "staging-package.md", "staged_path": str(staged), "size": len(source), "sha256": digest}
    preflight = matching_read("preflight", "intake-preflight", {"files": [staged_file]})
    assert preflight["items"][0]["path"] == staged_file["path"]
    package = {"category": "specs", "document_path": staged_file["path"], "files": [
        {**direct, "path": staged_file["path"]},
    ]}
    status, saved = invoke(knowledge, "raw", "save-package", request=package)
    assert status == 0 and saved["data"]["sha256"] == digest, saved
    assert invoke(knowledge, "panel", "intake-save", request=package) == (status, saved)
    assert (knowledge / "docs-raw" / saved["data"]["path"]).read_bytes() == source


def test_legacy_ingest_aliases_and_grouped_status_keep_one_workflow(knowledge):
    assert invoke(knowledge, "ingest", "status") == invoke(knowledge, "status")
    root = knowledge / "docs-raw/specs/airtime.md"
    root.write_text("# Airtime\n\nAn already covered conclusion.\n", encoding="utf-8")
    assert invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/airtime.md")[0] == 0
    status, report = invoke(knowledge, "ingest", "status")
    assert status == 0 and report["phase"] == "prepared", report
    assert invoke(knowledge, "status") == (status, report)
    (knowledge / ".build/plan.md").write_text(
        "---\ncards: []\n---\nThe source adds no new knowledge after full review.\n", encoding="utf-8")
    assert invoke(knowledge, "review") == invoke(knowledge, "ingest", "check")
    status, committed = invoke(knowledge, "apply", request={"reason": "Already covered by the existing knowledge."})
    assert status == 0 and committed["phase"] == "completed", committed
    assert invoke(knowledge, "ingest", "status") == invoke(knowledge, "status")
    assert invoke(knowledge, "maintain", "lint") == invoke(knowledge, "lint")
    assert invoke(knowledge, "maintain", "audit")[1]["data"] == {"findings": []}


@pytest.mark.parametrize("arguments", [
    ("doctor", "--environment-only", "--knowledge-root", "workspace", "--json"),
    ("setup", "--jsonl", "--json"),
    ("ingest", "status", "--jsonl"),
])
def test_invalid_environment_options_have_one_machine_readable_error(tmp_path, arguments):
    result = run_knowledge(tmp_path, *arguments)
    assert result.returncode == 2 and not result.stderr, result
    assert len(result.stdout.splitlines()) == 1
    error = json.loads(result.stdout)
    assert error["status"] == "error" and error["phase"] == "invalid", error
    assert error["diagnostics"][0]["code"] in {"INVALID_ACTION", "INVALID_ARGUMENT"}, error
