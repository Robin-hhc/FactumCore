"""Check and install against the selected Python without modifying the test host."""

import hashlib
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
    monkeypatch.syspath_prepend(str(TOOL_ROOT / "runtime"))
    from himate_knowledge import environment
    return environment


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

    canonical = subprocess.run([
        sys.executable, "-S", "-B", str(TOOL_ROOT / "knowledge.py"),
        "doctor", "--environment-only", "--json", "--bin-dir", str(bin_dir),
    ], cwd=tmp_path, capture_output=True, check=True, timeout=60)
    assert json.loads(canonical.stdout) == payload
    assert canonical.stderr == b""
    assert not list(tmp_path.iterdir())


@pytest.fixture
def runtime(environment, monkeypatch, tmp_path):
    state = SimpleNamespace(dependencies_ready=False, installed=False, error=None, registered=[], checked=[])
    bin_dir = tmp_path / "isolated bin"

    def dependencies(requirements):
        assert requirements == TOOL_ROOT / "runtime/requirements.lock.txt"
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

    monkeypatch.setattr(environment.doctor, "inspect_dependencies", dependencies)
    monkeypatch.setattr(environment.command_install, "inspect_command", inspect)
    monkeypatch.setattr(environment.command_install, "deploy_command", register)
    return state, bin_dir


def execute(environment, action, bin_dir, *, output=None, legacy=True, tool_root=TOOL_ROOT):
    return environment.run_environment(tool_root, {"version": "test"}, action, bin_dir=bin_dir,
                                       output=output or ("jsonl" if action == "install" else "json"), legacy=legacy)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_install_runs_pinned_pip_before_registering(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if "pip" in argv:
            state.dependencies_ready = True

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing", "registering", "verifying"]
    assert final["status"] == "ready"
    assert final["command"]["installed"]
    assert state.checked == [False, True, True]
    assert len(state.registered) == 1
    (argv, options), (verification, verification_options) = calls
    assert argv == [sys.executable, "-m", "pip", "install", "-r", str(TOOL_ROOT / "runtime/requirements.lock.txt")]
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
    state, bin_dir = runtime
    state.dependencies_ready = True

    def run(argv, **kwargs):
        assert argv[-1] == "--help"

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "check", bin_dir) == 0
    assert events(capsys)[0]["status"] == "needs_cli"
    assert not state.registered
    state.error = environment.NodeError("COMMAND_EXISTS", "third-party filename omitted from output")
    assert execute(environment, "install", bin_dir) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "registering"
    assert failure["diagnostics"][0]["code"] == "COMMAND_EXISTS"
    assert "third-party" not in failure["message"]
    state.error = None
    assert execute(environment, "install", bin_dir) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "registering", "verifying"]
    assert final["status"] == "ready"
    assert execute(environment, "install", bin_dir) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "verifying"]
    assert final["status"] == "ready"
    assert len(state.registered) == 2


