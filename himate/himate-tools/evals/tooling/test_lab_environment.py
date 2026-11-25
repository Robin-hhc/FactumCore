"""Exercise managed test runs without installing or copying runtime dependencies."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest


@pytest.fixture
def lab_source():
    source = Path(__file__).resolve().parents[4] / "dev/lab.py"
    if not source.is_file():
        pytest.skip("Repository development tooling is not part of the standalone CLI package")
    spec = importlib.util.spec_from_file_location("factum_lab_under_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lab(lab_source, monkeypatch, tmp_path):
    module = lab_source
    lock = tmp_path / "requirements.lock.txt"
    lock.write_text("fixture==1.0\n", encoding="utf-8")
    dependency = tmp_path / "external-deps"
    dependency.mkdir()
    monkeypatch.setattr(module, "REQUIREMENTS", lock)
    monkeypatch.setattr(module, "code_revision", lambda: {"head": "fixed-head", "worktree_status": []})
    monkeypatch.setattr(module, "probe_python", lambda executable: {
        "kind": "python", "executable": str(executable), "version": "3.12.10", "platform": sys.platform,
        "arch": "fixture", "requirements_sha256": module.digest(lock), "external_paths": [str(dependency)],
        "owned": False, "read_only": True,
    })
    return module


def prepare(lab, tmp_path):
    root = tmp_path / "lab"
    assert lab.main(["--root", str(root), "init"]) == 0
    assert lab.main(["--root", str(root), "register-python", "--executable", sys.executable]) == 0
    return root


def runner_script(tmp_path, *, passed=True):
    runner = tmp_path / "fake_runner.py"
    runner.write_text("""
