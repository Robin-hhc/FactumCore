"""Static source admission retains exact identity without claiming a build."""

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
DOMAIN = ROOT / "aiotbot-knowledge-wifi-mp"
fixture_spec = importlib.util.spec_from_file_location(
    "source_admission_fixture",
    DOMAIN.parent / "skills/common/knowledge/hs-knowledge-local-check/tests/test_public_code_gate.py",
)
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)
contract_spec = importlib.util.spec_from_file_location(
    "source_admission_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(contract_spec)
sys.modules[contract_spec.name] = contract
contract_spec.loader.exec_module(contract)
from source_admission_contract import source_resources, validation  # noqa: E402


@pytest.mark.parametrize("usage, with_target, nested", [
    ("historical", False, False), ("guidance", True, False), ("current", True, False),
    ("current", True, True),
])
def test_source_identity_is_rechecked_without_build_artifacts(tmp_path, monkeypatch, usage, with_target, nested):
    monkeypatch.setenv("AIOTBOT_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests(methodName="test_signed_positive_support_then_apply_and_verify")
    environment.setUp()
    try:
        if nested:
            moved = environment.workspace / "aiotbot" / environment.root.name
            assert moved.resolve().is_relative_to(environment.workspace.resolve())
            moved.parent.mkdir()
            environment.root.rename(moved)
            environment.root = moved
            config_path = environment.workspace / "config.yml"
            config = yaml.safe_load(config_path.read_bytes())
            config["knowledge_roots"]["wifi"] = moved.relative_to(environment.workspace).as_posix()
            config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            context = json.loads((environment.root / environment.context_ref).read_bytes())
            context.update(knowledge_root=str(moved), config_digest=fixture.digest(config_path.read_bytes()))
            environment.save(environment.context_ref, fixture.seal(context))
        # Re-pin this newly created synthetic copy during parallel development.
        lock_path = environment.root / "governance/framework.lock.yaml"
        framework = yaml.safe_load(lock_path.read_bytes())
        for entry in framework["files"].values():
            entry["sha256"] = fixture.digest((environment.root / entry["path"]).read_bytes())
        lock_path.write_text(yaml.safe_dump(framework, sort_keys=False), encoding="utf-8")
        environment.rules_digest = fixture.digest(lock_path.read_bytes())
        if usage == "current":
            context = json.loads((environment.root / environment.context_ref).read_bytes())
            context.pop("build_evidence")
            environment.save(environment.context_ref, fixture.seal(context))
        else:
            environment.source_analysis_view(usage=usage, with_target=with_target)
        context = json.loads((environment.root / environment.context_ref).read_bytes())
        context["rules_digest"] = environment.rules_digest
        context = fixture.seal(context)
        environment.save(environment.context_ref, context)
        environment.view["rules_digest"] = environment.rules_digest
        environment.view = fixture.seal(environment.view)
        environment.save(environment.view_ref, environment.view)
        environment.catalog.pop("semantic_reviewers", None)
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        # Agent review is an ordinary bound content record. Its fixture facts
        # are independent literals; it uses no reviewer key or signature.
        environment.save(environment.report_ref, {
            "schema_version": "2.0", "record_kind": "semantic_review",
            "reviewer_id": "independent-source-reader",
            "payload": {
                "author_id": "fixture", "independent_context": "fresh-source-read-context",
                "findings": [], "view_digest": environment.view["digest"],
                "context_digest": context["digest"], "mode": "local", "issued_at": time.time(),
                "claims": [{
                    "card_id": "fixture-code-flow", "claim_id": "c1", "status": "supported",
                    "reason": "The actual function definition on line one returns the literal one.",
                    "evidence": [{
                        "source_id": "fixture-code", "snapshot_id": "fixture-code-snapshot",
                        "locator": {"kind": "lines", "start": 1, "end": 1,
                                    "repo_id": "wifi-code", "path": "src/wifi.c"},
                        "sha256": hashlib.sha256(b"int fixture_wifi_ready(void) { return 1; }\n").hexdigest(),
                    }],
                }],
            },
        })
        checked = environment.invoke()
        proof = json.loads((environment.root / checked["data"]["local_check_ref"]).read_bytes())
        assert checked["data"]["check_status"] == "passed", proof
        assert proof["verification_tier"] == "agent_content_review"
        assert "signature_b64" not in proof["semantic_report"]
        identity = proof["code_identity"]
        rules = validation.load_rules(environment.root, environment.rules_digest)
        arguments = (
            identity, environment.workspace / "config.yml", context["config_digest"],
            rules, environment.catalog["code_policy"],
        )
        assert source_resources.validate_current_code_identity(*arguments) == identity
        for name in ("hs-knowledge-index-build", "hs-knowledge-query", "hs-knowledge-query-regression", "hs-knowledge-source-capture"):
            package = DOMAIN.parent / "skills/common/knowledge" / name
            environment.catalog["skills"][name] = {
                "root": str(package), "entry": "scripts/cli.py", "python": sys.executable,
                "package_digest": fixture.package_digest(package),
            }
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        applied = environment.invoke("hs-knowledge-apply", request={
            "operation_id": "op", "view_ref": environment.view_ref,
            "proof_ref": checked["data"]["local_check_ref"],
        })
        assert applied["phase"] == "committed"
        verified = environment.invoke("hs-knowledge-apply", action="verify-result", request={
            "operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"],
        })
        assert verified["data"]["verification_scope"] == "verified_content_eligibility"
        assert verified["data"]["verification_tier"] == "agent_content_review"
        generation = environment.invoke("hs-knowledge-index-build", action="build", request={"operation_id": "op"})
        regression = environment.invoke("hs-knowledge-query-regression", request={
            "operation_id": "op", "generation_ref": generation["data"]["generation_ref"],
            "expected_active": None, "cases": [{
                "id": "static-source", "query": "Fixture", "required": ["fixture-code-flow"],
                "purpose": usage, "context": context.get("target") or {},
            }],
        })
        report = json.loads((environment.root / regression["data"]["report_ref"]).read_bytes())
        search_results = [json.loads((environment.root / row["receipt_ref"]).read_bytes())["result"]
                          for row in report["outcomes"]]
        assert regression["data"]["passed"] is True, (report, search_results)
        assert regression["data"]["activated"] is True
        searched = environment.invoke("hs-knowledge-query", action="search", request={
            "operation_id": "op", "query": "Fixture", "purpose": usage,
            "context": context.get("target") or {},
        })
        assert searched["data"]["matches"][0]["card_id"] == "fixture-code-flow"
        read = environment.invoke("hs-knowledge-query", action="read", request={
            "operation_id": "op", "receipt_ref": searched["data"]["receipt_ref"],
            "card_id": "fixture-code-flow",
        })
        assert read["data"]["generation_ref"] == searched["data"]["generation_ref"]
        assert not environment.root.joinpath(".git").exists()
        environment.code.joinpath("src/wifi.c").write_bytes(b"changed uncommitted source\n")
        with pytest.raises(ValueError, match="CODE_BYTES_CHANGED"):
            source_resources.validate_current_code_identity(*arguments)
        environment.invoke("hs-knowledge-apply", action="verify-result", request={
            "operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"],
        }, expected=3)
        if usage == "current":
            changed = environment.invoke("hs-knowledge-query", action="search", request={
                "operation_id": "op", "query": "Fixture", "purpose": "current",
                "context": context["target"],
            })
            assert changed["data"]["matches"] == []
    finally:
        environment.doCleanups()


