"""Execution profiles use real node CLIs; SSH transport is isolated in tests."""

import copy
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shlex
import shutil
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[4]
RUNNER = REPO / "aiotbot-knowledge-wifi-mp/tools/deploy/run_node.py"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_runner():
    assert RUNNER.is_file(), "The configured local/SSH execution entry does not exist"
    spec = importlib.util.spec_from_file_location("execution_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def execution(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "execution_pipeline", REPO / "aiotbot-knowledge-wifi-mp/evals/pipeline_harness.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    pipeline = fixture.Pipeline(tmp_path / "a project with spaces")
    profile = {"schema_version": "1.0", "mode": "local",
               "knowledge_root": str(pipeline.root), "catalog": str(pipeline.catalog_path),
               "rules_digest": pipeline.rules}
    profile_path = tmp_path / "local profile.json"
    profile_path.write_bytes(canonical(profile))
    request = {"operation_id": "execution-query", "query": "capture"}
    return pipeline, profile_path, profile, request


def test_local_runs_real_node_and_preserves_node_failure(execution, tmp_path):
    _, profile, _, request = execution
    assert RUNNER.is_file(), "The configured local/SSH execution entry does not exist"
    incoming, outgoing = tmp_path / "in.json", tmp_path / "out.json"
    incoming.write_bytes(canonical(request))
    process = subprocess.run([sys.executable, str(RUNNER), "--profile", str(profile),
                              "--skill", "hs-knowledge-query", "--action", "search",
                              "--input", str(incoming), "--output", str(outgoing)],
                             capture_output=True)
    result = json.loads(outgoing.read_bytes())
    assert process.returncode == 2, result
    assert result["schema_version"] == "2.0" and result["record_kind"] == "result"
    assert result["status"] == "error" and result["tool_identity"]["skill"] == "hs-knowledge-query"
    assert result["digest"] == hashlib.sha256(canonical(
        {key: value for key, value in result.items() if key != "digest"})).hexdigest()


def ssh_profile(execution):
    pipeline, profile_path, _, _ = execution
    return {"schema_version": "1.0", "mode": "ssh", "target": "wifi-linux",
            "remote_python": "/srv/Agent's runtime/python",
            "remote_runner": "/srv/Agent's tools/run_node.py",
            "remote_profile": "/srv/config/remote profile.json",
            "remote_profile_digest": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            "expected_catalog": str(pipeline.catalog_path), "rules_digest": pipeline.rules}


def test_ssh_roundtrip_uses_real_remote_worker_and_fixed_catalog(execution, monkeypatch):
    runner = load_runner()
    _, remote_profile, _, request = execution
    profile = ssh_profile(execution)
    calls = []
    real_run = subprocess.run

    def transport(argv, **kwargs):
        calls.append((argv, kwargs))
        return real_run([sys.executable, str(RUNNER), "--worker", "--profile", str(remote_profile)],
                        input=kwargs["input"], capture_output=True)

    monkeypatch.setattr(runner.subprocess, "run", transport)
    code, raw = runner.dispatch(profile, "hs-knowledge-query", request, "search")
    result = json.loads(raw)
    assert code == 2 and result["status"] == "error"
    argv, kwargs = calls[0]
    assert argv[:10] == ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                         "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3"]
    assert "timeout" not in kwargs
    assert "StrictHostKeyChecking=no" not in argv and "-n" not in argv
    assert shlex.split(argv[-1]) == [profile["remote_python"], "-B", profile["remote_runner"],
                                    "--worker", "--profile", profile["remote_profile"]]
    packet = json.loads(kwargs["input"])
    assert packet["request"] == request and packet["skill"] == "hs-knowledge-query"
    assert "--input" not in argv[-1] and "capture" not in argv[-1]


@pytest.mark.parametrize("mutation", [
    {"target": "-oProxyCommand=bad"}, {"target": "host;bad"},
    {"remote_python": "python"}, {"remote_runner": "/srv/runner\nbad"},
    {"remote_profile_digest": "bad"}, {"mode": "automatic"}, {"timeout": 600},
])
def test_invalid_profile_is_rejected_before_spawn(execution, mutation, monkeypatch):
    runner = load_runner()
    profile = {**ssh_profile(execution), **mutation}
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned"))
    with pytest.raises(runner.ExecutionError):
        runner.dispatch(profile, "hs-knowledge-query", execution[3], "search")


