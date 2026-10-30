"""Current-input snapshots bind only the actual configured project entry."""

from support import staging as fixture

import os

import pytest
import yaml


inputs = fixture.helper.module("input_snapshot")
runtime = fixture.runtime


def project(tmp_path):
    workspace = tmp_path / "repo"
    root = workspace / "himate" / "knowledge"
    fixture.write(root, "governance/framework.lock.yaml", b"explicit synthetic rules identity\n")
    fixture.write(workspace, "config.yml", yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "entry-fixture",
        "knowledge_roots": {"wifi": "himate/knowledge"}, "code_root": "main", "modules": [],
    }).encode())
    fixture.write(workspace, "AGENTS.md", b"# Actual project entry\n")
    ctx = fixture.make_context(root, "entry")
    ctx.args.rules_digest = runtime.sha((root / "governance/framework.lock.yaml").read_bytes())
    return workspace, root, ctx


def capture(ctx, entry, *, expected=None):
    return inputs.capture_inputs(ctx, material={"current_files": []}, context={
        "current_files": [{"path": entry.as_posix(),
                           "sha256": expected or runtime.sha(entry.read_bytes())}],
    })


def test_current_snapshot_accepts_only_actual_project_entry(tmp_path):
    workspace, _, ctx = project(tmp_path)
    entry = workspace / "AGENTS.md"
    snapshot = capture(ctx, entry)
    observed = snapshot["current_files"][str(entry)]
    assert observed["sha256"] == runtime.sha(b"# Actual project entry\n")
    assert inputs.compare_inputs(ctx, snapshot)["unchanged"]


def test_adopted_entry_drift_is_not_rebound(tmp_path):
    workspace, _, ctx = project(tmp_path)
    entry = workspace / "AGENTS.md"
    expected = runtime.sha(entry.read_bytes())
    snapshot = capture(ctx, entry)
    entry.write_bytes(b"# Changed project entry\n")
    observed = inputs.compare_inputs(ctx, snapshot)
    assert not observed["unchanged"]
    assert any(row.get("path") == str(entry) and row["reason"] == "input_changed"
               for row in observed["changes"])
    with pytest.raises(runtime.NodeError) as error:
        capture(ctx, entry, expected=expected)
    assert error.value.code == "INPUT_CHANGED"


@pytest.mark.parametrize("target", ["peer", "nested-entry", "outside-entry", "traversal", "case-alias"])
def test_project_entry_permission_does_not_broaden_workspace_scope(tmp_path, target):
    workspace, _, ctx = project(tmp_path)
    if target == "peer":
        entry = workspace / "README.md"
    elif target == "nested-entry":
        entry = workspace / "unregistered" / "AGENTS.md"
    elif target == "outside-entry":
        entry = tmp_path / "AGENTS.md"
    elif target == "traversal":
        (workspace / "unregistered").mkdir()
        entry = workspace / "unregistered" / ".." / "AGENTS.md"
    else:
        entry = workspace / "agents.md"
    if target not in {"traversal", "case-alias"}:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"# Unselected input\n")
    with pytest.raises(ValueError) as error:
        capture(ctx, entry, expected=runtime.sha(b"# Unselected input\n"))
    assert error.value.code in {"UNSAFE_PATH", "PATH_CASE_ALIAS"}


def test_project_entry_cannot_be_a_link_alias(tmp_path):
    workspace, _, ctx = project(tmp_path)
    entry = workspace / "AGENTS.md"
    entry.unlink()
    destination = workspace / "actual-entry-directory"
    destination.mkdir()
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(destination), str(entry))
    else:
        entry.symlink_to(destination, target_is_directory=True)
    with pytest.raises(runtime.NodeError) as error:
        capture(ctx, entry, expected=runtime.sha(b"# Unselected input\n"))
    assert error.value.code == "UNSAFE_PATH"