def test_install_failure_does_not_emit_raw_pip_output(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pip", stderr=b"private index configuration")

    monkeypatch.setattr(environment.subprocess, "run", fail)
    assert execute(environment, "install", bin_dir) == 1
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[-1]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert "private index configuration" not in output
    assert not any(event["phase"] == "verifying" for event in events)
    assert not state.registered


def test_failed_dependency_verification_prevents_registration(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: None)
    assert execute(environment, "install", bin_dir) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "verifying"
    assert failure["diagnostics"][0]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert not state.registered


def test_unusable_launcher_fails_verification(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    state.dependencies_ready = state.installed = True

    def run(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv, stderr=b"local paths")

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "check", bin_dir) == 0
    checked = events(capsys)[0]
    assert checked["status"] == "needs_cli"
    assert checked["diagnostics"][0]["code"] == "CLI_VERIFICATION_FAILED"
    assert not state.registered
    assert execute(environment, "install", bin_dir) == 1
    failure = events(capsys)[-1]
    assert failure["phase"] == "verifying"
    assert failure["diagnostics"][0]["code"] == "CLI_VERIFICATION_FAILED"
    assert "local paths" not in failure["message"]


def test_canonical_setup_emits_one_final_result_in_json_mode(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    state.dependencies_ready = True
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: None)
    assert execute(environment, "install", bin_dir, output="json", legacy=False) == 0
    [final] = events(capsys)
    assert final["status"] == "ready"
    assert len(state.registered) == 1

    state.installed = False
    state.error = environment.NodeError("COMMAND_PATH_CONFLICT", "fake path")
    assert execute(environment, "install", bin_dir, output="json", legacy=False) == 1
    [failure] = events(capsys)
    assert failure["status"] == "failed"
    assert failure["phase"] == "registering"
    assert failure["diagnostics"][0]["code"] == "COMMAND_PATH_CONFLICT"


@pytest.fixture
def npm_installation(tmp_path):
    tool_root = tmp_path / "installed tool"
    tool_root.mkdir()
    prefix = tmp_path / "npm prefix"
    modules = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules")
    package = modules / "@himate/knowledge-cli"
    dispatcher = package / "bin/knowledge.js"
    dispatcher.parent.mkdir(parents=True)
    dispatcher.write_text('throw new Error("The inspection must not execute the npm script");\n', encoding="utf-8")
    (package / "package.json").write_text(json.dumps({
        "name": "@himate/knowledge-cli", "version": "test", "bin": {"knowledge": "bin/knowledge.js"},
    }), encoding="utf-8")
    marker = {"package": "@himate/knowledge-cli", "version": "test", "packageRoot": str(package),
              "launcherSha256": hashlib.sha256(dispatcher.read_bytes()).hexdigest()}
    (tool_root / ".install.json").write_text(json.dumps(marker), encoding="utf-8")
    if os.name == "nt":
        shim = prefix / "knowledge.cmd"
        shim.write_text('@ECHO off\n"%_prog%" "%dp0%\\node_modules\\@himate\\knowledge-cli\\bin\\knowledge.js" %*\n',
                        encoding="utf-8")
    else:
        shim = prefix / "bin/knowledge"
        shim.parent.mkdir()
        dispatcher.chmod(0o755)
        shim.symlink_to(dispatcher)
    return tool_root, shim


def test_npm_setup_reuses_launcher_and_selected_python(environment, npm_installation, monkeypatch, capsys):
    tool_root, shim = npm_installation
    state = SimpleNamespace(ready=False, pip_calls=0)
    monkeypatch.setattr(environment.command_install, "_find_on_path", lambda: str(shim))
    monkeypatch.setattr(environment.command_install, "deploy_command", lambda *a, **kw: pytest.fail("Duplicate launcher"))

    def dependencies(requirements):
        assert requirements == tool_root / "runtime/requirements.lock.txt"
        return [], [] if state.ready else [{"code": "DEPENDENCY_UNAVAILABLE"}]

    def run(argv, **kwargs):
        assert argv[0] == sys.executable
        if "pip" in argv:
            state.pip_calls += 1
            state.ready = True
        else:
            assert argv == [sys.executable, "-B", str(tool_root / "knowledge.py"), "--help"]

    monkeypatch.setattr(environment.doctor, "inspect_dependencies", dependencies)
    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", None, legacy=False, tool_root=tool_root) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing", "verifying"]
    assert final["status"] == "ready"
    assert final["command"]["kind"] == "npm" and final["command"]["on_path"]
    assert final["command"]["path"] == str(shim)
    assert execute(environment, "install", None, legacy=False, tool_root=tool_root) == 0
    assert [step["phase"] for step in events(capsys)[:-1]] == ["checking", "verifying"]
    assert state.pip_calls == 1


def test_npm_setup_honors_explicit_bin_dir(environment, npm_installation, monkeypatch, capsys, tmp_path):
    tool_root, shim = npm_installation
    bin_dir = tmp_path / "custom bin"
    monkeypatch.setattr(environment.command_install, "_find_on_path", lambda: str(shim))
    monkeypatch.setattr(environment.doctor, "inspect_dependencies", lambda _: ([], []))
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: None)

    assert execute(environment, "check", bin_dir, legacy=False, tool_root=tool_root) == 0
    [initial] = events(capsys)
    assert initial["status"] == "needs_cli"
    assert initial["command"]["bin_dir"] == str(bin_dir)
    assert execute(environment, "install", bin_dir, legacy=False, tool_root=tool_root) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "registering", "verifying"]
    assert final["status"] == "ready"
    assert Path(final["command"]["path"]).parent == bin_dir
    assert Path(final["command"]["path"]).is_file()
    assert shim.is_file()


@pytest.mark.parametrize("problem", ["missing", "shadowed", "tampered"])
def test_npm_setup_leaves_unowned_paths_untouched(environment, npm_installation, monkeypatch, capsys, problem):
    tool_root, shim = npm_installation
    found = str(shim)
    if problem == "missing":
        shim.unlink()
        found = None
    elif problem == "shadowed":
        found = str(tool_root / "unrelated/knowledge")
    else:
        marker = tool_root / ".install.json"
        metadata = json.loads(marker.read_text(encoding="utf-8"))
        metadata["launcherSha256"] = "0" * 64
        marker.write_text(json.dumps(metadata), encoding="utf-8")
        found = None

    monkeypatch.setattr(environment.command_install, "_find_on_path", lambda: found)
    monkeypatch.setattr(environment.command_install, "deploy_command", lambda *a, **kw: pytest.fail("Duplicate launcher"))
    monkeypatch.setattr(environment.doctor, "inspect_dependencies", lambda _: ([], []))
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: pytest.fail("Unexpected execution"))
    assert execute(environment, "check", None, legacy=False, tool_root=tool_root) == 0
    assert events(capsys)[0]["status"] == "needs_cli"
    assert execute(environment, "install", None, legacy=False, output="json", tool_root=tool_root) == 1
    [failure] = events(capsys)
    assert failure["status"] == "failed"
    assert failure["code"] == ("COMMAND_PATH_CONFLICT" if problem == "shadowed" else "NPM_LAUNCHER_UNAVAILABLE")
