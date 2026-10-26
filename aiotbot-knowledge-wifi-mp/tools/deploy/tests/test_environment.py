"""Bootstrap public boundaries; never modifies the host Python environment."""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


REPOSITORY = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("factum_install_environment", SCRIPTS / "install_environment.py")
environment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(environment)
sys.path.remove(str(SCRIPTS))


def runtime_lock(source, text):
    path = source / "aiotbot-knowledge-wifi-mp/tools/deploy/requirements.runtime.lock.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def workspace(source):
    source.mkdir(parents=True, exist_ok=True)
    (source / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: fixture\nknowledge_roots:\n  wifi: aiotbot-knowledge-wifi-mp\n",
        encoding="utf-8",
    )
    lock = source / "aiotbot-knowledge-wifi-mp/governance/framework.lock.yaml"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"schema_version: '2.0'\n")
    return source


def test_runtime_lock_is_independent_of_capabilities_and_normalizes_names(monkeypatch, tmp_path):
    runtime_lock(tmp_path, "# Runtime only\n\ntyping_extensions==4.13.2\nPyYAML==6.0.2\n")
    monkeypatch.setattr(environment.catalog, "package_files", lambda path: pytest.fail("must not read Skills"))
    assert environment.runtime_pins(tmp_path) == {"pyyaml": "6.0.2", "typing-extensions": "4.13.2"}
    assert not (tmp_path / "skills").exists()
    assert not (tmp_path / "workflows").exists()


@pytest.mark.parametrize("second", ["example_name", "example-name", "Example.Name"])
def test_conflicting_alias_locks_are_rejected(tmp_path, second):
    runtime_lock(tmp_path, f"example_name==1.0\n{second}==2.0\n")
    with pytest.raises(environment.catalog.InstallError, match="CONFLICTING_DEPENDENCY"):
        environment.runtime_pins(tmp_path)


def test_missing_runtime_lock_never_reads_capability_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(environment.catalog, "package_files", lambda path: pytest.fail("must not discover Skills"))
    with pytest.raises(environment.catalog.InstallError, match="RUNTIME_LOCK"):
        environment.runtime_pins(tmp_path)


@pytest.mark.parametrize("text", ["PyYAML>=6.0\n", "--index-url https://example.invalid/simple\n", "PyYAML==6.0 ; python_version > '3'\n"])
def test_runtime_lock_requires_only_exact_pins(tmp_path, text):
    runtime_lock(tmp_path, text)
    with pytest.raises(environment.catalog.InstallError, match="INVALID_DEPENDENCY_LOCK"):
        environment.runtime_pins(tmp_path)


def test_empty_runtime_lock_is_not_a_successful_environment(tmp_path):
    runtime_lock(tmp_path, "# No runtime pins\n\n")
    with pytest.raises(environment.catalog.InstallError, match="EMPTY_RUNTIME_LOCK"):
        environment.runtime_pins(tmp_path)


def test_deployment_runtime_lock_matches_all_distributed_skill_runtime_pins():
    expected = {}
    for identity in environment.catalog.SKILLS:
        files = {"requirements.lock.txt": (REPOSITORY / "skills/common/knowledge" / identity / "requirements.lock.txt").read_bytes()}
        for name, version in environment.catalog.dependencies(files).items():
            normalized = re.sub(r"[-_.]+", "-", name).lower()
            assert normalized not in expected or expected[normalized] == version
            expected[normalized] = version
    assert environment.runtime_pins(REPOSITORY) == dict(sorted(expected.items()))
    assert "pytest" not in expected and "ruff" not in expected


