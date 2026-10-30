"""Local-source edge cases through public CLIs and test-owned files only."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import pytest
import yaml


DBOX = "docs-raw/sources/dbox"
LOCAL = "docs-raw/sources/dbox.local.yml"


def test_configure_preserves_real_concurrent_edit_after_directory_validation(harness, monkeypatch):
    local = harness.root / LOCAL
    original = local.read_bytes()
    proposed = harness.base / "proposed directory"
    proposed.mkdir()
    other = harness.base / "concurrent directory"
    other.mkdir()
    concurrent = b"# Written concurrently\n" + yaml.safe_dump(
        {"schema_version": "1.0", "path": str(other)}, sort_keys=False
    ).encode()
    probe = harness.base / "configure timing probe"
    probe.mkdir()
    ready, release = probe / "ready.json", probe / "release"
    script = r'''import hashlib, json, sys, time
from pathlib import Path

def profile(frame, event, value):
    filename = frame.f_code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]
    caller = frame.f_back
    if (event == "return" and filename == "source_resources.py"
            and frame.f_code.co_name == "_dbox_location" and caller is not None
            and caller.f_code.co_name == "configure_dbox"):
        sys.setprofile(None)
        Path(READY).write_text(json.dumps({
            "before_sha256": hashlib.sha256(caller.f_locals["before"]).hexdigest(),
            "validated_root": str(value[0]),
        }), encoding="utf-8")
        deadline = time.monotonic() + 30
        while not Path(RELEASE).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("SYNTHETIC_CONFIGURE_RELEASE_TIMEOUT")
            time.sleep(0.01)

sys.setprofile(profile)
'''
    (probe / "sitecustomize.py").write_text(
        script.replace("READY", repr(str(ready))).replace("RELEASE", repr(str(release))),
        encoding="utf-8",
    )
    finished = threading.Event()
    writer_errors = []

    def replace_configuration():
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                if finished.is_set():
                    return
                if time.monotonic() >= deadline:
                    raise AssertionError("Public configure never reached the timing probe")
                time.sleep(0.01)
            observed = json.loads(ready.read_text(encoding="utf-8"))
            assert observed["before_sha256"] == hashlib.sha256(original).hexdigest()
            assert Path(observed["validated_root"]) == proposed
            replacement = harness.base / "concurrent-local.yml"
            replacement.write_bytes(concurrent)
            os.replace(replacement, local)
        except Exception as exc:
            writer_errors.append(exc)
        finally:
            release.write_bytes(b"release")

    writer = threading.Thread(target=replace_configuration)
    writer.start()
    try:
        with monkeypatch.context() as environment:
            environment.setenv("PYTHONPATH", str(probe))
            response = harness.run(
                "source", {"operation_id": "configure-concurrent", "path": str(proposed)},
                "configure", expected=3,
            )
    finally:
        finished.set()
        release.write_bytes(b"release")
        writer.join(timeout=35)
    assert not writer.is_alive()
    assert not writer_errors, writer_errors
    assert ready.is_file(), "The public subprocess must have reached the real timing boundary"
    assert response["diagnostics"][0]["code"] == "DBOX_BINDING_CHANGED"
    assert local.read_bytes() == concurrent


def test_separate_directory_mappings_preserve_source_snapshot_and_shared_config_identity(harness):
    shared_config = yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "shared-dbox-project",
        "knowledge_roots": {"wifi": "synthetic-knowledge"}, "code_root": ".", "modules": [],
    }, sort_keys=False).encode()
    shared_digest = hashlib.sha256(shared_config).hexdigest()
    original = b"# Shared source\nIdentical exact original bytes.\n"
    observations = []
    for machine in ("machine-a", "machine-b"):
        workspace = harness.base / machine
        workspace.mkdir()
        current = type(harness)(workspace)
        (workspace / "config.yml").write_bytes(shared_config)
        external = workspace / (machine + " documents")
        (external / "nested").mkdir(parents=True)
        (external / "nested/source.md").write_bytes(original)
        current.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
        result = current.run("source", {"operation_id": "prepare-shared"})
        assert result["phase"] == "prepared"
        inventory = current.record(result["data"]["scan_ref"])
        material = current.record(result["data"]["material_ref"])
        bundle = current.record(material["bundle_ref"])
        unit = next(row for row in inventory["units"] if row["path"] == DBOX + "/nested/source.md")
        snapshot = bundle["snapshots"][0]
        assert snapshot["source_id"] == unit["source_id"]
        assert inventory["current_context"]["config_digest"] == shared_digest
        assert (workspace / "config.yml").read_bytes() == shared_config
        observations.append({
            "source_id": unit["source_id"], "snapshot_id": snapshot["snapshot_id"],
            "config_digest": inventory["current_context"]["config_digest"],
            "binding": inventory["dbox_binding"],
        })
    assert observations[0]["binding"] != observations[1]["binding"]
    assert {key: value for key, value in observations[0].items() if key != "binding"} == {
        key: value for key, value in observations[1].items() if key != "binding"
    }


def test_missing_registered_snapshot_cannot_use_new_bytes_or_search_virtual_git_path(harness, monkeypatch):
    shared_config = yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "git-history-oracle",
        "knowledge_roots": {"wifi": harness.root.name}, "code_root": ".", "modules": [],
    }, sort_keys=False).encode()
    (harness.base / "config.yml").write_bytes(shared_config)
    external = harness.base / "registered documents"
    external.mkdir()
    original = b"# Original\nOld synthetic evidence.\n"
    changed = b"# Original\nNew synthetic evidence.\n"
    assert len(original) == len(changed) and hashlib.sha256(original).digest() != hashlib.sha256(changed).digest()
    child = external / "source.md"
    child.write_bytes(original)
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    captured = harness.run("source", {
        "operation_id": "capture-old", "source_id": "registered-dbox-edge",
        "source_path": DBOX + "/source.md",
    }, "capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    ordinary_path = "docs-raw/specs/history.md"
    harness.write(ordinary_path, original)
    ordinary_capture = harness.run("source", {
        "operation_id": "capture-ordinary", "source_id": "ordinary-history-control",
        "source_path": ordinary_path,
    }, "capture")
    ordinary_bundle = harness.record(ordinary_capture["data"]["bundle_ref"])

    # Capture first, then commit the exact originals: recovery must search the
    # registered path's later local history rather than use a direct Git snapshot.
    for captured_bundle in (bundle, ordinary_bundle):
        assert captured_bundle["snapshots"][0]["recovery"]["method"] == "evidence_object"
    virtual_path = DBOX + "/source.md"
    harness.write(virtual_path, original)
    git_environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    git_environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})

    def git(*arguments):
        return subprocess.run([
            "git", "-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgsign=false",
            "-c", "user.name=Synthetic history oracle", "-c", "user.email=fixture@example.invalid",
            "-C", str(harness.base), *arguments,
        ], env=git_environment, capture_output=True, check=True).stdout

    git("init", "--quiet")
    prefix = harness.root.relative_to(harness.base).as_posix()
    git("add", "--", "config.yml", prefix + "/" + ordinary_path, prefix + "/" + virtual_path)
    git("commit", "--quiet", "-m", "Synthetic exact originals for history oracle")
    assert Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() == harness.base.resolve()
    for path in (ordinary_path, virtual_path):
        assert git("cat-file", "blob", "HEAD:" + prefix + "/" + path) == original

    # This creates formal-history fixture bytes; it is not an assertion of P7 execution.
    harness.publish_bundle(bundle)
    harness.publish_bundle(ordinary_bundle)
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": bundle["resources"] + ordinary_bundle["resources"],
        "snapshots": bundle["snapshots"] + ordinary_bundle["snapshots"],
    }, sort_keys=False).encode())
    snapshot = bundle["snapshots"][0]
    ordinary_snapshot = ordinary_bundle["snapshots"][0]
    for captured_bundle in (bundle, ordinary_bundle):
        harness.bundle_path(captured_bundle, captured_bundle["snapshots"][0]["recovery"]["path"]).unlink()
    for reference in {snapshot["recovery"]["path"], ordinary_snapshot["recovery"]["path"]}:
        (harness.root / reference).unlink()
    child.write_bytes(changed)
    harness.write(ordinary_path, changed)
    script = r'''import json, shlex, sys
from pathlib import Path
Path(LOADED).write_bytes(b"loaded")

def audit(event, arguments):
    if event != "subprocess.Popen":
        return
    command = arguments[1]
    argv = command if isinstance(command, (list, tuple)) else shlex.split(command, posix=False)
    executable = arguments[0] or argv[0]
    if Path(str(executable).strip('"')).name.casefold() in {"git", "git.exe"}:
        with Path(ATTEMPTED).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(argv) + "\n")
        if REJECT_GIT:
            raise RuntimeError("SYNTHETIC_FORBIDDEN_GIT_RECOVERY")

sys.addaudithook(audit)
'''
    probes = {}
    for name, reject in (("ordinary history control", False), ("forbid virtual git recovery", True)):
        probe = harness.base / name
        probe.mkdir()
        loaded, attempted = probe / "loaded", probe / "git-attempted.jsonl"
        (probe / "sitecustomize.py").write_text(
            script.replace("LOADED", repr(str(loaded))).replace("ATTEMPTED", repr(str(attempted)))
            .replace("REJECT_GIT", repr(reject)), encoding="utf-8",
        )
        probes[name] = (probe, loaded, attempted)

    def source_ref(selected):
        return {"evidence_ref": "e1", "source_id": selected["source_id"],
                "snapshot_id": selected["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 2}}

    probe, loaded, attempted = probes["ordinary history control"]
    with monkeypatch.context() as environment:
        environment.setenv("PYTHONPATH", str(probe))
        positive = harness.run("source", {
            "operation_id": "ordinary-git-history-control", "source_ref": source_ref(ordinary_snapshot),
        }, "resolve-source")
    assert loaded.read_bytes() == b"loaded"
    commands = [json.loads(line) for line in attempted.read_text(encoding="utf-8").splitlines()]
    assert any("log" in command and prefix + "/" + ordinary_path in command for command in commands)
    assert any("cat-file" in command for command in commands)
    assert positive["data"]["original_ref"].startswith("git:")
    assert positive["data"]["text"] == original.decode()
    assert (harness.root / ordinary_path).read_bytes() == changed

    probe, loaded, attempted = probes["forbid virtual git recovery"]
    with monkeypatch.context() as environment:
        environment.setenv("PYTHONPATH", str(probe))
        result = harness.run("source", {
            "operation_id": "missing-old-snapshot",
            "source_ref": source_ref(snapshot),
        }, "resolve-source", expected=2)
    assert loaded.read_bytes() == b"loaded"
    assert not attempted.exists(), "Virtual dbox paths must not invoke Git history recovery"
    assert result["diagnostics"][0]["code"] == "SOURCE_INPUT_UNAVAILABLE"
    assert child.read_bytes() == changed
    assert (harness.root / virtual_path).read_bytes() == original


@pytest.mark.parametrize("kind", ["file", "linked-directory"])
def test_configure_rejects_non_directory_or_linked_root_without_replacing_old_config(harness, kind):
    local = harness.root / LOCAL
    before = local.read_bytes()
    selected = harness.base / "invalid selected root"
    if kind == "file":
        selected.write_bytes(b"A regular file is not a source directory\n")
        expected_code = "DBOX_ROOT_UNAVAILABLE"
    else:
        target = harness.base / "ordinary link target"
        target.mkdir()
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(selected), str(target)],
                           capture_output=True, check=True)
        else:
            selected.symlink_to(target, target_is_directory=True)
        expected_code = "DBOX_PATH_UNSAFE"
    result = harness.run("source", {
        "operation_id": "reject-root", "path": str(selected),
    }, "configure", expected=2)
    assert result["diagnostics"][0]["code"] == expected_code
    assert local.read_bytes() == before
