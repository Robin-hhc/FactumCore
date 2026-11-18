"""Isolated deployment of Skill and Workflow packages without environment setup."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


CAPABILITIES_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def distribution(tmp_path):
    spec = importlib.util.spec_from_file_location("skill_deploy", CAPABILITIES_ROOT / "scripts/deploy.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    source = tmp_path / "capabilities with spaces" / "custom" / "nested" / "package-root"
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
    assert not (source.parents[2] / ".git").exists()
    return backend, source, package, workflows


def arguments(source, tmp_path):
    return ["--source-root", str(source),
            "--skills-root", str(tmp_path / "installed skills"),
            "--cac-skills-root", str(tmp_path / "cac skills"),
            "--workflows-root", str(tmp_path / "workflow templates"), "--non-interactive"]


def test_copy_all_destinations_without_environment_setup(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows = distribution
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

    def reject_process(*args, **kwargs):
        pytest.fail("Capability deployment must complete without invoking CLI, pip or model installers")

    monkeypatch.setattr(subprocess, "run", reject_process)
    assert backend.main(arguments(source, tmp_path)) == 0
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
    assert all(not (parent / name).exists() for parent in (source, *source.parents)
               if parent.is_relative_to(tmp_path)
               for name in ("config.yml", "AGENTS.md", "artifacts", "runtime", "knowledge.py"))


@pytest.mark.parametrize("option", ["--capabilities-root", "--source-root"])
def test_install_reads_explicit_capability_package(distribution, tmp_path, option):
    backend, source, package, _ = distribution
    capabilities = tmp_path / "shared capabilities"
    capabilities.mkdir()
    for name in ("skills", "workflows"):
        (source / name).rename(capabilities / name)
    options = arguments(source, tmp_path)
    options[:2] = [option, str(capabilities)]

    assert backend.main(options) == 0
    for directory in ("installed skills", "cac skills"):
        installed = tmp_path / directory / package.name / "SKILL.md"
        assert installed.read_bytes() == (capabilities / "skills" / package.name / "SKILL.md").read_bytes()
    workflow = "hs-knowledge-ingest/workflow.yaml"
    installed = tmp_path / "workflow templates" / workflow
    assert installed.read_bytes() == (capabilities / "workflows" / workflow).read_bytes()


def test_explicit_install_preserves_capability_sources(distribution, tmp_path):
    backend, source, package, _ = distribution
    capabilities = tmp_path / "shared capabilities"
    capabilities.mkdir()
    for name in ("skills", "workflows"):
        (source / name).rename(capabilities / name)
    skill = capabilities / "skills" / package.name / "SKILL.md"
    before = skill.read_bytes()
    options = arguments(source, tmp_path)
    options[:2] = ["--capabilities-root", str(capabilities)]

    assert backend.main([*options, "--skills-root", str(skill.parent.parent)]) == 1
    assert skill.read_bytes() == before


@pytest.mark.parametrize("option", ["--knowledge-root", "--download-models", "--skip-ocr"])
def test_environment_options_are_rejected_before_replacing_packages(distribution, tmp_path, option):
    backend, source, package, _ = distribution
    old = tmp_path / "installed skills" / package.name / "SKILL.md"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old installed package")

    with pytest.raises(SystemExit) as error:
        backend.main([*arguments(source, tmp_path), option])
    assert error.value.code == 2
    assert old.read_bytes() == b"old installed package"
    assert not (tmp_path / "workflow templates").exists()


def test_interactive_defaults_show_three_installation_roots(distribution, tmp_path, monkeypatch):
    backend, source, package, _ = distribution
    home = tmp_path / "synthetic user"
    project = source.parents[1]
    (project / "config.yml").write_text("keep config", encoding="utf-8")
    (project / "AGENTS.md").write_text("keep instructions", encoding="utf-8")
    answers, prompts = iter(["", "", ""]), []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("builtins.input", answer)
    assert backend.main(["--source-root", str(source)]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    assert len(prompts) == 3
    for prompt, relative in zip(prompts, (".openflow/config/skills", ".cac/skills",
                                          ".openflow/config/workflow-templates")):
        assert str(home / relative) in prompt
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep config"
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "keep instructions"


def test_interactive_custom_directories(distribution, tmp_path, monkeypatch):
    backend, source, package, _ = distribution
    destinations = [tmp_path / name for name in ("custom openflow", "custom cac", "custom workflow")]
    answers = iter(map(str, destinations))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert backend.main(["--source-root", str(source)]) == 0
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()


def test_noninteractive_defaults_keep_existing_entries(distribution, tmp_path, monkeypatch):
    backend, source, package, _ = distribution
    home = tmp_path / "synthetic user"
    for name in ("config.yml", "AGENTS.md"):
        (source.parents[1] / name).write_text("old project entry", encoding="utf-8")
    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    assert backend.main(["--source-root", str(source), "--non-interactive"]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    for name in ("config.yml", "AGENTS.md"):
        assert (source.parents[1] / name).read_text(encoding="utf-8") == "old project entry"


@pytest.mark.parametrize("kind", ["skills", "cac", "workflows"])
def test_replacement_cannot_delete_distribution_sources(distribution, tmp_path, monkeypatch, kind):
    backend, source, package, workflows = distribution
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    option = {"skills": "--skills-root", "cac": "--cac-skills-root", "workflows": "--workflows-root"}[kind]
    target = workflows if kind == "workflows" else package.parent
    assert backend.main([*arguments(source, tmp_path), option, str(target)]) == 1
    assert {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()} == before


def test_replacement_cannot_delete_another_installation_root(distribution, tmp_path, monkeypatch):
    backend, source, package, _ = distribution
    shared = tmp_path / "installation"
    nested = shared / package.name
    nested.mkdir(parents=True)
    keep = nested / "keep.txt"
    keep.write_bytes(b"keep")
    assert backend.main([*arguments(source, tmp_path), "--skills-root", str(shared),
                         "--cac-skills-root", str(nested)]) == 1
    assert keep.read_bytes() == b"keep"


def test_install_does_not_follow_ancestor_config_link(distribution, tmp_path, monkeypatch):
    backend, source, _, _ = distribution
    external = tmp_path / "outside.yml"
    external.write_text("keep external", encoding="utf-8")
    try:
        (source.parents[1] / "config.yml").symlink_to(external)
    except OSError:
        pytest.skip("Symbolic links unavailable")
    assert backend.main(arguments(source, tmp_path)) == 0
    assert external.read_text(encoding="utf-8") == "keep external"


@pytest.mark.parametrize("kind", ["skills", "cac", "workflows"])
def test_replacement_rejects_linked_package_target(distribution, tmp_path, kind):
    backend, source, package, _ = distribution
    outside = tmp_path / "outside"
    outside.mkdir()
    keep = outside / "keep.txt"
    keep.write_bytes(b"keep outside")
    directory = {"skills": "installed skills", "cac": "cac skills", "workflows": "workflow templates"}[kind]
    name = "hs-knowledge-ingest" if kind == "workflows" else package.name
    target = tmp_path / directory / name
    target.parent.mkdir()
    try:
        target.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links unavailable")

    assert backend.main(arguments(source, tmp_path)) == 1
    assert keep.read_bytes() == b"keep outside"
    assert target.is_symlink()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
@pytest.mark.parametrize("source_flag", [None, "-CapabilitiesRoot", "-SourceRoot"])
def test_powershell_forwards_options_without_its_own_prompts(tmp_path, source_flag):
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
               str(CAPABILITIES_ROOT / "deploy.ps1"), "-NonInteractive", "-Python", str(recorder)]
    if source_flag:
        command += [source_flag, str(source)]
        for flag, name in (("-SkillsRoot", "skills"), ("-CacSkillsRoot", "cac"),
                           ("-WorkflowsRoot", "workflows")):
            command += [flag, str(tmp_path / name)]
    result = subprocess.run(command, capture_output=True, timeout=30,
                            env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    received = json.loads(capture.read_text(encoding="utf-8"))
    assert Path(received[0]) == CAPABILITIES_ROOT / "scripts/deploy.py"
    if source_flag:
        assert received[received.index("--capabilities-root") + 1] == str(source)
    else:
        assert "--capabilities-root" not in received
    assert "--python" not in received
    assert "--non-interactive" in received
    for flag, name in (("--skills-root", "skills"), ("--cac-skills-root", "cac"),
                       ("--workflows-root", "workflows")):
        if source_flag:
            assert received[received.index(flag) + 1] == str(tmp_path / name)
        else:
            assert flag not in received


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
@pytest.mark.parametrize("option", ["-KnowledgeRoot", "-DownloadModels", "-SkipOcr"])
def test_powershell_rejects_environment_options_without_starting_python(tmp_path, option):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    capture = tmp_path / "python-started.txt"
    recorder = tmp_path / "chosen python.ps1"
    recorder.write_text(
        "[System.IO.File]::WriteAllText($env:FACTUM_DEPLOY_TEST_CAPTURE, 'started')\nexit 0\n",
        encoding="utf-8")
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(CAPABILITIES_ROOT / "deploy.ps1"), "-NonInteractive", "-Python", str(recorder), option],
        capture_output=True, timeout=30,
        env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode != 0
    assert option.lstrip("-").encode() in result.stderr
    assert not capture.exists()


@pytest.mark.parametrize("kind", [
    pytest.param("sh", marks=pytest.mark.skipif(os.name != "posix", reason="POSIX wrapper")),
    pytest.param("powershell", marks=pytest.mark.skipif(os.name != "nt", reason="Windows wrapper")),
])
def test_wrapper_installs_capabilities_with_only_the_standard_library(distribution, tmp_path, kind):
    _, source, package, _ = distribution
    project = tmp_path / "data root"
    project.mkdir()
    (project / "config.yml").write_text("keep project", encoding="utf-8")
    (project / "AGENTS.md").write_text("old instructions", encoding="utf-8")
    backend = source / "scripts/deploy.py"
    backend.parent.mkdir(parents=True)
    shutil.copyfile(CAPABILITIES_ROOT / "scripts/deploy.py", backend)
    wrapper_name = "deploy.sh" if kind == "sh" else "deploy.ps1"
    wrapper = source / wrapper_name
    shutil.copyfile(CAPABILITIES_ROOT / wrapper_name, wrapper)
    if kind == "sh":
        command = ["sh", str(wrapper), "--python", sys.executable]
    else:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            pytest.skip("PowerShell unavailable")
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(wrapper), "-Python", sys.executable]
    destinations = [tmp_path / name for name in ("openflow skill", "cac skill", "openflow workflow")]
    result = subprocess.run(command, input="\n".join([*(str(path) for path in destinations), ""]),
                            text=True, capture_output=True, timeout=30, cwd=tmp_path,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    assert ".openflow" in result.stdout and ".cac" in result.stdout and "Overwrite" not in result.stdout
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep project"
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "old instructions"
    assert not (project / ".git").exists()
    assert not (project / "artifacts").exists()
    assert not (source / "runtime").exists()
    assert not (source / "knowledge.py").exists()
