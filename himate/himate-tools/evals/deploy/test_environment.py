"""Check and install against the selected Python without modifying the test host."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]
ENTRY = TOOL_ROOT / "tools/deploy/environment.py"


@pytest.fixture
def environment(monkeypatch):
    deploy_spec = importlib.util.spec_from_file_location("deploy", ENTRY.with_name("deploy.py"))
    deploy = importlib.util.module_from_spec(deploy_spec)
    deploy_spec.loader.exec_module(deploy)
    monkeypatch.setitem(sys.modules, "deploy", deploy)
    spec = importlib.util.spec_from_file_location("toolkit_environment", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_reports_dependencies_without_a_knowledge_root(tmp_path):
    bin_dir = tmp_path / "isolated bin"
    result = subprocess.run([sys.executable, "-S", "-B", str(ENTRY), "check", "--bin-dir", str(bin_dir)], cwd=tmp_path,
                            capture_output=True, check=True, timeout=60)
    payload = json.loads(result.stdout)
    manifest = json.loads((TOOL_ROOT / "runtime/manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "needs_install"
    assert Path(payload["tool_root"]) == TOOL_ROOT
    assert Path(payload["python"]).samefile(sys.executable)
    assert payload["toolkit_version"] == manifest["version"]
    pyyaml = next(row for row in payload["dependencies"] if row["name"].casefold() == "pyyaml")
    assert pyyaml == {"name": pyyaml["name"], "expected": "6.0.3", "actual": None, "status": "missing"}
    assert payload["command"]["bin_dir"] == str(bin_dir)
    assert not payload["command"]["installed"]
    assert not list(tmp_path.iterdir())


@pytest.fixture
def runtime(environment, monkeypatch, tmp_path):
    class CommandError(ValueError):
        code = "COMMAND_EXISTS"

    state = SimpleNamespace(dependencies_ready=False, installed=False, error=None, registered=[], checked=[])
    bin_dir = tmp_path / "isolated bin"

    def dependencies(requirements):
        assert requirements == environment.REQUIREMENTS
        state.checked.append(state.dependencies_ready)
        gaps = [] if state.dependencies_ready else [{"code": "DEPENDENCY_UNAVAILABLE"}]
        return [], gaps

    def inspect(tool_root, requested_bin):
        assert tool_root == TOOL_ROOT
        assert requested_bin == bin_dir
        return {"path": str(bin_dir / ("knowledge.cmd" if os.name == "nt" else "knowledge")),
                "bin_dir": str(bin_dir), "dispatcher": str(bin_dir / "knowledge-dispatch.py"),
                "on_path": False, "installed": state.installed}

    def register(tool_root, requested_bin, *, add_path):
        assert state.checked[-1]
        assert tool_root == TOOL_ROOT
        assert requested_bin == bin_dir
        assert not add_path
        state.registered.append(requested_bin)
        if state.error:
            raise state.error
        state.installed = True

    commands = SimpleNamespace(inspect_command=inspect, deploy_command=register)
    monkeypatch.setattr(environment, "load_runtime", lambda: ("test", dependencies, commands, CommandError))
    return state, ["--bin-dir", str(bin_dir)], CommandError


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_install_runs_pinned_pip_before_registering(environment, runtime, monkeypatch, capsys):
    state, args, _ = runtime
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if "pip" in argv:
            state.dependencies_ready = True

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert environment.main(["install", *args]) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing", "registering", "verifying"]
    assert final["status"] == "ready"
    assert final["command"]["installed"]
    assert state.checked == [False, True, True]
    assert len(state.registered) == 1
    (argv, options), (verification, verification_options) = calls
    assert argv == [sys.executable, "-m", "pip", "install", "-r", str(environment.REQUIREMENTS)]
    assert options["cwd"] == TOOL_ROOT
    assert options["check"] is True
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL
    command = final["command"]
    assert verification == ([sys.executable, "-B", command["dispatcher"], "--help"] if os.name == "nt"
                            else [command["path"], "--help"])
    assert verification_options["cwd"] == command["bin_dir"]
    assert verification_options["check"] is True
    assert verification_options["timeout"] == 10


def test_check_and_retry_when_only_registration_is_needed(environment, runtime, monkeypatch, capsys):
    state, args, CommandError = runtime
    state.dependencies_ready = True

    def run(argv, **kwargs):
        assert argv[-1] == "--help"

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert environment.main(["check", *args]) == 0
    assert events(capsys)[0]["status"] == "needs_cli"
    assert not state.registered
    state.error = CommandError("third-party filename omitted from output")
    assert environment.main(["install", *args]) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "registering"
    assert failure["diagnostics"][0]["code"] == "COMMAND_EXISTS"
    assert "third-party" not in failure["message"]
    state.error = None
    assert environment.main(["install", *args]) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "registering", "verifying"]
    assert final["status"] == "ready"
    assert environment.main(["install", *args]) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "verifying"]
    assert final["status"] == "ready"
    assert len(state.registered) == 2


def test_install_failure_does_not_emit_raw_pip_output(environment, runtime, monkeypatch, capsys):
    state, args, _ = runtime

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pip", stderr=b"private index configuration")

    monkeypatch.setattr(environment.subprocess, "run", fail)
    assert environment.main(["install", *args]) == 1
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[-1]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert "private index configuration" not in output
    assert not any(event["phase"] == "verifying" for event in events)
    assert not state.registered


def test_failed_dependency_verification_prevents_registration(environment, runtime, monkeypatch, capsys):
    state, args, _ = runtime
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: None)
    assert environment.main(["install", *args]) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "verifying"
    assert failure["diagnostics"][0]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert not state.registered


def test_unusable_launcher_fails_verification(environment, runtime, monkeypatch, capsys):
    state, args, _ = runtime
    state.dependencies_ready = state.installed = True

    def run(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv, stderr=b"local paths")

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert environment.main(["check", *args]) == 0
    checked = events(capsys)[0]
    assert checked["status"] == "needs_cli"
    assert checked["diagnostics"][0]["code"] == "CLI_VERIFICATION_FAILED"
    assert not state.registered
    assert environment.main(["install", *args]) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "verifying"
    assert failure["diagnostics"][0]["code"] == "CLI_VERIFICATION_FAILED"
    assert "local paths" not in failure["message"]