def test_unknown_skill_and_action_cannot_become_commands(execution, monkeypatch):
    runner = load_runner()
    profile = execution[2]
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned"))
    for skill, action in [("../../other", "search"), ("hs-codegraph-setup", None),
                          ("hs-knowledge-query", "search;other")]:
        with pytest.raises(runner.ExecutionError):
            runner.dispatch(profile, skill, execution[3], action)


def test_ssh_disconnect_never_retries_or_returns_unverified_node(execution, monkeypatch):
    runner = load_runner()
    calls = []

    def transport(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args[0], 255, b"", b"connection lost")

    monkeypatch.setattr(runner.subprocess, "run", transport)
    with pytest.raises(runner.ExecutionError, match="SSH_RESULT_UNAVAILABLE"):
        runner.dispatch(ssh_profile(execution), "hs-knowledge-query", execution[3], "search")
    assert len(calls) == 1


def test_remote_profile_and_catalog_digests_are_pinned(execution):
    runner = load_runner()
    pipeline, profile_path, _, request = execution
    packet = runner.make_packet(ssh_profile(execution), "hs-knowledge-query", request, "search")
    packet["remote_profile_digest"] = "0" * 64
    with pytest.raises(runner.ExecutionError, match="REMOTE_PROFILE_CHANGED"):
        runner.worker(profile_path, packet)
    packet = runner.make_packet(ssh_profile(execution), "hs-knowledge-query", request, "search")
    packet["catalog_digest"] = "0" * 64
    with pytest.raises(runner.ExecutionError, match="CATALOG_CHANGED"):
        runner.worker(profile_path, packet)
    packet = runner.make_packet(ssh_profile(execution), "hs-knowledge-query", request, "search")
    packet["rules_digest"] = "0" * 64
    with pytest.raises(runner.ExecutionError, match="REMOTE_RULES_MISMATCH"):
        runner.worker(profile_path, packet)
    assert pipeline.catalog_path.is_file()


@pytest.mark.parametrize("mutation", [
    {"rules_digest": "0" * 64}, {"status": "ok"},
    {"tool_identity": {"skill": "hs-knowledge-query", "package_digest": "0" * 64}},
])
def test_authenticity_and_exit_status_must_match(execution, mutation):
    runner = load_runner()
    pipeline, _, _, _ = execution
    catalog = json.loads(pipeline.catalog_path.read_bytes())
    entry = catalog["skills"]["hs-knowledge-query"]
    response = {"schema_version": "2.0", "record_kind": "result", "status": "blocked",
                "phase": "blocked", "rules_digest": pipeline.rules,
                "tool_identity": {"skill": "hs-knowledge-query", "package_digest": entry["package_digest"]}}
    response.update(copy.deepcopy(mutation))
    response["digest"] = hashlib.sha256(canonical(response)).hexdigest()
    with pytest.raises(runner.ExecutionError):
        runner.verify_response(response, 3, "hs-knowledge-query", entry, pipeline.rules)


