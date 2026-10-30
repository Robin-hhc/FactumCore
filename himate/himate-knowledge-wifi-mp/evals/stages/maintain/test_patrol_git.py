"""Native Git observations use real isolated repos; synchronization is fake."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


_spec = importlib.util.spec_from_file_location("patrol_git_fixture_helpers", Path(__file__).resolve().parents[2] / "support/stages/maintain.py")
_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers)
adapter = _helpers.public_module("patrol_git")
validation = _helpers.public_module("validation")


def native(root, *arguments, input=None):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    process = subprocess.run([
        "git", "-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgSign=false",
        "-c", "core.autocrlf=false", "-c", "user.name=Patrol Fixture",
        "-c", "user.email=patrol@example.invalid", "-C", str(root), *arguments,
    ], env=env, input=input, capture_output=True, timeout=30, check=False)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    return process.stdout.decode("utf-8").strip()


def make_repository(root):
    root.mkdir(parents=True)
    native(root, "init", "-b", "main")
    (root / "file.c").write_bytes(b"int selected(void) { return 1; }\n")
    return commit(root)


def commit(root):
    native(root, "add", "--all")
    native(root, "commit", "-m", "isolated fixture")
    return native(root, "rev-parse", "HEAD")


def configured(workspace, modules):
    declared = {"schema_version": "2.0", "workspace_id": "patrol-git", "knowledge_roots": {"wifi": "knowledge"},
                "code_root": "main", "modules": [{"path": path, "chips": ["chip12"], "sides": ["host"]}
                                                   for path in modules]}
    path = workspace / "config.yml"
    raw = json.dumps(declared).encode()
    path.write_bytes(raw)
    return {"path": path, "raw": raw, "config": validation.normalize_workspace(declared, workspace)}


def context(request=None):
    return SimpleNamespace(request=request or {}, modules={"validation": validation})


def observe(config, previous=None):
    return adapter.observe_repositories(context(), config, previous or {})


def test_real_multirepo_commit_changes_and_same_relative_paths_remain_separate(tmp_path):
    host, device = tmp_path / "main/host", tmp_path / "main/device"
    make_repository(host)
    make_repository(device)
    config = configured(tmp_path, ["host", "device"])
    initial = observe(config)
    assert initial["complete"] and all(row["full_scan"] for row in initial["repositories"])
    (host / "file.c").write_bytes(b"int selected(void) { return 2; }\n")
    target = commit(host)
    result = observe(config, initial["heads"])
    rows = {Path(row["root"]).name: row for row in result["repositories"]}
    assert result["complete"]
    assert rows["host"]["head"] == target and rows["host"]["changed_paths"] == ["file.c"]
    assert rows["device"]["changed_paths"] == []
    assert all(not row["full_scan"] and row["dirty_paths"] == [] for row in rows.values())


def test_scope_nested_under_git_root_filters_other_modules_and_maps_paths(tmp_path):
    repository = tmp_path / "main/group"
    make_repository(repository)
    for child in ("host", "device"):
        (repository / child).mkdir()
        (repository / child / "file.c").write_bytes(b"int value;\n")
    commit(repository)
    config = configured(tmp_path, ["group/host"])
    initial = observe(config)
    (repository / "host/file.c").write_bytes(b"int changed;\n")
    (repository / "device/file.c").write_bytes(b"int unrelated;\n")
    commit(repository)
    result = observe(config, initial["heads"])
    row = result["repositories"][0]
    assert result["complete"] and row["git_root"] == str(repository.resolve())
    assert row["changed_paths"] == ["file.c"]
    assert row["dirty_paths"] == []


@pytest.mark.parametrize("relative,authorized", [("file.c", False), ("allowed/conflict.c", True)])
def test_real_unmerged_index_only_blocks_authorized_module_paths(tmp_path, relative, authorized):
    repository = tmp_path / "main/host"
    make_repository(repository)
    (repository / "allowed").mkdir()
    (repository / "allowed/conflict.c").write_bytes(b"int allowed;\n")
    base = commit(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    # A legacy repository can authorize only one architecture subtree even
    # though Git's status describes the enclosing repository checkout.
    for binding in config["config"]["architecture"]:
        binding["module_root"] = "allowed"
    blob = native(repository, "hash-object", "--", "file.c")
    entries = ["0 " + "0" * len(blob) + "\t" + relative]
    entries.extend("100644 " + blob + " " + str(stage) + "\t" + relative for stage in (1, 2, 3))
    native(repository, "update-index", "--index-info", input=("\n".join(entries) + "\n").encode())
    assert len(native(repository, "ls-files", "--unmerged", "--", relative).splitlines()) == 3
    result = observe(config, {identity: base})
    row = result["repositories"][0]
    assert row["dirty_paths"] == ([relative] if authorized else [])
    if authorized:
        assert result["complete"] is False
        assert [(gap["code"], gap["repo_id"], gap["path"]) for gap in result["gaps"]] == [
            ("PATROL_GIT_UNMERGED", identity, relative)]
    else:
        assert result["complete"] is True and result["gaps"] == []


def test_committed_rename_delete_and_chinese_space_paths(tmp_path):
    repository = tmp_path / "main/host"
    make_repository(repository)
    original = repository / "原始 文件.c"
    original.write_bytes(b"int original(void) { return 9; }\n")
    (repository / "delete.c").write_bytes(b"int removed;\n")
    base = commit(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    original.rename(repository / "新的 文件.c")
    (repository / "delete.c").unlink()
    commit(repository)
    result = observe(config, {identity: base})
    row = result["repositories"][0]
    assert result["complete"] and row["dirty_paths"] == []
    assert set(row["changed_paths"]) == {"delete.c", "原始 文件.c", "新的 文件.c"}
    assert row["rename_rows"] == [{"status": "R100", "old_path": "原始 文件.c", "new_path": "新的 文件.c", "kind": "committed"}]


def test_porcelain_combines_staged_unstaged_untracked_and_rename(tmp_path):
    repository = tmp_path / "main/host"
    base = make_repository(repository)
    (repository / "staged.c").write_bytes(b"int staged;\n")
    (repository / "rename old.c").write_bytes(b"int rename_me;\n")
    base = commit(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    (repository / "file.c").write_bytes(b"int unstaged;\n")
    (repository / "staged.c").write_bytes(b"int staged_new;\n")
    native(repository, "add", "staged.c")
    native(repository, "mv", "rename old.c", "rename new.c")
    (repository / "未跟踪 文件.c").write_bytes(b"int untracked;\n")
    row = observe(config, {identity: base})["repositories"][0]
    assert not row["full_scan"] and row["changed_paths"] == []
    assert set(row["dirty_paths"]) == {"file.c", "staged.c", "rename old.c", "rename new.c", "未跟踪 文件.c"}
    assert row["rename_rows"] == [{"status": "R ", "old_path": "rename old.c", "new_path": "rename new.c", "kind": "working_tree"}]


def test_missing_old_commit_and_rewritten_history_require_full_hash_scan(tmp_path):
    repository = tmp_path / "main/host"
    original = make_repository(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    missing = observe(config, {identity: "f" * 40})
    assert missing["complete"] and missing["repositories"][0]["full_scan"]
    assert missing["repositories"][0]["fallback_reason"] == "baseline_unavailable"
    native(repository, "checkout", "--orphan", "rewritten")
    (repository / "file.c").write_bytes(b"int independent_history;\n")
    commit(repository)
    rewritten = observe(config, {identity: original})
    assert rewritten["complete"] and rewritten["repositories"][0]["full_scan"]
    assert rewritten["repositories"][0]["fallback_reason"] == "history_rewritten"


def test_shallow_clone_missing_baseline_does_not_claim_no_changes(tmp_path):
    source = tmp_path / "source"
    original = make_repository(source)
    (source / "file.c").write_bytes(b"int new_value;\n")
    commit(source)
    destination = tmp_path / "main/host"
    destination.parent.mkdir()
    native(tmp_path, "-c", "protocol.file.allow=always", "clone", "--depth=1", source.as_uri(), str(destination))
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    row = observe(config, {identity: original})["repositories"][0]
    assert row["full_scan"] and row["fallback_reason"] == "baseline_unavailable"
    assert row["head"] != original


def test_no_git_and_no_git_executable_are_explicit_full_scan_fallbacks(tmp_path, monkeypatch):
    exported = tmp_path / "main/exported"
    exported.mkdir(parents=True)
    (exported / "file.c").write_bytes(b"int exported;\n")
    config = configured(tmp_path, ["exported"])
    row = observe(config)["repositories"][0]
    assert row["full_scan"] and row["fallback_reason"] == "not_git" and row["head"] is None
    monkeypatch.setenv("PATH", "")
    unavailable = observe(config)
    assert unavailable["complete"]
    assert unavailable["repositories"][0]["fallback_reason"] == "git_unavailable"


def test_invalid_or_missing_authorized_root_is_a_gap(tmp_path):
    repository = tmp_path / "main/host"
    make_repository(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    config["config"]["code_policy"]["repo_roots"][identity] = str(tmp_path)
    result = observe(config)
    assert not result["complete"]
    assert result["gaps"][0]["code"] == "PATROL_REPOSITORY_UNAUTHORIZED"
    config["config"]["code_policy"]["repo_roots"][identity] = str(tmp_path / "absent")
    config["config"]["repos"][0]["root"] = str(tmp_path / "absent")
    result = observe(config)
    assert not result["complete"] and result["repositories"][0]["full_scan"]


def test_inherited_git_repository_and_index_overrides_are_ignored(tmp_path, monkeypatch):
    repository = tmp_path / "main/host"
    expected = make_repository(repository)
    foreign = tmp_path / "foreign"
    make_repository(foreign)
    config = configured(tmp_path, ["host"])
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "wrong-index"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.bare")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    result = observe(config)
    assert result["complete"] and result["repositories"][0]["head"] == expected
    assert not (tmp_path / "wrong-index").exists()


def test_parser_handles_nul_paths_and_rejects_truncated_or_escaping_data():
    rows = adapter.parse_diff("R100\0旧 文件.c\0新 文件.c\0M\0line\nname.c\0".encode())
    assert rows[0]["old_path"] == "旧 文件.c" and rows[1]["new_path"] == "line\nname.c"
    assert adapter.parse_status(b"R  new.c\0old.c\0?? untracked.c\0")[0]["old_path"] == "old.c"
    for raw in (b"M\0file.c", b"R100\0old.c\0", b"M\0../escape\0", b"M\0/absolute\0"):
        with pytest.raises(ValueError):
            adapter.parse_diff(raw)
    with pytest.raises(ValueError):
        adapter.parse_status(b"R  destination.c\0")


def test_git_io_failure_and_head_drift_remain_gaps(tmp_path, monkeypatch):
    repository = tmp_path / "main/host"
    original = make_repository(repository)
    config = configured(tmp_path, ["host"])
    identity = config["config"]["repos"][0]["repo_id"]
    actual = adapter._git

    def inaccessible(root, arguments):
        if arguments[0] == "status":
            return SimpleNamespace(returncode=128, stdout=b"", stderr=b"fatal: Permission denied")
        return actual(root, arguments)

    monkeypatch.setattr(adapter, "_git", inaccessible)
    failed = observe(config, {identity: original})
    assert not failed["complete"] and failed["repositories"][0]["full_scan"]
    assert failed["gaps"][0]["code"] == "PATROL_GIT_UNAVAILABLE"
    calls = 0

    def drift(root, arguments):
        nonlocal calls
        result = actual(root, arguments)
        if arguments[:2] == ["rev-parse", "--verify"]:
            calls += 1
            if calls == 2:
                return SimpleNamespace(returncode=0, stdout=b"e" * 40 + b"\n", stderr=b"")
        return result

    monkeypatch.setattr(adapter, "_git", drift)
    changed = observe(config, {identity: original})
    assert not changed["complete"] and changed["gaps"][0]["code"] == "PATROL_REPOSITORY_CHANGED"


def test_sync_defaults_to_skip_and_explicit_argv_has_no_shell(tmp_path):
    assert adapter.sync(context())[1] == "skipped"
    output = tmp_path / "adapter-observation.json"
    marker = tmp_path / "must-not-exist"
    literal = "literal & echo unexpected > " + str(marker)
    code = "import json,os,sys;open(sys.argv[1],'w',encoding='utf-8').write(json.dumps({'cwd':os.getcwd(),'arg':sys.argv[2]}))"
    request = {"sync": {"argv": [sys.executable, "-c", code, str(output), literal],
                        "cwd": str(tmp_path), "timeout_seconds": 10}}
    result, phase = adapter.sync(context(request))
    actual = json.loads(output.read_text(encoding="utf-8"))
    assert phase == "synced" and result["scope"] == "adapter_command_only"
    assert actual == {"cwd": str(tmp_path), "arg": literal}
    assert not marker.exists()


@pytest.mark.parametrize("command,timeout,expected", [
    (["-c", "import sys; print('failed'); sys.exit(7)"], 10, "PATROL_SYNC_FAILED"),
    (["-c", "import time; time.sleep(20)"], 0.1, "PATROL_SYNC_TIMEOUT"),
])
def test_fake_sync_failure_and_timeout_keep_diagnostics(tmp_path, command, timeout, expected):
    request = {"sync": {"argv": [sys.executable, *command], "cwd": str(tmp_path), "timeout_seconds": timeout}}
    with pytest.raises(ValueError) as error:
        adapter.sync(context(request))
    assert error.value.code == expected and error.value.blocked
    assert error.value.data["adapter_digest"]
    if expected == "PATROL_SYNC_FAILED":
        assert error.value.data["exit_code"] == 7 and "failed" in error.value.data["stdout"]


@pytest.mark.parametrize("sync", [
    {"argv": "git mm sync", "cwd": "relative", "timeout_seconds": 1},
    {"argv": [], "cwd": "relative", "timeout_seconds": 1},
    {"argv": ["git"], "cwd": "relative", "timeout_seconds": True},
    {"argv": ["git"], "cwd": "relative", "timeout_seconds": 0},
    {"argv": ["git"], "cwd": "relative", "timeout_seconds": 1, "shell": True},
])
def test_invalid_sync_configuration_never_starts_a_process(sync, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid adapter configuration started a process")
    monkeypatch.setattr(adapter.subprocess, "Popen", unexpected)
    with pytest.raises(ValueError):
        adapter.sync(context({"sync": sync}))