def test_unsigned_v3_review_remains_valid_for_query_and_maintenance(tmp_path, monkeypatch):
    monkeypatch.setenv("AIOTBOT_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests(methodName="test_committed_code_capture_reaches_v3_apply_index_and_target_queries")
    environment.setUp()
    try:
        environment.catalog.pop("semantic_reviewers", None)
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        environment.test_committed_code_capture_reaches_v3_apply_index_and_target_queries()
        report = json.loads((environment.root / environment.report_ref).read_bytes())
        assert "signature_b64" not in report
        assert "semantic_reviewers" not in json.loads(environment.catalog_path.read_bytes())
        package = DOMAIN.parent / "skills/common/knowledge/hs-knowledge-maintain"
        environment.catalog["skills"][package.name] = {
            "root": str(package), "entry": "scripts/cli.py", "python": sys.executable,
            "package_digest": fixture.package_digest(package),
        }
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        inspected = environment.invoke("hs-knowledge-maintain", action="inspect-context", request={"operation_id": "op"})
        assert inspected["data"]["complete"] is True, inspected
        assert inspected["data"]["affected_claims"] == [], inspected
        environment.code.joinpath("src/wifi.c").write_bytes(b"int fixture_wifi_ready(void) { return 99; }\n")
        changed = environment.invoke("hs-knowledge-maintain", action="inspect-context", request={"operation_id": "op"})
        assert any(row["card_id"] == "fixture-code-flow" for row in changed["data"]["affected_claims"])
    finally:
        environment.doCleanups()