def test_existing_install_is_preserved_before_any_subprocess(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "old installation"
    destination.mkdir()
    marker = destination / "keep"
    marker.write_bytes(b"user owned")
    monkeypatch.setattr(environment, "run", lambda *args: pytest.fail("must not execute"))
    with pytest.raises(environment.catalog.InstallError, match="DESTINATION_EXISTS"):
        environment.prepare(source, destination)
    assert marker.read_bytes() == b"user owned"
    assert list(destination.iterdir()) == [marker]


def test_failed_offline_dependency_install_never_publishes_catalog(monkeypatch, tmp_path):
    source = workspace(tmp_path / "source")
    wheels = tmp_path / "empty wheels"
    wheels.mkdir()
    destination = tmp_path / "failed installation"
    monkeypatch.setattr(environment, "runtime_pins", lambda source: {"pyyaml": "6.0.2"})
    monkeypatch.setattr(environment, "validate_pip_destination", lambda python: None)
    calls = []

    def failing_pip(command, label):
        calls.append(command)
        if "install" in command:
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(environment, "run", failing_pip)
    monkeypatch.setattr(environment.catalog, "install", lambda *args, **kwargs: pytest.fail("must not publish"))
    with pytest.raises(subprocess.CalledProcessError):
        environment.prepare(source, destination, wheelhouse=wheels)
    assert "--copies" in calls[0]
    assert "--no-index" in calls[1]
    assert calls[1][-2:] == ["--find-links", str(wheels)]
    assert "--only-binary=:all:" in calls[1]
    assert "--no-user" in calls[1]
    assert calls[1][calls[1].index("--prefix") + 1] == str(destination / "venv")
    assert not (destination / "capabilities").exists()
    assert not (destination / "installation.json").exists()


def mock_runtime_install(monkeypatch, source):
    runtime_lock(source, "PyYAML==6.0.2\n")
    monkeypatch.setattr(environment, "run", lambda *args: None)
    monkeypatch.setattr(environment, "validate_pip_destination", lambda python: None)
    monkeypatch.setattr(environment.catalog, "validate_interpreter", lambda *args: None)
    registry = {"schema_version": "2.0", "workspaces": [{"workspace_id": "fixture", "config_path": str(source / "config.yml"), "rules_digest": "a" * 64}]}
    calls = []

    def registration(config, python):
        calls.append((config, python))
        return {"fixture": {"config": str(config), "rules_digest": "a" * 64}}, registry

    monkeypatch.setattr(environment.catalog, "workspace_registration", registration)
    return calls, registry


def test_prepare_runtime_without_root_skills_or_workflows(monkeypatch, tmp_path):
    source = workspace(tmp_path / "business workspace")
    calls, registry = mock_runtime_install(monkeypatch, source)
    monkeypatch.setattr(environment.catalog, "install", lambda *args, **kwargs: pytest.fail("runtime preparation must not install capabilities"))
    destination = tmp_path / "private runtime"
    report = environment.prepare(source, destination)
    assert report["status"] == "runtime_ready"
    assert all(report[name] is None for name in ("catalog", "skills", "workflows"))
    assert report["runtime_packages"] == {"pyyaml": "6.0.2"}
    assert json.loads(Path(report["workspace_registry"]).read_text(encoding="utf-8")) == registry
    assert calls[0][0] == source / "config.yml"
    assert (destination / "installation.json").is_file()
    assert not (source / "skills").exists() and not (source / "workflows").exists()
    assert not (destination / "capabilities").exists()


def test_prepare_registers_explicit_agent_directories_without_recopying(monkeypatch, tmp_path):
    source = workspace(tmp_path / "business workspace")
    mock_runtime_install(monkeypatch, source)
    skills = tmp_path / "agent-one" / "skills"
    workflows = tmp_path / "agent-two" / "workflows"
    skills.mkdir(parents=True)
    workflows.mkdir(parents=True)
    calls = []

    def register(source_root, destination, python, config, **kwargs):
        calls.append((source_root, destination, python, config, kwargs))
        destination.mkdir(parents=True)
        catalog = destination / "catalog.json"
        catalog.write_text("{}", encoding="utf-8")
        return catalog

    monkeypatch.setattr(environment.catalog, "install", register)
    report = environment.prepare(source, tmp_path / "private runtime", skills_root=skills, workflows_root=workflows)
    assert report["status"] == "installed"
    assert report["skills"] == str(skills) and report["workflows"] == str(workflows)
    assert Path(report["catalog"]).is_file()
    assert len(calls) == 1
    assert calls[0][4] == {"skills_root": skills, "workflows_root": workflows, "register_existing": True}


@pytest.mark.parametrize("provided", ["skills_root", "workflows_root"])
def test_prepare_requires_both_agent_directories_before_creating_environment(monkeypatch, tmp_path, provided):
    source = workspace(tmp_path / "source")
    directory = tmp_path / "agent"
    directory.mkdir()
    monkeypatch.setattr(environment, "run", lambda *args: pytest.fail("must not create environment"))
    destination = tmp_path / "uncreated runtime"
    with pytest.raises(environment.catalog.InstallError, match="(?:ROOTS|BOTH|paired)"):
        environment.prepare(source, destination, **{provided: directory})
    assert not destination.exists()


def test_registration_failure_never_publishes_a_successful_installation(monkeypatch, tmp_path):
    source = workspace(tmp_path / "business workspace")
    mock_runtime_install(monkeypatch, source)
    skills, workflows = tmp_path / "agent skills", tmp_path / "agent workflows"
    skills.mkdir()
    workflows.mkdir()

    def fail_registration(*args, **kwargs):
        raise environment.catalog.InstallError("CAPABILITY_CHANGED_DURING_REGISTRATION")

    monkeypatch.setattr(environment.catalog, "install", fail_registration)
    destination = tmp_path / "failed runtime"
    with pytest.raises(environment.catalog.InstallError, match="CAPABILITY_CHANGED"):
        environment.prepare(source, destination, skills_root=skills, workflows_root=workflows)
    assert destination.is_dir()  # Keep diagnostics and the prepared environment for inspection.
    assert (destination / "requirements.runtime.lock.txt").is_file()
    assert not (destination / "installation.json").exists()
    assert not (destination / "workspace-registry.json").exists()
    assert not (destination / "registration/catalog.json").exists()


@pytest.mark.parametrize("platform", ["powershell", "bash"])
def test_platform_entry_forwards_external_paths_from_another_directory(tmp_path, platform):
    if platform == "powershell":
        if sys.platform != "win32":
            pytest.skip("PowerShell entry is verified on Windows")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            pytest.skip("PowerShell is unavailable")
        filename = "install.ps1"
    else:
        shell = os.environ.get("FACTUM_POSIX_SHELL")
        if not shell and sys.platform != "win32":
            shell = shutil.which("bash")
        if not shell:
            pytest.skip("set FACTUM_POSIX_SHELL to an actual Bash for this platform")
        filename = "install.sh"
    repository = tmp_path / "deployment repo"
    tools = repository / "aiotbot-knowledge-wifi-mp/tools/deploy"
    tools.mkdir(parents=True)
    wrapper = tools / filename
    shutil.copyfile(SCRIPTS / filename, wrapper)
    captured = tmp_path / "captured arguments.json"
    (tools / "install_environment.py").write_text(
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(captured)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'cwd': str(pathlib.Path.cwd())}}), encoding='utf-8')\n"
        "raise SystemExit(17)\n",
        encoding="utf-8",
    )
    invocation = tmp_path / "operator cwd"
    invocation.mkdir()
    arguments = {
        "--destination": "../private runtime",
        "--wheelhouse": "../offline wheels",
        "--skills-root": "../agent skills",
        "--workflows-root": "../agent workflows",
    }
    if platform == "powershell":
        command = [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper), "-Python", sys.executable]
        names = {"--destination": "-Destination", "--wheelhouse": "-Wheelhouse", "--skills-root": "-SkillsRoot", "--workflows-root": "-WorkflowsRoot"}
        command += [item for key, value in arguments.items() for item in (names[key], value)]
    else:
        command = [shell, str(wrapper), "--python", sys.executable]
        command += [item for key, value in arguments.items() for item in (key, value)]
    result = subprocess.run(command, cwd=invocation, capture_output=True, timeout=30)
    assert result.returncode == 17, (result.stdout, result.stderr)
    data = json.loads(captured.read_text(encoding="utf-8"))
    assert Path(data["cwd"]) == invocation
    argv = data["argv"]
    assert Path(argv[argv.index("--source-root") + 1]).resolve() == repository.resolve()
    assert {key: argv[argv.index(key) + 1] for key in arguments} == arguments


