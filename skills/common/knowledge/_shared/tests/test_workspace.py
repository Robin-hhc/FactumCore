"""Behavioral checks for explicit project discovery; fixtures contain no business data."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _shared import contracts
from _shared.workspace import ProjectError, resolve_project

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture(autouse=True)
def isolated_git_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Synthetic repositories must not depend on the user's installed LFS or
    # other executable helper configuration. Production discovery inspects it.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def make_workspace(tmp_path: Path, name: str = "workspace") -> dict:
    root = tmp_path / name
    code = root / "source"
    code.mkdir(parents=True)
    source = code / "host.c"
    source.write_text("void wifi_fixture(void) {}\n", encoding="utf-8")
    knowledge = root / "aiot-wifi-knowledge"
    shutil.copytree(ROOT / "aiot-wifi-knowledge/governance", knowledge / "governance")
    for entry in (root / "AGENTS.md", knowledge / "AGENTS.md", knowledge / "knowledge/AGENTS.md"):
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("Fixture project instructions.\n", encoding="utf-8")
    targets = [
        {
            "target_id": f"{chip}-{side}",
            "chip": chip,
            "side": side,
            "source_bindings": ["wifi-source"],
            "module_roots": [],
            "build_profile": None,
            "required_features": [],
            "protocol_versions": [],
        }
        for chip in ("chip12", "chip08", "chip07c")
        for side in ("host", "device")
    ]
    config = {
        "schema_version": "1.0",
        "workspace_id": name,
        "knowledge_roots": {"wifi": "aiot-wifi-knowledge"},
        "repos": [
            {
                "repo_id": "wifi-source",
                "kind": "export",
                "root": "source",
                "expected_identity": None,
            }
        ],
        "architecture": [
            {
                "binding_id": "wifi-main",
                "repo_id": "wifi-source",
                "module_root": ".",
                "knowledge_domain": "wifi",
                "override_nested": False,
            }
        ],
        "wiki_entities": {},
        "symbol_aliases": {},
        "targets": targets,
        "pairs": [
            {
                "pairing_id": f"{chip}-pair",
                "host_target": f"{chip}-host",
                "device_target": f"{chip}-device",
                "compatibility_policy": "unknown",
            }
            for chip in ("chip12", "chip08", "chip07c")
        ],
        "query": {"default_channel": "local", "allowed_channels": ["local", "shared"]},
    }
    config_path = root / "config.yml"
    write_json(config_path, config)
    registry = tmp_path / f"{name}-registry.json"
    write_json(
        registry,
        {
            "schema_version": "1.0",
            "workspaces": [
                {
                    "workspace_id": name,
                    "config": str(config_path),
                    "config_digest": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                }
            ],
        },
    )
    return {
        "root": root,
        "code": code,
        "source": source,
        "knowledge": knowledge,
        "config": config,
        "config_path": config_path,
        "registry": registry,
    }


def save_configuration(project: dict) -> None:
    write_json(project["config_path"], project["config"])
    write_json(
        project["registry"],
        {
            "schema_version": "1.0",
            "workspaces": [
                {
                    "workspace_id": project["config"]["workspace_id"],
                    "config": str(project["config_path"]),
                    "config_digest": hashlib.sha256(
                        project["config_path"].read_bytes()
                    ).hexdigest(),
                }
            ],
        },
    )


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def make_git_project(tmp_path: Path) -> dict:
    project = make_workspace(tmp_path)
    git(project["code"], "init", "--quiet")
    git(project["code"], "add", "host.c")
    git(
        project["code"],
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    project["config"]["repos"][0]["kind"] = "git"
    save_configuration(project)
    return project


def test_public_resolve_from_unrelated_cwd_reads_no_entry_bodies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_workspace(tmp_path)
    elsewhere = tmp_path / "unrelated"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    receipt = resolve_project(project["source"], project["registry"])

    assert receipt["status"] == "resolved"
    assert Path(receipt["canonical_path"]) == project["source"].resolve()
    assert receipt["workspace_id"] == "workspace"
    assert receipt["entry_reads"] == []
    assert len(receipt["required_entry_files"]) == 3
    assert receipt["checkout_identity"]["kind"] == "export"
    assert receipt["checkout_identity"]["head"] is None
    assert receipt["checkout_identity"]["dirty"] is None


def test_entry_reading_requires_load_context_and_records_actual_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_workspace(tmp_path, "\u4e2d\u6587 workspace")
    expected_paths = [
        project["root"] / "AGENTS.md",
        project["knowledge"] / "AGENTS.md",
        project["knowledge"] / "knowledge/AGENTS.md",
    ]
    real_read = Path.read_bytes
    reads = []

    def tracking_read(path: Path) -> bytes:
        if path in expected_paths:
            reads.append(path)
        return real_read(path)

    monkeypatch.setattr(Path, "read_bytes", tracking_read)
    resolved = resolve_project(project["source"], project["registry"])
    assert resolved["entry_reads"] == []
    assert reads == []

    loaded = resolve_project(
        project["source"],
        project["registry"],
        load_context=True,
        authorization_epoch="fixture-epoch",
    )
    assert loaded["status"] == "context_loaded"
    assert set(reads) == set(expected_paths)
    assert loaded["authorization_epoch"] == "fixture-epoch"
    assert len(loaded["entry_reads"]) == 3
    for index, record in enumerate(loaded["entry_reads"], start=1):
        actual = real_read(Path(record["path"]))
        assert record["digest"] == hashlib.sha256(actual).hexdigest()
        assert record["bytes"] == len(actual)
        assert record["trace"] == {
            "tool": "workspace.resolve_project",
            "action": "read_bytes",
            "sequence": index,
        }


def test_relative_request_requires_explicit_base(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    with pytest.raises(ProjectError) as error:
        resolve_project("source/host.c", project["registry"])
    assert error.value.code == "BASE_REQUIRED"
    result = resolve_project("source/host.c", project["registry"], base_path=project["root"])
    assert Path(result["canonical_path"]) == project["source"].resolve()


def test_registry_config_location_is_relative_to_registry_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_workspace(tmp_path)
    registry = json.loads(project["registry"].read_text(encoding="utf-8"))
    registry["workspaces"][0]["config"] = "workspace/config.yml"
    write_json(project["registry"], registry)
    monkeypatch.chdir(project["knowledge"])
    assert resolve_project(project["source"], project["registry"])["workspace_id"] == "workspace"


def test_path_prefix_is_not_a_directory_boundary(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    sibling = project["root"] / "source-extra/host.c"
    sibling.parent.mkdir()
    sibling.write_text("fixture", encoding="utf-8")
    with pytest.raises(ProjectError) as error:
        resolve_project(sibling, project["registry"])
    assert error.value.code == "UNREGISTERED_PATH"


def test_stale_registry_fails_without_modifying_any_source(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    before = project["source"].read_bytes()
    project["config_path"].write_text(
        project["config_path"].read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    config_before = project["config_path"].read_bytes()
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=True)
    assert error.value.code == "REGISTRY_STALE"
    assert project["source"].read_bytes() == before
    assert project["config_path"].read_bytes() == config_before


def test_missing_entry_prevents_even_resolved_receipt(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    (project["knowledge"] / "knowledge/AGENTS.md").unlink()
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "ENTRY_UNAVAILABLE"
    assert error.value.path.endswith("AGENTS.md")


def test_private_overrides_are_not_loaded_and_unknown_targets_are_not_selected(
    tmp_path: Path,
) -> None:
    project = make_workspace(tmp_path)
    (project["root"] / "config.local.yml").write_text(
        "malformed: [must not parse", encoding="utf-8"
    )
    result = resolve_project(project["source"], project["registry"])
    assert result["config"]["local_overrides_loaded"] is False
    assert result["resolved_context"]["selected_target"] is None
    assert len(result["resolved_context"]["target_candidates"]) == 6
    assert "targets.chip12-host.build_profile" in result["unknown_fields"]
    assert result["checkout_identity"]["snapshot_status"] == "not_captured"


def test_two_workspaces_matching_same_path_are_ambiguous(tmp_path: Path) -> None:
    first = make_workspace(tmp_path, "first")
    second = make_workspace(tmp_path, "second")
    second["config"]["repos"][0]["root"] = str(first["code"])
    save_configuration(second)
    registrations = [
        json.loads(project["registry"].read_text(encoding="utf-8"))["workspaces"][0]
        for project in (first, second)
    ]
    write_json(first["registry"], {"schema_version": "1.0", "workspaces": registrations})
    with pytest.raises(ProjectError) as error:
        resolve_project(first["source"], first["registry"])
    assert error.value.code == "AMBIGUOUS_BINDING"


def test_nested_binding_needs_explicit_child_override(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    child_file = project["code"] / "module/nested.c"
    child_file.parent.mkdir()
    child_file.write_text("fixture", encoding="utf-8")
    child = {
        "binding_id": "nested",
        "repo_id": "wifi-source",
        "module_root": "module",
        "knowledge_domain": "wifi",
        "override_nested": False,
    }
    project["config"]["architecture"].append(child)
    save_configuration(project)
    with pytest.raises(ProjectError) as error:
        resolve_project(child_file, project["registry"])
    assert error.value.code == "AMBIGUOUS_BINDING"
    child["override_nested"] = True
    save_configuration(project)
    assert resolve_project(child_file, project["registry"])["binding_id"] == "nested"


def test_realpath_cannot_follow_a_module_link_outside_registered_repo(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "outside.c"
    source.write_text("fixture", encoding="utf-8")
    link = project["code"] / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Host does not permit creation of directory symlinks.")
        # Windows directory junctions exercise the production resolve path even
        # when unprivileged symlink creation is unavailable. Paths are passed as
        # environment values, never interpolated into shell source.
        command = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path $env:AIOT_TEST_LINK -Target $env:AIOT_TEST_TARGET | Out-Null"
        junction = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            env={**os.environ, "AIOT_TEST_LINK": str(link), "AIOT_TEST_TARGET": str(outside)},
        )
        if junction.returncode:
            pytest.skip("Host permits neither symlink nor junction fixture creation.")
    with pytest.raises(ProjectError) as error:
        resolve_project(link / "outside.c", project["registry"])
    assert error.value.code == "UNREGISTERED_PATH"


def test_git_identity_uses_actual_head_dirty_and_origin(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    git(project["code"], "remote", "add", "origin", "https://example.invalid/wifi.git")
    project["config"]["repos"][0]["expected_identity"] = "https://example.invalid/wifi.git"
    save_configuration(project)
    clean = resolve_project(project["source"], project["registry"])
    assert clean["checkout_identity"]["head"] == git(project["code"], "rev-parse", "HEAD")
    assert clean["checkout_identity"]["dirty"] is False
    project["source"].write_text("changed fixture\n", encoding="utf-8")
    assert (
        resolve_project(project["source"], project["registry"])["checkout_identity"]["dirty"]
        is True
    )
    git(project["code"], "remote", "set-url", "origin", "https://example.invalid/different.git")
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "REPO_IDENTITY_MISMATCH"


def test_git_worktree_is_a_distinct_checkout(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    checkout = tmp_path / "separate checkout"
    git(project["code"], "worktree", "add", "--quiet", "--detach", str(checkout))
    project["config"]["repos"][0]["root"] = str(checkout)
    save_configuration(project)
    result = resolve_project(checkout / "host.c", project["registry"])
    identity = result["checkout_identity"]
    assert Path(identity["root"]) == checkout.resolve()
    assert Path(identity["git_dir"]) != project["code"] / ".git"
    assert Path(identity["common_dir"]) == project["code"] / ".git"


def test_nested_git_checkout_does_not_inherit_parent_binding(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    nested = project["code"] / "nested"
    nested.mkdir()
    git(nested, "init", "--quiet")
    source = nested / "nested.c"
    source.write_text("fixture", encoding="utf-8")
    with pytest.raises(ProjectError) as error:
        resolve_project(source, project["registry"])
    assert error.value.code == "GIT_BOUNDARY_MISMATCH"


@pytest.mark.parametrize("bad_path", ["missing.c", "missing/sub/file.c"])
def test_missing_requested_path_is_explicit(tmp_path: Path, bad_path: str) -> None:
    project = make_workspace(tmp_path)
    with pytest.raises(ProjectError) as error:
        resolve_project(bad_path, project["registry"], base_path=project["root"])
    assert error.value.code == "PATH_UNAVAILABLE"


def test_schema_invalid_configuration_is_not_accepted_by_discovery(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    project["config"]["unexpected_setting"] = "unrecognized policy"
    save_configuration(project)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "CONFIG_INVALID"


def test_discovery_rejects_tampered_contract_bundle(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    contract = project["knowledge"] / "governance/schemas/workspace.schema.json"
    contract.write_bytes(contract.read_bytes() + b"\n")
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "LOCK_DIGEST_MISMATCH"


def test_actual_context_receipt_passes_persistent_record_contract(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    receipt = resolve_project(project["source"], project["registry"], load_context=True)
    assert contracts.validate_document("record", receipt, project["knowledge"]) == []


def test_changed_contract_during_context_read_cannot_receive_a_loaded_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_workspace(tmp_path)
    entry = project["root"] / "AGENTS.md"
    lock = project["knowledge"] / "governance/framework.lock.yaml"
    real_read = Path.read_bytes
    changed = False

    def changing_read(path: Path) -> bytes:
        nonlocal changed
        data = real_read(path)
        if path == entry and not changed:
            changed = True
            lock.write_bytes(real_read(lock) + b"\n")
        return data

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=True)
    assert error.value.code == "BINDING_CHANGED"


def test_entry_change_after_an_earlier_read_invalidates_whole_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_workspace(tmp_path)
    first = project["root"] / "AGENTS.md"
    last = project["knowledge"] / "knowledge/AGENTS.md"
    real_read = Path.read_bytes
    changed = False

    def changing_read(path: Path) -> bytes:
        nonlocal changed
        data = real_read(path)
        if path == last and not changed:
            changed = True
            first.write_text("Changed context.\n", encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=True)
    assert error.value.code == "ENTRY_CHANGED"


def test_changed_checkout_during_context_read_invalidates_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_git_project(tmp_path)
    entry = project["root"] / "AGENTS.md"
    real_read = Path.read_bytes
    changed = False

    def changing_read(path: Path) -> bytes:
        nonlocal changed
        data = real_read(path)
        if path == entry and not changed:
            changed = True
            project["source"].write_text("Changed fixture code.\n", encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=True)
    assert error.value.code == "CHECKOUT_CHANGED"


def test_public_cli_loads_unicode_path_and_exposes_entry_text(tmp_path: Path) -> None:
    project = make_workspace(tmp_path, "\u4e2d\u6587 cli workspace")
    command = [
        sys.executable,
        str(ROOT / "skills/common/knowledge/_shared/cli.py"),
        "project",
        "resolve",
        "--path",
        str(project["source"]),
        "--registry",
        str(project["registry"]),
        "--load-context",
    ]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "ok"
    assert response["result"]["status"] == "context_loaded"
    assert response["result"]["entry_reads"][0]["content"] == (
        project["root"] / "AGENTS.md"
    ).read_bytes().decode("utf-8")
    assert response["result"]["skill_digest"] is None


def test_public_cli_reports_expected_discovery_error_without_traceback(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "skills/common/knowledge/_shared/cli.py"),
        "project",
        "resolve",
        "--path",
        "source/host.c",
        "--registry",
        str(project["registry"]),
    ]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    response = json.loads(result.stdout)
    assert response["status"] == "invalid"
    assert response["diagnostics"][0]["code"] == "BASE_REQUIRED"
    assert "Traceback" not in result.stderr


def test_unknown_code_root_is_reported_without_borrowing_an_existing_directory(
    tmp_path: Path,
) -> None:
    project = make_workspace(tmp_path)
    project["config"]["repos"][0]["root"] = None
    save_configuration(project)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "CODE_ROOT_UNCONFIGURED"


def test_export_does_not_invent_an_expected_snapshot_identity(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    project["config"]["repos"][0]["expected_identity"] = "unverified-snapshot"
    save_configuration(project)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"])
    assert error.value.code == "IDENTITY_UNVERIFIABLE"


def test_successful_context_load_does_not_write_project_or_source_files(tmp_path: Path) -> None:
    project = make_workspace(tmp_path)
    before = {
        str(path.relative_to(project["root"])): path.read_bytes()
        for path in project["root"].rglob("*")
        if path.is_file()
    }
    resolve_project(project["source"], project["registry"], load_context=True)
    after = {
        str(path.relative_to(project["root"])): path.read_bytes()
        for path in project["root"].rglob("*")
        if path.is_file()
    }
    assert after == before


def test_project_discovery_never_executes_repository_fsmonitor(tmp_path: Path) -> None:
    project = make_git_project(tmp_path)
    marker = project["code"] / "fsmonitor-executed.txt"
    git(project["code"], "config", "core.fsmonitor", "echo triggered > fsmonitor-executed.txt")
    assert not marker.exists()

    receipt = resolve_project(project["source"], project["registry"])

    assert not marker.exists(), "Read-only discovery executed a repository-configured helper."
    assert receipt["checkout_identity"]["dirty"] is False


@pytest.mark.parametrize("helper", ["clean", "process", "smudge"])
def test_project_discovery_skips_status_for_configured_attribute_helpers(
    tmp_path: Path, helper: str
) -> None:
    project = make_git_project(tmp_path)
    marker = project["code"] / "filter-executed.txt"
    (project["code"] / ".gitattributes").write_text("host.c filter=audit\n", encoding="utf-8")
    git(project["code"], "config", f"filter.audit.{helper}", "echo triggered > filter-executed.txt")
    metadata = project["source"].stat()
    os.utime(project["source"], (metadata.st_atime, metadata.st_mtime + 5))

    receipt = resolve_project(project["source"], project["registry"])
    assert receipt["status"] == "resolved"
    assert receipt["checkout_identity"]["dirty"] is None
    assert receipt["checkout_identity"]["dirty_status"] == "unavailable_configured_helpers"
    assert "checkout.dirty" in receipt["unknown_fields"]
    assert not marker.exists(), "Discovery must refuse before running Git status."


def test_project_discovery_skips_status_for_external_git_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = make_git_project(tmp_path)
    global_config = tmp_path / "synthetic-user.gitconfig"
    global_config.write_text(
        '[filter "global-audit"]\n\tclean = echo triggered > global-filter-executed.txt\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    receipt = resolve_project(project["source"], project["registry"])
    assert receipt["status"] == "resolved"
    assert receipt["checkout_identity"]["dirty"] is None
    assert receipt["checkout_identity"]["dirty_status"] == "unavailable_configured_helpers"
    assert not (project["code"] / "global-filter-executed.txt").exists()


def create_directory_link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Host does not permit creation of a directory link fixture.")
        command = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path $env:AIOT_TEST_LINK -Target $env:AIOT_TEST_TARGET | Out-Null"
        junction = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            env={**os.environ, "AIOT_TEST_LINK": str(link), "AIOT_TEST_TARGET": str(target)},
        )
        assert junction.returncode == 0, "Could not create a real junction fixture."


@pytest.mark.parametrize("load_context", [False, True])
def test_required_entry_junction_cannot_escape_registered_knowledge_root(
    tmp_path: Path, load_context: bool
) -> None:
    project = make_workspace(tmp_path)
    outside = tmp_path / "outside-instructions"
    outside.mkdir()
    (outside / "AGENTS.md").write_text("Outside fixture instructions.\n", encoding="utf-8")
    knowledge_directory = project["knowledge"] / "knowledge"
    (knowledge_directory / "AGENTS.md").unlink()
    knowledge_directory.rmdir()
    create_directory_link(knowledge_directory, outside)

    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=load_context)

    assert error.value.code == "ENTRY_PATH_ESCAPE"


@pytest.mark.parametrize("load_context", [False, True])
def test_final_entry_recheck_detects_a_new_escape_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, load_context: bool
) -> None:
    project = make_workspace(tmp_path)
    outside = tmp_path / "late-outside-instructions"
    outside.mkdir()
    (outside / "AGENTS.md").write_text("Outside fixture instructions.\n", encoding="utf-8")
    knowledge_directory = project["knowledge"] / "knowledge"
    real_validate = contracts.validate_document
    validations = 0

    def changing_validate(kind, document, knowledge_root):
        nonlocal validations
        diagnostics = real_validate(kind, document, knowledge_root)
        validations += 1
        if validations == 2:
            (knowledge_directory / "AGENTS.md").unlink()
            knowledge_directory.rmdir()
            create_directory_link(knowledge_directory, outside)
        return diagnostics

    monkeypatch.setattr(contracts, "validate_document", changing_validate)
    with pytest.raises(ProjectError) as error:
        resolve_project(project["source"], project["registry"], load_context=load_context)
    assert error.value.code == "ENTRY_PATH_ESCAPE"


@pytest.mark.parametrize("document_kind", ["registry", "config"])
def test_aba_document_bytes_cannot_select_an_unregistered_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document_kind: str
) -> None:
    project = make_workspace(tmp_path)
    alternate = project["root"] / "alternate-source"
    alternate.mkdir()
    alternate_file = alternate / "alternate.c"
    alternate_file.write_text("alternate fixture\n", encoding="utf-8")
    config_b = json.loads(json.dumps(project["config"]))
    config_b["repos"][0]["root"] = str(alternate)
    if document_kind == "config":
        path = project["config_path"]
        bytes_b = json.dumps(config_b).encode("utf-8")
    else:
        alternate_config = project["root"] / "alternate-config.yml"
        write_json(alternate_config, config_b)
        registry_b = {
            "schema_version": "1.0",
            "workspaces": [
                {
                    "workspace_id": project["config"]["workspace_id"],
                    "config": str(alternate_config),
                    "config_digest": hashlib.sha256(alternate_config.read_bytes()).hexdigest(),
                }
            ],
        }
        path = project["registry"]
        bytes_b = json.dumps(registry_b).encode("utf-8")
    bytes_a = path.read_bytes()
    real_read_bytes = Path.read_bytes
    real_read_text = Path.read_text
    reads = 0

    def observe() -> bytes:
        nonlocal reads
        reads += 1
        # A is used for the old digest read, B for the old independent parse,
        # then the on-disk A is restored before the final digest recheck.
        if reads == 2:
            path.write_bytes(bytes_b)
            try:
                return real_read_bytes(path)
            finally:
                path.write_bytes(bytes_a)
        return real_read_bytes(path)

    def changing_bytes(candidate: Path) -> bytes:
        return observe() if candidate == path else real_read_bytes(candidate)

    def changing_text(candidate: Path, *args, **kwargs) -> str:
        if candidate == path:
            return observe().decode(kwargs.get("encoding") or "utf-8")
        return real_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", changing_bytes)
    monkeypatch.setattr(Path, "read_text", changing_text)

    with pytest.raises(ProjectError) as error:
        resolve_project(alternate_file, project["registry"])

    assert error.value.code == "UNREGISTERED_PATH"
    assert real_read_bytes(path) == bytes_a


def test_configured_helper_keeps_context_discovery_available_with_unknown_dirty(
    tmp_path: Path,
) -> None:
    project = make_git_project(tmp_path)
    marker = project["code"] / "unknown-dirty-filter-executed.txt"
    git(
        project["code"],
        "config",
        "filter.audit.clean",
        "echo triggered > unknown-dirty-filter-executed.txt",
    )

    receipt = resolve_project(project["source"], project["registry"], load_context=True)

    assert receipt["status"] == "context_loaded"
    assert receipt["checkout_identity"]["head"] == git(project["code"], "rev-parse", "HEAD")
    assert receipt["checkout_identity"]["dirty"] is None
    assert receipt["checkout_identity"]["dirty_status"] == "unavailable_configured_helpers"
    assert "checkout.dirty" in receipt["unknown_fields"]
    assert not marker.exists()


def test_submodule_helper_cannot_execute_during_parent_discovery(tmp_path: Path) -> None:
    parent = make_git_project(tmp_path / "parent")
    child = make_git_project(tmp_path / "child")
    git(
        parent["code"],
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "--quiet",
        str(child["code"]),
        "sub",
    )
    module = parent["code"] / "sub"
    marker = module / "submodule-filter-executed.txt"
    (module / ".gitattributes").write_text("host.c filter=audit\n", encoding="utf-8")
    git(module, "config", "filter.audit.clean", "echo triggered > submodule-filter-executed.txt")
    metadata = (module / "host.c").stat()
    os.utime(module / "host.c", (metadata.st_atime, metadata.st_mtime + 5))

    receipt = resolve_project(parent["source"], parent["registry"], load_context=True)

    assert receipt["status"] == "context_loaded"
    assert receipt["checkout_identity"]["dirty"] is None
    assert receipt["checkout_identity"]["dirty_status"] == "unavailable_submodules"
    assert "checkout.dirty" in receipt["unknown_fields"]
    assert not marker.exists(), "Parent discovery executed a submodule-configured helper."
