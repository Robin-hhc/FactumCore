"""Check and install against the selected Python without modifying the test host."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

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
    result = subprocess.run([sys.executable, "-S", "-B", str(ENTRY), "check"], cwd=tmp_path,
                            capture_output=True, check=True, timeout=60)
    payload = json.loads(result.stdout)
    manifest = json.loads((TOOL_ROOT / "runtime/manifest.json").read_text(encoding="utf-8"))
    assert payload["status"] == "needs_install"
    assert Path(payload["tool_root"]) == TOOL_ROOT
    assert Path(payload["python"]).samefile(sys.executable)
    assert payload["toolkit_version"] == manifest["version"]
    pyyaml = next(row for row in payload["dependencies"] if row["name"].casefold() == "pyyaml")
    assert pyyaml == {"name": pyyaml["name"], "expected": "6.0.3", "actual": None, "status": "missing"}
    assert not list(tmp_path.iterdir())


def test_install_runs_pinned_pip_and_emits_stages(environment, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(environment, "report", lambda: {"status": "needs_install"})

    def run(argv, **kwargs):
        calls.append((argv, kwargs))

    monkeypatch.setattr(environment.subprocess, "run", run)
    assert environment.main(["install"]) == 0
    stages = [json.loads(line)["phase"] for line in capsys.readouterr().out.splitlines()]
    assert stages == ["checking", "installing", "verifying"]
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv == [sys.executable, "-m", "pip", "install", "-r", str(environment.REQUIREMENTS)]
    assert options["cwd"] == TOOL_ROOT
    assert options["check"] is True
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL


def test_install_keeps_an_already_ready_environment(environment, monkeypatch, capsys):
    monkeypatch.setattr(environment, "report", lambda: {"status": "ready"})

    def fail(*args, **kwargs):
        pytest.fail("An already ready environment must not run pip")

    monkeypatch.setattr(environment.subprocess, "run", fail)
    assert environment.main(["install"]) == 0
    stages = [json.loads(line)["phase"] for line in capsys.readouterr().out.splitlines()]
    assert stages == ["checking", "verifying"]


def test_install_failure_does_not_emit_raw_pip_output(environment, monkeypatch, capsys):
    monkeypatch.setattr(environment, "report", lambda: {"status": "needs_install"})

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pip", stderr=b"private index configuration")

    monkeypatch.setattr(environment.subprocess, "run", fail)
    assert environment.main(["install"]) == 1
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[-1]["code"] == "DEPENDENCY_INSTALL_FAILED"
    assert "private index configuration" not in output
    assert not any(event["phase"] == "verifying" for event in events)