def test_existing_output_is_rejected_before_execution(execution, tmp_path):
    runner = load_runner()
    _, profile, _, request = execution
    incoming, outgoing = tmp_path / "input.json", tmp_path / "already.json"
    incoming.write_bytes(canonical(request))
    outgoing.write_bytes(b"keep this output")
    assert runner.main(["--profile", str(profile), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)]) == 2
    assert outgoing.read_bytes() == b"keep this output"


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("bad_card", [False, True])
def test_lint_protocol_and_persistent_remote_reference(execution, monkeypatch, remote, bad_card):
    runner = load_runner()
    pipeline, remote_profile, local, _ = execution
    if bad_card:
        pipeline.write("knowledge/rules/broken.md", b"# Missing required metadata\n")
    profile = ssh_profile(execution) if remote else local
    if remote:
        real_run = subprocess.run

        def transport(argv, **kwargs):
            return real_run([sys.executable, str(RUNNER), "--worker", "--profile", str(remote_profile)],
                            input=kwargs["input"], capture_output=True)

        monkeypatch.setattr(runner.subprocess, "run", transport)
    code, raw = runner.dispatch(profile, "hs-knowledge-lint",
                                 {"operation_id": "execution-lint", "mode": "formal"})
    report = json.loads(raw)
    assert code == (1 if bad_card else 0), report
    assert report["report_version"] == "1.0" and "record_kind" not in report
    assert report["status"] == ("failed" if bad_card else "passed")
    report_path = Path(report["data"]["report_ref"])
    assert report_path.is_file() and report_path.read_bytes() == raw
    assert report_path.relative_to(pipeline.root).parts[:4] == (
        ".build", "operations", "execution-lint", "execution")
    # The real node output remains available after both runner and worker exit.
    assert report_path.with_name("request.json").is_file()


def test_lint_output_feeds_next_public_record_node(execution, monkeypatch):
    runner = load_runner()
    pipeline, remote_profile, _, _ = execution
    operation = "execution-p6"
    pipeline.write("docs-raw/specs/execution.md", b"# Source\nCapture is a synthetic rule.\n")
    scan_ref = pipeline.call("knowledge-source-scan", {"operation_id": operation})["data"]["scan_ref"]
    unit = pipeline.record(scan_ref)["units"][0]
    material_ref = pipeline.call("knowledge-source-scan", {"operation_id": operation,
        "scan_ref": scan_ref}, "prepare")["data"]["material_ref"]
    bundle_ref = pipeline.record(material_ref)["bundle_ref"]
    bundle = pipeline.record(bundle_ref)
    view_ref = pipeline.view(operation, bundle_ref, "execution-card", pipeline.card("execution-card", bundle))
    real_run = subprocess.run

    def transport(argv, **kwargs):
        return real_run([sys.executable, str(RUNNER), "--worker", "--profile", str(remote_profile)],
                        input=kwargs["input"], capture_output=True)

    monkeypatch.setattr(runner.subprocess, "run", transport)
    code, raw = runner.dispatch(ssh_profile(execution), "hs-knowledge-lint",
                                 {"operation_id": operation, "view_ref": view_ref})
    report = json.loads(raw)
    assert code == 0, report
    lint_ref = Path(report["data"]["report_ref"]).relative_to(pipeline.root).as_posix()
    # This is a second real worker/node invocation, not a rewritten report.
    code, raw = runner.dispatch(ssh_profile(execution), "hs-knowledge-source-scan",
        {"operation_id": operation, "scan_ref": scan_ref, "view_ref": view_ref, "lint_ref": lint_ref,
         "dispositions": [{"unit_id": unit["unit_id"], "action": "create", "reason": "Synthetic execution test",
                           "observed_fingerprint": unit["observed_fingerprint"],
                           "adopted_fingerprint": unit["observed_fingerprint"], "progress": "completed",
                           "card_refs": ["execution-card"], "claim_refs": ["execution-card#c1"]}]}, "record")
    result = json.loads(raw)
    assert code == 0 and result["phase"] == "recorded", result
    assert pipeline.record(result["data"]["ingest_record_ref"])["lint_ref"] == lint_ref


def test_caller_profile_change_blocks_result_publication(execution, tmp_path, monkeypatch):
    runner = load_runner()
    _, profile_path, profile, request = execution
    incoming, outgoing = tmp_path / "profile-input.json", tmp_path / "profile-output.json"
    incoming.write_bytes(canonical(request))

    def execute(*args):
        profile_path.write_bytes(canonical({**profile, "rules_digest": "0" * 64}))
        return 0, canonical({"should_not_be_published": True})

    monkeypatch.setattr(runner, "dispatch", execute)
    code = runner.main(["--profile", str(profile_path), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)])
    result = json.loads(outgoing.read_bytes())
    assert code == 3 and result["record_kind"] == "execution_error"
    assert result["diagnostics"][0]["code"] == "CALLER_PROFILE_CHANGED_INSPECT_EXECUTION"


