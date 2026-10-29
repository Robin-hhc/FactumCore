"""Exercise the Windows PowerShell entry with synthetic distribution assets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_deploy import make_source


ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "deploy.ps1"
POWERSHELL = shutil.which("powershell")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")


@pytest.fixture
def distribution(tmp_path):
    source = make_source(tmp_path / "distribution")
    backend = source / "tools/deploy/deploy.py"
    backend.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "tools/deploy/deploy.py", backend)
    shutil.copyfile(LAUNCHER, source / "deploy.ps1")
    return source


def invoke(source, *args, answers=None):
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCHER),
         "-SourceRoot", str(source), "-Python", sys.executable, *map(str, args)],
        input=answers, capture_output=True, text=True, encoding="utf-8-sig", timeout=40,
    )


def target_arguments(tmp_path):
    return ["-SkillsRoot", tmp_path / "skills [中文]", "-WorkflowsRoot", tmp_path / "workflow templates",
            "-ProjectRoot", tmp_path / "project 中文"]


def test_plan_uses_literal_unicode_paths_and_creates_no_destinations(distribution, tmp_path):
    arguments = target_arguments(tmp_path)
    result = invoke(distribution, *arguments, "-Plan", "-NonInteractive")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "planned"
    assert Path(report["targets"]["skills_root"]) == arguments[1]
    assert Path(report["targets"]["project_root"]) == arguments[5]
    assert report["environment"]["python"] == sys.executable
    assert report["environment"]["remote_checked"] is False
    assert not any(Path(arguments[index]).exists() for index in (1, 3, 5))


def test_default_source_root_is_the_launchers_own_directory(distribution, tmp_path):
    arguments = target_arguments(tmp_path)
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
         str(distribution / "deploy.ps1"), "-Python", sys.executable, "-Plan", "-NonInteractive", *map(str, arguments)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8-sig", timeout=40,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "planned"
    assert not any(Path(arguments[index]).exists() for index in (1, 3, 5))


def test_noninteractive_deploy_and_repeat_keep_business_bytes(distribution, tmp_path):
    arguments = target_arguments(tmp_path)
    first = invoke(distribution, *arguments, "-NonInteractive")
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["status"] == "deployed" and report["zip_count"] == 3
    project = Path(arguments[5])
    config = (project / "config.yml").read_bytes()
    agents = project / "AGENTS.md"
    agents.write_bytes(b"business-specific instructions\n")
    second = invoke(distribution, *arguments, "-NonInteractive")
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["write_count"] == 0
    assert agents.read_bytes() == b"business-specific instructions\n"
    assert (project / "config.yml").read_bytes() == config


def test_plan_and_dependency_installation_are_mutually_exclusive(distribution, tmp_path):
    arguments = target_arguments(tmp_path)
    result = invoke(distribution, *arguments, "-Plan", "-InstallDependencies", "-NonInteractive")
    assert result.returncode == 3
    assert "-Plan" in result.stderr and "-InstallDependencies" in result.stderr
    assert not any(Path(arguments[index]).exists() for index in (1, 3, 5))


def test_dependency_progress_on_stderr_keeps_a_successful_exit(distribution, tmp_path):
    # Dependency installers emit progress on stderr. No package installation is
    # needed to verify that PowerShell preserves the backend's actual exit code.
    backend = distribution / "tools/deploy/deploy.py"
    backend.write_text(
        "import sys\nprint('synthetic dependency progress', file=sys.stderr)\n"
        "print('{\"status\":\"deployed\"}')\n",
        encoding="utf-8",
    )
    result = invoke(distribution, *target_arguments(tmp_path), "-NonInteractive", "-InstallDependencies")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "deployed"
    assert "synthetic dependency progress" in result.stderr


def test_interactive_prompts_accept_three_paths(distribution, tmp_path):
    # The launcher must be allowed to use Read-Host in this process. Supply paths
    # through standard input rather than touching the real default installation.
    paths = [tmp_path / "interactive 技能", tmp_path / "interactive workflows", tmp_path / "interactive 项目"]
    command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCHER),
               "-SourceRoot", str(distribution), "-Python", sys.executable]
    result = subprocess.run(command, input="\n".join(map(str, paths)) + "\n", capture_output=True,
                            text=True, encoding="utf-8-sig", timeout=40)
    assert result.returncode == 0, result.stderr
    assert (paths[0] / "hs-knowledge-explore/SKILL.md").is_file()
    assert (paths[1] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (paths[2] / "config.yml").is_file()


def test_tilde_expansion_matches_current_profile_without_installing(distribution, tmp_path):
    # -Plan is essential: these defaults must never create actual host packages.
    result = invoke(distribution, "-Plan", "-NonInteractive", "-ProjectRoot", tmp_path / "unused-project",
                    "-SkillsRoot", "~/.openflow/config/skills", "-WorkflowsRoot", "~/.openflow/config/workflow-templates")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert Path(report["targets"]["skills_root"]) == Path.home() / ".openflow/config/skills"
    assert Path(report["targets"]["workflows_root"]) == Path.home() / ".openflow/config/workflow-templates"
    assert not (tmp_path / "unused-project").exists()
