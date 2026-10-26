"""Bootstrap public boundaries; never modifies the host Python environment."""

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("factum_install_environment", SCRIPTS / "install_environment.py")
environment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(environment)
sys.path.remove(str(SCRIPTS))


def test_runtime_union_uses_only_runtime_locks_and_normalizes_names(monkeypatch, tmp_path):
    monkeypatch.setattr(environment.catalog, "SKILLS", ("one", "two"))
    monkeypatch.setattr(environment.catalog, "package_files", lambda path: {
        "requirements.lock.txt": b"typing_extensions==4.13.2\n" if path.name == "one" else b"typing-extensions==4.13.2\nPyYAML==6.0.2\n",
        "requirements-dev.lock.txt": b"pytest==8.4.2\n",
    })
    assert environment.runtime_pins(tmp_path) == {"pyyaml": "6.0.2", "typing-extensions": "4.13.2"}


def test_conflicting_alias_locks_are_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(environment.catalog, "SKILLS", ("one", "two"))
    monkeypatch.setattr(environment.catalog, "package_files", lambda path: {
        "requirements.lock.txt": b"example_name==1.0\n" if path.name == "one" else b"example-name==2.0\n",
    })
    with pytest.raises(environment.catalog.InstallError, match="CONFLICTING_DEPENDENCY"):
        environment.runtime_pins(tmp_path)


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
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.yml").write_text("workspace_id: fixture\n", encoding="utf-8")
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
    monkeypatch.setattr(environment.catalog, "install", lambda *args: pytest.fail("must not publish"))
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