def test_optional_result_request_bindings_cannot_name_another_call(execution):
    runner = load_runner()
    pipeline, _, _, request = execution
    entry = json.loads(pipeline.catalog_path.read_bytes())["skills"]["hs-knowledge-query"]
    for binding in ({"operation_id": "other"}, {"request_digest": "0" * 64}):
        response = {"schema_version": "2.0", "record_kind": "result", "status": "ok",
                    "rules_digest": pipeline.rules, "tool_identity": {"skill": "hs-knowledge-query",
                    "package_digest": entry["package_digest"]}, **binding}
        response["digest"] = hashlib.sha256(canonical(response)).hexdigest()
        with pytest.raises(runner.ExecutionError, match="NODE_REQUEST_BINDING_MISMATCH"):
            runner.verify_response(response, 0, "hs-knowledge-query", entry, pipeline.rules, request)


def test_forbidden_output_never_creates_even_an_error_in_originals(execution, tmp_path):
    runner = load_runner()
    pipeline, profile_path, _, request = execution
    incoming = tmp_path / "read-only-input.json"
    incoming.write_bytes(canonical(request))
    outgoing = pipeline.root / "docs-raw/specs/should-not-exist.json"
    code = runner.main(["--profile", str(profile_path), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)])
    assert code == 2 and not outgoing.exists()


def test_tool_helper_uses_exact_source_instead_of_a_matching_pyc(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    script = tools / "run_node.py"
    helper = tools / "install_catalog.py"
    shutil.copyfile(RUNNER, script)
    shutil.copyfile(RUNNER.with_name("install_catalog.py"), helper)
    poison = tmp_path / "poison.py"
    poison.write_text("raise RuntimeError('cached helper must not execute')\n", encoding="utf-8")
    cached = Path(importlib.util.cache_from_source(str(helper)))
    cached.parent.mkdir()
    py_compile.compile(str(poison), cfile=str(cached), doraise=True)
    raw = bytearray(cached.read_bytes())
    raw[8:16] = struct.pack("<II", int(helper.stat().st_mtime), helper.stat().st_size)
    cached.write_bytes(raw)
    process = subprocess.run([sys.executable, str(script), "--help"], capture_output=True)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    assert b"--profile" in process.stdout


@pytest.mark.parametrize("valid_input", [False, True])
@pytest.mark.parametrize("area", ["docs-raw/specs", "knowledge/rules", "governance"])
def test_ssh_caller_cannot_write_another_nested_knowledge_root(
        execution, tmp_path, monkeypatch, valid_input, area):
    runner = load_runner()
    profile = tmp_path / "ssh-profile.json"
    profile.write_bytes(canonical(ssh_profile(execution)))
    incoming = tmp_path / "ssh-input.json"
    incoming.write_bytes(canonical(execution[3]) if valid_input else b"{invalid JSON")
    caller_root = tmp_path / "caller project/aiotbot/another-wifi"
    marker = caller_root / "governance/framework.lock.yaml"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"Marker only: this file must never be executed.\n")
    outgoing = caller_root / area / "should-not-exist.json"
    spawned = []

    def execute(*args):
        spawned.append(args)
        return 0, canonical({"would_have_been_a_result": True})

    monkeypatch.setattr(runner, "dispatch", execute)
    code = runner.main(["--profile", str(profile), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)])
    assert code == 2 and not outgoing.exists() and not spawned


