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
        "knowledge_roots": {"wifi": "himate-knowledge-wifi-mp"},
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


def test_workspace_schema_accepts_named_domains_without_a_wifi_entry():
    raw = {**config(), "knowledge_roots": {"bluetooth": "himate/himate-knowledge-bluetooth"}}
    assert validate(raw) is raw


def test_workspace_schema_accepts_multiple_named_knowledge_roots():
    raw = {**config(), "knowledge_roots": {
        "wifi": "himate/himate-knowledge-wifi",
        "bluetooth": "himate/himate-knowledge-bluetooth",
    }}
    assert validate(raw) is raw


@pytest.mark.parametrize("roots", [{}, {"": "himate/domain"}, {"bluetooth": ""}, {"bluetooth": 42}])
def test_workspace_schema_rejects_empty_or_invalid_knowledge_roots(roots):
    with pytest.raises(v.ContractError, match="SCHEMA_INVALID"):
        validate({**config(), "knowledge_roots": roots})


@pytest.mark.parametrize("domain", ["wifi", "bluetooth"])
def test_explicit_legacy_config_still_selects_current_root(tmp_path, domain):
    roots = {"wifi": "himate/himate-knowledge-wifi", "bluetooth": "himate/himate-knowledge-bluetooth"}
    for relative in roots.values():
        (tmp_path / relative).mkdir(parents=True)
    configuration = write(tmp_path, "config.yml", json.dumps({**config(), "knowledge_roots": roots}).encode())
    assert v.workspace_config_path(tmp_path / roots[domain], config_path=configuration) == configuration.resolve()


def test_workspace_uses_its_local_config_and_preserves_module_identities(tmp_path):
    root = tmp_path / "himate/domain"
    root.mkdir(parents=True)
    write(tmp_path, "main/host/driver.c")
    legacy = {**config({"path": "host"}), "knowledge_roots": {"domain": "himate/domain"}}
    write(tmp_path, "config.yml", json.dumps(legacy).encode())
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_UNAVAILABLE"):
        v.workspace_config_path(root)

    local = {**legacy, "code_root": "../../main"}
    del local["knowledge_roots"]
    assert validate(local) is local
    configuration = write(root, "config.yml", json.dumps(local).encode())
    assert v.workspace_config_path(root) == configuration.resolve()
    old, new = v.normalize_workspace(legacy, tmp_path), v.normalize_workspace(local, root)
    assert new["workspace_root"] == old["workspace_root"] == str(tmp_path)
    assert new["code_root_path"] == old["code_root_path"] == str(tmp_path / "main")
    assert new["repos"] == old["repos"]
    assert new["architecture"] == old["architecture"]

    other = write(tmp_path, "other/config.yml", json.dumps(local).encode())
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_UNAVAILABLE"):
        v.workspace_config_path(root, config_path=other)


def test_terminal_parent_hops_preserve_manifest_root_as_code_root(tmp_path):
    root = tmp_path / "himate/domain"
    root.mkdir(parents=True)
    write(tmp_path, "host/driver.c")
    legacy = {**config({"path": "host"}), "code_root": "."}
    local = {**legacy, "code_root": "../.."}
    del local["knowledge_roots"]
    assert validate(local) is local
    old, new = v.normalize_workspace(legacy, tmp_path), v.normalize_workspace(local, root)
    assert new["code_root_path"] == str(tmp_path)
    assert new["repos"] == old["repos"]


@pytest.mark.parametrize("path", ["main/../outside", "../main/../outside", "../", "../.", "/main", "C:/main"])
def test_knowledge_root_config_only_accepts_leading_parent_hops(tmp_path, path):
    raw = config()
    del raw["knowledge_roots"]
    with pytest.raises(v.ContractError, match="UNSAFE_WORKSPACE_PATH"):
        v.normalize_workspace({**raw, "code_root": path}, tmp_path)