import argparse,json,pathlib,shutil,os
p=argparse.ArgumentParser()
p.add_argument('--output-dir');p.add_argument('--temp-dir');p.add_argument('--cleanup-temp')
p.add_argument('--profile');p.add_argument('--jobs');p.add_argument('--groups',nargs='+')
a=p.parse_args();out=pathlib.Path(a.output_dir);out.mkdir();work=pathlib.Path(a.temp_dir);work.mkdir()
(work/'fixture.txt').write_text('failure evidence')
passed=PASSED
removed=passed and a.cleanup_temp=='on-success'
if removed: shutil.rmtree(work)
(out/'summary.json').write_text(json.dumps({'passed':passed,'groups':[{'timed_out':False}],
'python_environment':{key:os.environ.get(key) for key in ['PYTHONPATH','PYTHONHOME','PYTHONNOUSERSITE','PYTHONUSERBASE','PYTHONUTF8','PYTHONDONTWRITEBYTECODE']},
'storage':{'temp_dir':str(work),'cleanup_status':'removed' if removed else 'retained'}}))
raise SystemExit(0 if passed else 2)
""".replace("PASSED", repr(passed)), encoding="utf-8")
    return runner


def test_init_is_idempotent_and_does_not_adopt_historical_runs(lab, tmp_path, capsys):
    root = prepare(lab, tmp_path)
    original = (root / "lab.json").read_bytes()
    old = root / "runs/old-install"
    old.mkdir()
    (old / "run.json").write_text('{"project":"historical"}', encoding="utf-8")
    assert lab.main(["--root", str(root), "init"]) == 0
    assert (root / "lab.json").read_bytes() == original
    assert lab.main(["--root", str(root), "status"]) == 0
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["runs"] == [] and result["unmanaged_run_entries"] == 1
    assert lab.main(["--root", str(root), "clean", "--run", "old-install", "--apply"]) == 2
    assert old.is_dir()


def test_run_success_keeps_report_and_removes_only_work(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path))
    assert lab.main(["--root", str(root), "run", "--run", "unit-one", "--groups", "query"]) == 0
    assert not (root / "runs/unit-one/work").exists()
    assert (root / "reports/unit-one/summary.json").is_file()
    saved = json.loads((root / "reports/unit-one/environment.json").read_text())
    assert saved["status"] == "passed" and saved["pid"] is None
    assert saved["code_revision"]["head"] == "fixed-head"
    assert lab.main(["--root", str(root), "run", "--run", "unit-one"]) == 2


def test_failed_run_retains_evidence_clean_is_preview_then_explicit(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path, passed=False))
    assert lab.main(["--root", str(root), "run", "--run", "failed-one"]) == 2
    fixture = root / "runs/failed-one/work/fixture.txt"
    assert fixture.read_text() == "failure evidence"
    assert lab.main(["--root", str(root), "clean", "--run", "failed-one"]) == 0
    assert fixture.is_file()
    assert lab.main(["--root", str(root), "clean", "--run", "failed-one", "--apply"]) == 0
    assert not fixture.exists()
    assert (root / "reports/failed-one/environment.json").is_file()


def test_keep_temp_pins_run_until_explicit_release(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path))
    assert lab.main(["--root", str(root), "run", "--run", "pinned-one", "--keep-temp"]) == 0
    assert (root / "runs/pinned-one/work/fixture.txt").is_file()
    assert lab.main(["--root", str(root), "clean", "--run", "pinned-one", "--apply"]) == 2
    assert lab.main(["--root", str(root), "pin", "--run", "pinned-one", "--release"]) == 0
    assert lab.main(["--root", str(root), "clean", "--run", "pinned-one", "--apply"]) == 0


def test_requirements_change_rejects_reuse_before_creating_run(lab, tmp_path):
    root = prepare(lab, tmp_path)
    lab.REQUIREMENTS.write_text("fixture==2.0\n", encoding="utf-8")
    assert lab.main(["--root", str(root), "run", "--run", "changed-lock"]) == 2
    assert not (root / "runs/changed-lock").exists()


@pytest.mark.parametrize("identity", ["../escape", "a/b", "a\\b", ".", "..", "C:target"])
def test_run_id_cannot_escape_owned_directories(lab, tmp_path, identity):
    root = prepare(lab, tmp_path)
    assert lab.main(["--root", str(root), "run", "--run", identity]) == 2
    assert list((root / "runs").iterdir()) == []


def test_active_pid_or_running_status_blocks_clean_and_pin(lab, tmp_path):
    root = prepare(lab, tmp_path)
    data = lab.load_lab(root)
    run, report = lab.run_paths(root, "active")
    run.mkdir()
    row = {"schema_version": lab.SCHEMA, "owner_id": data["owner_id"], "run_id": "active",
           "run_dir": str(run), "report_dir": str(report), "status": "failed", "pid": os.getpid(),
           "pinned": False, "process_cleanup_confirmed": True}
    lab.json_write(run / "run.json", row)
    assert lab.main(["--root", str(root), "clean", "--run", "active", "--apply"]) == 2
    assert lab.main(["--root", str(root), "pin", "--run", "active"]) == 2
    row.update(pid=None, status="running")
    lab.json_write(run / "run.json", row)
    assert lab.main(["--root", str(root), "clean", "--run", "active", "--apply"]) == 2


def test_linked_run_content_is_not_followed_or_deleted(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path, passed=False))
    assert lab.main(["--root", str(root), "run", "--run", "linked"]) == 2
    outside = tmp_path / "outside"
    outside.mkdir()
    retained = outside / "important.txt"
    retained.write_text("retain")
    try:
        (root / "runs/linked/work/alias").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink permission is unavailable")
    assert lab.main(["--root", str(root), "clean", "--run", "linked", "--apply"]) == 2
    assert retained.read_text() == "retain"


def test_node_registration_rejects_incompatible_lock(lab, tmp_path):
    root = prepare(lab, tmp_path)
    site = tmp_path / "site"
    (site / "node_modules/dependency").mkdir(parents=True)
    (site / "package.json").write_text('{"dependencies":{"dependency":"1.0.0"}}')
    (site / "package-lock.json").write_text('{"packages":{"node_modules/dependency":{"version":"1.0.0"}}}')
    (site / "node_modules/dependency/package.json").write_text('{"version":"2.0.0"}')
    assert lab.main(["--root", str(root), "register-node", "--site", str(site), "--executable", sys.executable]) == 2
    assert list(lab.load_lab(root)["resources"].values())[0]["kind"] == "python"


def test_node_transitive_installation_lock_must_match_source(lab, tmp_path):
    root = prepare(lab, tmp_path)
    site = tmp_path / "site"
    (site / "node_modules").mkdir(parents=True)
    (site / "package.json").write_text('{"dependencies":{}}')
    (site / "package-lock.json").write_text('{"packages":{"node_modules/transitive":{"version":"1.0.0"}}}')
    (site / "node_modules/.package-lock.json").write_text('{"packages":{"node_modules/transitive":{"version":"2.0.0"}}}')
    assert lab.main(["--root", str(root), "register-node", "--site", str(site), "--executable", sys.executable]) == 2


def test_resource_paths_are_never_clean_targets(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    resource = tmp_path / "external-runtime"
    resource.mkdir()
    (resource / "file").write_text("retained")
    assert lab.main(["--root", str(root), "clean", "--run", str(resource), "--apply"]) == 2
    assert (resource / "file").read_text() == "retained"


def test_registered_resource_inside_owned_run_prevents_deletion(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path, passed=False))
    assert lab.main(["--root", str(root), "run", "--run", "adopted"]) == 2
    resource = root / "runs/adopted/work/runtime"
    resource.mkdir()
    (resource / "important").write_text("retained")
    item = {"kind": "node", "version": "v24.0.0", "platform": sys.platform, "arch": "test",
            "node_modules": str(resource), "package_lock_sha256": "f" * 64, "owned": False}
    lab.register(root, item, False)
    assert lab.main(["--root", str(root), "clean", "--run", "adopted", "--apply"]) == 2
    assert (resource / "important").read_text() == "retained"


def test_status_lists_only_safe_host_metadata(lab, tmp_path, capsys):
    root = prepare(lab, tmp_path)
    host = root / "hosts/cold"
    host.mkdir()
    lab.json_write(host / "launch.json", {"schemaVersion": 1, "port": 58880, "pinned": True,
                                         "unrelated_secret": "must-not-appear"})
    assert lab.main(["--root", str(root), "status"]) == 0
    output = capsys.readouterr().out.splitlines()[-1]
    assert "must-not-appear" not in output
    assert json.loads(output)["hosts"] == [{"name": "cold", "configuration": str(host / "launch.json"),
                                            "port": 58880, "pinned": True}]


def test_clean_serializes_with_pin_and_resource_registration(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path, passed=False))
    assert lab.main(["--root", str(root), "run", "--run", "race"]) == 2
    scanned = threading.Event()
    proceed = threading.Event()
    original = os.scandir

    def pause_scan(directory):
        if isinstance(directory, (str, os.PathLike)) and Path(directory) == root / "runs/race/work":
            scanned.set()
            assert proceed.wait(10), "The concurrent operation did not release the scan"
        return original(directory)

    monkeypatch.setattr(lab.os, "scandir", pause_scan)
    with ThreadPoolExecutor(max_workers=1) as pool:
        cleanup = pool.submit(lab.main, ["--root", str(root), "clean", "--run", "race", "--apply"])
        assert scanned.wait(10), "Cleanup did not reach the run payload"
        try:
            pin_code = lab.main(["--root", str(root), "pin", "--run", "race"])
            register_code = lab.main(["--root", str(root), "register-python", "--executable", sys.executable])
        finally:
            proceed.set()
        assert cleanup.result(timeout=10) == 0
    assert pin_code == register_code == 2
    assert not (root / "runs/race").exists()
    assert not (root / ".lab.lock").exists()


def test_run_removes_caller_python_environment_selection(lab, monkeypatch, tmp_path):
    root = prepare(lab, tmp_path)
    monkeypatch.setattr(lab, "RUNNER", runner_script(tmp_path))
    injected = tmp_path / "injected-modules"
    injected.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(injected))
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "invalid-python-home"))
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path / "caller-userbase"))
    monkeypatch.setenv("PYTHONUTF8", "1")
    assert lab.main(["--root", str(root), "run", "--run", "clean-python"]) == 0
    report = json.loads((root / "reports/clean-python/summary.json").read_text())
    assert report["python_environment"] == {"PYTHONPATH": None, "PYTHONHOME": None,
                                            "PYTHONNOUSERSITE": None, "PYTHONUSERBASE": None,
                                            "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def test_python_probe_ignores_caller_import_and_home_selection(lab_source, monkeypatch, tmp_path):
    lock = tmp_path / "requirements.lock.txt"
    lock.write_text("# No dependencies for this interpreter probe\n", encoding="utf-8")
    injected = tmp_path / "caller-pythonpath"
    injected.mkdir()
    monkeypatch.setattr(lab_source, "REQUIREMENTS", lock)
    monkeypatch.setenv("PYTHONPATH", str(injected))
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "invalid-python-home"))
    data = lab_source.probe_python(Path(sys.executable))
    assert str(injected) not in data["external_paths"]
    assert data["requirements_sha256"] == lab_source.digest(lock)


@pytest.mark.parametrize("handle,error,query,exit_code,expected", [
    (123, 0, True, 259, True),
    (123, 0, True, 0, False),
    (123, 0, False, 0, True),
    (0, 87, False, 0, False),
    (0, 5, False, 0, True),
])
def test_windows_pid_query_retains_unknown_processes_and_closes_handles(
        lab, monkeypatch, handle, error, query, exit_code, expected):
    calls = []

    def open_process(access, inherit, pid):
        calls.append(("open", access, inherit, pid))
        return handle

    def exit_process(process, destination):
        calls.append(("query", process))
        destination._obj.value = exit_code
        return query

    kernel = SimpleNamespace(OpenProcess=open_process, GetExitCodeProcess=exit_process,
                             CloseHandle=lambda process: calls.append(("close", process)))
    monkeypatch.setattr(lab, "windows_process_api", lambda: (kernel, lambda: error))
    monkeypatch.setattr(lab, "os", SimpleNamespace(name="nt"))
    assert lab.pid_alive(456) is expected
    assert calls == [("open", 0x1000, False, 456)] + (
        [("query", handle), ("close", handle)] if handle else [])


@pytest.mark.parametrize("failure,expected", [(None, True), (ProcessLookupError(), False),
                                            (PermissionError(), True), (OSError(), True)])
def test_posix_pid_query_is_conservative(lab, monkeypatch, failure, expected):
    calls = []

    def kill(pid, signal):
        calls.append((pid, signal))
        if failure is not None:
            raise failure

    monkeypatch.setattr(lab, "os", SimpleNamespace(name="posix", kill=kill))
    assert lab.pid_alive(456) is expected
    assert calls == [(456, 0)]


@pytest.mark.parametrize("pid,expected", [(None, False), (0, True), (-1, True), ("invalid", True),
                                        (2 ** 40, True)])
def test_invalid_pid_cannot_authorize_cleanup(lab, pid, expected):
    assert lab.pid_alive(pid) is expected
