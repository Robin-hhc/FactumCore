"""Real CLI calls against file workspaces, with no repository command available."""

import hashlib
import json
import subprocess
import sys

import pytest
import yaml


def mapped_workspace(harness, monkeypatch, *, nested=False):
    workspace = harness.root.parent
    modules = [
        {"path": "host", "chips": ["chip12"], "sides": ["host"], "description": "Host source"},
        {"path": "device", "chips": ["chip12"], "sides": ["device"]},
        {"path": "algorithm", "chips": ["chip12", "chip08"], "sides": ["host", "device"], "features": ["FILTER"]},
    ]
    if nested:
        modules.append({"path": "host/special", "chips": ["chip08"], "sides": ["host"]})
    config = {"schema_version": "2.0", "workspace_id": "file-workspace",
              "knowledge_roots": {"wifi": harness.root.name}, "code_root": "main", "modules": modules}
    config_path = workspace / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    for directory in ["host", "device", "algorithm", *(["host/special"] if nested else [])]:
        path = workspace / "main" / directory / "src/logic.c"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"/* {directory} */\nint result = 1;\n", encoding="utf-8")
    # These manager files are intentionally unusable. New mapping must never
    # inspect them or run any manager command, including for normal raw capture.
    (workspace / "main/host/.git").mkdir()
    (workspace / "main/host/.git/HEAD").write_text("not a Git checkout", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("Test workspace instructions", encoding="utf-8")
    (harness.root / "AGENTS.md").write_text("Test knowledge instructions", encoding="utf-8")
    catalog = json.loads(harness.catalog.read_bytes())
    catalog["workspaces"] = {config["workspace_id"]: {"config": str(config_path), "rules_digest": harness.rules}}
    harness.catalog.write_text(json.dumps(catalog), encoding="utf-8")
    no_commands = workspace / "empty-command-path"
    no_commands.mkdir()
    monkeypatch.setenv("PATH", str(no_commands))
    request, response = workspace / "explore-request.json", workspace / "explore-response.json"
    request.write_text(json.dumps({"operation_id": "explore-files", "target_path": str(workspace / "main")}), encoding="utf-8")
    package = harness.packages / "hs-workspace-explore"
    process = subprocess.run([sys.executable, str(package / "scripts/cli.py"), "--input", str(request),
                              "--output", str(response), "--rules-digest", harness.rules,
                              "--catalog", str(harness.catalog)], capture_output=True, check=False)
    result = json.loads(response.read_bytes())
    assert process.returncode == 0, result
    context_ref = result["data"]["context_ref"]
    context = harness.record(context_ref)
    assert all(item["head"] is None and item["identity"] is None for item in context["repos"].values())
    assert context["mapping_kind"] == "modules"
    return context_ref, {item["workspace_path"]: key for key, item in context["repos"].items()}, config_path


def capture(harness, context_ref, repo_id, operation, relative="src/logic.c", expected=0):
    return harness.run("source-capture", {"operation_id": operation, "kind": "code", "repo_id": repo_id,
                                          "relative_path": relative, "source_id": operation, "context_ref": context_ref}, expected=expected)


def test_file_workspace_discovers_and_captures_host_device_and_shared_without_git(harness, monkeypatch):
    context, repos, _ = mapped_workspace(harness, monkeypatch)
    assert set(repos) == {"main/host", "main/device", "main/algorithm"}
    snapshots = []
    for index, (path, repo_id) in enumerate(repos.items()):
        result = capture(harness, context, repo_id, f"capture-{index}")
        bundle = harness.record(result["data"]["bundle_ref"])
        snapshot = bundle["snapshots"][0]
        assert snapshot["code_identity"]["evidence_basis"] == "filesystem"
        assert snapshot["code_identity"]["workspace_path"] == path
        assert snapshot["code_identity"]["revision"] is None
        assert snapshot["version"] == "unknown"
        assert snapshot["recovery"]["method"] != "git"
        assert snapshot["sha256"] == hashlib.sha256((harness.root.parent / path / "src/logic.c").read_bytes()).hexdigest()
        snapshots.append(snapshot["sha256"])
    assert len(set(snapshots)) == 3


def test_file_workspace_current_source_read_detects_changed_bytes_without_git(harness, monkeypatch):
    context, repos, _ = mapped_workspace(harness, monkeypatch)
    captured = capture(harness, context, repos["main/host"], "capture-read")
    bundle = harness.record(captured["data"]["bundle_ref"])
    snapshot = bundle["snapshots"][0]
    source_ref = {"source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"],
                  "locator": {"kind": "lines", "start": 1, "end": 2}}
    request = {"operation_id": "read-original", "bundle_ref": captured["data"]["bundle_ref"], "source_ref": source_ref}
    original = harness.run("source-capture", request, "resolve-source")
    assert original["data"]["current_source_matches"] is True
    path = harness.root.parent / "main/host/src/logic.c"
    path.write_bytes(b"/* changed */\nint result = 2;\n")
    changed = harness.run("source-capture", {**request, "operation_id": "read-changed"}, "resolve-source")
    assert changed["data"]["current_source_matches"] is False
    assert changed["data"]["text"] == original["data"]["text"]


