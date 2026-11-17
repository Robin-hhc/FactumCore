"""Exercise the packaged native wrappers without installing dependencies."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[2]
BASE_PYTHON = Path(sys._base_executable)
PYTHON_IN_VENV = Path("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv(directory):
    subprocess.run([str(BASE_PYTHON), "-I", "-m", "venv", "--without-pip", str(directory)],
                   check=True, capture_output=True, timeout=30)
    return directory / PYTHON_IN_VENV


@pytest.fixture
def wrapper(tmp_path):
    account = tmp_path / "profile & tools ! 资料"
    directory = tmp_path / "source & scripts ! 资料"
    directory.mkdir()
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        shutil.copyfile(SOURCE / name, directory / name)
    shutil.copytree(SOURCE / "runtime", directory / "runtime")
    managed = account / ".himate/knowledge/.venv"
    bin_dir = tmp_path / "registered & commands 资料"
    command = [str(directory / "knowledge.cmd")] if os.name == "nt" else ["/bin/sh", str(directory / "knowledge.sh")]

    def run(*arguments, override=None, search_path=None):
        env = dict(os.environ)
        # Scope the account directory and PATH to the subprocess under test.
        env["USERPROFILE" if os.name == "nt" else "HOME"] = str(account)
        env["PATH"] = str(search_path if search_path is not None else tmp_path / "empty-path")
        env.pop("HIMATE_KNOWLEDGE_PYTHON", None)
        if override is not None:
            env["HIMATE_KNOWLEDGE_PYTHON"] = str(override)
        return subprocess.run([*command, *arguments], cwd=tmp_path, env=env,
                              capture_output=True, encoding="utf-8", timeout=30)

    def doctor(**options):
        result = run("doctor", "--environment-only", "--bin-dir", str(bin_dir), "--json", **options)
        assert result.returncode == 0, (result.stdout, result.stderr)
        return json.loads(result.stdout)

    return directory, managed, run, doctor


def test_wrappers_use_account_environment_without_system_python_on_path(wrapper):
    tool, managed, _, doctor = wrapper
    adjacent = venv(tool / ".venv")
    expected = venv(managed)

    assert Path(doctor()["python"]) == expected
    assert Path(doctor(override=BASE_PYTHON)["python"]) == expected
    assert Path(doctor(override=adjacent)["python"]) == adjacent


def test_wrappers_use_path_venv_only_as_base_bootstrap(wrapper, tmp_path):
    tool, managed, _, doctor = wrapper
    venv(tool / ".venv")
    discovered = venv(tmp_path / "activated project env")

    report = doctor(search_path=discovered.parent)

    assert report["python"] is None
    assert report["diagnostics"][0]["code"] == "VENV_REQUIRED"
    assert Path(report["bootstrap_python"]) != discovered
    assert not managed.exists()


def test_wrappers_reject_linked_default_environment(wrapper, tmp_path):
    _, managed, run, doctor = wrapper
    external = tmp_path / "other project env"
    executable = venv(external)
    managed.parent.mkdir(parents=True)
    if os.name == "nt":
        from _winapi import CreateJunction

        CreateJunction(str(external), str(managed))
    else:
        managed.symlink_to(external, target_is_directory=True)

    report = doctor(override=BASE_PYTHON)

    assert report["python"] is None and report["diagnostics"][0]["code"] == "VENV_REQUIRED"
    # Explicit reuse of the target environment stays supported.
    assert Path(doctor(override=executable)["python"]) == executable
    result = run("doctor", "--environment-only", "--json")
    # With an available system Python the wrapper reports the missing environment.
    # Otherwise the linked directory cannot bootstrap the CLI at all.
    if result.returncode == 0:
        assert json.loads(result.stdout)["python"] is None
    else:
        assert result.returncode == 3 and "requires" in result.stderr


def test_wrappers_propagate_cli_error_status_and_json(wrapper):
    _, _, run, _ = wrapper

    result = run("setup", "--json", "--jsonl", override=BASE_PYTHON)

    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ARGUMENT"


def test_wrappers_skip_configured_python_39(wrapper):
    _, managed, _, doctor = wrapper
    old_python = shutil.which("python3.9")
    if not old_python and os.name == "nt" and shutil.which("py"):
        installed = subprocess.run(["py", "-3.9", "-I", "-c", "import sys; print(sys.executable)"],
                                   capture_output=True, encoding="utf-8", timeout=10)
        if installed.returncode == 0:
            old_python = installed.stdout.strip()
    if not old_python:
        pytest.skip("Python 3.9 is not installed on this host")

    expected = venv(managed)

    assert Path(doctor(override=old_python)["python"]) == expected
