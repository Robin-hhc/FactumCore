"""Independent current-context manifest includes uncommitted checked file bytes."""

import hashlib
import base64
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
fixture_spec = importlib.util.spec_from_file_location("current_code_fixture", ROOT / "skills/common/knowledge/hs-knowledge-lint/tests/test_public_code_gate.py")
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)
contract_spec = importlib.util.spec_from_file_location("current_code_contract", ROOT / "himate-knowledge-wifi-mp/governance/contracts/__init__.py", submodule_search_locations=[str(ROOT / "himate-knowledge-wifi-mp/governance/contracts")])
contract = importlib.util.module_from_spec(contract_spec)
sys.modules[contract_spec.name] = contract
contract_spec.loader.exec_module(contract)
from current_code_contract import knowledge, source_resources, validation  # noqa: E402


def test_accepted_code_identity_detects_dirty_bytes_configuration_and_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("HIMATE_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests(methodName="test_signed_positive_support_then_apply_and_verify")
    environment.setUp()
    try:
        rules = validation.load_rules(environment.root, environment.rules_digest)
        context = json.loads((environment.root / environment.context_ref).read_bytes())
        identity = {
            "repos": {"wifi-code": {"root": str(environment.code), "head": environment.head,
                                    "files": {"src/wifi.c": hashlib.sha256(environment.source).hexdigest()}, "checked_files_dirty": False}},
            "target": context["target"], "macro_digest": context["build_evidence"]["macro_digest"],
            "build_files": {row["path"]: row["sha256"] for row in context["build_evidence"]["artifacts"]},
        }
        config = environment.workspace / "config.yml"
        config_raw = config.read_bytes()
        arguments = (identity, config, context["config_digest"], rules, environment.catalog["code_policy"])
        assert source_resources.validate_current_code_identity(*arguments) == identity
        card_write = environment.view["writes"][0]
        card = knowledge.parse_card(base64.b64decode(card_write["bytes_b64"]), card_write["path"], rules)
        source_lock = json.loads(base64.b64decode(environment.view["writes"][1]["bytes_b64"]))
        checked = source_resources.validate_code_references(card, source_lock, {
            "configuration": str(config), "config_digest": context["config_digest"],
            "repos": {"wifi-code": {"root": str(environment.code), "commit": environment.head}},
        }, rules)
        assert checked == [{"repo_id": "wifi-code", "path": "src/wifi.c", "commit": environment.head,
                            "sha256": hashlib.sha256(environment.source).hexdigest()}]
        source = environment.code / "src/wifi.c"
        source.write_bytes(b"int fixture_wifi_ready(void) { return 2; }\n")
        with pytest.raises(ValueError, match="CODE_"):
            source_resources.validate_current_code_identity(*arguments)
        config.write_bytes(config_raw)
        environment.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "new isolated revision")
        with pytest.raises(ValueError, match="CODE_REPOSITORY_CHANGED"):
            source_resources.validate_current_code_identity(*arguments)
        source.write_bytes(environment.source)
        config.write_bytes(config.read_bytes() + b"\n")
        with pytest.raises(ValueError, match="CODE_"):
            source_resources.validate_current_code_identity(*arguments)
    finally:
        environment.doCleanups()