@pytest.mark.parametrize("area", [".build", "logs/execution"])
def test_ssh_caller_may_publish_to_runtime_area(execution, tmp_path, monkeypatch, area):
    runner = load_runner()
    profile = tmp_path / "ssh-runtime-profile.json"
    profile.write_bytes(canonical(ssh_profile(execution)))
    incoming = tmp_path / "ssh-runtime-input.json"
    incoming.write_bytes(canonical(execution[3]))
    outgoing = execution[0].root / area / "caller-response.json"
    monkeypatch.setattr(runner, "dispatch", lambda *args: (0, canonical({"result_copy": True})))
    code = runner.main(["--profile", str(profile), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)])
    assert code == 0 and json.loads(outgoing.read_bytes()) == {"result_copy": True}


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("valid_input", [False, True])
def test_caller_cannot_publish_to_formal_ingest_records(execution, tmp_path, monkeypatch, remote, valid_input):
    runner = load_runner()
    profile_path = tmp_path / "formal-record-profile.json"
    profile_path.write_bytes(canonical(ssh_profile(execution) if remote else execution[2]))
    incoming = tmp_path / "formal-record-input.json"
    incoming.write_bytes(canonical(execution[3]) if valid_input else b"{broken")
    outgoing = execution[0].root / "logs/ingest/should-not-exist.json"
    monkeypatch.setattr(runner, "dispatch", lambda *args: (0, canonical({"would_run": True})))
    code = runner.main(["--profile", str(profile_path), "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", str(incoming), "--output", str(outgoing)])
    assert code == 2 and not outgoing.exists()


def test_outer_runtime_area_does_not_override_inner_originals(execution):
    runner = load_runner()
    outer = execution[0].root
    inner = outer / "logs/nested-wifi"
    marker = inner / "governance/framework.lock.yaml"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"Nested knowledge marker\n")
    with pytest.raises(runner.ExecutionError, match="OUTPUT_OUTSIDE_RUNTIME_AREA"):
        runner.caller_output_boundary(inner / "docs-raw/specs/new.json", ssh_profile(execution))


def test_ssh_result_from_a_different_action_is_refused(execution, monkeypatch):
    runner = load_runner()
    _, profile_path, _, request = execution
    real_run = subprocess.run

    def transport(argv, **kwargs):
        process = real_run([sys.executable, str(RUNNER), "--worker", "--profile", str(profile_path)],
                           input=kwargs["input"], capture_output=True)
        value = json.loads(process.stdout)
        value["action"] = "read"
        value.pop("digest")
        value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
        return subprocess.CompletedProcess(argv, process.returncode, canonical(value), b"")

    monkeypatch.setattr(runner.subprocess, "run", transport)
    with pytest.raises(runner.ExecutionError, match="UNVERIFIED_SSH_RESULT"):
        runner.dispatch(ssh_profile(execution), "hs-knowledge-query", request, "search")


@pytest.mark.parametrize("path", [r"\\server\share\repo", r"\\?\UNC\server\share\repo",
                                  r"\\?\unc\server\share\repo", "//server/share/repo"])
