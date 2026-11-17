"""Exercise public help and error streams through the verified CLI entrypoint."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]


def run_knowledge(cwd, *arguments):
    return subprocess.run(
        [sys.executable, "-B", str(TOOL_ROOT / "knowledge.py"), *arguments],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        timeout=10,
    )


@pytest.mark.parametrize("arguments", [(), ("-h",), ("--help",), ("-help",), ("help",)])
def test_top_level_help_works_without_a_knowledge_root(tmp_path, arguments):
    result = run_knowledge(tmp_path, *arguments)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "usage:" in result.stdout
    assert all(command in result.stdout for command in ("ingest", "panel", "doctor", "install-command"))
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "command", "actions"),
    [
        (("ingest", "-h"), "ingest", ("scan", "check", "commit")),
        (("help", "ingest"), "ingest", ("scan", "check", "commit")),
        (("ingest", "scan", "--help", "--json"), "ingest", ("scan", "check", "commit")),
        (("panel", "--help"), "panel", ("overview", "cards", "graph", "raw-list")),
    ],
)
def test_command_help_describes_its_actions(tmp_path, arguments, command, actions):
    result = run_knowledge(tmp_path, *arguments)
    assert result.returncode == 0, result.stderr or result.stdout
    assert command in result.stdout.splitlines()[0]
    assert all(action in result.stdout for action in actions)
    assert result.stderr == ""


def test_version_matches_the_runtime_manifest(tmp_path):
    version = json.loads((TOOL_ROOT / "runtime/manifest.json").read_text(encoding="utf-8"))["version"]
    result = run_knowledge(tmp_path, "--version")
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.split()[-1] == version
    assert result.stderr == ""


def test_human_argument_errors_go_to_stderr(tmp_path):
    result = run_knowledge(tmp_path, "invalid-command")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "INVALID_ARGUMENT" in result.stderr


def test_help_flag_after_option_terminator_is_not_help(tmp_path):
    result = run_knowledge(tmp_path, "query", "--", "--help")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "KNOWLEDGE_ROOT_UNAVAILABLE" in result.stderr


def test_json_argument_errors_preserve_the_stdout_envelope(tmp_path):
    result = run_knowledge(tmp_path, "invalid-command", "--json")
    assert result.returncode == 2
    assert result.stderr == ""
    assert len(result.stdout.splitlines()) == 1
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "error"
    assert envelope["phase"] == "invalid"
    assert envelope["diagnostics"][0]["code"] == "INVALID_ARGUMENT"


def test_panel_keeps_positional_and_flag_action_syntax(tmp_path):
    knowledge_root = tmp_path / "library"
    (knowledge_root / "docs-raw/specs").mkdir(parents=True)
    (knowledge_root / "knowledge").mkdir()
    (knowledge_root / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: synthetic\ncode_root: ../main\nmodules: []\n",
        encoding="utf-8",
    )
    positional = run_knowledge(tmp_path, "panel", "raw-list", "--knowledge-root", str(knowledge_root), "--json")
    flagged = run_knowledge(tmp_path, "--action", "raw-list", "panel", "--json", "--knowledge-root", str(knowledge_root))
    assert positional.returncode == flagged.returncode == 0, positional.stdout or flagged.stdout
    assert positional.stderr == flagged.stderr == ""
    assert json.loads(positional.stdout) == json.loads(flagged.stdout)