def test_nested_module_cannot_be_captured_through_parent_identity(harness, monkeypatch):
    context, repos, _ = mapped_workspace(harness, monkeypatch, nested=True)
    rejected = capture(harness, context, repos["main/host"], "wrong-parent", "special/src/logic.c", expected=3)
    assert rejected["diagnostics"][0]["code"] == "CODE_MODULE_UNKNOWN"
    accepted = capture(harness, context, repos["main/host/special"], "right-child")
    assert accepted["phase"] == "captured"


@pytest.mark.parametrize("relative", ["../device/src/logic.c", ".git/HEAD"])
def test_file_workspace_rejects_outside_or_management_source(harness, monkeypatch, relative):
    context, repos, _ = mapped_workspace(harness, monkeypatch)
    denied = capture(harness, context, repos["main/host"], "outside", relative, expected=2 if relative.startswith("..") else 3)
    assert denied["status"] in {"error", "blocked"}


def test_changed_mapping_requires_fresh_context(harness, monkeypatch):
    context, repos, config_path = mapped_workspace(harness, monkeypatch)
    config = yaml.safe_load(config_path.read_bytes())
    config["modules"][0]["description"] = "Updated declaration"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    denied = capture(harness, context, repos["main/host"], "stale-context", expected=3)
    assert denied["diagnostics"][0]["code"] == "CODE_CONTEXT_STALE"


def test_module_capture_does_not_need_repeated_catalog_code_policy(harness, monkeypatch):
    context, repos, _ = mapped_workspace(harness, monkeypatch)
    catalog = json.loads(harness.catalog.read_bytes())
    assert "code_policy" not in catalog
    catalog.pop("workspaces")
    harness.catalog.write_text(json.dumps(catalog), encoding="utf-8")
    denied = capture(harness, context, repos["main/host"], "unregistered", expected=3)
    assert denied["diagnostics"][0]["code"] == "CODE_AUTHORIZATION_REQUIRED"


def test_raw_capture_in_module_workspace_never_uses_git_recovery(harness, monkeypatch):
    mapped_workspace(harness, monkeypatch)
    _, bundle = harness.capture("raw-no-manager")
    assert bundle["snapshots"][0]["recovery"]["method"] != "git"


def test_agent_observed_version_label_is_retained_without_parsing_or_commands(harness, monkeypatch):
    context, repos, _ = mapped_workspace(harness, monkeypatch)
    label = "change_id: example-status-label"
    result = harness.run("source-capture", {"operation_id": "version-label", "kind": "code",
        "repo_id": repos["main/host"], "relative_path": "src/logic.c", "source_id": "observed-version",
        "context_ref": context, "version": label})
    snapshot = harness.record(result["data"]["bundle_ref"])["snapshots"][0]
    assert snapshot["version"] == label
    assert snapshot["code_identity"]["revision"] is None
    assert snapshot["code_identity"]["evidence_basis"] == "filesystem"
