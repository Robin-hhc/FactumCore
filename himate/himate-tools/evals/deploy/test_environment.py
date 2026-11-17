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
APT_VENV_HINT = f"sudo apt install python{sys.version_info.major}.{sys.version_info.minor}-venv"


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
    monkeypatch.delenv("HIMATE_KNOWLEDGE_PYTHON", raising=False)
    return home


@pytest.fixture
def selected(environment, monkeypatch):
    monkeypatch.setattr(environment, "selected_python", lambda _: Path(sys.executable))


def test_check_reports_dependencies_without_a_knowledge_root(tmp_path):
    bin_dir = tmp_path / "isolated bin"
    base = sys._base_executable
    result = subprocess.run([base, "-B", str(ENTRY), "check", "--bin-dir", str(bin_dir)], cwd=tmp_path,
                            capture_output=True, check=True, timeout=60)
    payload = json.loads(result.stdout)
    manifest = json.loads((TOOL_ROOT / "runtime/manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "needs_install"
    assert Path(payload["tool_root"]) == TOOL_ROOT
    assert payload["python"] is None
    assert Path(payload["bootstrap_python"]).samefile(base)
    assert payload["bootstrap_python_version"] == platform.python_version()
    assert payload["toolkit_version"] == manifest["version"]
    assert payload["dependencies"] == []
    assert payload["diagnostics"][0]["code"] in {"VENV_REQUIRED", "VENV_MODULE_MISSING"}
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
def runtime(environment, monkeypatch, tmp_path, selected):
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
    return state, bin_dir


def execute(environment, action, bin_dir, *, output=None, legacy=True, tool_root=TOOL_ROOT):
    return environment.run_environment(tool_root, {"version": "test"}, action, bin_dir=bin_dir,
                                       output=output or ("jsonl" if action == "install" else "json"), legacy=legacy)


def events(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def available_modules(environment, monkeypatch, *names):
    monkeypatch.setattr(environment, "find_spec", lambda name: object() if name in names else None)


@pytest.mark.parametrize(("modules", "platform_name", "distribution", "hint", "code"), [
    (("venv", "ensurepip"), "linux", {"ID": "ubuntu"}, "knowledge setup", "VENV_REQUIRED"),
    (("ensurepip",), "linux", {"ID": "ubuntu"}, APT_VENV_HINT, "VENV_MODULE_MISSING"),
    (("venv", "pip"), "linux", {"ID": "ubuntu"}, APT_VENV_HINT, "VENV_MODULE_MISSING"),
    (("venv",), "linux", {"ID": "mint", "ID_LIKE": "ubuntu debian"}, APT_VENV_HINT, "VENV_MODULE_MISSING"),
    (("venv",), "win32", {}, "勾选 pip", "VENV_MODULE_MISSING"),
])
def test_check_reports_bootstrap_modules_without_writing(
        environment, monkeypatch, capsys, tmp_path, modules, platform_name, distribution, hint, code):
    monkeypatch.setattr(environment, "selected_python", lambda _: None)
    monkeypatch.setattr(environment, "sys", SimpleNamespace(
        platform=platform_name, version_info=sys.version_info, executable=sys.executable,
    ))
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", lambda: distribution)
    available_modules(environment, monkeypatch, *modules)
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected execution"))

    assert execute(environment, "check", tmp_path / "bin", legacy=False) == 0

    [report] = events(capsys)
    assert report["status"] == "needs_install" and report["python"] is None
    assert report["bootstrap_python"] == sys.executable
    assert report["bootstrap_python_version"] == platform.python_version()
    assert report["diagnostics"][0]["code"] == code
    assert hint in report["diagnostics"][0]["message"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("existing_environment", [False, True])
def test_setup_reuses_early_venv_diagnostic_and_keeps_local_log(
        environment, runtime, monkeypatch, capsys, isolated_home, existing_environment):
    state, bin_dir = runtime
    target = Path(sys.executable) if existing_environment else None
    monkeypatch.setattr(environment, "selected_python", lambda _: target)
    monkeypatch.setattr(environment.sys, "platform", "linux")
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu"})
    available_modules(environment, monkeypatch, "venv")
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected execution"))

    assert execute(environment, "check", bin_dir, legacy=False) == 0

    [report] = events(capsys)
    assert report["status"] == "needs_install"
    assert report["python"] == (str(target) if target else None)
    diagnostic = report["diagnostics"][0]
    assert diagnostic["code"] == "VENV_MODULE_MISSING" and APT_VENV_HINT in diagnostic["message"]
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


def test_ready_external_environment_does_not_require_bootstrap_modules(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    state.dependencies_ready = state.installed = True
    available_modules(environment, monkeypatch)

    def run(argv, **kwargs):
        assert argv[-1] == "--help"

    monkeypatch.setattr(environment.subprocess, "run", run)

    for action in ("check", "install"):
        assert execute(environment, action, bin_dir, output="json", legacy=False) == 0
        [report] = events(capsys)
        assert report["status"] == "ready" and report["diagnostics"] == []


def test_install_runs_pinned_pip_before_registering(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    calls = []
    available_modules(environment, monkeypatch, "pip")

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
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
    (configuration, _), (argv, options), (verification, verification_options) = calls
    assert configuration == [sys.executable, *environment.PYTHON_MODULE_FLAGS, "pip", "--python=", "config", "list"]
    assert argv == [sys.executable, *environment.PYTHON_MODULE_FLAGS, "pip", "--require-virtualenv", "install", "-r",
                    str(TOOL_ROOT / "runtime/requirements.lock.txt")]
    assert options["cwd"] == TOOL_ROOT
    assert options["check"] is True
    assert options["stdin"] == subprocess.DEVNULL
    assert options["stdout"] == subprocess.PIPE
    assert options["stderr"] == subprocess.STDOUT
    log = Path(final["log_path"]).read_text(encoding="utf-8")
    assert "installed packages" in log and "user:private" not in log
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


def test_npm_setup_reuses_launcher_and_selected_python(environment, npm_installation, monkeypatch, capsys, selected):
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


def test_npm_setup_honors_explicit_bin_dir(environment, npm_installation, monkeypatch, capsys, tmp_path, selected):
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
def test_npm_setup_leaves_unowned_paths_untouched(environment, npm_installation, monkeypatch, capsys, problem, selected):
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


def test_first_setup_creates_venv_and_verifies_in_target(environment, monkeypatch, capsys, tmp_path):
    target = environment.managed_python(TOOL_ROOT)
    bin_dir = tmp_path / "isolated bin"
    state = SimpleNamespace(created=False, ready=False, registered=False, calls=[])
    monkeypatch.setattr(environment, "selected_python", lambda _: target if state.created else None)
    monkeypatch.setattr(environment.doctor, "inspect_dependencies", lambda _: pytest.fail("Read bootstrap packages"))
    available_modules(environment, monkeypatch, "venv", "ensurepip")
    for name in ("PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON", "PYTHONUSERBASE"):
        monkeypatch.setenv(name, str(tmp_path / "outside"))
    monkeypatch.setenv("PIP_USER", "1")
    monkeypatch.setenv("PIP_INDEX_URL", "https://packages.test/simple")

    def run(argv, **kwargs):
        state.calls.append(argv)
        assert set(kwargs["env"]).isdisjoint({"PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_ROOT", "PIP_PYTHON",
                                              "PYTHONUSERBASE"})
        assert kwargs["env"]["PIP_INDEX_URL"] == "https://packages.test/simple"
        if "venv" in argv:
            assert argv == [sys.executable, *environment.PYTHON_MODULE_FLAGS, "venv",
                            str(environment.managed_home(TOOL_ROOT) / ".venv")]
            state.created = True
            return SimpleNamespace(stdout="")
        assert argv[0] == str(target)
        if "config" in argv:
            assert "--python=" in argv
            return SimpleNamespace(stdout="")
        if "pip" in argv:
            assert not state.ready and "--require-virtualenv" in argv
            state.ready = True
            return SimpleNamespace(stdout="")
        assert "--json" in argv and str(bin_dir) in argv and state.ready
        if "install-command" in argv:
            state.registered = True
            return SimpleNamespace(stdout="{}", returncode=0)
        assert argv[3:5] == ["doctor", "--environment-only"]
        data = {"status": "ready" if state.registered else "needs_cli", "python": str(target),
                "tool_root": str(TOOL_ROOT), "toolkit_version": "test", "diagnostics": [],
                "command": {"installed": state.registered}}
        return SimpleNamespace(stdout=json.dumps(data), returncode=0)

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir, legacy=False) == 0
    *steps, final = events(capsys)
    assert [step["phase"] for step in steps] == ["checking", "installing", "registering", "verifying"]
    assert final["status"] == "ready" and final["python"] == str(target)
    assert [argv[3] if argv[1] == "-B" else argv[argv.index("-m") + 1] for argv in state.calls] == [
        "venv", "pip", "pip", "doctor", "install-command", "doctor"]


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


def test_missing_venv_support_does_not_install_system_packages(environment, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(environment, "selected_python", lambda _: None)
    monkeypatch.setattr(environment.sys, "platform", "linux")
    monkeypatch.setattr(environment.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu"})
    available_modules(environment, monkeypatch, "venv", "ensurepip")

    def no_ensurepip(argv, **kwargs):
        assert argv[:-1] == [sys.executable, *environment.PYTHON_MODULE_FLAGS, "venv"]
        raise subprocess.CalledProcessError(1, argv, output="ensurepip is not available")

    monkeypatch.setattr(environment.subprocess, "run", no_ensurepip)
    assert execute(environment, "install", tmp_path / "bin", output="json", legacy=False) == 1
    [final] = events(capsys)
    assert final["code"] == "VENV_MODULE_MISSING"
    assert APT_VENV_HINT in final["message"]
    assert Path(final["log_path"]).is_file()


def test_setup_recovers_an_existing_venv_without_pip(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    calls = []
    available_modules(environment, monkeypatch, "ensurepip")

    def run(argv, **kwargs):
        if "-m" not in argv:
            return None
        module = argv[argv.index("-m") + 1]
        name = "config" if "config" in argv else module
        calls.append(name)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, argv, output="No module named pip")
        if name == "pip":
            state.dependencies_ready = True
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert execute(environment, "install", bin_dir, output="json", legacy=False) == 0
    [final] = events(capsys)
    assert final["status"] == "ready"
    assert calls == ["config", "ensurepip", "config", "pip"]


def test_concurrent_setup_reports_busy_without_running_pip(environment, runtime, monkeypatch, capsys):
    state, bin_dir = runtime
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: pytest.fail("Unexpected execution"))
    with environment._setup_lock(environment.managed_home(TOOL_ROOT)):
        assert execute(environment, "install", bin_dir, output="json", legacy=False) == 1
    [final] = events(capsys)
    assert final["code"] == "INSTALL_BUSY"
    assert not state.registered


@pytest.mark.parametrize("option", ["install.target", "global.prefix", "install.root", "global.python", "install.user"])
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


def test_pip_config_allows_index_settings_and_explicit_user_false(environment):
    configuration = "global.index-url='https://mirror.test/simple'\nglobal.user='on'\ninstall.user='false'\n"
    assert not environment._has_pip_location_override(configuration)
