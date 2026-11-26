"""Exercise repository operations in real local Git repositories only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOL_ROOT / "runtime"))
from himate_knowledge import cli, repository  # noqa: E402
from himate_knowledge.protocol import NodeError  # noqa: E402


MESSAGE = ("Description:知识变更摘要\nDTS:opaque 12\n\nTeam:WIFI\n"
           "Feature or Bugfix:Feature\n\nChange-Id:Ideadbeef\n")


def git(root, *arguments):
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("GIT_")}
    result = subprocess.run(["git", *arguments], cwd=root, env=environment,
                            capture_output=True, encoding="utf-8", errors="replace", timeout=15)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "himate-knowledge-wifi-mp"
    root.mkdir()
    try:
        git(root, "init", "--quiet", "--initial-branch=master")
        git(root, "config", "user.name", "Synthetic Repo Test")
        git(root, "config", "user.email", "repo-test@example.invalid")
        git(root, "config", "core.autocrlf", "false")
        hooks = tmp_path / "empty-hooks"
        hooks.mkdir()
        git(root, "config", "core.hooksPath", str(hooks))
        (root / "docs-raw").mkdir()
        (root / "knowledge").mkdir()
        (root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "--quiet", "-m", "Synthetic master baseline")
        git(root, "update-ref", "refs/remotes/origin/master", "HEAD")
        yield root
    finally:
        # Git creates read-only objects on Windows; only restore the objects
        # owned by this fixture so the acceptance runner can reclaim its run.
        for path in (root / ".git/objects").rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(path.stat().st_mode | stat.S_IWUSR)


def modify(root):
    (root / "baseline.txt").write_text("updated baseline\n", encoding="utf-8")
    (root / "knowledge/new.md").write_text("# Synthetic knowledge\n", encoding="utf-8")
    (root / "docs-raw/source.md").write_text("# Synthetic source\n", encoding="utf-8")


def stub_upload(tmp_path, monkeypatch, *, output="https://local.invalid/change_requests/12 [CR CREATED]", code=0):
    directory = tmp_path / "git-stubs"
    directory.mkdir(exist_ok=True)
    script = directory / "git-mm"
    script.write_text("#!/bin/sh\n[ \"$1 $2 $3\" = \"upload . -y\" ] || exit 99\n"
                      + "printf '%s\\n' '" + output + "'\nexit " + str(code) + "\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])


def direct_cli(root, request, action, tmp_path, capsys):
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    code = cli.main(["repo", action, "--knowledge-root", str(root),
                     "--input", str(request_path), "--json"],
                    tool_root=TOOL_ROOT, manifest={"version": "test", "assets": {
                        "runtime/governance/framework.lock.yaml": {"sha256": "unused-by-repo"}}})
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def test_status_is_read_only_and_reports_raw_git_state(repo):
    modify(repo)
    index = (repo / ".git/index").read_bytes()
    data, phase = repository.run(repo, "status", {})
    assert phase == "ready"
    assert data["knowledge_root"] == str(repo.resolve())
    assert data["branch"] == "master"
    assert data["pending_commits"] == 0
    assert data["latest_commit"]["sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert data["latest_commit"]["message"] == "Synthetic master baseline\n"
    assert data["latest_commit"]["change_id"] is None and data["dts"] is None
    assert data["changes"] == git(repo, "status", "--short")
    assert (repo / ".git/index").read_bytes() == index
    assert not (repo / ".gitignore").exists() and not (repo / ".scratch").exists()


@pytest.mark.parametrize("message", [MESSAGE, "Alternative template\n\n# Keep this literal comment\nBody: value\n\nTeam:OTHER\n",
                                     "Message without a trailing newline"])
def test_create_stages_all_and_passes_full_message_without_template_rules(repo, message):
    modify(repo)
    (repo / ".scratch").mkdir()
    (repo / ".scratch/private.txt").write_text("local-only", encoding="utf-8")
    dts = "  opaque user value / 12  "
    data, phase = repository.run(repo, "commit", {"approved": True, "message": message, "dts": dts})
    assert phase == "committed" and data["mode"] == "create" and not data["uploaded"]
    assert data["pending_commits"] == 1
    assert data["commit_sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert git(repo, "log", "-1", "--format=format:%B") == message
    assert set(git(repo, "show", "--format=", "--name-only", "HEAD").splitlines()) == {
        ".gitignore", "baseline.txt", "docs-raw/source.md", "knowledge/new.md"}
    assert git(repo, "status", "--short") == ""
    assert json.loads((repo / repository.DTS_RECORD).read_text(encoding="utf-8")) == {"dts": dts}
    assert repository.run(repo, "status", {})[0]["dts"] == dts
    assert ["git", "add", "."] in [item["argv"] for item in data["commands"]]
    assert ["git", "commit", "--cleanup=verbatim", "--file", "-"] in [item["argv"] for item in data["commands"]]


def test_amend_preserves_message_change_id_and_parent_even_with_new_message(repo):
    modify(repo)
    first, _ = repository.run(repo, "commit", {"approved": True, "message": MESSAGE})
    parent = git(repo, "rev-parse", "HEAD^")
    original = git(repo, "log", "-1", "--format=format:%B")
    modify(repo)
    (repo / "knowledge/new.md").write_text("amended\n", encoding="utf-8")
    data, phase = repository.run(repo, "commit", {"approved": True, "message": "Ignored replacement"})
    assert phase == "committed" and data["mode"] == "amend"
    assert data["commit_sha"] != first["commit_sha"]
    assert data["pending_commits"] == 1 and data["change_id"] == "Ideadbeef"
    assert git(repo, "rev-parse", "HEAD^") == parent
    assert git(repo, "log", "-1", "--format=format:%B") == original
    assert [item["argv"] for item in data["commands"] if item["argv"][1] == "commit"] == [
        ["git", "commit", "--amend", "--no-edit"]]
    # No message is required when the latest pending commit is amended.
    assert repository.run(repo, "commit", {"approved": True})[0]["mode"] == "amend"


def test_multiple_pending_commits_still_amend_only_the_latest(repo):
    git(repo, "commit", "--allow-empty", "--quiet", "-m", "First pending")
    git(repo, "commit", "--allow-empty", "--quiet", "-m", MESSAGE)
    parent = git(repo, "rev-parse", "HEAD^")
    data, _ = repository.run(repo, "commit", {"approved": True})
    assert data["mode"] == "amend" and data["pending_commits"] == 2
    assert git(repo, "rev-parse", "HEAD^") == parent
    assert data["latest_commit"]["message"] == MESSAGE


def test_change_id_header_is_case_insensitive(repo):
    data, _ = repository.run(repo, "commit", {"approved": True,
                                            "message": MESSAGE.replace("Change-Id:", "change-id:")})
    assert data["change_id"] == "Ideadbeef"
    assert repository.run(repo, "status", {})[0]["latest_commit"]["change_id"] == "Ideadbeef"


@pytest.mark.parametrize("payload,code", [
    ({}, "REPO_APPROVAL_REQUIRED"), ({"approved": 1}, "REPO_APPROVAL_REQUIRED"),
    ({"approved": False}, "REPO_APPROVAL_REQUIRED"),
    ({"approved": True, "message": " "}, "INVALID_INPUT"),
    ({"approved": True, "dts": " "}, "INVALID_INPUT"),
    ({"approved": True, "upload": "false"}, "INVALID_INPUT"),
    ({"approved": True, "argv": ["reset"]}, "INVALID_INPUT"),
    ({"approved": True, "root": "elsewhere"}, "INVALID_INPUT"),
    ({"approved": True}, "REPO_MESSAGE_REQUIRED"),
])
def test_invalid_requests_do_not_stage_or_write(repo, payload, code):
    before = git(repo, "rev-parse", "HEAD")
    with pytest.raises(NodeError) as error:
        repository.run(repo, "commit", payload)
    assert error.value.code == code
    assert git(repo, "rev-parse", "HEAD") == before
    assert not (repo / ".gitignore").exists() and not (repo / ".scratch").exists()
    assert git(repo, "diff", "--cached", "--name-only") == ""


def test_status_rejects_input_and_actual_git_root_is_required(repo):
    with pytest.raises(NodeError) as error:
        repository.run(repo, "status", {"approved": True})
    assert error.value.code == "INVALID_INPUT"
    with pytest.raises(NodeError) as error:
        repository.run(repo / "knowledge", "status", {})
    assert error.value.code == "REPO_ROOT_REQUIRED"


def test_missing_origin_master_stops_without_writes(repo):
    git(repo, "update-ref", "-d", "refs/remotes/origin/master")
    with pytest.raises(repository.RepositoryError) as error:
        repository.run(repo, "commit", {"approved": True, "message": MESSAGE})
    assert error.value.data["commands"][-1]["argv"] == ["git", "rev-list", "--count", "origin/master..HEAD"]
    assert not (repo / ".gitignore").exists()


def test_existing_scratch_ignore_is_not_rewritten_and_tracked_state_is_rejected(repo):
    content = "# local state\n/.scratch/\n"
    (repo / ".gitignore").write_text(content, encoding="utf-8")
    data, _ = repository.run(repo, "commit", {"approved": True, "message": MESSAGE})
    assert (repo / ".gitignore").read_text(encoding="utf-8") == content
    assert data["pending_commits"] == 1
    (repo / ".scratch").mkdir()
    (repo / ".scratch/tracked.txt").write_text("tracked", encoding="utf-8")
    git(repo, "add", "--force", ".scratch/tracked.txt")
    with pytest.raises(repository.RepositoryError) as error:
        repository.run(repo, "commit", {"approved": True})
    assert error.value.code == "REPO_SCRATCH_TRACKED"


@pytest.mark.parametrize("output", [
    "https://local.invalid/reviews/7 [CR UPDATED]",
    "uploaded https://local.invalid/change_requests/12",
])
def test_upload_uses_fixed_local_stub_and_preserves_helper_cr_parsing(repo, tmp_path, monkeypatch, output):
    stub_upload(tmp_path, monkeypatch, output=output)
    data, phase = repository.run(repo, "commit", {"approved": True, "message": MESSAGE, "upload": True})
    assert phase == "uploaded" and data["uploaded"]
    assert data["cr_url"] in output
    assert data["commands"][-1]["argv"] == ["git", "mm", "upload", ".", "-y"]
    assert data["commands"][-1]["returncode"] == 0


@pytest.mark.parametrize("output,code,diagnostic", [
    ("synthetic upload failure", 9, "REPO_COMMAND_FAILED"),
    ("no CR link here", 0, "REPO_CR_URL_MISSING"),
])
def test_upload_failure_keeps_local_commit_commands_and_dts_in_cli_json(
        repo, tmp_path, monkeypatch, capsys, output, code, diagnostic):
    stub_upload(tmp_path, monkeypatch, output=output, code=code)
    status, result = direct_cli(repo, {"approved": True, "message": MESSAGE, "dts": "opaque",
                                      "upload": True}, "commit", tmp_path, capsys)
    assert status == 2 and result["status"] == "error" and result["phase"] == "failed"
    assert result["diagnostics"][0]["code"] == diagnostic
    data = result["data"]
    assert data["completed_phase"] == "committed" and data["failed_phase"] == "upload"
    assert data["commit_sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert data["pending_commits"] == 1 and not data["uploaded"]
    assert data["dts"] == "opaque" and data["commands"][-1]["returncode"] == code
    assert len([item for item in data["commands"] if item["argv"][1:3] == ["mm", "upload"]]) == 1


def test_commit_failure_does_not_upload_or_save_dts(repo, tmp_path, monkeypatch):
    stub_upload(tmp_path, monkeypatch)
    (repo / ".gitignore").write_text("/.scratch/\n", encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "--quiet", "-m", "Ignore baseline")
    git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
    with pytest.raises(repository.RepositoryError) as error:
        repository.run(repo, "commit", {"approved": True, "message": MESSAGE, "dts": "not saved", "upload": True})
    assert error.value.data["completed_phase"] == "staged"
    assert error.value.data["commands"][-1]["argv"][1] == "commit"
    assert not (repo / repository.DTS_RECORD).exists()


def test_shared_operation_budget_timeout_retains_commit_and_does_not_retry(repo, monkeypatch):
    original = subprocess.run
    timeouts = []

    def run(argv, **kwargs):
        timeouts.append(kwargs["timeout"])
        if argv[1:3] == ["mm", "upload"]:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=b"partial output", stderr=b"partial error")
        return original(argv, **kwargs)

    monkeypatch.setattr(repository.subprocess, "run", run)
    with pytest.raises(repository.RepositoryError) as error:
        repository.run(repo, "commit", {"approved": True, "message": MESSAGE, "upload": True})
    assert error.value.code == "REPO_COMMAND_TIMEOUT"
    data = error.value.data
    assert data["commit_sha"] and data["completed_phase"] == "committed"
    assert data["commands"][-1]["stdout"] == "partial output"
    assert data["commands"][-1]["stderr"] == "partial error"
    assert data["commands"][-1]["returncode"] is None
    assert 0 < timeouts[-1] < timeouts[0] <= 110


@pytest.mark.parametrize("timeout", [False, True])
def test_post_commit_inspection_failure_keeps_already_read_sha(repo, monkeypatch, timeout):
    original = subprocess.run
    counts = 0

    def run(argv, **kwargs):
        nonlocal counts
        if argv[1] == "rev-list":
            counts += 1
            if counts == 2:
                if timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                return subprocess.CompletedProcess(argv, 7, stdout=b"", stderr=b"synthetic inspection failure")
        return original(argv, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(repository.subprocess, "run", run)
        with pytest.raises(repository.RepositoryError) as error:
            repository.run(repo, "commit", {"approved": True, "message": MESSAGE, "upload": True})
    data = error.value.data
    assert data["completed_phase"] == "committed" and data["failed_phase"] == "inspect"
    assert data["commit_sha"] == git(repo, "rev-parse", "HEAD").strip()
    assert data["change_id"] == "Ideadbeef"
    assert data["commands"][-1]["argv"] == ["git", "rev-list", "--count", "origin/master..HEAD"]
    assert error.value.code == ("REPO_COMMAND_TIMEOUT" if timeout else "REPO_COMMAND_FAILED")


def test_inherited_git_dir_cannot_redirect_the_selected_root(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other.git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "other-index"))
    data, _ = repository.run(repo, "commit", {"approved": True, "message": MESSAGE})
    assert data["knowledge_root"] == str(repo.resolve())
    assert not (tmp_path / "other-index").exists()


def test_git_authentication_and_author_environment_are_preserved(repo, monkeypatch):
    original = subprocess.run
    environments = []

    def run(argv, **kwargs):
        environments.append(kwargs["env"])
        return original(argv, **kwargs)

    monkeypatch.setenv("GIT_SSH_COMMAND", "synthetic-ssh --identity local-key")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Environment Author")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "environment-author@example.invalid")
    with monkeypatch.context() as context:
        context.setattr(repository.subprocess, "run", run)
        repository.run(repo, "commit", {"approved": True, "message": MESSAGE})
    assert all(environment["GIT_SSH_COMMAND"] == "synthetic-ssh --identity local-key"
               and environment["GIT_AUTHOR_NAME"] == "Environment Author"
               for environment in environments)
    assert git(repo, "log", "-1", "--format=format:%an <%ae>") == (
        "Environment Author <environment-author@example.invalid>")


@pytest.mark.parametrize("input_kind", ["file", "stdin"])
def test_public_cli_status_create_and_amend(repo, tmp_path, input_kind):
    def invoke(action, request):
        path = tmp_path / "public-request.json"
        path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(TOOL_ROOT / "knowledge.py"), "repo", action,
                                 "--knowledge-root", str(repo), "--input", "-" if input_kind == "stdin" else str(path),
                                 "--json"], input=json.dumps(request), cwd=repo,
                                capture_output=True, encoding="utf-8", timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    status = invoke("status", {})
    assert status["status"] == "ok" and status["phase"] == "ready"
    created = invoke("commit", {"approved": True, "message": MESSAGE})
    assert created["phase"] == "committed" and created["data"]["mode"] == "create"
    amended = invoke("commit", {"approved": True})
    assert amended["data"]["mode"] == "amend"
    assert amended["data"]["latest_commit"]["message"] == MESSAGE
