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
    legacy = directory / ".venv"
    bin_dir = tmp_path / "registered & commands 资料"
    shim_dir = prefix if os.name == "nt" else prefix / "bin"
    shim = shim_dir / ("knowledge.cmd" if os.name == "nt" else "knowledge")
    environment = dict(os.environ)
    environment["USERPROFILE" if os.name == "nt" else "HOME"] = str(account)
    if os.name == "nt":
        environment["APPDATA"] = str(account / "AppData/Roaming")
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

    return directory, legacy, run, doctor, environment


def test_npm_cli_has_one_public_shim_and_one_runtime_entrypoint(npm_release, launcher):
    _, prefix, package = npm_release
    tool, _, run, _, _ = launcher
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


def test_npm_cli_uses_explicit_python_even_with_legacy_environment(launcher, tmp_path):
    _, legacy, _, doctor, _ = launcher
    venv(legacy)
    external = venv(tmp_path / "explicit project environment")

    assert Path(doctor(override=BASE_PYTHON)["python"]) == BASE_PYTHON
    assert Path(doctor(override=external)["python"]) == external
    assert (legacy / "pyvenv.cfg").is_file()


def test_npm_cli_uses_path_python_without_creating_an_environment(launcher, tmp_path):
    _, legacy, _, doctor, _ = launcher
    discovered = venv(tmp_path / "activated project env")

    report = doctor(search_path=discovered.parent)

    assert report["python_version"].split(".")[:2] in [["3", "10"], ["3", "11"], ["3", "12"]]
    if os.name != "nt":
        assert Path(report["python"]).parent == discovered.parent
    assert not legacy.exists()


def test_npm_cli_leaves_linked_legacy_environment_alone(launcher, tmp_path):
    _, legacy, run, doctor, _ = launcher
    external = tmp_path / "other project env"
    executable = venv(external)
    if os.name == "nt":
        from _winapi import CreateJunction

        CreateJunction(str(external), str(legacy))
    else:
        legacy.symlink_to(external, target_is_directory=True)

    report = doctor(override=BASE_PYTHON)

    assert Path(report["python"]) == BASE_PYTHON
    # Explicit reuse of the target environment stays supported.
    assert Path(doctor(override=executable)["python"]) == executable
    result = run("doctor", "--environment-only", "--json")
    if result.returncode == 0:
        assert Path(json.loads(result.stdout)["python"]) != legacy / PYTHON_IN_VENV
    else:
        assert result.returncode == 1 and "No supported Python found" in result.stderr
    assert (legacy / "pyvenv.cfg").is_file()


def test_npm_cli_reads_selected_pythons_user_site(launcher):
    _, _, _, doctor, environment = launcher
    probe = subprocess.run([str(BASE_PYTHON), "-E", "-B", "-X", "utf8", "-c",
                            "import site; print(site.getusersitepackages() if site.ENABLE_USER_SITE else '')"],
                           env=environment, capture_output=True, encoding="utf-8", check=True, timeout=30)
    if not probe.stdout.strip():
        pytest.skip("The selected base Python disables the user site")
    site = Path(probe.stdout.strip())
    account = Path(environment["USERPROFILE" if os.name == "nt" else "HOME"])
    assert site.is_relative_to(account)
    requirements = (SOURCE / "runtime/requirements.lock.txt").read_text(encoding="utf-8").splitlines()
    expected = next(line.split("==", 1)[1] for line in requirements if line.casefold().startswith("pyyaml=="))
    installed = site / f"pyyaml-{expected}.dist-info"
    installed.mkdir(parents=True)
    (installed / "METADATA").write_text(f"Name: PyYAML\nVersion: {expected}\n", encoding="utf-8")

    report = doctor(override=BASE_PYTHON)

    dependency = next(item for item in report["dependencies"] if item["name"].casefold() == "pyyaml")
    assert dependency["actual"] == expected and dependency["status"] == "ready"


def test_npm_cli_propagates_error_status_and_json(launcher):
    _, _, run, _, _ = launcher

    result = run("setup", "--json", "--jsonl", override=BASE_PYTHON)

    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ARGUMENT"


def test_npm_cli_skips_configured_python_39(launcher):
    _, _, _, doctor, _ = launcher
    old_python = shutil.which("python3.9")
    if not old_python and os.name == "nt" and shutil.which("py"):
        installed = subprocess.run(["py", "-3.9", "-I", "-c", "import sys; print(sys.executable)"],
                                   capture_output=True, encoding="utf-8", timeout=10)
        if installed.returncode == 0:
            old_python = installed.stdout.strip()
    if not old_python:
        pytest.skip("Python 3.9 is not installed on this host")

    report = doctor(override=old_python, search_path=BASE_PYTHON.parent)

    assert Path(report["python"]) != Path(old_python)
    assert report["python_version"].split(".")[:2] in [["3", "10"], ["3", "11"], ["3", "12"]]
