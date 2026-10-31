"""Isolated capability copying and PowerShell argument forwarding; no real pip."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture
def distribution(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "skill_deploy", Path(__file__).resolve().parents[1] / "deploy.py"
    )
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    source = tmp_path / "source"
    package = source / "skills/common/knowledge/hs-knowledge-example"
    (package / "references").mkdir(parents=True)
    (package / "SKILL.md").write_text("current instructions", encoding="utf-8")
    (package / "references/guide.md").write_text("business reference", encoding="utf-8")
    workflows = source / "workflows/common/knowledge"
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        template = workflows / name
        template.mkdir(parents=True)
        (template / "workflow.yaml").write_text("id: " + name + "\n", encoding="utf-8")
        (template / "layouts.yaml").write_text("canvas: {}\n", encoding="utf-8")
        (template / "README.md").write_text("工作流说明\n", encoding="utf-8")
    (workflows / "not-a-template").mkdir()
    (workflows / "not-a-template/README.md").write_text("not a workflow", encoding="utf-8")
    lock = source / "himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt"
    lock.parent.mkdir(parents=True)
    lock.write_text("PyYAML==6.0.3\n", encoding="utf-8")
    return backend, source, package, workflows, lock


def test_copy_skills_workflows_and_install_with_selected_python(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows, lock = distribution
    target = tmp_path / "installed skills"
    (target / package.name).mkdir(parents=True)
    (target / package.name / "SKILL.md").write_text("old", encoding="utf-8")
    stale_skill = target / package.name / "old-script.py"
    stale_skill.write_text("retired script", encoding="utf-8")
    unrelated = target / "user-package/SKILL.md"
    unrelated.parent.mkdir()
    unrelated.write_text("keep", encoding="utf-8")
    workflow_target = tmp_path / "workflow templates"
    (workflow_target / "hs-knowledge-ingest").mkdir(parents=True)
    (workflow_target / "hs-knowledge-ingest/workflow.yaml").write_text("old workflow", encoding="utf-8")
    extra = workflow_target / "hs-knowledge-ingest/user-notes.txt"
    extra.write_text("stale package file", encoding="utf-8")
    other = workflow_target / "user-workflow/workflow.yaml"
    other.parent.mkdir()
    other.write_text("keep unrelated", encoding="utf-8")
    calls = []
    phases = []

    def run(command, **kwargs):
        assert stale_skill.is_file() and extra.is_file()
        phases.append("install")
        calls.append((command, kwargs))

    monkeypatch.setattr(backend.subprocess, "run", run)
    original_remove, original_copy = backend.shutil.rmtree, backend.shutil.copytree

    def remove(*args, **kwargs):
        phases.append("delete")
        return original_remove(*args, **kwargs)

    def copy(*args, **kwargs):
        phases.append("copy")
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(backend.shutil, "rmtree", remove)
    monkeypatch.setattr(backend.shutil, "copytree", copy)
    selected_python = str(tmp_path / "chosen-env/python.exe")
    assert backend.main([
        "--source-root", str(source), "--skills-root", str(target),
        "--workflows-root", str(workflow_target), "--python", selected_python,
    ]) == 0
    assert (target / package.name / "SKILL.md").read_text(encoding="utf-8") == "current instructions"
    assert (target / package.name / "references/guide.md").read_text(encoding="utf-8") == "business reference"
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert set(path.name for path in target.iterdir()) == {package.name, "user-package"}
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        for filename in ("workflow.yaml", "layouts.yaml", "README.md"):
            assert (workflow_target / name / filename).read_bytes() == (workflows / name / filename).read_bytes()
    assert not stale_skill.exists() and not extra.exists()
    assert other.read_text(encoding="utf-8") == "keep unrelated"
    assert set(path.name for path in workflow_target.iterdir()) == {
        "hs-knowledge-ingest", "hs-knowledge-lint", "user-workflow",
    }
    assert calls == [([selected_python, "-m", "pip", "install", "-r", str(lock)], {"check": True})]
    assert phases[0] == "install"
    assert max(index for index, phase in enumerate(phases) if phase == "delete") < phases.index("copy")


def test_failed_dependency_install_keeps_existing_packages(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows, lock = distribution
    target = tmp_path / "installed skills"
    workflow_target = tmp_path / "installed workflows"
    for root, name, filename in ((target, package.name, "SKILL.md"),
                                 (workflow_target, "hs-knowledge-ingest", "workflow.yaml")):
        old = root / name / filename
        old.parent.mkdir(parents=True)
        old.write_bytes(b"old installed package")
    before = {str(path): path.read_bytes() for root in (target, workflow_target)
              for path in root.rglob("*") if path.is_file()}

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backend.subprocess, "run", fail)
    assert backend.main(["--source-root", str(source), "--skills-root", str(target),
                         "--workflows-root", str(workflow_target)]) == 1
    assert {str(path): path.read_bytes() for root in (target, workflow_target)
            for path in root.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("kind", ["skills", "workflows"])
def test_replacement_cannot_delete_distribution_sources(distribution, tmp_path, monkeypatch, kind):
    backend, source, package, workflows, lock = distribution
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    skills_root = package.parent if kind == "skills" else tmp_path / "skills"
    workflows_root = workflows if kind == "workflows" else tmp_path / "workflows"
    assert backend.main(["--source-root", str(source), "--skills-root", str(skills_root),
                         "--workflows-root", str(workflows_root)]) == 1
    assert {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()} == before
    assert calls == []


@pytest.mark.parametrize("nested_root", ["workflows", "skills"])
def test_replacement_cannot_delete_the_other_installation_root(distribution, tmp_path, monkeypatch, nested_root):
    backend, source, package, workflows, lock = distribution
    shared = tmp_path / "installation"
    if nested_root == "workflows":
        skills_root, workflows_root = shared, shared / package.name
    else:
        skills_root, workflows_root = shared / "hs-knowledge-ingest", shared
    for root in (skills_root, workflows_root):
        extra = root / "unrelated-package/keep.txt"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"keep unrelated content")
    before = {str(path): path.read_bytes() for path in shared.rglob("*") if path.is_file()}
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(["--source-root", str(source), "--skills-root", str(skills_root),
                         "--workflows-root", str(workflows_root)]) == 1
    assert {str(path): path.read_bytes() for path in shared.rglob("*") if path.is_file()} == before
    assert calls == []


def test_default_workflow_directory_is_under_the_selected_user_home(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows, lock = distribution
    home = tmp_path / "synthetic user"
    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source)]) == 0
    assert (home / ".openflow/config/skills" / package.name / "SKILL.md").is_file()
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        assert (home / ".openflow/config/workflow-templates" / name / "workflow.yaml").read_bytes() == (
            workflows / name / "workflow.yaml").read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
@pytest.mark.parametrize("explicit_workflow_root", [False, True], ids=["default", "explicit"])
def test_powershell_forwards_workflow_destination(tmp_path, explicit_workflow_root):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    capture = tmp_path / "arguments.json"
    recorder = tmp_path / "chosen python.ps1"
    recorder.write_text(
        "[System.IO.File]::WriteAllText($env:FACTUM_DEPLOY_TEST_CAPTURE, "
        "(ConvertTo-Json -InputObject @($args) -Compress))\nexit 0\n", encoding="utf-8",
    )
    source = tmp_path / "source root"
    skills = tmp_path / "skills root"
    workflows = tmp_path / "workflow root"
    wrapper = Path(__file__).resolve().parents[3] / "deploy.ps1"
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper),
               "-NonInteractive", "-SkillsRoot", str(skills), "-Python", str(recorder),
               "-SourceRoot", str(source)]
    if explicit_workflow_root:
        command += ["-WorkflowsRoot", str(workflows)]
    result = subprocess.run(command, capture_output=True, timeout=30,
                            env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    arguments = json.loads(capture.read_text(encoding="utf-8"))
    assert arguments[arguments.index("--source-root") + 1] == str(source)
    assert arguments[arguments.index("--skills-root") + 1] == str(skills)
    expected = workflows if explicit_workflow_root else Path.home() / ".openflow/config/workflow-templates"
    assert Path(arguments[arguments.index("--workflows-root") + 1]) == expected
    assert arguments[arguments.index("--python") + 1] == str(recorder)
    assert not skills.exists() and not workflows.exists()
