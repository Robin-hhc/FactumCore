"""T01 tests the public CLI, rather than a duplicated validator implementation."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]
CLI = ROOT / "skills/common/knowledge/_shared/cli.py"
KNOWLEDGE = ROOT / "aiot-wifi-knowledge"


def configuration():
    chips = ("chip12", "chip08", "chip07c")
    return {
        "schema_version": "1.0",
        "workspace_id": "synthetic-workspace",
        "knowledge_roots": {"wifi": "aiot-wifi-knowledge"},
        "repos": [{"repo_id": "wifi-code", "kind": "git", "root": None, "expected_identity": None}],
        "architecture": [
            {
                "binding_id": "wifi-main",
                "repo_id": "wifi-code",
                "module_root": ".",
                "knowledge_domain": "wifi",
                "override_nested": False,
            }
        ],
        "wiki_entities": {},
        "symbol_aliases": {},
        "targets": [
            {
                "target_id": f"{chip}-{side}",
                "chip": chip,
                "side": side,
                "source_bindings": [],
                "module_roots": [],
                "build_profile": None,
                "required_features": [],
                "protocol_versions": [],
            }
            for chip in chips
            for side in ("host", "device")
        ],
        "pairs": [
            {
                "pairing_id": f"{chip}-host-device",
                "host_target": f"{chip}-host",
                "device_target": f"{chip}-device",
                "compatibility_policy": "unknown",
            }
            for chip in chips
        ],
        "query": {"default_channel": "local", "allowed_channels": ["local", "shared"]},
    }


def run_validation(tmp_path, document, kind="workspace", knowledge_root=KNOWLEDGE):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    before = source.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "contract",
            "validate",
            "--kind",
            kind,
            "--input",
            str(source),
            "--knowledge-root",
            str(knowledge_root),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert source.read_bytes() == before
    return result


def test_valid_unknown_target_configuration_is_accepted_without_claiming_deployment(tmp_path):
    result = run_validation(tmp_path, configuration())
    assert result.returncode == 0, result.stderr or result.stdout
    body = json.loads(result.stdout)
    assert body["status"] == "ok"
    assert body["result"]["validation"] == "shape_and_configuration"
    assert body["result"]["business_ready"] is False
    assert body["result"]["unknown_targets"] == [
        "chip07c-device",
        "chip07c-host",
        "chip08-device",
        "chip08-host",
        "chip12-device",
        "chip12-host",
    ]


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda c: c.update(schema_version="9.0"), "SCHEMA_VALIDATION"),
        (lambda c: c["pairs"][0].update(device_target="chip08-device"), "INVALID_PAIR"),
        (lambda c: c["targets"][0].update(target_id="chip08-host"), "DUPLICATE_TARGET"),
        (lambda c: c["targets"][0].update(source_bindings=["missing-repo"]), "SOURCE_REF_MISSING"),
    ],
)
def test_invalid_configuration_has_machine_diagnostics_without_input_mutation(
    tmp_path, mutation, code
):
    document = configuration()
    mutation(document)
    result = run_validation(tmp_path, document)
    assert result.returncode == 2
    body = json.loads(result.stdout)
    assert body["status"] == "invalid"
    assert code in {d["code"] for d in body["diagnostics"]}
    assert "Traceback" not in result.stderr


def cloned_contracts(tmp_path):
    root = tmp_path / "knowledge"
    shutil.copytree(KNOWLEDGE / "governance", root / "governance")
    return root


def test_modified_schema_does_not_use_stale_lock(tmp_path):
    root = cloned_contracts(tmp_path)
    target = root / "governance/schemas/workspace.schema.json"
    target.write_bytes(target.read_bytes() + b" ")
    result = run_validation(tmp_path, configuration(), knowledge_root=root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "LOCK_DIGEST_MISMATCH"


def test_remote_schema_ref_is_rejected_even_when_hash_matches(tmp_path):
    root = cloned_contracts(tmp_path)
    target = root / "governance/schemas/workspace.schema.json"
    target.write_text(json.dumps({"$ref": "https://invalid.example/never-fetch"}), encoding="utf-8")
    lock_file = root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
    lock["files"]["workspace"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    lock_file.write_text(yaml.safe_dump(lock), encoding="utf-8")
    result = run_validation(tmp_path, configuration(), knowledge_root=root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "REMOTE_SCHEMA_REFERENCE"


@pytest.mark.parametrize(
    "content",
    ["schema_version: '1.0'\nschema_version: '9.0'\n", "!!python/object:os.system {}", "{unclosed"],
)
def test_invalid_yaml_is_diagnostic_not_a_tool_crash(tmp_path, content):
    source = tmp_path / "invalid.yml"
    source.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "contract",
            "validate",
            "--kind",
            "workspace",
            "--input",
            str(source),
            "--knowledge-root",
            str(KNOWLEDGE),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_DOCUMENT"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("arguments", [["unknown"], ["contract", "validate", "--kind", "unknown"]])
def test_invalid_cli_arguments_use_same_json_envelope(arguments):
    result = subprocess.run(
        [sys.executable, str(CLI), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_ARGUMENTS"


@pytest.mark.parametrize(
    "profile", ["entity", "flow", "protocol", "rule", "command", "runbook", "glossary"]
)
def test_seven_profiles_accept_document_declarations_without_code_gate_records(tmp_path, profile):
    card = {
        "schema_version": "1.0",
        "id": "synthetic-card",
        "profile": profile,
        "title": "Synthetic document statement",
        "summary": "Fixture; no business fact",
        "lifecycle": "stable",
        "review_mode": "manual_document",
        "owner": "synthetic",
        "scope": {"applicability": "universal", "contexts": []},
        "aliases": [],
        "sources": ["synthetic-source@snapshot-1"],
        "claims": [
            {
                "id": "claim-1",
                "text_ref": "#statement",
                "evidence_kind": "design",
                "source_ids": ["synthetic-source@snapshot-1"],
                "context_ids": [],
                "usage": "guidance",
                "verification_requirements": [],
            }
        ],
        "relations": [],
    }
    result = run_validation(tmp_path, card, kind="card")
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["result"]["business_ready"] is False
    card["claims"][0]["evidence_kind"] = "assumed_true"
    invalid = run_validation(tmp_path, card, kind="card")
    assert invalid.returncode == 2


def test_sources_empty_lock_has_no_coverage_claim_and_malformed_snapshot_is_rejected(tmp_path):
    lock = {"schema_version": "1.0", "resources": [], "snapshots": []}
    result = run_validation(tmp_path, lock, kind="sources")
    assert result.returncode == 0
    assert json.loads(result.stdout)["result"]["business_ready"] is False
    lock["snapshots"] = [{"snapshot_id": "missing-real-bytes"}]
    assert run_validation(tmp_path, lock, kind="sources").returncode == 2


def test_manual_record_requires_confirmation_reference_but_not_code_pass_records(tmp_path):
    record = {
        "schema_version": "1.0",
        "record_kind": "manual_review",
        "review_id": "synthetic-review",
        "operation_id": "synthetic-operation",
        "review_mode": "manual_document",
        "baseline_digest": "0" * 64,
        "target_file_digests": {"knowledge/synthetic.md": "1" * 64},
        "card_ids": ["synthetic-card"],
        "claim_decisions": [],
        "source_snapshot_refs": ["synthetic-source@snapshot-1"],
        "source_set_digest": "2" * 64,
        "scope_digest": "3" * 64,
        "decision": "accepted",
        "confirmed_by": "synthetic-test-actor",
        "confirmed_at": "2026-10-19T00:00:00Z",
        "confirmation_ref": "synthetic-test-action",
        "limitations": ["Shape-only fixture; this is not a real human confirmation"],
    }
    result = run_validation(tmp_path, record, kind="record")
    assert result.returncode == 0, result.stdout
    del record["confirmation_ref"]
    assert run_validation(tmp_path, record, kind="record").returncode == 2


def test_contract_lock_cannot_escape_declared_knowledge_root(tmp_path):
    root = cloned_contracts(tmp_path)
    lock_file = root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    lock["files"]["workspace"] = {
        "path": "../outside.json",
        "sha256": hashlib.sha256(b"{}").hexdigest(),
    }
    lock_file.write_text(yaml.safe_dump(lock), encoding="utf-8")
    result = run_validation(tmp_path, configuration(), knowledge_root=root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "CONTRACT_PATH_ESCAPE"


def test_importing_shared_modules_has_no_filesystem_side_effects(tmp_path):
    code = (
        "import sys;sys.path.insert(0,sys.argv[1]);"
        "import _shared, _shared.receipts, _shared.contracts, _shared.scope"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(ROOT / "skills/common/knowledge")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_dangling_local_schema_ref_uses_diagnostic_instead_of_traceback(tmp_path):
    root = cloned_contracts(tmp_path)
    schema_path = root / "governance/schemas/workspace.schema.json"
    schema_path.write_bytes(b'{"$ref":"#/$defs/missing"}')
    lock_file = root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_file.read_text(encoding="utf-8"))
    lock["files"]["workspace"]["sha256"] = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    lock_file.write_text(yaml.safe_dump(lock), encoding="utf-8")
    result = run_validation(tmp_path, configuration(), knowledge_root=root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "INVALID_SCHEMA_REFERENCE"
    assert "Traceback" not in result.stderr


def test_schema_parsing_cannot_read_different_bytes_than_pinned_digest(tmp_path, monkeypatch):
    from _shared import contracts

    root = cloned_contracts(tmp_path)
    target = root / "governance/schemas/workspace.schema.json"
    original = target.read_bytes()
    read_text = Path.read_text

    def temporarily_replace_during_parse(path, *args, **kwargs):
        if path == target:
            path.write_bytes(b"{}")
            try:
                return read_text(path, *args, **kwargs)
            finally:
                path.write_bytes(original)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", temporarily_replace_during_parse)
    diagnostics = contracts.validate_document("workspace", {"schema_version": "invalid"}, root)
    assert diagnostics and all(d["code"] == "SCHEMA_VALIDATION" for d in diagnostics)
