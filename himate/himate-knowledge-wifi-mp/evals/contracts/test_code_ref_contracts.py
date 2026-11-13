"""Optional symbol selectors preserve fixed evidence and use real current files."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
import pytest
import yaml


_spec = importlib.util.spec_from_file_location(
    "code_ref_contract_support", Path(__file__).parents[1] / "support/contracts.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
resources = _helper.module("source_resources")
validation = _helper.module("validation")


def reference():
    return {"evidence_ref": "entry", "source_id": "source", "snapshot_id": "v1",
            "locator": {"kind": "lines", "start": 1, "end": 1},
            "code_ref": {"kind": "function", "name": "ready", "parameter_types": []}}


def source_lock(raw=b"int ready(void) { return 1; }\n", *, kind="code"):
    return {"schema_version": "2.0", "resources": [{"source_id": "source", "kind": kind, "path": "src/ready.c"}],
            "snapshots": [{"source_id": "source", "snapshot_id": "v1",
                           "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                           "recovery": {"method": "evidence_object", "path": "logs/evidence/old.bin"}}]}


def test_code_ref_cannot_be_attached_to_document_evidence():
    with pytest.raises(validation.ContractError, match="CODE_REF_NON_CODE_SOURCE"):
        resources.validate_source_ref(reference(), source_lock(kind="raw"))


def test_source_schema_accepts_optional_code_ref_without_changing_old_shape():
    card_schema = json.loads((Path(__file__).parents[2] / "governance/schemas/frontmatter.schema.json").read_bytes())
    schema = {**card_schema["properties"]["sources"]["items"], "$defs": card_schema["$defs"]}
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(reference()))
    old = reference()
    del old["code_ref"]
    assert not list(validator.iter_errors(old))


@pytest.mark.parametrize(("selector", "valid"), [
    ({"kind": "type_alias", "name": "callback_t"}, True),
    ({"kind": "variable", "name": "state_table"}, True),
    ({"kind": "function", "name": "api", "role": "declaration"}, True),
    ({"kind": "function", "name": "api", "role": "unknown"}, False),
    ({"kind": "variable", "name": "state_table", "role": "declaration"}, False),
    ({"kind": "type_alias", "name": "callback_t", "parameter_types": []}, False),
])
def test_schema_supports_real_source_aliases_variables_and_explicit_api_declarations(selector, valid):
    card_schema = json.loads((Path(__file__).parents[2] / "governance/schemas/frontmatter.schema.json").read_bytes())
    schema = {**card_schema["properties"]["sources"]["items"], "$defs": card_schema["$defs"]}
    errors = list(Draft202012Validator(schema).iter_errors({**reference(), "code_ref": selector}))
    assert (not errors) is valid


def test_fixed_snapshot_ref_checks_symbol_and_line_binding():
    raw = b"int other(void) { return 2; }\nint ready(void) { return 1; }\n"
    ref = reference()
    lock = source_lock(raw)
    with pytest.raises(validation.ContractError, match="CODE_REF_LOCATOR_MISMATCH"):
        resources.validate_reference(ref, lock, lambda _: raw)
    ref["locator"] = {"kind": "lines", "start": 2, "end": 2}
    checked = resources.validate_reference(ref, lock, lambda _: raw)
    assert checked["code_ref"] == ref["code_ref"]


def test_old_evidence_does_not_require_a_symbol_selector():
    ref = reference()
    del ref["code_ref"]
    raw = b"int ready(void) { return 1; }\n"
    assert resources.validate_reference(ref, source_lock(raw), lambda _: raw)["snapshot_id"] == "v1"


@pytest.mark.parametrize("locator", [{"kind": "lines", "start": 1}, {"kind": "lines", "number": 1}])
def test_symbol_binding_preserves_existing_single_line_locator_forms(locator):
    ref = reference()
    ref["locator"] = locator
    raw = b"int ready(void) { return 1; }\n"
    assert resources.validate_reference(ref, source_lock(raw), lambda _: raw)["code_ref"] == ref["code_ref"]


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "repo"
    domain = root / "knowledge-root"
    domain.mkdir(parents=True)
    code = root / "main/host/src/ready.c"
    code.parent.mkdir(parents=True)
    original = b"int ready(void) { return 1; }\n"
    code.write_bytes(original)
    config = {"schema_version": "2.0", "workspace_id": "code-ref-test", "code_root": "../main",
              "modules": [{"path": "host", "chips": ["chip12"], "sides": ["host"], "description": "test"}]}
    config_path = domain / "config.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    mapping = validation.normalize_workspace(config, domain)["repos"][0]
    lock = source_lock(original)
    lock["resources"][0]["repo_id"] = mapping["repo_id"]
    return domain, code, original, lock, config_path, mapping


def test_current_navigation_uses_symbol_after_insertions_not_old_line_numbers(workspace):
    domain, code, original, lock, _, _ = workspace
    code.write_bytes(b"/* new heading */\n\nint ready(void) { return 7; }\n")
    observed = resources.resolve_code_navigation(domain, reference(), lock)
    assert observed["status"] == "resolved"
    assert observed["range"]["start_line"] == 3
    assert observed["sha256"] != hashlib.sha256(original).hexdigest()
    assert resources.validate_reference(reference(), lock, lambda _: original)["locator"]["start"] == 1


def test_navigation_ignores_other_knowledge_roots_and_ancestor_configs(workspace):
    domain, code, _, lock, config_path, _ = workspace
    config = yaml.safe_load(config_path.read_bytes())
    other = domain.parent / "other-knowledge-root"
    other.mkdir()
    (other / "config.yml").write_text(yaml.safe_dump({**config, "modules": []}), encoding="utf-8")
    (domain.parent / "config.yml").write_text("an invalid ancestor configuration[\n", encoding="utf-8")
    code.write_bytes(b"/* current revision */\nint ready(void) { return 7; }\n")

    observed = resources.resolve_code_navigation(domain, reference(), lock)

    assert observed["status"] == "resolved", observed
    assert observed["range"]["start_line"] == 2
    assert observed["sha256"] == hashlib.sha256(code.read_bytes()).hexdigest()
    assert observed["config_digest"] == hashlib.sha256(config_path.read_bytes()).hexdigest()


@pytest.mark.parametrize("layout", ["outer", "standalone", "added_nested_checkout"])
def test_fixed_git_recovery_uses_owning_repo_and_preserves_current_original(tmp_path, layout):
    project = tmp_path / "repository"
    domain = project / "himate/himate-knowledge-bluetooth"
    original = domain / "docs-raw/specs/design.md"
    original.parent.mkdir(parents=True)
    old_bytes = b"# Design\n\nOriginal documented requirement.\n"
    original.write_bytes(old_bytes)
    repository = domain if layout == "standalone" else project
    relative = original.relative_to(repository).as_posix()
    foreign_original = repository / "foreign/docs-raw/specs/design.md"
    foreign_original.parent.mkdir(parents=True)
    foreign_original.write_bytes(b"A different domain's original.\n")

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid",
             "-c", "core.autocrlf=false", "-C", str(repository), *args],
            check=True, capture_output=True,
        ).stdout.decode().strip()

    git("init", "--quiet")
    git("add", "--", relative, foreign_original.relative_to(repository).as_posix())
    git("commit", "--quiet", "-m", "Record synthetic original")
    commit = git("rev-parse", "HEAD")
    recovery = resources.git_recovery_for_current(domain, "docs-raw/specs/design.md", old_bytes)
    assert (recovery["commit"], recovery["path"]) == (commit, relative)
    if layout == "added_nested_checkout":
        subprocess.run(["git", "-C", str(domain), "init", "--quiet"], check=True, capture_output=True)
        assert resources.git_recovery_for_current(domain, "docs-raw/specs/design.md", old_bytes) is None
    current = b"# Design\n\nUncommitted local requirement.\n"
    original.write_bytes(current)

    recovered = resources._recover_git(domain, {"commit": commit, "path": relative})

    assert recovered == old_bytes
    assert original.read_bytes() == current
    with pytest.raises(validation.ContractError, match="RECOVERY_SCOPE_REQUIRED"):
        resources._recover_git(domain, {
            "commit": commit, "path": foreign_original.relative_to(repository).as_posix(),
        })


def test_deleted_current_file_is_reported_missing_without_losing_old_snapshot(workspace):
    domain, code, original, lock, _, _ = workspace
    code.unlink()
    observed = resources.resolve_code_navigation(domain, reference(), lock)
    assert observed["status"] == "missing"
    assert resources.validate_reference(reference(), lock, lambda _: original)["snapshot_id"] == "v1"


def test_fixed_checkout_requires_its_real_configuration_fingerprint(workspace):
    domain, code, _, lock, config_path, mapping = workspace
    checkout = {"configuration": str(config_path), "config_digest": "0" * 64,
                "repos": {mapping["repo_id"]: {"root": str(code.parents[1])}}}
    observed = resources.resolve_code_navigation(domain, reference(), lock, checkout)
    assert observed["status"] == "unavailable"
    assert "fingerprint" in observed["reason"]


def test_fixed_checkout_cannot_substitute_another_root_with_the_same_symbol(workspace):
    domain, code, original, lock, config_path, mapping = workspace
    foreign = domain.parent / "foreign"
    (foreign / "src").mkdir(parents=True)
    (foreign / "src/ready.c").write_bytes(original)
    checkout = {"configuration": str(config_path),
                "config_digest": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                "repos": {mapping["repo_id"]: {"root": str(foreign)}}}
    assert resources.resolve_code_navigation(domain, reference(), lock, checkout)["status"] == "unavailable"
    checkout["repos"][mapping["repo_id"]]["root"] = "main/host"
    assert resources.resolve_code_navigation(domain, reference(), lock, checkout)["status"] == "unavailable"
    checkout["repos"][mapping["repo_id"]]["root"] = str(code.parents[1])
    assert resources.resolve_code_navigation(domain, reference(), lock, checkout)["status"] == "resolved"


def test_navigation_rejects_configuration_bound_to_another_knowledge_root(workspace):
    domain, code, _, lock, config_path, mapping = workspace
    other = domain.parent / "other-knowledge-root"
    other.mkdir()
    other_config = other / "config.yml"
    other_config.write_bytes(config_path.read_bytes())
    checkout = {"configuration": str(other_config),
                "config_digest": hashlib.sha256(other_config.read_bytes()).hexdigest(),
                "repos": {mapping["repo_id"]: {"root": str(code.parents[1])}}}
    observed = resources.resolve_code_navigation(domain, reference(), lock, checkout)
    assert observed["status"] == "unavailable"


def target_identity(workspace, chip, side):
    domain, code, original, _, config_path, _ = workspace
    config = yaml.safe_load(config_path.read_bytes())
    config["modules"][0].update(chips=[chip], sides=[side])
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    mapped = validation.normalize_workspace(config, domain)
    repo = mapped["repos"][0]
    identity = {
        "basis": "source", "target": {"target_id": f"{chip}-{side}", "chip": chip, "side": side},
        "build_files": {}, "macro_digest": None,
        "repos": {repo["repo_id"]: {
            "kind": "export", "workspace_path": repo["workspace_path"], "evidence_basis": "filesystem",
            "head": None, "checked_files_dirty": None, "identity": None,
            "files": {code.relative_to(code.parents[1]).as_posix(): hashlib.sha256(original).hexdigest()},
        }},
    }
    schema = json.loads((Path(__file__).parents[2] / "governance/schemas/workspace.schema.json").read_bytes())
    rules = {"knowledge_root": str(domain), "schemas": {"workspace": schema}}
    return identity, config, rules


@pytest.mark.parametrize("side", ["host", "device"])
def test_current_code_identity_accepts_target_derived_from_custom_module_chip(workspace, side):
    _, _, _, _, config_path, _ = workspace
    identity, _, rules = target_identity(workspace, "soc-new", side)

    checked = resources.validate_current_code_identity(
        identity, config_path, hashlib.sha256(config_path.read_bytes()).hexdigest(), rules, {},
    )

    assert checked == identity


def test_current_code_identity_rejects_sibling_module_outside_custom_target(workspace):
    domain, code, original, _, config_path, _ = workspace
    identity, config, rules = target_identity(workspace, "soc-new", "host")
    sibling = domain.parent / "main/device/src/ready.c"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(original)
    config["modules"].append({"path": "device", "chips": ["soc-new"], "sides": ["device"]})
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    mapped = validation.normalize_workspace(config, domain)
    sibling_repo = next(repo for repo in mapped["repos"] if repo["workspace_path"] == "main/device")
    recorded = next(iter(identity["repos"].values()))
    recorded["workspace_path"] = sibling_repo["workspace_path"]
    identity["repos"] = {sibling_repo["repo_id"]: recorded}

    with pytest.raises(validation.ContractError, match="CODE_TARGET_CHANGED"):
        resources.validate_current_code_identity(
            identity, config_path, hashlib.sha256(config_path.read_bytes()).hexdigest(), rules, {},
        )
    assert code.read_bytes() == original
    assert sibling.read_bytes() == original


def test_current_code_identity_rejects_target_removed_by_module_chip_change(workspace):
    _, _, _, _, config_path, _ = workspace
    identity, config, rules = target_identity(workspace, "soc-old", "host")
    config["modules"][0]["chips"] = ["soc-new"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(validation.ContractError, match="CODE_TARGET_CHANGED"):
        resources.validate_current_code_identity(
            identity, config_path, hashlib.sha256(config_path.read_bytes()).hexdigest(), rules, {},
        )
