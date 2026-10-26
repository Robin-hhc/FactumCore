"""Module labels locate actual files without depending on a repository manager."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "workspace_mapping_contract",
    DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)
from workspace_mapping_contract import validation as v  # noqa: E402


def config(*modules):
    return {
        "schema_version": "2.0",
        "workspace_id": "workspace-example",
        "knowledge_roots": {"wifi": "aiotbot-knowledge-wifi-mp"},
        "code_root": "main",
        "modules": list(modules),
    }


def validate(value):
    schema = json.loads((DOMAIN / "governance/schemas/workspace.schema.json").read_text(encoding="utf-8"))
    return v.validate_shape("workspace", value, {"schemas": {"workspace": schema}})


def write(root, ref, data=b"actual selected source\n"):
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def repo_for(normalized, workspace_path):
    return next(item for item in normalized["repos"] if item["workspace_path"] == workspace_path)


def test_minimal_mapping_allows_document_use_before_code_is_available(tmp_path):
    raw = config()
    before = copy.deepcopy(raw)
    assert validate(raw) is raw
    mapped = v.normalize_workspace(raw, tmp_path)
    assert raw == before
    assert mapped["mapping_kind"] == "modules"
    assert mapped["repos"] == []
    assert all(not target["source_bindings"] for target in mapped["targets"])
    assert mapped["layout_gaps"] == [{"code": "code_root_missing", "path": "main"}]
    assert mapped["query"] == {"default_channel": "local", "allowed_channels": ["local"]}


def test_missing_module_records_gap_without_inventing_an_accessible_scope(tmp_path):
    (tmp_path / "main").mkdir()
    mapped = v.normalize_workspace(config({"path": "not-yet-present", "chips": ["chip12"], "sides": ["host"]}), tmp_path)
    assert mapped["repos"] == []
    assert mapped["layout_gaps"] == [{"code": "module_missing", "path": "main/not-yet-present"}]
    assert not v.workspace_file_allowed(mapped, "invented", "file.c")


def test_shared_module_has_explicit_chip_side_membership_and_no_build_facts(tmp_path):
    write(tmp_path, "main/algorithm/src/filter.c")
    raw = config({"path": "algorithm", "chips": ["chip12", "chip08"],
                  "sides": ["host", "device"], "features": ["FILTER_ENABLED"], "description": "Shared algorithm"})
    validate(raw)
    mapped = v.normalize_workspace(raw, tmp_path)
    repo = repo_for(mapped, "main/algorithm")
    assert repo["kind"] == "export" and repo["evidence_basis"] == "filesystem"
    assert repo["expected_identity"] is None
    assert mapped["architecture"][0]["features"] == ["FILTER_ENABLED"]
    assert all(target["build_profile"] is None and target["required_features"] == [] for target in mapped["targets"])
    for target in ("chip12-host", "chip12-device", "chip08-host", "chip08-device"):
        assert v.workspace_file_allowed(mapped, repo["repo_id"], "src/filter.c", target)
    assert not v.workspace_file_allowed(mapped, repo["repo_id"], "src/filter.c", "chip07c-host")


def test_same_relative_file_name_in_different_modules_cannot_cross_targets(tmp_path):
    write(tmp_path, "main/host/src/main.c")
    write(tmp_path, "main/device/src/main.c")
    mapped = v.normalize_workspace(config(
        {"path": "host", "chips": ["chip12"], "sides": ["host"]},
        {"path": "device", "chips": ["chip08"], "sides": ["device"]},
    ), tmp_path)
    host = repo_for(mapped, "main/host")["repo_id"]
    device = repo_for(mapped, "main/device")["repo_id"]
    assert v.workspace_file_allowed(mapped, host, "src/main.c", "chip12-host")
    assert not v.workspace_file_allowed(mapped, host, "src/main.c", "chip08-device")
    assert v.workspace_file_allowed(mapped, device, "src/main.c", "chip08-device")
    assert not v.workspace_file_allowed(mapped, device, "src/main.c", "chip12-host")


def test_more_specific_declared_module_owns_nested_files(tmp_path):
    write(tmp_path, "main/shared/common.c")
    write(tmp_path, "main/shared/special/src/file.c")
    mapped = v.normalize_workspace(config(
        {"path": "shared", "chips": ["chip12"], "sides": ["host"]},
        {"path": "shared/special", "chips": ["chip08"], "sides": ["device"]},
    ), tmp_path)
    parent = repo_for(mapped, "main/shared")["repo_id"]
    child = repo_for(mapped, "main/shared/special")["repo_id"]
    assert v.workspace_file_allowed(mapped, parent, "common.c")
    assert not v.workspace_file_allowed(mapped, parent, "special/src/file.c")
    assert v.workspace_file_allowed(mapped, child, "src/file.c", "chip08-device")
    assert not v.workspace_file_allowed(mapped, child, "src/file.c", "chip12-host")


def test_internal_git_and_manifest_files_are_not_read_or_executed(tmp_path, monkeypatch):
    write(tmp_path, "main/device/source.c")
    write(tmp_path, "main/device/.git", b"unrelated internal repository-manager metadata\n")
    write(tmp_path, "main/device/.repo/manifest.xml", b"not a public manifest format\n")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("Repository commands must not run"))
    original_read = Path.read_bytes

    def read_without_manager_metadata(path):
        assert not {".git", ".repo"}.intersection(path.parts)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_without_manager_metadata)
    mapped = v.normalize_workspace(config({"path": "device"}), tmp_path)
    repo = repo_for(mapped, "main/device")["repo_id"]
    assert v.workspace_file_allowed(mapped, repo, "source.c")
    assert not v.workspace_file_allowed(mapped, repo, ".git")
    assert not v.workspace_file_allowed(mapped, repo, ".repo/manifest.xml")


def test_scope_identity_is_portable_and_metadata_changes_do_not_rename_it(tmp_path):
    first = tmp_path / "first workspace"
    second = tmp_path / "second workspace"
    write(first, "main/device/source.c")
    write(second, "main/device/source.c")
    left = v.normalize_workspace(config({"path": "device", "description": "before"}), first)
    right = v.normalize_workspace(config({"path": "device", "description": "after", "features": ["new-label"]}), second)
    assert left["repos"][0]["repo_id"] == right["repos"][0]["repo_id"]
    assert left["architecture"][0]["binding_id"] == right["architecture"][0]["binding_id"]


def test_unregistered_chip_is_an_architecture_label_without_expanding_claim_scope(tmp_path):
    write(tmp_path, "main/device/source.c")
    raw = config({"path": "device", "chips": ["future-chip"], "sides": ["device"]})
    validate(raw)
    mapped = v.normalize_workspace(raw, tmp_path)
    assert mapped["layout_gaps"][0]["code"] == "non_domain_chip_labels"
    assert not any(target["source_bindings"] for target in mapped["targets"])
    assert not v.workspace_file_allowed(mapped, mapped["repos"][0]["repo_id"], "source.c", "future-chip-device")


@pytest.mark.parametrize("path", ["../escape", "/outside", "C:/outside", "a\\b", "a//b", "a/./b", "a/../b", "a/x:stream", "NUL", "a/trailing."])
def test_unsafe_module_and_code_root_are_rejected(tmp_path, path):
    for raw in (config({"path": path}), {**config(), "code_root": path}):
        with pytest.raises(v.ContractError, match="UNSAFE_WORKSPACE_PATH"):
            v.normalize_workspace(raw, tmp_path)


def test_same_module_path_cannot_be_duplicated_with_conflicting_labels(tmp_path):
    with pytest.raises(v.ContractError, match="WORKSPACE_MODULE_DUPLICATE"):
        validate(config({"path": "device", "chips": ["chip12"]}, {"path": "DEVICE", "chips": ["chip08"]}))


@pytest.mark.parametrize("field,value", [("repos", []), ("architecture", []), ("targets", []), ("pairs", []), ("code_policy", {})])
def test_new_and_legacy_layouts_cannot_be_mixed(field, value):
    with pytest.raises(v.ContractError, match="SCHEMA_INVALID"):
        validate({**config(), field: value})


def test_declared_linked_module_is_rejected_even_with_an_in_workspace_target(tmp_path):
    actual = tmp_path / "main/actual"
    actual.mkdir(parents=True)
    alias = tmp_path / "main/alias"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(actual), str(alias))
    else:
        alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(v.ContractError, match="WORKSPACE_LINKED_PATH"):
        v.normalize_workspace(config({"path": "alias"}), tmp_path)


def test_legacy_registration_is_kept_without_mutating_or_auto_authorizing_it(tmp_path):
    raw = {"repos": [{"repo_id": "old", "kind": "git", "root": ".", "expected_identity": "legacy-origin"}],
           "architecture": [], "targets": [], "pairs": [], "code_policy": {"repo_roots": {"old": str(tmp_path)}}}
    mapped = v.normalize_workspace(raw, tmp_path)
    assert mapped == raw and mapped is not raw
    mapped["repos"][0]["root"] = "changed"
    assert raw["repos"][0]["root"] == "."


def test_scope_file_paths_cannot_escape_or_select_management_data(tmp_path):
    write(tmp_path, "main/device/source.c")
    mapped = v.normalize_workspace(config({"path": "device"}), tmp_path)
    repo = mapped["repos"][0]["repo_id"]
    for relative in ("../other/source.c", "/source.c", "C:/source.c", "nested/.git/config", ".repo/manifest.xml", ".svn/entries"):
        assert not v.workspace_file_allowed(mapped, repo, relative)


@pytest.mark.parametrize("path", [".git", "nested/.repo", ".svn", ".hg"])
def test_management_directories_cannot_be_declared_as_code_scopes(tmp_path, path):
    for raw in (config({"path": path}), {**config(), "code_root": path}):
        with pytest.raises(v.ContractError, match="WORKSPACE_MANAGEMENT_PATH"):
            v.normalize_workspace(raw, tmp_path)