def test_wrong_python_fails_before_creating_destination(monkeypatch, tmp_path):
    monkeypatch.setattr(environment.sys, "version_info", (3, 9, 0))
    destination = tmp_path / "uncreated"
    with pytest.raises(environment.catalog.InstallError, match="PYTHON_VERSION"):
        environment.prepare(tmp_path, destination)
    assert not destination.exists()


@pytest.mark.parametrize("name", ["PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_PYTHON"])
def test_environment_cannot_redirect_installation(monkeypatch, tmp_path, name):
    protected = tmp_path / "protected"
    protected.mkdir()
    marker = protected / "keep"
    marker.write_bytes(b"unchanged")
    monkeypatch.setenv(name, str(protected))
    monkeypatch.setattr(environment, "run", lambda *args: pytest.fail("must not execute"))
    destination = tmp_path / "uncreated"
    with pytest.raises(environment.catalog.InstallError, match="PIP_DESTINATION_OVERRIDE"):
        environment.prepare(tmp_path, destination)
    assert not destination.exists()
    assert list(protected.iterdir()) == [marker]
    assert marker.read_bytes() == b"unchanged"


@pytest.mark.parametrize("key", ["global.target", "install.prefix", "global.root", "global.python"])
def test_pip_config_cannot_redirect_installation(monkeypatch, key):
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, stdout=f"{key}='/protected/path'\n", stderr="",
    ))
    with pytest.raises(environment.catalog.InstallError, match="PIP_DESTINATION_OVERRIDE"):
        environment.validate_pip_destination(Path("private-python"))


def test_company_index_and_auth_settings_are_preserved(monkeypatch):
    monkeypatch.setattr(environment.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, stdout="global.index-url='https://private.example/simple'\nglobal.cert='/private/ca.pem'\n", stderr="",
    ))
    environment.validate_pip_destination(Path("private-python"))


@pytest.mark.parametrize("index", ["ftp://example.internal/simple", "https://user:secret@example.internal/simple"])
def test_invalid_or_inline_authenticated_index_fails_early(monkeypatch, tmp_path, index):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "uncreated"
    with pytest.raises(environment.catalog.InstallError, match="INDEX_"):
        environment.prepare(source, destination, index_url=index)
    assert not destination.exists()
