"""Exercise the POSIX entry point without installing packages or touching a host."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX wrapper targets Linux")
WRAPPER = Path(__file__).resolve().parents[4] / "deploy.sh"


def recorder(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b'#!/bin/sh\nprintf "%s\\0" "$0" "$@" > "$FACTUM_DEPLOY_TEST_CAPTURE"\n'
        b'exit "${FACTUM_DEPLOY_TEST_EXIT:-0}"\n'
    )
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("selection", ["default", "environment", "flag", "equals"])
def test_posix_selects_python_and_forwards_paths_from_another_directory(tmp_path, selection):
    distribution = tmp_path / "distribution with spaces"
    distribution.mkdir()
    wrapper = distribution / "deploy.sh"
    shutil.copyfile(WRAPPER, wrapper)
    working = tmp_path / "other working directory"
    working.mkdir()
    capture = tmp_path / "arguments.bin"
    selected = recorder(tmp_path / "chosen python")
    default = recorder(tmp_path / "bin/python3")
    environment = dict(os.environ, FACTUM_DEPLOY_TEST_CAPTURE=str(capture),
                       PATH=str(default.parent) + os.pathsep + os.environ.get("PATH", ""))
    environment.pop("HIMATE_KNOWLEDGE_PYTHON", None)
    arguments = ["--source-root", str(tmp_path / "source root"),
                 "--skills-root", str(tmp_path / "skills root"),
                 "--workflows-root", str(tmp_path / "workflow root")]
    if selection == "environment":
        environment["HIMATE_KNOWLEDGE_PYTHON"] = str(selected)
    elif selection == "flag":
        arguments += ["--python", str(selected)]
        environment["HIMATE_KNOWLEDGE_PYTHON"] = str(default)
    elif selection == "equals":
        arguments += ["--python=" + str(selected)]
    else:
        selected = default

    result = subprocess.run(["sh", str(wrapper), *arguments], cwd=working, env=environment,
                            capture_output=True, timeout=30)

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    recorded = capture.read_bytes().decode("utf-8").split("\0")[:-1]
    assert Path(recorded[0]) == selected
    assert Path(recorded[1]) == distribution / "tools/deploy/deploy.py"
    assert recorded[2:] == arguments
    assert not (tmp_path / "skills root").exists()
    assert not (tmp_path / "workflow root").exists()


def test_posix_propagates_interpreter_failure(tmp_path):
    selected = recorder(tmp_path / "chosen python")
    result = subprocess.run(
        ["sh", str(WRAPPER), "--python", str(selected)],
        env=dict(os.environ, FACTUM_DEPLOY_TEST_CAPTURE=str(tmp_path / "arguments.bin"),
                 FACTUM_DEPLOY_TEST_EXIT="31"),
        capture_output=True, timeout=30,
    )
    assert result.returncode == 31


@pytest.mark.parametrize("argument", ["--python", "--python="])
def test_posix_rejects_missing_python_before_running_backend(tmp_path, argument):
    capture = tmp_path / "arguments.bin"
    selected = recorder(tmp_path / "chosen python")
    result = subprocess.run(
        ["sh", str(WRAPPER), argument],
        env=dict(os.environ, HIMATE_KNOWLEDGE_PYTHON=str(selected),
                 FACTUM_DEPLOY_TEST_CAPTURE=str(capture)),
        capture_output=True, timeout=30,
    )
    assert result.returncode == 2
    assert b"--python" in result.stderr
    assert not capture.exists()


def test_posix_help_reaches_shared_backend_without_deployment(tmp_path):
    result = subprocess.run(["sh", str(WRAPPER), "--python", sys.executable, "--help"],
                            cwd=tmp_path, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert b"--skills-root" in result.stdout and b"--workflows-root" in result.stdout
    assert not (tmp_path / ".openflow").exists()
