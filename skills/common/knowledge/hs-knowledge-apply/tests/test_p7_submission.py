"""Read-only submission proof retains real object and process boundaries."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SPEC = importlib.util.spec_from_file_location("p7_submission_helpers", Path(__file__).with_name("p7_test_helpers.py"))
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
SUBMISSION = HELPER.load_contract("submission")


def test_submission_git_reads_cannot_lazy_fetch_or_execute_hooks(tmp_path, monkeypatch):
    commit, content = "1" * 40, b"exact selected bytes\n"
    handoff = {"write_manifest": [{"path": "knowledge/card.md", "sha256": HELPER.sha(content)}],
               "delete_manifest": ["knowledge/deleted.md"],
               "commit_files": ["knowledge/card.md", "knowledge/deleted.md"],
               "view_ref": ".build/operations/op/view.json", "view_digest": "2" * 64,
               "external_obligations": [], "git_merge_verified": False, "remote_push_verified": False}
    saved, calls = {}, []
    context = SimpleNamespace(root=tmp_path, operation="op", rules={},
        modules={"validation": SimpleNamespace(workspace_config_path=lambda root: tmp_path / "config.yml")},
        record=lambda ref: handoff, seal=lambda fields, kind: {**fields, "record_kind": kind},
        save=lambda ref, value: saved.update({ref: value}))
    monkeypatch.setattr(SUBMISSION, "publish_handoff", lambda ctx, request: {"publish_handoff_ref": "ready"})
    monkeypatch.setenv("GIT_DIR", "/unrelated.git")

    def run(command, **kwargs):
        calls.append(command)
        environment = kwargs["env"]
        assert environment["GIT_NO_LAZY_FETCH"] == "1"
        assert environment["GIT_TERMINAL_PROMPT"] == "0" and "GIT_DIR" not in environment
        assert "protocol.allow=never" in command and "protocol.file.allow=never" in command
        assert "core.fsmonitor=false" in command and "diff.external=" in command
        assert any(value.startswith("core.hooksPath=") for value in command)
        assert not set(command) & {"fetch", "push", "merge", "commit", "checkout"}
        code, output = 0, b""
        if "--show-toplevel" in command:
            output = (str(tmp_path) + "\n").encode()
        elif "rev-parse" in command:
            output = (commit + "\n").encode()
        elif "blob" in command:
            output = content
        elif "-e" in command:
            code = 1
        elif "diff-tree" in command:
            output = b"knowledge/card.md\0knowledge/deleted.md\0"
        return SimpleNamespace(returncode=code, stdout=output)

    monkeypatch.setattr(SUBMISSION.subprocess, "run", run)
    result = SUBMISSION.verify_submission(context, {"operation_id": "op", "commit_sha": commit})
    assert result["phase"] == "submitted" and result["commit_sha"] == commit
    assert len(calls) == 6
    assert next(iter(saved.values()))["git_commit_verified"] is True