def test_unc_paths_are_refused_before_filesystem_inspection(path, monkeypatch):
    runner = load_runner()
    monkeypatch.setattr(runner._installer, "absolute", lambda *a, **k: pytest.fail("filesystem inspected"))
    with pytest.raises(runner.ExecutionError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        runner.absolute(path, exists=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows drive classification API")
@pytest.mark.parametrize("kind,diagnostic", [(4, "REMOTE_FILESYSTEM_REQUIRES_SSH"),
                                           (0, "EXECUTION_STORAGE_TYPE_UNAVAILABLE"),
                                           (1, "EXECUTION_STORAGE_TYPE_UNAVAILABLE")])
def test_mapped_or_unclassified_drives_fail_before_filesystem_inspection(kind, diagnostic, monkeypatch):
    runner = load_runner()
    queried = []

    def drive_type(root):
        queried.append(root)
        return kind

    monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW", drive_type)
    monkeypatch.setattr(runner._installer, "absolute", lambda *a, **k: pytest.fail("filesystem inspected"))
    with pytest.raises(runner.ExecutionError, match=diagnostic):
        runner.absolute(r"Z:\repo\knowledge", exists=False)
    assert queried == ["Z:\\"]


@pytest.mark.skipif(os.name != "nt", reason="Windows extended local paths")
def test_extended_local_drive_is_not_misclassified_as_unc(monkeypatch):
    runner = load_runner()
    queried = []

    def drive_type(root):
        queried.append(root)
        return 3

    monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW", drive_type)
    runner.require_native_storage(r"\\?\C:\local\runner.py")
    assert queried == ["\\\\?\\C:\\"]


@pytest.mark.parametrize("location", ["runner", "python", "prefix"])
def test_runtime_refuses_network_location_before_loading_sibling(location, monkeypatch):
    source = RUNNER.read_bytes()
    namespace = {"__name__": "storage_bootstrap_under_test", "__file__": str(RUNNER)}
    remote = r"\\server\share\runtime"
    if location == "runner":
        namespace["__file__"] = remote + r"\run_node.py"
    else:
        monkeypatch.setattr(sys, "executable" if location == "python" else "prefix", remote)
    monkeypatch.setattr(Path, "read_bytes", lambda *a, **k: pytest.fail("sibling loaded before storage guard"))
    with pytest.raises(ValueError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        exec(compile(source, str(RUNNER), "exec"), namespace)


@pytest.mark.parametrize("field", ["child_root", "child_python", "registered_config"])
def test_local_mirror_entry_cannot_leave_child_cli_or_project_on_share(execution, monkeypatch, field):
    runner = load_runner()
    pipeline, _, profile, request = execution
    catalog = json.loads(pipeline.catalog_path.read_bytes())
    remote = r"\\server\share\project"
    if field == "registered_config":
        catalog["workspaces"] = {"remote": {"config": remote + r"\config.yml", "rules_digest": pipeline.rules}}
    else:
        catalog["skills"]["hs-knowledge-source-capture"]["root" if field == "child_root" else "python"] = remote
    pipeline.catalog_path.write_bytes(canonical(catalog))
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned with remote child/config"))
    with pytest.raises(runner.ExecutionError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        runner.dispatch(profile, "hs-knowledge-query", request, "search")


@pytest.mark.parametrize("path", ["//server/share/python", r"/srv\share\python"])
def test_ssh_requires_server_native_posix_paths(execution, monkeypatch, path):
    runner = load_runner()
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned non-native remote path"))
    with pytest.raises(runner.ExecutionError, match="INVALID_REMOTE_PATH"):
        runner.dispatch({**ssh_profile(execution), "remote_python": path},
                        "hs-knowledge-query", execution[3], "search")


@pytest.mark.parametrize("mapped", [False, True])
@pytest.mark.parametrize("location", ["profile", "catalog", "identity", "input", "output"])
def test_ssh_caller_files_must_be_local_before_remote_file_inspection(
        execution, tmp_path, monkeypatch, capsys, location, mapped):
    if mapped and os.name != "nt":
        pytest.skip("Windows mapped drive classification")
    runner = load_runner()
    profile = ssh_profile(execution)
    remote = r"Z:\share\caller-file.json" if mapped else r"\\server\share\caller-file.json"
    if mapped:
        classify = ctypes.windll.kernel32.GetDriveTypeW
        monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW",
                            lambda root: 4 if root.upper() == "Z:\\" else classify(root))
    profile_path = tmp_path / "native-caller-profile.json"
    incoming, outgoing = tmp_path / "native-input.json", tmp_path / "native-output.json"
    incoming.write_bytes(canonical(execution[3]))
    if location == "catalog":
        profile["expected_catalog"] = remote
    elif location == "identity":
        profile["identity_file"] = remote
    profile_path.write_bytes(canonical(profile))
    values = {"profile": str(profile_path), "input": str(incoming), "output": str(outgoing)}
    if location in values:
        values[location] = remote
    inspect = runner._installer.absolute

    def local_inspection_only(value, **kwargs):
        assert "\\\\server" not in value and not value.startswith("Z:"), "remote filesystem inspected"
        return inspect(value, **kwargs)

    monkeypatch.setattr(runner._installer, "absolute", local_inspection_only)
    monkeypatch.setattr(runner, "dispatch", lambda *a, **k: pytest.fail("spawned remote caller path"))
    code = runner.main(["--profile", values["profile"], "--skill", "hs-knowledge-query", "--action", "search",
                        "--input", values["input"], "--output", values["output"]])
    assert code == 2 and "REMOTE_FILESYSTEM_REQUIRES_SSH" in capsys.readouterr().err
    if location == "input":
        result = json.loads(outgoing.read_bytes())
        assert result["record_kind"] == "execution_error"
        assert result["diagnostics"] == [{"code": "REMOTE_FILESYSTEM_REQUIRES_SSH"}]
    else:
        assert not outgoing.exists()


@pytest.mark.parametrize("field", ["knowledge_root", "catalog"])
def test_local_profile_refuses_remote_working_paths_before_read(execution, monkeypatch, field):
    runner = load_runner()
    profile = {**execution[2], field: r"\\server\share\working-path"}
    inspect = runner._installer.absolute

    def local_inspection_only(value, **kwargs):
        assert not value.startswith("\\\\"), "remote filesystem inspected"
        return inspect(value, **kwargs)

    monkeypatch.setattr(runner._installer, "absolute", local_inspection_only)
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned remote local profile"))
    with pytest.raises(runner.ExecutionError, match="REMOTE_FILESYSTEM_REQUIRES_SSH"):
        runner.dispatch(profile, "hs-knowledge-query", execution[3], "search")


@pytest.mark.parametrize("ssh", [False, True])
def test_public_cli_refuses_unc_input_without_connecting(execution, tmp_path, ssh):
    profile = tmp_path / "public-native-profile.json"
    profile.write_bytes(canonical(ssh_profile(execution) if ssh else execution[2]))
    output = tmp_path / "public-native-response.json"
    process = subprocess.run([sys.executable, str(RUNNER), "--profile", str(profile),
        "--skill", "hs-knowledge-query", "--action", "search", "--input", r"\\server\share\request.json",
        "--output", str(output)], capture_output=True)
    assert process.returncode == 2 and process.stderr.strip() == b"REMOTE_FILESYSTEM_REQUIRES_SSH"
    result = json.loads(output.read_bytes())
    assert result["record_kind"] == "execution_error"
    assert result["diagnostics"] == [{"code": "REMOTE_FILESYSTEM_REQUIRES_SSH"}]


@pytest.mark.skipif(os.name != "nt", reason="Windows drive classification API")
def test_failed_drive_classification_is_not_treated_as_local(monkeypatch):
    runner = load_runner()

    def unavailable(_root):
        raise OSError("synthetic classification failure")

    monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW", unavailable)
    monkeypatch.setattr(runner._installer, "absolute", lambda *a, **k: pytest.fail("filesystem inspected"))
    with pytest.raises(runner.ExecutionError, match="EXECUTION_STORAGE_TYPE_UNAVAILABLE"):
        runner.absolute(r"Z:\repo\request.json", exists=False)


@pytest.mark.skipif(os.name == "nt", reason="Linux catalog path grammar")
@pytest.mark.parametrize("field", ["root", "python"])
def test_linux_rejects_windows_paths_in_unselected_child_cli(execution, monkeypatch, field):
    runner = load_runner()
    pipeline, _, profile, request = execution
    catalog = json.loads(pipeline.catalog_path.read_bytes())
    catalog["skills"]["hs-knowledge-source-capture"][field] = r"C:\server\runtime"
    pipeline.catalog_path.write_bytes(canonical(catalog))
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: pytest.fail("spawned with non-native child"))
    with pytest.raises(runner.ExecutionError, match="INVALID_EXECUTION_PATH"):
        runner.dispatch(profile, "hs-knowledge-query", request, "search")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction/reparse attributes")
def test_local_junction_is_refused_before_inspecting_children(tmp_path, monkeypatch):
    runner = load_runner()
    bridge = tmp_path / "junction-to-share"
    lstat = Path.lstat

    def inspect(path, *args, **kwargs):
        if path == bridge:
            return SimpleNamespace(st_file_attributes=0x400)
        assert not path.is_relative_to(bridge), "inspected through junction"
        return lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", inspect)
    monkeypatch.setattr(runner._installer, "absolute", lambda *a, **k: pytest.fail("filesystem inspected after junction"))
    with pytest.raises(runner.ExecutionError, match="INVALID_EXECUTION_PATH"):
        runner.absolute(str(bridge / "child/request.json"), exists=False)
