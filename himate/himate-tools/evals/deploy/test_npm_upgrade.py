"""Exercise the npm postinstall replacement against existing user state."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]


def test_npm_postinstall_preserves_managed_environment_and_logs(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the npm postinstall test")

    home = tmp_path / "profile with spaces"
    installed = home / ".himate/knowledge"
    previous_runtime = installed / "runtime/obsolete.py"
    environment_config = installed / ".venv/pyvenv.cfg"
    install_log = installed / "logs/setup.log"
    for target, contents in (
        (previous_runtime, b"previous runtime"),
        (environment_config, b"previous virtual environment"),
        (install_log, b"previous setup diagnostics"),
    ):
        target.parent.mkdir(parents=True)
        target.write_bytes(contents)

    marker = installed / ".install.json"
    marker.write_text('{"package":"@himate/knowledge-cli","version":"0.22.5"}', encoding="utf-8")
    profile = tmp_path / "isolated-profile.cjs"
    profile.write_text(
        "require('node:os').homedir = () => process.env.HIMATE_TEST_INSTALL_HOME;\n",
        encoding="utf-8",
    )
    subprocess.run(
        [node, "--require", str(profile), str(TOOL_ROOT / "scripts/install.js")],
        check=True,
        env={**os.environ, "HIMATE_TEST_INSTALL_HOME": str(home)},
        capture_output=True,
        timeout=30,
    )

    package_version = json.loads((TOOL_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    assert json.loads(marker.read_text(encoding="utf-8"))["version"] == package_version
    assert not previous_runtime.exists()
    assert environment_config.read_bytes() == b"previous virtual environment"
    assert install_log.read_bytes() == b"previous setup diagnostics"
    assert (installed / "runtime/manifest.json").read_bytes() == (TOOL_ROOT / "runtime/manifest.json").read_bytes()
