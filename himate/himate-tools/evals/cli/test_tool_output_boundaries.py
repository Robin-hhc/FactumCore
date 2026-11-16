"""Outputs and command launchers respect the installed tool's directory."""

import json
import os
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


def invoke_command_installer(tool, destination, cwd):
    return subprocess.run(
        [sys.executable, "-B", str(tool / "knowledge.py"), "install-command",
         "--bin-dir", str(destination), "--json"],
        cwd=cwd, capture_output=True, text=True, timeout=30,
    )


def test_managed_command_reinstalls_repairs_and_rebinds_after_moving_tool(tmp_path):
    tool = tmp_path / "new checkout"
    shutil.copytree(SOURCE / "runtime", tool / "runtime")
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        shutil.copyfile(SOURCE / name, tool / name)
    destination = tmp_path / "local bin"

    first = invoke_command_installer(SOURCE, destination, tmp_path)
    assert first.returncode == 0, (first.stdout, first.stderr)
    installed = json.loads(first.stdout)["data"]
    launcher, dispatcher = Path(installed["path"]), Path(installed["dispatcher"])
    original_dispatcher = dispatcher.read_bytes()

    second = invoke_command_installer(SOURCE, destination, tmp_path)
    assert second.returncode == 0, (second.stdout, second.stderr)
    assert dispatcher.read_bytes() == original_dispatcher

    launcher.unlink()
    repaired = invoke_command_installer(SOURCE, destination, tmp_path)
    assert repaired.returncode == 0 and launcher.is_file()
    relocated = invoke_command_installer(tool, destination, tmp_path)
    assert relocated.returncode == 0, (relocated.stdout, relocated.stderr)
    assert json.loads(relocated.stdout)["data"]["tool_root"] == str(tool)
    assert repr(str(tool / "knowledge.py")).encode("utf-8") in dispatcher.read_bytes()
    invoked = subprocess.run([sys.executable, "-B", str(dispatcher), "--help"], cwd=tmp_path,
                             capture_output=True, text=True, timeout=30)
    assert invoked.returncode == 0 and "install-command" in invoked.stdout


def test_unrelated_launcher_is_preserved_and_does_not_leave_dispatcher(tmp_path):
    destination = tmp_path / "bin"
    destination.mkdir()
    launcher = destination / ("knowledge.cmd" if os.name == "nt" else "knowledge")
    unrelated = b"existing unrelated command"
    launcher.write_bytes(unrelated)

    result = invoke_command_installer(SOURCE, destination, tmp_path)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "COMMAND_EXISTS"
    assert launcher.read_bytes() == unrelated
    assert not (destination / "knowledge-dispatch.py").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows user PATH registration")
def test_windows_registration_preserves_existing_path_and_notifies_once(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import winreg
    from support.contracts import runtime_module

    installer = runtime_module("command_install")
    current = r"C:\Existing Bin"
    home_bin = tmp_path / "user bin"
    notifications = []
    monkeypatch.setattr(winreg, "OpenKey", lambda *args: nullcontext("read"))
    monkeypatch.setattr(winreg, "CreateKey", lambda *args: nullcontext("write"))
    monkeypatch.setattr(winreg, "QueryValueEx", lambda *args: (current, winreg.REG_EXPAND_SZ))
    monkeypatch.setattr(installer, "_notify_user_path_changed", lambda: notifications.append(True))

    def set_path(key, name, reserved, kind, value):
        nonlocal current
        assert key == "write" and name == "Path" and kind == winreg.REG_EXPAND_SZ
        current = value

    monkeypatch.setattr(winreg, "SetValueEx", set_path)
    assert not installer._user_path(home_bin)
    assert installer._user_path(home_bin, add=True)
    assert current == r"C:\Existing Bin" + ";" + str(home_bin)
    assert installer._user_path(home_bin, add=True)
    assert notifications == [True]
