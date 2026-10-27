"""The setup entry uses the selected global Python and creates no deployment tree."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def deployment(tmp_path):
    skill = tmp_path / "agent/.codex/skills/hs-knowledge-explore"
    (skill / "scripts").mkdir(parents=True)
    shutil.copyfile(SOURCE / "scripts/setup.py", skill / "scripts/setup.py")
    shutil.copyfile(SOURCE / "requirements.lock.txt", skill / "requirements.lock.txt")
    project = tmp_path / "business"
    knowledge = project / "nested/himate-knowledge-wifi-mp"
    knowledge.mkdir(parents=True)
    (project / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: setup-example\n"
        "knowledge_roots:\n  wifi: nested/himate-knowledge-wifi-mp\ncode_root: .\nmodules: []\n",
        encoding="utf-8")
    return skill, project, knowledge


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def invoke(deployment, *args, no_site=False):
    skill, project, _ = deployment
    command = [sys.executable, "-B", "-I"]
    if no_site:
        command.append("-S")
    command += [str(skill / "scripts/setup.py"), *args]
    return subprocess.run(command, cwd=project, capture_output=True, timeout=60)


def test_help_and_missing_dependency_report_need_only_stdlib(deployment):
    skill, project, _ = deployment
    before = snapshot(project.parent)
    help_result = invoke(deployment, "--help", no_site=True)
    assert help_result.returncode == 0
    result = invoke(deployment, "--local", "--check-only", no_site=True)
    report = json.loads(result.stdout)
    assert result.returncode == 2 and report["status"] == "missing_dependencies"
    assert any(row["name"].lower() == "pyyaml" for row in report["missing"])
    assert snapshot(project.parent) == before


def test_existing_global_dependencies_and_repeat_leave_both_parts_unchanged(deployment):
    skill, project, knowledge = deployment
    before = snapshot(project.parent)
    for _ in range(2):
        result = invoke(deployment, "--local", "--check-only")
        report = json.loads(result.stdout)
        assert result.returncode == 0, report
        assert report["status"] == "ready" and report["dependencies"] == "already_available"
        assert report["python"] == sys.executable
        assert Path(report["knowledge_root"]) == knowledge
        assert not any(key in report for key in ("catalog", "registry", "binding", "venv"))
    assert snapshot(project.parent) == before
    assert not (knowledge / ".build").exists()


def test_ssh_config_is_a_harness_hint_without_connecting_or_imposing_port_checks(deployment):
    skill, project, _ = deployment
    (skill / "config.env").write_text(
        "EXECUTION_MODE=ssh\nSSH_HOST=host.example\nSSH_USER=operator\n"
        "SSH_PORT=port-resolved-by-harness\nREMOTE_PROJECT_ROOT=/srv/real-project\n"
        "SSH_PASSWORD=must-not-be-returned\n", encoding="utf-8")
    before = snapshot(project.parent)
    # -S also proves that SSH entry discovery neither installs nor imports runtime packages.
    result = invoke(deployment, no_site=True)
    report = json.loads(result.stdout)
    assert result.returncode == 0 and report["status"] == "ssh_entry"
    assert report["ssh"]["SSH_PORT"] == "port-resolved-by-harness"
    assert "must-not-be-returned" not in result.stdout.decode()
    assert snapshot(project.parent) == before


def test_missing_packages_are_installed_into_the_same_python(deployment, monkeypatch, capsys):
    skill, project, _ = deployment
    spec = importlib.util.spec_from_file_location("global_setup_test", skill / "scripts/setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    outcomes = iter([[{"name": "example", "required": "1", "installed": None}], []])
    monkeypatch.setattr(setup, "missing_packages", lambda pins: next(outcomes))
    commands = []
    monkeypatch.setattr(setup.subprocess, "run", lambda command, **kwargs: commands.append(command))
    before = snapshot(project.parent)
    code = setup.main(["--local", "--workspace-config", str(project / "config.yml")])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report["dependencies"] == "installed"
    assert commands[0][:3] == [sys.executable, "-m", "pip"]
    assert "--no-cache-dir" in commands[0] and "--no-user" in commands[0]
    assert not any(flag in commands[0] for flag in ("--prefix", "--target", "venv"))
    assert snapshot(project.parent) == before


def test_failed_global_install_does_not_publish_any_state(deployment, monkeypatch, capsys):
    skill, project, _ = deployment
    spec = importlib.util.spec_from_file_location("failed_setup_test", skill / "scripts/setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    monkeypatch.setattr(setup, "missing_packages", lambda pins: [{"name": "missing"}])

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(setup.subprocess, "run", fail)
    before = snapshot(project.parent)
    assert setup.main(["--local", "--workspace-config", str(project / "config.yml")]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert snapshot(project.parent) == before


def test_config_error_is_reported_without_creating_a_binding(deployment):
    _, project, _ = deployment
    (project / "config.yml").write_text("knowledge_roots: [invalid\n", encoding="utf-8")
    before = snapshot(project.parent)
    result = invoke(deployment, "--local", "--check-only")
    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "failed"
    assert "Traceback" not in result.stderr.decode()
    assert snapshot(project.parent) == before


def test_missing_project_config_is_reported_before_installing_packages(deployment, monkeypatch, capsys):
    skill, project, _ = deployment
    spec = importlib.util.spec_from_file_location("missing_config_setup_test", skill / "scripts/setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    monkeypatch.setattr(setup, "missing_packages", lambda pins: pytest.fail("project path must be checked first"))
    assert setup.main(["--local", "--workspace-config", str(project / "absent.yml")]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
