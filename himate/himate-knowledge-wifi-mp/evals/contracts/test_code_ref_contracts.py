"""Optional symbol selectors preserve fixed evidence and use real current files."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

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
checks = _helper.module("checks")


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
    config = {"schema_version": "2.0", "workspace_id": "code-ref-test",
              "knowledge_roots": {"wifi": "knowledge-root"}, "code_root": "main",
              "modules": [{"path": "host", "chips": ["chip12"], "sides": ["host"], "description": "test"}]}
    config_path = root / "config.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    mapping = validation.normalize_workspace(config, root)["repos"][0]
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
    config = yaml.safe_load(config_path.read_bytes())
    config["knowledge_roots"]["wifi"] = other.name
    other_config = domain.parent / "other-config.yml"
    other_config.write_text(yaml.safe_dump(config), encoding="utf-8")
    checkout = {"configuration": str(other_config),
                "config_digest": hashlib.sha256(other_config.read_bytes()).hexdigest(),
                "repos": {mapping["repo_id"]: {"root": str(code.parents[1])}}}
    observed = resources.resolve_code_navigation(domain, reference(), lock, checkout)
    assert observed["status"] == "unavailable"


def formal_view(workspace, *, mode="formal"):
    domain, _, _, lock, _, _ = workspace
    (domain / "governance").mkdir(exist_ok=True)
    (domain / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    (domain / "knowledge").mkdir(exist_ok=True)
    (domain / "knowledge/index.md").write_text("# Knowledge\n\n[Ready](ready.md)\n", encoding="utf-8")
    meta = {"schema_version": "2.0", "id": "ready-card", "profile": "flow", "title": "Ready",
            "summary": "Documented ready flow", "lifecycle": "stable", "review_mode": "manual_document",
            "owner": "fixture", "scope": {"applicability": "unknown", "contexts": []}, "aliases": [],
            "sources": [reference()], "claims": [{"id": "ready-claim", "text_ref": "#ready-claim",
                "evidence_kind": "design", "source_refs": ["entry"], "context_ids": [],
                "usage": "guidance", "verification_requirements": []}], "relations": []}
    body = "# Ready\n\n<a id=\"ready-claim\"></a>\nDocumented ready flow.\n"
    for heading in ("起终点", "步骤", "调用与消息", "异常", "条件", "证据"):
        body += "\n## " + heading + "\n\nDocumented scope.\n"
    (domain / "knowledge/ready.md").write_text("---\n" + yaml.safe_dump(meta) + "---\n" + body, encoding="utf-8")
    governance = Path(__file__).parents[2] / "governance"
    rules = {"knowledge_root": domain, "rules_digest": "0" * 64,
             "profiles": yaml.safe_load((governance / "schemas/profiles.yaml").read_bytes()),
             "registries": yaml.safe_load((governance / "schemas/registries.yaml").read_bytes()),
             "schemas": {kind: json.loads((governance / "schemas" / (name + ".schema.json")).read_bytes())
                         for kind, name in (("card", "frontmatter"), ("sources", "sources"),
                                            ("workspace", "workspace"), ("record", "records"))}}
    return checks.prepare_view(domain, mode=mode), rules


def test_fixed_checks_validate_navigation_for_document_mode_without_code_gate(workspace):
    view, rules = formal_view(workspace)
    report = checks.run(view, rules, inputs={"source_objects": {"v1": workspace[2]}}, scope="full")
    assert report["status"] == "passed", report["findings"]
    source_result = next(row for row in report["checks"] if row["group"] == "source")
    assert source_result["code_navigation"][0]["status"] == "resolved"
    workspace[1].write_bytes(b"int renamed(void) { return 1; }\n")
    failed = checks.run(view, rules, inputs={"source_objects": {"v1": workspace[2]}}, scope="full")
    assert failed["status"] == "failed"
    assert any(row["code"] == "CODE_SYMBOL_MISSING" for row in failed["findings"])


def test_ci_does_not_resolve_current_navigation_from_an_unprovided_checkout(workspace):
    view, rules = formal_view(workspace, mode="ci")
    report = checks.run(view, rules, inputs={"source_objects": {"v1": workspace[2]}}, scope="full")
    assert report["status"] == "incomplete"
    assert any(row["code"] == "CODE_INPUT_UNAVAILABLE" for row in report["findings"])


def test_protected_ci_script_loads_symbol_module_and_checks_actual_current_code(workspace):
    domain, code, original, _, config_path, mapping = workspace
    formal_view(workspace)
    code.write_bytes(b"/* new heading */\n\nint ready(void) { return 9; }\n")
    package_root = Path(__file__).parents[2]
    trusted = domain.parent / "trusted"
    trusted.mkdir()
    shutil.copytree(package_root / "governance", trusted / "governance",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(package_root / "check.py", trusted / "check.py")
    old_source = domain.parent / "adopted-source.c"
    old_source.write_bytes(original)
    job_input = domain.parent / "ci-input.json"
    job_input.write_text(json.dumps({"inputs": {"source_objects": {"v1": str(old_source)},
        "code_checkout": {"configuration": str(config_path),
            "config_digest": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "repos": {mapping["repo_id"]: {"root": str(code.parents[1])}}}}}), encoding="utf-8")
    output = domain.parent / "ci-output.json"
    process = subprocess.run([sys.executable, str(trusted / "check.py"),
        "--trusted-root", str(trusted), "--candidate-root", str(domain),
        "--rules-digest", hashlib.sha256((trusted / "governance/framework.lock.yaml").read_bytes()).hexdigest(),
        "--commit", "a" * 40, "--input", str(job_input), "--output", str(output)],
        capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, process.stdout + process.stderr
    report = json.loads(output.read_bytes())
    observed = next(row for row in report["checks"] if row["group"] == "source")["code_navigation"][0]
    assert observed["status"] == "resolved" and observed["range"]["start_line"] == 3
