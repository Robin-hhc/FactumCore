"""Registered project roots remain explicit when the domain is nested."""

import importlib.util
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "nested_workspace_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
checks, knowledge, v = (importlib.import_module(spec.name + "." + name)
                        for name in ("checks", "knowledge", "validation"))


def fixture(tmp_path):
    root = tmp_path / "business"
    domain = root / "himate/himate-knowledge-wifi-mp"
    domain.mkdir(parents=True)
    config = root / "config.yml"
    value = {"schema_version": "2.0", "workspace_id": "business",
             "knowledge_roots": {"wifi": "himate/himate-knowledge-wifi-mp"},
             "code_root": "main", "modules": []}
    config.write_text(json.dumps(value), encoding="utf-8")
    registrations = {"business": {"config": str(config), "rules_digest": "1" * 64}}
    return root, domain, config, value, registrations


def test_registered_nested_config_selects_actual_project_root(tmp_path):
    root, domain, config, _, registrations = fixture(tmp_path)
    selected = v.workspace_config_path(domain, registrations, "1" * 64)
    assert selected == config
    assert selected.parent == root


def test_registered_mapping_must_match_selected_domain_and_rules(tmp_path):
    _, domain, config, value, registrations = fixture(tmp_path)
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_UNAVAILABLE"):
        v.workspace_config_path(domain, registrations, "2" * 64)
    value["knowledge_roots"]["wifi"] = "different-domain"
    config.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_UNAVAILABLE"):
        v.workspace_config_path(domain, registrations, "1" * 64)


def test_explicit_nested_config_rejects_traversal_and_wrong_domain(tmp_path):
    _, domain, config, value, _ = fixture(tmp_path)
    assert v.workspace_config_path(domain, config_path=config) == config
    value["knowledge_roots"]["wifi"] = "../business/himate/himate-knowledge-wifi-mp"
    config.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(v.ContractError, match="UNSAFE_WORKSPACE_PATH"):
        v.workspace_config_path(domain, config_path=config)


def test_discovery_requires_one_exact_wifi_mapping(tmp_path):
    root, domain, config, value, _ = fixture(tmp_path)
    assert v.workspace_config_path(domain) == config
    duplicate = root / "himate/config.yml"
    value["knowledge_roots"]["wifi"] = "himate-knowledge-wifi-mp"
    duplicate.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(v.ContractError, match="WORKSPACE_CONFIG_AMBIGUOUS"):
        v.workspace_config_path(domain)


@pytest.mark.parametrize("relative", ["../business/himate/himate-knowledge-wifi-mp", "/absolute", "C:/drive", "a\\b", "a//b", "a/./b", "a/NUL", "a/name. "])
def test_registered_knowledge_mapping_rejects_unsafe_components(tmp_path, relative):
    _, domain, config, value, registrations = fixture(tmp_path)
    value["knowledge_roots"]["wifi"] = relative
    config.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(v.ContractError, match="UNSAFE_WORKSPACE_PATH"):
        v.workspace_config_path(domain, registrations, "1" * 64)


def test_config_cannot_be_rebound_through_an_in_workspace_link(tmp_path):
    root, domain, config, value, registrations = fixture(tmp_path)
    alias = root / "linked"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(root / "himate"), str(alias))
    else:
        alias.symlink_to(root / "himate", target_is_directory=True)
    value["knowledge_roots"]["wifi"] = "linked/himate-knowledge-wifi-mp"
    config.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(v.ContractError, match="WORKSPACE_LINKED_PATH|UNSAFE_PATH"):
        v.workspace_config_path(domain, registrations, "1" * 64)


@pytest.mark.parametrize("config_state", ["absent", "wrong", "ambiguous", "unsafe"])
def test_git_history_reader_without_private_config_keeps_exact_old_card(tmp_path, config_state):
    workspace = tmp_path / "published workspace"
    domain = workspace / "himate/himate-knowledge-wifi-mp"
    shutil.copytree(DOMAIN / "governance", domain / "governance",
                    ignore=shutil.ignore_patterns("__pycache__"))
    template = (domain / "governance/templates/rule.md").read_text(encoding="utf-8")
    fields = {"card_id": "history-rule", "title": "History", "summary": "Fixed historical body",
              "owner": "fixture", "evidence_ref": "e1", "source_id": "source", "snapshot_id": "snapshot",
              "claim_id": "c1", "claim_text": "Original exact synthetic body."}
    for name, value in fields.items():
        template = template.replace("{{" + name + "}}", value)
    original = template.encode("utf-8")
    relative = "knowledge/rules/history-rule.md"
    path = domain / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(original)
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(workspace), *args],
                              capture_output=True, check=True).stdout
    git("init", "-q")
    git("add", "--", path.relative_to(workspace).as_posix())
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "original")
    path.write_bytes(original.replace(b"Original exact", b"Updated exact"))
    git("add", "--", path.relative_to(workspace).as_posix())
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "updated")
    mapping = {"knowledge_roots": {"wifi": "himate/himate-knowledge-wifi-mp"}}
    if config_state == "wrong":
        (workspace / "config.yml").write_text(json.dumps({"knowledge_roots": {"wifi": "other"}}), encoding="utf-8")
    elif config_state == "ambiguous":
        (workspace / "config.yml").write_text(json.dumps(mapping), encoding="utf-8")
        (domain.parent / "config.yml").write_text(json.dumps({"knowledge_roots": {"wifi": domain.name}}), encoding="utf-8")
    elif config_state == "unsafe":
        target = workspace / "actual-config"
        target.mkdir()
        (target / "config.yml").write_text(json.dumps(mapping), encoding="utf-8")
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(target), str(domain.parent / "config-link"))
        else:
            (domain.parent / "config-link").symlink_to(target, target_is_directory=True)
        # An explicit config through a directory link must never become a
        # registration, even when the repository contains the old exact card.
        mapping["knowledge_roots"]["wifi"] = "config-link/../himate-knowledge-wifi-mp"
        (domain.parent / "config.yml").write_text(json.dumps(mapping), encoding="utf-8")
    lock_path = domain / "governance/framework.lock.yaml"
    rules_digest = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    rules = v.load_rules(domain, rules_digest)
    current = knowledge.parse_card(path.read_bytes(), relative, rules)
    resolver = checks._record_resolver({"history-rule": current}, rules, {}, domain, {"commit": "HEAD"})
    ref = {"card_id": "history-rule", "sha256": hashlib.sha256(original).hexdigest()}
    if config_state == "absent":
        assert resolver(ref, {})["sha256"] == ref["sha256"]
    else:
        with pytest.raises(v.ContractError, match="RECORD_HISTORY_UNAVAILABLE"):
            resolver(ref, {})
