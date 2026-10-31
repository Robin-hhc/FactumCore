"""Contained deployment and shared interaction; no real pip or user directories."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def distribution(tmp_path):
    spec = importlib.util.spec_from_file_location("skill_deploy", KNOWLEDGE_ROOT / "tools/deploy/deploy.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    source = tmp_path / "project with spaces" / "himate" / "knowledge-root"
    package = source / "skills/hs-knowledge-example"
    (package / "references").mkdir(parents=True)
    (package / "SKILL.md").write_text("current instructions", encoding="utf-8")
    (package / "references/guide.md").write_text("business reference", encoding="utf-8")
    workflows = source / "workflows"
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        template = workflows / name
        template.mkdir(parents=True)
        (template / "workflow.yaml").write_text("id: " + name + "\n", encoding="utf-8")
        (template / "layouts.yaml").write_text("canvas: {}\n", encoding="utf-8")
        (template / "README.md").write_text("工作流说明\n", encoding="utf-8")
    (workflows / "not-a-template").mkdir()
    (workflows / "not-a-template/README.md").write_text("not a workflow", encoding="utf-8")
    lock = source / "runtime/requirements.lock.txt"
    lock.parent.mkdir(parents=True)
    lock.write_text("PyYAML==6.0.3\n", encoding="utf-8")
    (source / "config.yml").write_text("workspace_id: synthetic\n", encoding="utf-8")
    (source / "AGENTS-code-root.md").write_text("# Synthetic project instructions\n", encoding="utf-8")
    assert not (source.parents[1] / ".git").exists()
    return backend, source, package, workflows, lock


def arguments(source, tmp_path):
    return ["--source-root", str(source),
            "--skills-root", str(tmp_path / "installed skills"),
            "--cac-skills-root", str(tmp_path / "cac skills"),
            "--workflows-root", str(tmp_path / "workflow templates"), "--non-interactive"]


def test_copy_all_destinations_then_project_entries_without_git(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows, lock = distribution
    skill_targets = [tmp_path / "installed skills", tmp_path / "cac skills"]
    workflow_target = tmp_path / "workflow templates"
    stale = []
    for target in skill_targets:
        (target / package.name).mkdir(parents=True)
        (target / package.name / "SKILL.md").write_text("old", encoding="utf-8")
        old = target / package.name / "old-script.py"
        old.write_text("retired script", encoding="utf-8")
        stale.append(old)
        (target / "user-package").mkdir()
        (target / "user-package/SKILL.md").write_text("keep", encoding="utf-8")
    (workflow_target / "hs-knowledge-ingest").mkdir(parents=True)
    old = workflow_target / "hs-knowledge-ingest/user-notes.txt"
    old.write_text("old", encoding="utf-8")
    stale.append(old)
    (workflow_target / "user-workflow").mkdir()
    (workflow_target / "user-workflow/workflow.yaml").write_text("keep", encoding="utf-8")
    calls, phases = [], []

    def run(command, **kwargs):
        assert all(path.is_file() for path in stale)
        assert not (source.parents[1] / "config.yml").exists()
        calls.append((command, kwargs))
        phases.append("install")

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
    assert backend.main([*arguments(source, tmp_path), "--python", selected_python]) == 0
    for target in skill_targets:
        assert (target / package.name / "SKILL.md").read_text(encoding="utf-8") == "current instructions"
        assert (target / package.name / "references/guide.md").read_text(encoding="utf-8") == "business reference"
        assert (target / "user-package/SKILL.md").read_text(encoding="utf-8") == "keep"
        assert set(path.name for path in target.iterdir()) == {package.name, "user-package"}
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        for filename in ("workflow.yaml", "layouts.yaml", "README.md"):
            assert (workflow_target / name / filename).read_bytes() == (workflows / name / filename).read_bytes()
    assert all(not path.exists() for path in stale)
    assert (workflow_target / "user-workflow/workflow.yaml").read_text(encoding="utf-8") == "keep"
    assert not (workflow_target / "not-a-template").exists()
    for original, name in (("config.yml", "config.yml"), ("AGENTS-code-root.md", "AGENTS.md")):
        assert (source.parents[1] / name).read_bytes() == (source / original).read_bytes()
        assert (source / original).is_file()
    assert calls == [([selected_python, "-m", "pip", "install", "-r", str(lock)], {"check": True})]
    assert phases[0] == "install"
    assert max(index for index, phase in enumerate(phases) if phase == "delete") < phases.index("copy")


def test_failed_pip_keeps_packages_and_project_files(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    for root, name, filename in ((tmp_path / "installed skills", package.name, "SKILL.md"),
                                 (tmp_path / "cac skills", package.name, "SKILL.md"),
                                 (tmp_path / "workflow templates", "hs-knowledge-ingest", "workflow.yaml")):
        old = root / name / filename
        old.parent.mkdir(parents=True)
        old.write_bytes(b"old installed package")
    for name in ("config.yml", "AGENTS.md"):
        (source.parents[1] / name).write_text("old project file", encoding="utf-8")
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backend.subprocess, "run", fail)
    assert backend.main(arguments(source, tmp_path)) == 1
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_interactive_defaults_show_three_roots_and_keep_one_entry(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    home = tmp_path / "synthetic user"
    project = source.parents[1]
    (project / "config.yml").write_text("keep config", encoding="utf-8")
    (project / "AGENTS.md").write_text("replace instructions", encoding="utf-8")
    answers, prompts = iter(["", "", "", "n", ""]), []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source)]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    assert len(prompts) == 5
    for prompt, relative in zip(prompts, (".openflow/config/skills", ".cac/skills",
                                          ".openflow/config/workflow-templates")):
        assert str(home / relative) in prompt
    assert str(project / "config.yml") in prompts[3] and "Y/n" in prompts[3]
    assert str(project / "AGENTS.md") in prompts[4] and "Y/n" in prompts[4]
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep config"
    assert (project / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()


def test_interactive_custom_directories_and_yes_overwrite(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    destinations = [tmp_path / name for name in ("custom openflow", "custom cac", "custom workflow")]
    (source.parents[1] / "config.yml").write_text("old config", encoding="utf-8")
    (source.parents[1] / "AGENTS.md").write_text("old instructions", encoding="utf-8")
    answers = iter([*(str(path) for path in destinations), "y", "N"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source)]) == 0
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (source.parents[1] / "config.yml").read_bytes() == (source / "config.yml").read_bytes()
    assert (source.parents[1] / "AGENTS.md").read_text(encoding="utf-8") == "old instructions"


def test_noninteractive_defaults_overwrite_existing_entries(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    home = tmp_path / "synthetic user"
    for name in ("config.yml", "AGENTS.md"):
        (source.parents[1] / name).write_text("old project entry", encoding="utf-8")
    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source), "--non-interactive"]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    assert (source.parents[1] / "config.yml").read_bytes() == (source / "config.yml").read_bytes()
    assert (source.parents[1] / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()


@pytest.mark.parametrize("kind", ["skills", "cac", "workflows"])
def test_replacement_cannot_delete_distribution_sources(distribution, tmp_path, monkeypatch, kind):
    backend, source, package, workflows, _ = distribution
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    option = {"skills": "--skills-root", "cac": "--cac-skills-root", "workflows": "--workflows-root"}[kind]
    target = workflows if kind == "workflows" else package.parent
    assert backend.main([*arguments(source, tmp_path), option, str(target)]) == 1
    assert {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()} == before
    assert calls == []


def test_replacement_cannot_delete_another_installation_root(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    shared = tmp_path / "installation"
    nested = shared / package.name
    nested.mkdir(parents=True)
    keep = nested / "keep.txt"
    keep.write_bytes(b"keep")
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main([*arguments(source, tmp_path), "--skills-root", str(shared),
                         "--cac-skills-root", str(nested)]) == 1
    assert keep.read_bytes() == b"keep" and calls == []


@pytest.mark.parametrize("name", ["config.yml", "AGENTS-code-root.md"])
def test_missing_project_template_fails_before_install(distribution, tmp_path, monkeypatch, name):
    backend, source, _, _, _ = distribution
    (source / name).unlink()
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(arguments(source, tmp_path)) == 1
    assert calls == []


def test_entry_symlink_cannot_overwrite_external_file(distribution, tmp_path, monkeypatch):
    backend, source, _, _, _ = distribution
    external = tmp_path / "outside.yml"
    external.write_text("keep external", encoding="utf-8")
    try:
        (source.parents[1] / "config.yml").symlink_to(external)
    except OSError:
        pytest.skip("Symbolic links unavailable")
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(arguments(source, tmp_path)) == 1
    assert calls == [] and external.read_text(encoding="utf-8") == "keep external"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
@pytest.mark.parametrize("explicit_roots", [False, True], ids=["backend-defaults", "explicit"])
def test_powershell_forwards_options_without_its_own_prompts(tmp_path, explicit_roots):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    capture = tmp_path / "arguments.json"
    recorder = tmp_path / "chosen python.ps1"
    recorder.write_text(
        "[System.IO.File]::WriteAllText($env:FACTUM_DEPLOY_TEST_CAPTURE, "
        "(ConvertTo-Json -InputObject @($args) -Compress))\nexit 0\n", encoding="utf-8")
    source = tmp_path / "source root"
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(KNOWLEDGE_ROOT / "deploy.ps1"), "-NonInteractive", "-Python", str(recorder),
               "-SourceRoot", str(source)]
    if explicit_roots:
        for flag, name in (("-SkillsRoot", "skills"), ("-CacSkillsRoot", "cac"),
                           ("-WorkflowsRoot", "workflows")):
            command += [flag, str(tmp_path / name)]
    result = subprocess.run(command, capture_output=True, timeout=30,
                            env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    received = json.loads(capture.read_text(encoding="utf-8"))
    assert Path(received[0]) == KNOWLEDGE_ROOT / "tools/deploy/deploy.py"
    assert received[received.index("--source-root") + 1] == str(source)
    assert received[received.index("--python") + 1] == str(recorder)
    assert "--non-interactive" in received
    for flag, name in (("--skills-root", "skills"), ("--cac-skills-root", "cac"),
                       ("--workflows-root", "workflows")):
        if explicit_roots:
            assert received[received.index(flag) + 1] == str(tmp_path / name)
        else:
            assert flag not in received


@pytest.mark.parametrize("kind", [
    pytest.param("sh", marks=pytest.mark.skipif(os.name != "posix", reason="POSIX wrapper")),
    pytest.param("powershell", marks=pytest.mark.skipif(os.name != "nt", reason="Windows wrapper")),
])
def test_wrapper_uses_shared_interaction_and_fixed_project_root(distribution, tmp_path, kind):
    _, source, package, _, _ = distribution
    project = source.parents[1]
    (project / "config.yml").write_text("keep project", encoding="utf-8")
    (project / "AGENTS.md").write_text("old instructions", encoding="utf-8")
    fake = tmp_path / "fake pip"
    fake.mkdir()
    (fake / "pip.py").write_text("# Synthetic pip substitute: no installation.\n", encoding="utf-8")
    backend = source / "tools/deploy/deploy.py"
    backend.parent.mkdir(parents=True)
    shutil.copyfile(KNOWLEDGE_ROOT / "tools/deploy/deploy.py", backend)
    wrapper_name = "deploy.sh" if kind == "sh" else "deploy.ps1"
    wrapper = source / wrapper_name
    shutil.copyfile(KNOWLEDGE_ROOT / wrapper_name, wrapper)
    if kind == "sh":
        command = ["sh", str(wrapper), "--python", sys.executable]
    else:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            pytest.skip("PowerShell unavailable")
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(wrapper), "-Python", sys.executable]
    destinations = [tmp_path / name for name in ("openflow skill", "cac skill", "openflow workflow")]
    result = subprocess.run(command, input="\n".join([*(str(path) for path in destinations), "n", "", ""]),
                            text=True, capture_output=True, timeout=30, cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(fake), "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    assert ".openflow" in result.stdout and ".cac" in result.stdout and "Y/n" in result.stdout
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep project"
    assert (project / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()
    assert not (project / ".git").exists()
