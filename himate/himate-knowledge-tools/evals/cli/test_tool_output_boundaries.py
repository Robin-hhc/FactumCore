"""Outputs and command launchers respect the installed tool's directory."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case_alias", [False, True])
def test_command_writes_cannot_target_the_tool_directory(tmp_path, case_alias):
    tool = tmp_path / "MixedCaseTool"
    tool.mkdir()
    destination = tool
    if case_alias:
        destination = tool.with_name(tool.name.lower())
        if destination == tool or not destination.is_dir() or not destination.samefile(tool):
            pytest.skip("Filesystem paths do not have distinct spellings for the same directory")

    shutil.copytree(SOURCE / "runtime", tool / "runtime")
    shutil.copytree(SOURCE / "governance", tool / "governance")
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        shutil.copyfile(SOURCE / name, tool / name)
    knowledge = tmp_path / "knowledge-data"
    for part in ("docs-raw", "knowledge"):
        (knowledge / part).mkdir(parents=True)

    commands = [
        (["status", "--knowledge-root", str(knowledge), "--output", str(destination / "blocked/report.json")],
         "OUTPUT_INSIDE_TOOL"),
        (["install-command", "--bin-dir", str(destination / "blocked")], "COMMAND_INSIDE_TOOL"),
    ]
    for arguments, forbidden in commands:
        result = subprocess.run([sys.executable, "-B", str(tool / "knowledge.py"), *arguments, "--json"],
                                cwd=tmp_path, capture_output=True, text=True, timeout=30)
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert json.loads(result.stdout)["diagnostics"][0]["code"] == forbidden
        assert not (tool / "blocked").exists()
