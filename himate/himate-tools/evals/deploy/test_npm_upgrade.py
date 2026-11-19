"""Check npm release contents and preserve existing user state during installation."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]
NPM_SCRIPTS = TOOL_ROOT / "distribution/npm"


def run_postinstall(tmp_path, profile, *, fault="", **settings):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the npm postinstall test")
    preload = tmp_path / "isolated-profile.cjs"
    preload.write_text(
        "require('node:os').homedir = () => process.env.HIMATE_TEST_INSTALL_HOME;\n",
        encoding="utf-8",
    )
    command = [node, "--require", str(preload)]
    if fault:
        injected = tmp_path / "postinstall-fault.cjs"
        injected.write_text(fault, encoding="utf-8")
        command.extend(("--require", str(injected)))
    env = {**os.environ, "HIMATE_TEST_INSTALL_HOME": str(profile), **settings}
    return subprocess.run(
        [*command, str(NPM_SCRIPTS / "install.js")],
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def test_npm_postinstall_preserves_managed_environment_and_logs(tmp_path):
    home = tmp_path / "profile with spaces"
    installed = home / ".himate/knowledge"
    previous_runtime = installed / "runtime/obsolete.py"
    environment_config = installed / ".venv/pyvenv.cfg"
    install_log = installed / "logs/setup.log"
    previously_installed_model = installed / "tools/deploy/models/docling-cpu/saved-model"
    stale_wrapper = installed / "knowledge.sh"
    retired_deployment = installed / "distribution/source/deploy.py"
    customized_wrapper = installed / "knowledge.cmd"
    old_wrapper = b"legacy wrapper\n"
    customized = b"user-modified wrapper\n"
    for target, contents in (
        (previous_runtime, b"previous runtime"),
        (environment_config, b"previous virtual environment"),
        (install_log, b"previous setup diagnostics"),
        (previously_installed_model, b"independently installed model"),
        (stale_wrapper, old_wrapper),
        (retired_deployment, b"previous capability installer"),
        (customized_wrapper, customized),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    marker = installed / ".install.json"
    marker.write_text('{"package":"@himate/knowledge-cli","version":"0.22.5"}', encoding="utf-8")
    previous_manifest = {
        "schema_version": "1.1", "version": "0.22.5", "entrypoints": {
            stale_wrapper.name: {"sha256": sha256(old_wrapper).hexdigest()},
            customized_wrapper.name: {"sha256": sha256(b"previous unmodified command wrapper\n").hexdigest()},
        },
    }
    (installed / "runtime/manifest.json").write_text(json.dumps(previous_manifest), encoding="utf-8")
    result = run_postinstall(tmp_path, home)
    assert result.returncode == 0, result.stderr

    package_version = json.loads((TOOL_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    assert json.loads(marker.read_text(encoding="utf-8"))["version"] == package_version
    assert not previous_runtime.exists()
    assert not stale_wrapper.exists()
    assert not retired_deployment.exists()
    assert customized_wrapper.read_bytes() == customized
    assert environment_config.read_bytes() == b"previous virtual environment"
    assert install_log.read_bytes() == b"previous setup diagnostics"
    assert previously_installed_model.read_bytes() == b"independently installed model"
    assert not (installed / "distribution/release").exists()
    assert (installed / "runtime/governance/framework.lock.yaml").is_file()
    assert (installed / "runtime/manifest.json").read_bytes() == (TOOL_ROOT / "runtime/manifest.json").read_bytes()


@pytest.mark.parametrize(("item", "transient"), [
    ("runtime", False),
    (".install.json", False),
    pytest.param("runtime", True, marks=pytest.mark.skipif(os.name != "nt", reason="Windows rename retries")),
])
def test_npm_postinstall_recovers_from_blocked_rename(tmp_path, item, transient):
    home = tmp_path / "profile & tools !"
    installed = home / ".himate/knowledge"
    old_version = "0.22.5"
    old_wrapper = b"old wrapper\n"
    previous = {
        ".install.json": json.dumps({"package": "@himate/knowledge-cli", "version": old_version}).encode(),
        "knowledge.py": b'from pathlib import Path\nprint((Path(__file__).parent / "runtime/version.txt").read_text())\n',
        "runtime/version.txt": old_version.encode(),
        "runtime/manifest.json": json.dumps({
            "version": old_version, "entrypoints": {"knowledge.sh": {"sha256": sha256(old_wrapper).hexdigest()}},
        }).encode(),
        "distribution/source/obsolete.py": b"old runtime helper",
        "docs/DEPLOY.md": b"old instructions",
        "knowledge.sh": old_wrapper,
    }
    for reference, data in previous.items():
        target = installed / reference
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    result = run_postinstall(tmp_path, home, HIMATE_TEST_BLOCKED_ITEM=item,
                             HIMATE_TEST_TRANSIENT=str(int(transient)), HIMATE_TEST_OLD_VERSION=old_version, fault="""