def test_workspace_config_rejects_two_domain_names_for_the_same_root(tmp_path):
    root = tmp_path / "himate/himate-knowledge-bluetooth"
    root.mkdir(parents=True)
    roots = {"bluetooth": "himate/himate-knowledge-bluetooth", "alias": "himate/himate-knowledge-bluetooth"}
    configuration = write(tmp_path, "config.yml", json.dumps({**config(), "knowledge_roots": roots}).encode())
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_AMBIGUOUS"):
        v.workspace_config_path(root, config_path=configuration)


def test_workspace_config_checks_other_domain_paths_before_selecting_current_root(tmp_path):
    root = tmp_path / "himate/himate-knowledge-bluetooth"
    root.mkdir(parents=True)
    roots = {"bluetooth": "himate/himate-knowledge-bluetooth", "unsafe": "../outside"}
    configuration = write(tmp_path, "config.yml", json.dumps({**config(), "knowledge_roots": roots}).encode())
    with pytest.raises(v.ContractError, match="UNSAFE_WORKSPACE_PATH"):
        v.workspace_config_path(root, config_path=configuration)


def test_workspace_config_does_not_select_an_unmapped_knowledge_root(tmp_path):
    root = tmp_path / "himate/himate-knowledge-bluetooth"
    root.mkdir(parents=True)
    configuration = write(tmp_path, "config.yml", json.dumps(config()).encode())
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_UNAVAILABLE"):
        v.workspace_config_path(root, config_path=configuration)


def test_minimal_mapping_allows_document_use_before_code_is_available(tmp_path):
    raw = config()
    before = copy.deepcopy(raw)
    assert validate(raw) is raw
    mapped = v.normalize_workspace(raw, tmp_path)
    assert raw == before
    assert mapped["mapping_kind"] == "modules"
    assert mapped["repos"] == []
    assert mapped["targets"] == []
    assert mapped["pairs"] == []
    assert mapped["layout_gaps"] == [{"code": "code_root_missing", "path": "main"}]
    assert mapped["query"] == {"default_channel": "local", "allowed_channels": ["local"]}


def test_missing_module_records_gap_without_inventing_an_accessible_scope(tmp_path):
    (tmp_path / "main").mkdir()
    mapped = v.normalize_workspace(config({"path": "not-yet-present", "chips": ["soc-next"], "sides": ["host"]}), tmp_path)
    assert mapped["repos"] == []
    assert [(target["target_id"], target["source_bindings"]) for target in mapped["targets"]] == [("soc-next-host", [])]
    assert mapped["pairs"] == []
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
    assert {target["target_id"] for target in mapped["targets"]} == {
        "chip12-host", "chip12-device", "chip08-host", "chip08-device",
    }
    assert {pair["pairing_id"] for pair in mapped["pairs"]} == {"chip12-host-device", "chip08-host-device"}
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
    assert {target["target_id"] for target in mapped["targets"]} == {"chip12-host", "chip08-device"}
    assert mapped["pairs"] == []
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


def test_custom_chip_creates_only_its_configured_target_and_code_scope(tmp_path):
    write(tmp_path, "main/device/source.c")
    raw = config({"path": "device", "chips": ["future-chip"], "sides": ["device"]})
    validate(raw)
    mapped = v.normalize_workspace(raw, tmp_path)
    assert mapped["layout_gaps"] == []
    assert [target["target_id"] for target in mapped["targets"]] == ["future-chip-device"]
    assert mapped["pairs"] == []
    repo_id = mapped["repos"][0]["repo_id"]
    assert v.workspace_file_allowed(mapped, repo_id, "source.c", "future-chip-device")
    assert not v.workspace_file_allowed(mapped, repo_id, "source.c", "future-chip-host")
    assert not v.workspace_file_allowed(mapped, repo_id, "source.c", "chip12-device")


