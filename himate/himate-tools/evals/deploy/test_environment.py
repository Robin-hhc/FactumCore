"""Check and install against the selected Python without modifying the test host."""

import hashlib
import json
import os
from pathlib import Path
import platform
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


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path):
    home = tmp_path / "isolated home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(home / "AppData/Roaming"))
    monkeypatch.delenv("HIMATE_KNOWLEDGE_PYTHON", raising=False)
    return home


def test_check_reports_dependencies_without_a_knowledge_root(tmp_path):
    bin_dir = tmp_path / "isolated bin"
    base = sys._base_executable
    result = subprocess.run([base, "-B", str(ENTRY), "check", "--bin-dir", str(bin_dir)], cwd=tmp_path,
                            capture_output=True, check=True, timeout=60)
    payload = json.loads(result.stdout)
    manifest = json.loads((TOOL_ROOT / "runtime/manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] in {"needs_install", "needs_cli"}
    assert Path(payload["tool_root"]) == TOOL_ROOT
    assert Path(payload["python"]).samefile(base)
    assert payload["python_version"] == platform.python_version()
    assert payload["toolkit_version"] == manifest["version"]
    assert any(item["name"].casefold() == "pyyaml" for item in payload["dependencies"])
    assert all(not entry["code"].startswith("VENV_") for entry in payload["diagnostics"])
    assert "bootstrap_python" not in payload
    assert payload["command"]["bin_dir"] == str(bin_dir)
    assert not payload["command"]["installed"]
    assert not list(tmp_path.iterdir())

    canonical = subprocess.run([
        base, "-B", str(TOOL_ROOT / "knowledge.py"),
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
    monkeypatch.setattr(environment, "find_spec", lambda _: object())
    monkeypatch.setattr(environment, "_fresh_report", environment._report)
    return state, bin_dir


def execute(environment, action, bin_dir, *, output=None, legacy=True, tool_root=TOOL_ROOT):
    return environment.run_environment(tool_root, {"version": "test"}, action, bin_dir=bin_dir,
                                       output=output or ("jsonl" if action == "install" else "json"), legacy=legacy)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_setup_reuses_missing_pip_diagnostic_and_keeps_local_log(
        environment, runtime, monkeypatch, capsys, isolated_home):
    state, bin_dir = runtime

    def probe(name):
        assert name == "pip"
        return None

    monkeypatch.setattr(environment, "find_spec", probe)
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected execution"))

    assert execute(environment, "check", bin_dir, legacy=False) == 0

    [report] = events(capsys)
    assert report["status"] == "needs_install"
    assert report["python"] == sys.executable
    diagnostic = report["diagnostics"][0]
    assert diagnostic["code"] == "DEPENDENCY_PIP_MISSING" and "pip" in diagnostic["message"]
    assert not isolated_home.exists()

    assert execute(environment, "install", bin_dir, output="jsonl", legacy=False) == 1

    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing"]
    assert final["status"] == "failed" and final["phase"] == "installing"
    assert final["diagnostics"][0]["code"] == diagnostic["code"]
    assert final["diagnostics"][0]["message"] == diagnostic["message"]
    log = Path(final["log_path"])
    assert log.parent == isolated_home / ".himate/knowledge/logs"
    assert diagnostic["message"] in log.read_text(encoding="utf-8")
    assert not state.registered
    assert not (isolated_home / ".himate/knowledge/.venv").exists()


def test_ready_interpreter_can_be_used_without_pip(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    state.dependencies_ready = state.installed = True
    monkeypatch.setattr(environment, "find_spec", lambda _: None)

    def run(argv, **kwargs):
        assert argv[-1] == "--help"

    monkeypatch.setattr(environment.subprocess, "run", run)

    for action in ("check", "install"):
        assert execute(environment, action, bin_dir, output="json", legacy=False) == 0
        [report] = events(capsys)
        assert report["status"] == "ready" and report["diagnostics"] == []


def test_install_runs_pinned_pip_on_the_invoked_interpreter_before_registering(
        environment, runtime, monkeypatch, capsys, isolated_home):
    state, bin_dir = runtime
    calls = []

    def probe(name):
        assert name == "pip"
        return object()

    monkeypatch.setattr(environment, "find_spec", probe)
    for key in ("PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON"):
        monkeypatch.setenv(key, str(isolated_home / "other destination"))
    monkeypatch.setenv("PIP_USER", "1")
    monkeypatch.setenv("PIP_INDEX_URL", "https://packages.test/simple")

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if "pip" in argv:
            working = Path(kwargs["cwd"])
            assert working.is_dir() and not list(working.iterdir())
        if "config" in argv:
            return SimpleNamespace(stdout="global.index-url='https://user:private@packages.test/simple'\n")
        if "pip" in argv:
            state.dependencies_ready = True
            return SimpleNamespace(stdout="installed packages")

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing", "registering", "verifying"]
    assert final["status"] == "ready"
    assert final["command"]["installed"]
    assert state.checked == [False, False, True, True]
    assert len(state.registered) == 1
    (configuration, configuration_options), (argv, options), (verification, verification_options) = calls
    assert configuration == [sys.executable, *environment.PYTHON_MODULE_FLAGS, "pip", "--python=", "config", "list"]
    assert argv == [sys.executable, "-E", "-X", "utf8", "-m", "pip", "install", "-r",
                    str(TOOL_ROOT / "runtime/requirements.lock.txt")]
    assert options["env"]["PIP_USER"] == "1"
    assert options["env"]["PIP_INDEX_URL"] == "https://packages.test/simple"
    assert not {"PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON"}.intersection(options["env"])
    assert not (isolated_home / ".himate/knowledge/.venv").exists()
    assert options["cwd"] == configuration_options["cwd"] and options["cwd"] != TOOL_ROOT
    assert not Path(options["cwd"]).exists()
    assert options["check"] is True
    assert options["stdin"] == subprocess.DEVNULL
    assert options["stdout"] == subprocess.PIPE
    assert options["stderr"] == subprocess.STDOUT
    log = Path(final["log_path"]).read_text(encoding="utf-8")
    assert "installed packages" in log and "user:private" not in log
    command = final["command"]
    assert verification == ([sys.executable, "-E", "-B", command["dispatcher"], "--help"] if os.name == "nt"
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

    def fail(argv, **kwargs):
        if "config" in argv:
            return SimpleNamespace(stdout="")
        raise subprocess.CalledProcessError(1, "pip", stderr=b"private index config https://user:key@packages.test/p?token=abc")

    monkeypatch.setattr(environment.subprocess, "run", fail)
    assert execute(environment, "install", bin_dir) == 1
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[-1]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert "private index config" not in output
    log = Path(events[-1]["log_path"]).read_text(encoding="utf-8")
    assert "https://packages.test/" in log and "user:key" not in log and "token=abc" not in log
    assert not any(event["phase"] == "verifying" for event in events)
    assert not state.registered


def test_failed_dependency_verification_prevents_registration(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=""))
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


def test_npm_setup_reuses_launcher_and_invoked_python(environment, npm_installation, monkeypatch, capsys):
    tool_root, shim = npm_installation
    state = SimpleNamespace(ready=False, pip_calls=0)
    monkeypatch.setattr(environment.command_install, "_find_on_path", lambda: str(shim))
    monkeypatch.setattr(environment.command_install, "deploy_command", lambda *a, **kw: pytest.fail("Duplicate launcher"))

    def dependencies(requirements):
        assert requirements == tool_root / "runtime/requirements.lock.txt"
        return [], [] if state.ready else [{"code": "DEPENDENCY_UNAVAILABLE"}]

    def run(argv, **kwargs):
        assert argv[0] == sys.executable
        if "config" in argv:
            return SimpleNamespace(stdout="")
        if "pip" in argv:
            state.pip_calls += 1
            state.ready = True
            return SimpleNamespace(stdout="")
        else:
            assert argv == [sys.executable, "-E", "-B", str(tool_root / "knowledge.py"), "--help"]

    monkeypatch.setattr(environment.doctor, "inspect_dependencies", dependencies)
    monkeypatch.setattr(environment, "find_spec", lambda _: object())
    monkeypatch.setattr(environment, "_fresh_report", environment._report)
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


@pytest.mark.parametrize(("reason", "diagnostic"), [
    ("error: externally-managed-environment", "DEPENDENCY_EXTERNALLY_MANAGED"),
    ("ConnectionError: Connection refused", "DEPENDENCY_INDEX_UNAVAILABLE"),
    ("401 Client Error: Unauthorized", "DEPENDENCY_INDEX_AUTH_FAILED"),
    ("[Errno 13] Permission denied", "DEPENDENCY_PERMISSION_DENIED"),
    ("[Errno 28] No space left on device", "DEPENDENCY_DISK_FULL"),
])
def test_pip_failures_are_diagnosable(environment, runtime, monkeypatch, capsys, reason, diagnostic):
    state, bin_dir = runtime

    def run(argv, **kwargs):
        if "config" in argv:
            return SimpleNamespace(stdout="")
        raise subprocess.CalledProcessError(1, argv, output=reason)

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir, output="json", legacy=False) == 1
    [final] = events(capsys)
    assert final["code"] == diagnostic
    assert reason in Path(final["log_path"]).read_text(encoding="utf-8")
    assert not state.registered


def test_concurrent_setup_reports_busy_without_running_pip(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected execution"))
    with environment._setup_lock(environment.managed_home(TOOL_ROOT)):
        assert execute(environment, "install", bin_dir, output="json", legacy=False) == 1
    [final] = events(capsys)
    assert final["code"] == "INSTALL_BUSY"
    assert not state.registered


@pytest.mark.parametrize("option", ["install.target", "global.prefix", "install.root", "global.python"])
def test_setup_blocks_pip_config_that_overrides_install_location(environment, runtime, monkeypatch, capsys, option):
    state, bin_dir = runtime

    def run(argv, **kwargs):
        assert argv[-3:] == ["--python=", "config", "list"]
        return SimpleNamespace(stdout=f"{option}='private-path'\n")

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir, output="json", legacy=False) == 1
    [final] = events(capsys)
    assert final["code"] == "DEPENDENCY_LOCATION_OVERRIDE"
    assert "private-path" not in Path(final["log_path"]).read_text(encoding="utf-8")
    assert not state.registered


def test_pip_config_allows_index_settings_and_user_install(environment):
    configuration = "global.index-url='https://mirror.test/simple'\ninstall.user='true'\n"
    assert not environment._has_pip_location_override(configuration)