const fs = require('node:fs');
const path = require('node:path');
const item = process.env.HIMATE_TEST_BLOCKED_ITEM;
const dest = path.join(process.env.HIMATE_TEST_INSTALL_HOME, '.himate', 'knowledge', item);
const rename = fs.renameSync;
let blocked = false;
fs.renameSync = (source, target) => {
  if (target === dest && (process.env.HIMATE_TEST_TRANSIENT === '0' || !blocked)) {
    const old = item === 'runtime'
      ? fs.existsSync(path.join(source, 'version.txt'))
      : JSON.parse(fs.readFileSync(source, 'utf8')).version === process.env.HIMATE_TEST_OLD_VERSION;
    if (!old) {
      blocked = true;
      throw Object.assign(new Error('injected rename failure: ' + item), { code: 'EPERM' });
    }
  }
  return rename(source, target);
};
""")

    marker = installed / ".install.json"
    if transient:
        assert result.returncode == 0, result.stderr
        expected = json.loads((TOOL_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
        assert json.loads(marker.read_text(encoding="utf-8"))["version"] == expected
        return

    assert result.returncode != 0
    assert f"injected rename failure: {item}" in result.stderr
    for reference, data in previous.items():
        assert (installed / reference).read_bytes() == data, reference
    assert sorted(path.name for path in (installed / "runtime").iterdir()) == ["manifest.json", "version.txt"]
    launcher = subprocess.run(
        [shutil.which("node"), "--require", str(tmp_path / "isolated-profile.cjs"),
         str(NPM_SCRIPTS / "knowledge.js"), "--version"],
        env={**os.environ, "HIMATE_TEST_INSTALL_HOME": str(home), "HIMATE_KNOWLEDGE_PYTHON": sys.executable},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert launcher.returncode == 0, launcher.stderr
    assert launcher.stdout.strip() == old_version

    retry = run_postinstall(tmp_path, home)
    assert retry.returncode == 0, retry.stderr


def test_npm_postinstall_rejects_incomplete_manifest_before_switching(tmp_path):
    home = tmp_path / "profile"
    installed = home / ".himate/knowledge"
    installed.mkdir(parents=True)
    previous = installed / "knowledge.py"
    previous.write_bytes(b"previous entrypoint")

    result = run_postinstall(tmp_path, home, fault="""
const fs = require('node:fs');
const path = require('node:path');
const copy = fs.cpSync;
fs.cpSync = (source, target, options) => {
  copy(source, target, options);
  if (path.basename(source) === 'runtime') {
    fs.writeFileSync(path.join(target, 'manifest.json'), '{}');
  }
};
""")

    assert result.returncode != 0
    assert "Invalid staged runtime manifest" in result.stderr
    assert previous.read_bytes() == b"previous entrypoint"
    assert not (installed / "runtime").exists()


def test_npm_postinstall_can_retry_after_process_stops_at_switch(tmp_path):
    home = tmp_path / "profile"
    result = run_postinstall(tmp_path, home, fault="require('node:fs').renameSync = () => process.exit(67);\n")

    assert result.returncode == 67, result.stderr
    retry = run_postinstall(tmp_path, home)
    assert retry.returncode == 0, retry.stderr


def test_npm_pack_excludes_caches_without_removing_source_files(tmp_path):
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        pytest.skip("Node.js and npm are required for the package preview test")
    package = tmp_path / "package"
    package.mkdir()
    shutil.copyfile(TOOL_ROOT / "package.json", package / "package.json")
    npm_sources = "distribution/npm"
    shutil.copytree(TOOL_ROOT / npm_sources, package / npm_sources)
    included = {"runtime/entry.py", "runtime/governance/framework.lock.yaml",
                f"{npm_sources}/install.js", f"{npm_sources}/knowledge.js",
                "distribution/source/environment.py"}
    excluded = {"runtime/__pycache__/entry.pyc", "runtime/.pytest_cache/README.md", "runtime/unused.pyo",
                "runtime/governance/contracts/__pycache__/contract.pyc", f"{npm_sources}/__pycache__/cache",
                "distribution/release/build_runtime_manifest.py", "distribution/models/manifest.json"}
    for name in (included | excluded) - {f"{npm_sources}/install.js", f"{npm_sources}/knowledge.js"}:
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="utf-8")

    outside = tmp_path / "outside package"
    guard = outside / "__pycache__/external.pyc"
    guard.parent.mkdir(parents=True)
    guard.write_text("external fixture", encoding="utf-8")
    link_type = "junction" if os.name == "nt" else "dir"
    subprocess.run([node, "-e", "require('fs').symlinkSync(...process.argv.slice(1))",
                    str(outside), str(package / "runtime/governance/linked"), link_type],
                   check=True, capture_output=True, timeout=30)

    user_config, global_config = tmp_path / "user.npmrc", tmp_path / "global.npmrc"
    user_config.touch()
    global_config.touch()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("NPM_CONFIG_")}
    env.update(NPM_CONFIG_USERCONFIG=str(user_config), NPM_CONFIG_GLOBALCONFIG=str(global_config),
               NPM_CONFIG_CACHE=str(tmp_path / "npm-cache"))
    preview = subprocess.run([npm, "pack", "--dry-run", "--json", "--offline"], cwd=package, env=env,
                             check=True, capture_output=True, text=True, encoding="utf-8", timeout=30)
    payload = json.loads(preview.stdout)
    record = payload[0] if isinstance(payload, list) else payload["@himate/knowledge-cli"]
    packaged = {file["path"] for file in record["files"]}
    assert included <= packaged
    assert packaged.isdisjoint(excluded)
    assert not any(path.startswith("runtime/governance/linked/") for path in packaged)
    assert all((package / path).read_text(encoding="utf-8") == "fixture" for path in excluded)
    assert guard.read_text(encoding="utf-8") == "external fixture"
