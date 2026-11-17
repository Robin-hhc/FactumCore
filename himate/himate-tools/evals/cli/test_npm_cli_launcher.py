"""Exercise an offline npm release without installing Python dependencies."""

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


@pytest.fixture(scope="module")
def npm_release(tmp_path_factory):
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        pytest.skip("Node.js and npm are required to install the release fixture")
    workspace = tmp_path_factory.mktemp("npm-release")
    prefix = workspace / "prefix"
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("NPM_CONFIG_") and key.upper() not in {"NODE_OPTIONS", "NODE_PATH"}}
    for scope in ("USERCONFIG", "GLOBALCONFIG"):
        config = workspace / f"{scope.lower()}.npmrc"
        config.touch()
        environment[f"NPM_CONFIG_{scope}"] = str(config)
    environment["NPM_CONFIG_CACHE"] = str(workspace / "cache")
    subprocess.run([npm, "pack", "--offline", "--ignore-scripts", "--pack-destination", str(workspace)],
                   cwd=SOURCE, env=environment, check=True, capture_output=True, timeout=60)
    archive, = workspace.glob("*.tgz")
    subprocess.run([npm, "install", "--global", "--offline", "--ignore-scripts", "--prefix", str(prefix), str(archive)],
                   cwd=workspace, env=environment, check=True, capture_output=True, timeout=60)
    global_modules = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules")
    return Path(node), prefix, global_modules / "@himate/knowledge-cli"


@pytest.fixture
def launcher(tmp_path, npm_release):
    node, prefix, package = npm_release
    account = tmp_path / "profile & tools ! 资料"
    account.mkdir()
    directory = account / ".himate/knowledge"
    managed = directory / ".venv"
    bin_dir = tmp_path / "registered & commands 资料"
    shim_dir = prefix if os.name == "nt" else prefix / "bin"
    shim = shim_dir / ("knowledge.cmd" if os.name == "nt" else "knowledge")
    environment = dict(os.environ)
    environment["USERPROFILE" if os.name == "nt" else "HOME"] = str(account)
    for key in ("HIMATE_KNOWLEDGE_PYTHON", "NODE_OPTIONS", "NODE_PATH"):
        environment.pop(key, None)
    # Run the installed package's lifecycle entry explicitly so this fixture is
    # independent of npm's version-specific script approval policies.
    result = subprocess.run([str(node), str(package / "scripts/install.js")], cwd=tmp_path, env=environment,
                            capture_output=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, (result.stdout, result.stderr)

    def run(*arguments, override=None, search_path=None, via_shim=False):
        env = dict(environment)
        env["PATH"] = str(search_path if search_path is not None else tmp_path / "empty-path")
        if via_shim:
            command = [str(shim)]
            env["PATH"] = os.pathsep.join((str(shim_dir), str(node.parent), env["PATH"]))
        else:
            command = [str(node), str(package / "bin/knowledge.js")]
        if override is not None:
            env["HIMATE_KNOWLEDGE_PYTHON"] = str(override)
        return subprocess.run([*command, *arguments], cwd=tmp_path, env=env,
                              capture_output=True, encoding="utf-8", timeout=30)

    def doctor(**options):
        result = run("doctor", "--environment-only", "--bin-dir", str(bin_dir), "--json", **options)
        assert result.returncode == 0, (result.stdout, result.stderr)
        return json.loads(result.stdout)

    return directory, managed, run, doctor


def test_npm_cli_has_one_public_shim_and_one_runtime_entrypoint(npm_release, launcher):
    _, prefix, package = npm_release
    tool, _, run, _ = launcher
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    assert metadata["bin"] == {"knowledge": "bin/knowledge.js"}
    shim_dir = prefix if os.name == "nt" else prefix / "bin"
    assert not list(shim_dir.glob("himate-knowledge*"))
    for retired in ("knowledge.cmd", "knowledge.sh"):
        assert not (package / retired).exists()
        assert not (tool / retired).exists()
    manifest = json.loads((tool / "runtime/manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["entrypoints"]) == {"knowledge.py"}
    result = run("--version", override=BASE_PYTHON, via_shim=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout.strip() == f"knowledge {metadata['version']}"


def test_npm_cli_uses_account_environment_without_system_python_on_path(launcher, tmp_path):
    _, managed, _, doctor = launcher
    expected = venv(managed)
    external = venv(tmp_path / "explicit project environment")

    assert Path(doctor()["python"]) == expected
    assert Path(doctor(override=BASE_PYTHON)["python"]) == expected
    assert Path(doctor(override=external)["python"]) == external


def test_npm_cli_uses_path_venv_only_as_base_bootstrap(launcher, tmp_path):
    _, managed, _, doctor = launcher
    discovered = venv(tmp_path / "activated project env")

    report = doctor(search_path=discovered.parent)

    assert report["python"] is None
    assert report["diagnostics"][0]["code"] == "VENV_REQUIRED"
    assert Path(report["bootstrap_python"]) != discovered
    assert not managed.exists()


def test_npm_cli_rejects_linked_default_environment(launcher, tmp_path):
    _, managed, run, doctor = launcher
    external = tmp_path / "other project env"
    executable = venv(external)
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
    # With an available system Python the launcher reports the missing environment.
    # Otherwise the linked directory cannot bootstrap the CLI at all.
    if result.returncode == 0:
        assert json.loads(result.stdout)["python"] is None
    else:
        assert result.returncode == 1 and "No supported Python found" in result.stderr


def test_npm_cli_propagates_error_status_and_json(launcher):
    _, _, run, _ = launcher

    result = run("setup", "--json", "--jsonl", override=BASE_PYTHON)

    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ARGUMENT"


def test_npm_cli_skips_configured_python_39(launcher):
    _, managed, _, doctor = launcher
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
