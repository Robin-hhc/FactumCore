"""Recovery from a checkout never broadens the registered source scope."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "checkout_recovery_contracts", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
CONTRACTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACTS
SPEC.loader.exec_module(CONTRACTS)
from checkout_recovery_contracts import source_resources as sources, validation as v  # noqa: E402


def fixture(tmp_path, *, kind="raw", relative="docs-raw/specs/source.md", repo_id=None):
    root = tmp_path / "himate-knowledge-wifi-mp"
    (root / "governance").mkdir(parents=True)
    raw = b"Exact frozen source.\n"
    resource = {"source_id": "fixture-source", "kind": kind, "path": relative}
    if repo_id:
        resource["repo_id"] = repo_id
    snapshot = {"source_id": resource["source_id"], "snapshot_id": "fixture-snapshot",
                "sha256": v.sha256_bytes(raw), "bytes": len(raw),
                "recovery": {"method": "evidence_object", "path": "logs/evidence/objects/missing.bin"}}
    lock = {"schema_version": "2.0", "resources": [resource], "snapshots": [snapshot]}
    (root / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    return root, raw, snapshot, lock


def save_lock(root, lock):
    (root / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")


def test_missing_private_snapshot_uses_only_exact_registered_current_bytes(tmp_path):
    root, raw, snapshot, lock = fixture(tmp_path)
    path = root / lock["resources"][0]["path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    assert sources.recover_snapshot_source(root, snapshot) == (raw, "docs-raw/specs/source.md")
    path.write_bytes(b"A different newer source.\n")
    with pytest.raises(v.ContractError, match="SOURCE_INPUT_UNAVAILABLE"):
        sources.recover_snapshot(root, snapshot)
    path.write_bytes(raw)
    forged = {**snapshot, "snapshot_id": "not-in-shared-lock"}
    with pytest.raises(v.ContractError, match="SOURCE_INPUT_UNAVAILABLE"):
        sources.recover_snapshot(root, forged)


def test_strict_git_failure_cannot_be_replaced_with_local_or_current_file(tmp_path):
    root, raw, snapshot, lock = fixture(tmp_path)
    current = root / lock["resources"][0]["path"]
    current.parent.mkdir(parents=True)
    current.write_bytes(raw)
    local = root / "logs/evidence/objects/retained.bin"
    local.parent.mkdir(parents=True)
    local.write_bytes(raw)
    snapshot["local_recovery"] = {"method": "evidence_object", "path": "logs/evidence/objects/retained.bin"}
    snapshot["recovery"] = {"kind": "git", "commit": "0" * 40,
                            "path": root.name + "/docs-raw/specs/source.md"}
    save_lock(root, lock)
    with pytest.raises(v.ContractError, match="RECOVERY_CONFIG_REQUIRED"):
        sources.recover_snapshot(root, snapshot, allow_local_fallback=False)
    # An invalid or unavailable current config does not hide retained evidence.
    assert sources.recover_snapshot_source(root, snapshot) == (raw, "logs/evidence/objects/retained.bin")
    local.write_bytes(b"Corrupted retained object.\n")
    with pytest.raises(v.ContractError, match="EVIDENCE_OBJECT_CHANGED"):
        sources.recover_snapshot(root, snapshot)


@pytest.mark.parametrize("relative", ["child/wifi.c", ".git/config", ".repo/manifest.xml"])
def test_current_code_recovery_rejects_excluded_child_and_management_paths(tmp_path, relative):
    repo_id = "repo-" + v.sha256_bytes(b"main/wifi")[:16]
    root, raw, snapshot, _ = fixture(tmp_path, kind="code", relative=relative, repo_id=repo_id)
    module = tmp_path / "main/wifi"
    path = module / relative
    path.parent.mkdir(parents=True)
    (module / "child").mkdir(exist_ok=True)
    path.write_bytes(raw)
    configuration = {"knowledge_roots": {"wifi": root.name}, "code_root": "main",
                     "modules": [{"path": "wifi"}, {"path": "wifi/child"}]}
    (tmp_path / "config.yml").write_text(yaml.safe_dump(configuration), encoding="utf-8")
    with pytest.raises(v.ContractError, match="RECOVERY_SCOPE_REQUIRED"):
        sources.recover_snapshot(root, snapshot)
    git_snapshot = {**snapshot, "recovery": {"kind": "git", "repo_id": repo_id,
                                           "commit": "0" * 40, "path": relative}}
    with pytest.raises(v.ContractError, match="RECOVERY_SCOPE_REQUIRED|UNSAFE_RECOVERY_PATH"):
        sources.recover_snapshot(root, git_snapshot, allow_local_fallback=False)


def test_current_raw_recovery_rejects_links_even_when_target_stays_inside_root(tmp_path):
    root, raw, snapshot, lock = fixture(tmp_path)
    original = root / "docs-raw/specs/actual.md"
    original.parent.mkdir(parents=True)
    original.write_bytes(raw)
    linked = original.with_name("source.md")
    try:
        linked.symlink_to(original)
    except OSError:
        if os.name != "nt":
            pytest.skip("The host does not permit creation of a file symlink")
        junction = original.parent / "linked-directory"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(original.parent)], capture_output=True)
        if result.returncode:
            pytest.skip("The host does not permit creation of a file link or directory junction")
        try:
            lock["resources"][0]["path"] = "docs-raw/specs/linked-directory/actual.md"
            save_lock(root, lock)
            with pytest.raises(v.ContractError, match="WORKSPACE_LINKED_PATH"):
                sources.recover_snapshot(root, snapshot)
        finally:
            os.rmdir(junction)
        return
    with pytest.raises(v.ContractError, match="WORKSPACE_LINKED_PATH"):
        sources.recover_snapshot(root, snapshot)