def test_replacing_module_configuration_replaces_targets_and_file_bindings(tmp_path):
    write(tmp_path, "main/previous/source.c")
    write(tmp_path, "main/current/source.c")
    previous = v.normalize_workspace(config({"path": "previous", "chips": ["soc-old"], "sides": ["host"]}), tmp_path)
    current = v.normalize_workspace(config({"path": "current", "chips": ["soc-new"], "sides": ["device"]}), tmp_path)
    assert [target["target_id"] for target in previous["targets"]] == ["soc-old-host"]
    assert [target["target_id"] for target in current["targets"]] == ["soc-new-device"]
    current_repo = repo_for(current, "main/current")["repo_id"]
    previous_repo = repo_for(previous, "main/previous")["repo_id"]
    assert v.workspace_file_allowed(current, current_repo, "source.c", "soc-new-device")
    assert not v.workspace_file_allowed(current, current_repo, "source.c", "soc-old-host")
    assert not v.workspace_file_allowed(current, previous_repo, "source.c")


def test_same_chip_side_combines_only_its_actual_module_bindings(tmp_path):
    for module in ("host-driver", "host-shared", "device-driver"):
        write(tmp_path, f"main/{module}/source.c")
    mapped = v.normalize_workspace(config(
        {"path": "host-driver", "chips": ["soc-new"], "sides": ["host"]},
        {"path": "host-shared", "chips": ["soc-new"], "sides": ["host"]},
        {"path": "device-driver", "chips": ["soc-new"], "sides": ["device"]},
    ), tmp_path)
    assert [target["target_id"] for target in mapped["targets"]] == ["soc-new-device", "soc-new-host"]
    for path, target_id, other_target in (
        ("host-driver", "soc-new-host", "soc-new-device"),
        ("host-shared", "soc-new-host", "soc-new-device"),
        ("device-driver", "soc-new-device", "soc-new-host"),
    ):
        repo_id = repo_for(mapped, f"main/{path}")["repo_id"]
        assert v.workspace_file_allowed(mapped, repo_id, "source.c", target_id)
        assert not v.workspace_file_allowed(mapped, repo_id, "source.c", other_target)
    assert mapped["pairs"] == [{"pairing_id": "soc-new-host-device", "host_target": "soc-new-host",
                                "device_target": "soc-new-device", "compatibility_policy": "unknown"}]


@pytest.mark.parametrize("labels", [{}, {"chips": ["soc-new"]}, {"sides": ["host"]}])
def test_incomplete_target_labels_keep_generic_file_scope_without_inventing_targets(tmp_path, labels):
    write(tmp_path, "main/driver/source.c")
    mapped = v.normalize_workspace(config({"path": "driver", **labels}), tmp_path)
    assert mapped["targets"] == []
    assert mapped["pairs"] == []
    assert mapped["layout_gaps"] == []
    assert v.workspace_file_allowed(mapped, mapped["repos"][0]["repo_id"], "source.c")


def test_target_and_pair_order_is_independent_of_configuration_order(tmp_path):
    for module in ("first", "second"):
        write(tmp_path, f"main/{module}/source.c")
    left = v.normalize_workspace(config(
        {"path": "first", "chips": ["soc-z", "soc-a"], "sides": ["host", "device"]},
        {"path": "second", "chips": ["soc-a"], "sides": ["host"]},
    ), tmp_path)
    right = v.normalize_workspace(config(
        {"path": "second", "chips": ["soc-a"], "sides": ["host"]},
        {"path": "first", "chips": ["soc-a", "soc-z"], "sides": ["device", "host"]},
    ), tmp_path)
    assert left["targets"] == right["targets"]
    assert left["pairs"] == right["pairs"]
    assert [target["target_id"] for target in left["targets"]] == [
        "soc-a-device", "soc-a-host", "soc-z-device", "soc-z-host",
    ]
    assert [pair["pairing_id"] for pair in left["pairs"]] == ["soc-a-host-device", "soc-z-host-device"]


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


def test_knowledge_root_config_rejects_a_linked_code_root(tmp_path):
    root = tmp_path / "himate/domain"
    root.mkdir(parents=True)
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "main"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(actual), str(alias))
    else:
        alias.symlink_to(actual, target_is_directory=True)
    raw = {**config(), "code_root": "../../main"}
    del raw["knowledge_roots"]
    with pytest.raises(v.ContractError, match="WORKSPACE_LINKED_PATH"):
        v.normalize_workspace(raw, root)


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
