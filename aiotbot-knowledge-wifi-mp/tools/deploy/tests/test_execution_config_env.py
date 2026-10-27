"""Explicit config.env is deployment data, never shell code or implicit input."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "run_node.py"
REPO = Path(__file__).resolve().parents[4]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load_runner():
    spec = importlib.util.spec_from_file_location("env_execution_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def remote_env(tmp_path):
    catalog = {"schema_version": "2.0", "workspaces": {"remote": {
        "config": "/srv/a project/config.yml", "rules_digest": "b" * 64}},
        "skills": {"hs-knowledge-query": {"root": "/srv/agent/hs-knowledge-query",
            "entry": "scripts/cli.py", "python": "/srv/runtime/bin/python",
            "package_digest": "a" * 64}}}
    catalog_path = tmp_path / "expected remote catalog.json"
    catalog_path.write_bytes(canonical(catalog))
    key_path = tmp_path / "a key file"
    key_path.write_text("synthetic key placeholder, never read by loader", encoding="utf-8")
    path = tmp_path / "config.env"
    path.write_text("\n".join([
        "# Synthetic private settings", "EXECUTION_MODE=ssh", "SSH_HOST=host.example",
        "SSH_USER=developer", "SSH_PORT=2202", f'SSH_IDENTITY_FILE="{key_path}"',
        'REMOTE_PROJECT_ROOT="/srv/a project"', "REMOTE_CATALOG=/srv/private/catalog.json",
        f'EXPECTED_CATALOG="{catalog_path}"', ""]), encoding="utf-8")
    return path, catalog, key_path


def test_env_derives_registered_rules_and_python_without_duplicate_profile(remote_env):
    runner = load_runner()
    path, catalog, key_path = remote_env
    profile = runner.load_configuration(path, config_env=True, skill="hs-knowledge-query")
    assert profile == {"schema_version": "1.0", "mode": "ssh", "target": "developer@host.example",
        "port": 2202, "identity_file": str(key_path.resolve()), "remote_workspace": "/srv/a project",
        "remote_catalog": "/srv/private/catalog.json", "remote_python": "/srv/runtime/bin/python",
        "expected_catalog": str(path.parent / "expected remote catalog.json"), "rules_digest": "b" * 64}
    assert "remote_profile" not in profile


@pytest.mark.parametrize("text", [
    "SSH_HOST=a\nSSH_HOST=b", "NOT_ALLOWED=TOP_SECRET", "SSH_HOST=$(TOP_SECRET)",
    "SSH_HOST=`TOP_SECRET`", "export SSH_HOST=TOP_SECRET", "SSH_HOST", "SSH_HOST='unclosed",
    "SSH_HOST=a\nssh_host=TOP_SECRET", "SSH_HOST=${TOP_SECRET}",
])
def test_invalid_env_data_has_no_evaluation_or_value_disclosure(text):
    runner = load_runner()
    with pytest.raises(runner.ExecutionError) as caught:
        runner.parse_config_env(text.encode())
    assert "TOP_SECRET" not in str(caught.value)


@pytest.mark.parametrize("extra", ["SSH_PORT=0", "SSH_PORT=65536", "SSH_PORT=22 -oBad",
    "RULES_DIGEST=" + "c" * 64, "REMOTE_PROJECT_ROOT=/different/project"])
def test_env_rejects_invalid_connection_or_mismatched_binding(remote_env, extra):
    runner = load_runner()
    path, _, _ = remote_env
    content = path.read_text(encoding="utf-8")
    key = extra.split("=", 1)[0]
    content = "\n".join(line for line in content.splitlines() if not line.startswith(key + "="))
    path.write_text(content + "\n" + extra + "\n", encoding="utf-8")
    with pytest.raises(runner.ExecutionError):
        runner.load_configuration(path, config_env=True)


def test_env_json_profile_compatibility(tmp_path):
    runner = load_runner()
    profile = {"schema_version": "1.0", "mode": "local", "knowledge_root": str(tmp_path),
               "catalog": str(tmp_path / "catalog.json"), "rules_digest": "a" * 64}
    (tmp_path / "catalog.json").write_bytes(b"{}")
    path = tmp_path / "profile.json"
    path.write_bytes(canonical(profile))
    assert runner.load_configuration(path) == profile


@pytest.fixture
def registered_local(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "env_pipeline", REPO / "aiotbot-knowledge-wifi-mp/evals/pipeline_harness.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    pipeline = fixture.Pipeline(tmp_path / "a business project")
    project = pipeline.root.parent
    config = project / "config.yml"
    config.write_bytes(canonical({"schema_version": "2.0", "workspace_id": "env-fixture",
        "knowledge_roots": {"wifi": pipeline.root.name}, "code_root": "main", "modules": []}))
    pipeline.catalog["workspaces"] = {"env-fixture": {"config": str(config), "rules_digest": pipeline.rules}}
    pipeline.catalog_path.write_bytes(canonical(pipeline.catalog))
    return pipeline, project


def test_local_env_runs_real_public_node(registered_local, tmp_path):
    pipeline, project = registered_local
    env = tmp_path / "config.env"
    env.write_text(f'EXECUTION_MODE=local\nPROJECT_ROOT="{project}"\nCATALOG="{pipeline.catalog_path}"\n', encoding="utf-8")
    incoming, outgoing = tmp_path / "request.json", tmp_path / "response.json"
    incoming.write_bytes(canonical({"operation_id": "env-status"}))
    process = subprocess.run([sys.executable, str(RUNNER), "--config-env", env.name,
        "--skill", "hs-knowledge-source-scan", "--action", "status", "--input", incoming.name,
        "--output", outgoing.name], cwd=tmp_path, capture_output=True)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    response = json.loads(outgoing.read_bytes())
    assert process.returncode == 0 and response["phase"] == "status", response


def test_workspace_worker_resolves_and_verifies_real_registered_mapping(registered_local):
    runner = load_runner()
    pipeline, project = registered_local
    binding = {"workspace_root": str(project), "catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    request = {"operation_id": "env-worker-status"}
    packet = {"schema_version": "1.0", "skill": "hs-knowledge-source-scan", "action": "status",
        "request": request, "request_digest": hashlib.sha256(canonical(request)).hexdigest(),
        "catalog_digest": hashlib.sha256(pipeline.catalog_path.read_bytes()).hexdigest(),
        "rules_digest": pipeline.rules, "execution_binding": binding}
    code, raw = runner.workspace_worker(binding, packet)
    response = json.loads(raw)
    assert code == 0 and response["response"]["phase"] == "status", response
    assert response["execution_binding"] == binding
    wrong = {**binding, "workspace_root": str(project.parent)}
    with pytest.raises(runner.ExecutionError):
        runner.workspace_worker(wrong, packet)


def test_env_ssh_flags_and_bootstrap_are_separate_arguments(remote_env, monkeypatch):
    runner = load_runner()
    path, _, key = remote_env
    profile = runner.load_configuration(path, config_env=True)
    commands = []

    def ssh(argv, **kwargs):
        commands.append(argv)
        assert "timeout" not in kwargs
        return subprocess.CompletedProcess(argv, 255, b"", b"synthetic disconnect")

    monkeypatch.setattr(runner.subprocess, "run", ssh)
    with pytest.raises(runner.ExecutionError, match="SSH_RESULT_UNAVAILABLE"):
        runner.dispatch(profile, "hs-knowledge-query", {"operation_id": "env-ssh"}, "search")
    command = commands[0]
    assert command[:10] == ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                           "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3"]
    assert command[command.index("-p") + 1] == "2202"
    assert command[command.index("-i") + 1] == str(key.resolve())
    remote = shlex.split(command[-1])
    assert remote[:3] == ["/srv/runtime/bin/python", "-B", "-c"]
    assert remote[4:] == ["/srv/a project", "/srv/private/catalog.json", "b" * 64]
    assert remote[3] == runner.WORKSPACE_BOOTSTRAP


def test_explicit_trusted_launcher_can_drop_uid_without_replacing_node_python(remote_env):
    runner = load_runner()
    path, catalog, _ = remote_env
    with path.open("a", encoding="utf-8") as stream:
        stream.write('REMOTE_PYTHON="/srv/private/run as shared user"\n')
    profile = runner.load_configuration(path, config_env=True)
    assert profile["remote_python"] == "/srv/private/run as shared user"
    packet = runner.make_packet(profile, "hs-knowledge-query", {"operation_id": "launcher-test"}, "search")
    assert packet["catalog_digest"] == hashlib.sha256(canonical(catalog)).hexdigest()
    assert catalog["skills"]["hs-knowledge-query"]["python"] == "/srv/runtime/bin/python"


def test_fixed_bootstrap_reaches_real_workspace_worker(registered_local):
    runner = load_runner()
    pipeline, project = registered_local
    tools = pipeline.root / "tools/deploy"
    tools.mkdir(parents=True)
    shutil.copyfile(RUNNER, tools / "run_node.py")
    shutil.copyfile(RUNNER.with_name("install_catalog.py"), tools / "install_catalog.py")
    binding = {"workspace_root": str(project), "catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    request = {"operation_id": "env-bootstrap-status"}
    packet = {"schema_version": "1.0", "skill": "hs-knowledge-source-scan", "action": "status", "request": request,
        "request_digest": hashlib.sha256(canonical(request)).hexdigest(),
        "catalog_digest": hashlib.sha256(pipeline.catalog_path.read_bytes()).hexdigest(),
        "rules_digest": pipeline.rules, "execution_binding": binding}
    process = subprocess.run([sys.executable, "-B", "-c", runner.WORKSPACE_BOOTSTRAP,
                              str(project), str(pipeline.catalog_path), pipeline.rules],
                             input=canonical(packet), capture_output=True)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    result = json.loads(process.stdout)
    assert result["response"]["phase"] == "status" and result["execution_binding"] == binding


def test_workspace_rejects_stale_catalog_before_selecting_a_parser_runtime(registered_local, monkeypatch):
    runner = load_runner()
    pipeline, project = registered_local
    request = {"operation_id": "stale-bootstrap"}
    binding = {"workspace_root": str(project), "catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    packet = {"schema_version": "1.0", "skill": "hs-knowledge-query", "action": "search", "request": request,
        "request_digest": hashlib.sha256(canonical(request)).hexdigest(), "catalog_digest": "0" * 64,
        "rules_digest": pipeline.rules, "execution_binding": binding}
    monkeypatch.setattr(runner._installer, "parse_yaml_data", lambda *a, **k: pytest.fail("unverified catalog runtime"))
    with pytest.raises(runner.ExecutionError, match="CATALOG_CHANGED"):
        runner.workspace_worker(binding, packet)


def test_bootstrap_binding_checks_remain_active_with_python_optimization(registered_local, tmp_path):
    runner = load_runner()
    pipeline, project = registered_local
    tools = pipeline.root / "tools/deploy"
    tools.mkdir(parents=True)
    marker = tmp_path / "candidate-ran"
    (tools / "run_node.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unexpected execution')\n", encoding="utf-8")
    binding = {"workspace_root": str(project), "catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}
    packet = {"catalog_digest": "0" * 64, "execution_binding": binding, "rules_digest": pipeline.rules}
    process = subprocess.run([sys.executable, "-O", "-B", "-c", runner.WORKSPACE_BOOTSTRAP,
                              str(project), str(pipeline.catalog_path), pipeline.rules],
                             input=canonical(packet), capture_output=True)
    assert process.returncode != 0 and not marker.exists()


@pytest.mark.parametrize("field", ["EXPECTED_CATALOG", "SSH_IDENTITY_FILE", "config_file"])
def test_ssh_env_caller_paths_refuse_unc_before_file_inspection(remote_env, monkeypatch, field):
    runner = load_runner()
    path, _, _ = remote_env
    remote = r"\\server\share\caller-file"
    if field == "config_file":
        path = remote
    else:
        content = path.read_text(encoding="utf-8")
        content = "\n".join(line for line in content.splitlines() if not line.startswith(field + "="))
        path.write_text(content + "\n" + field + "=" + remote + "\n", encoding="utf-8")
    inspect = runner._installer.absolute

    def local_inspection_only(value, **kwargs):
        assert "\\\\server" not in value, "remote filesystem inspected"
        return inspect(value, **kwargs)

    monkeypatch.setattr(runner._installer, "absolute", local_inspection_only)
    with pytest.raises(runner.ExecutionError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        runner.load_configuration(path, config_env=True)


@pytest.mark.parametrize("field", ["PROJECT_ROOT", "CATALOG", "KNOWLEDGE_ROOT"])
def test_local_env_cannot_point_at_network_project_material(registered_local, tmp_path, field):
    runner = load_runner()
    pipeline, project = registered_local
    values = {"EXECUTION_MODE": "local", "PROJECT_ROOT": str(project), "CATALOG": str(pipeline.catalog_path)}
    values[field] = r"\\server\share\working-path"
    config = tmp_path / "native-env-config.env"
    config.write_text("\n".join(key + "=" + value for key, value in values.items()) + "\n", encoding="utf-8")
    with pytest.raises(runner.ExecutionError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        runner.load_configuration(config, config_env=True, skill="hs-knowledge-query")
