"""Static source admission retains exact identity without claiming a build."""

from support.stages import lint_code as fixture
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[4]
DOMAIN = ROOT / "himate/himate-knowledge-wifi-mp"
contract_spec = importlib.util.spec_from_file_location(
    "source_admission_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
contract = importlib.util.module_from_spec(contract_spec)
sys.modules[contract_spec.name] = contract
contract_spec.loader.exec_module(contract)
from source_admission_contract import source_resources, validation  # noqa: E402

pipeline_spec = importlib.util.spec_from_file_location("source_admission_packages", DOMAIN / "evals/support/pipeline.py")
pipeline = importlib.util.module_from_spec(pipeline_spec)
pipeline_spec.loader.exec_module(pipeline)


def setup_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HIMATE_TEST_TMP", str(tmp_path))
    environment = fixture.PublicCodeGateTests()
    environment.setUp()
    environment.catalog["skills"] = {name: value for name, value in environment.catalog["skills"].items()
                                     if name in pipeline.PUBLIC_SKILLS}
    environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
    assert not any((fixture.SKILLS / name).exists() for name in pipeline.RETIRED_SKILLS)
    return environment


@pytest.mark.parametrize("usage, with_target, nested", [
    ("historical", False, False), ("guidance", True, False), ("current", True, False),
    ("current", True, True),
])
def test_source_identity_is_rechecked_without_build_artifacts(tmp_path, monkeypatch, usage, with_target, nested):
    environment = setup_environment(tmp_path, monkeypatch)
    try:
        if nested:
            moved = environment.workspace / "himate" / environment.root.name
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
        checked = environment.invoke("hs-knowledge-lint", "code-check")
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
        for name in ("hs-knowledge-apply", "hs-knowledge-query", "hs-knowledge-source"):
            package = fixture.SKILLS / name
            environment.catalog["skills"][name] = {
                "root": str(package), "entry": "scripts/cli.py", "python": sys.executable,
                "package_digest": fixture.package_digest(package),
            }
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        apply_request = {
            "operation_id": "op", "view_ref": environment.view_ref,
            "check_inputs": {},
        }
        if usage == "current":
            environment.code.joinpath("src/wifi.c").write_bytes(b"changed before apply without a commit\n")
            environment.invoke("hs-knowledge-apply", request=apply_request, expected=3)
            assert not (environment.root / "knowledge/flows/fixture-code-flow.md").exists()
            environment.code.joinpath("src/wifi.c").write_bytes(environment.source)
        applied = environment.invoke("hs-knowledge-apply", request=apply_request)
        assert applied["phase"] == "committed"
        verified = environment.invoke("hs-knowledge-apply", action="verify-result", request={
            "operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"],
        })
        assert verified["data"]["verification_scope"] == "verified_content_integrity"
        assert verified["data"]["verification_tier"] == "fixed_business_checks"
        generation = environment.invoke("hs-knowledge-apply", action="index-build", request={"operation_id": "op"})
        regression = environment.invoke("hs-knowledge-apply", action="regression", request={
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
        integrity = environment.invoke("hs-knowledge-apply", action="verify-result", request={
            "operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"],
        }, expected=3 if usage == "current" else 0)
        if usage != "current":
            assert integrity["data"]["verification_scope"] == "verified_content_integrity"
        historical = environment.invoke("hs-knowledge-apply", action="verify-result", request={
            "operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"],
            "purpose": "historical",
        })
        assert historical["data"]["eligible_files"] == []
        assert historical["data"]["historical_files"][0]["path"] == "knowledge/flows/fixture-code-flow.md"
        if usage == "current":
            changed = environment.invoke("hs-knowledge-query", action="search", request={
                "operation_id": "op", "query": "Fixture", "purpose": "current",
                "context": context["target"],
            })
            assert changed["data"]["matches"] == []
    finally:
        environment.doCleanups()


def test_unsigned_v3_review_remains_valid_for_query_and_maintenance(tmp_path, monkeypatch):
    environment = setup_environment(tmp_path, monkeypatch)
    try:
        environment.catalog.pop("semantic_reviewers", None)
        environment.catalog_path.write_bytes(fixture.canonical(environment.catalog))
        environment.prepare_committed_code_publication()
        report = json.loads((environment.root / environment.report_ref).read_bytes())
        assert "signature_b64" not in report
        assert "semantic_reviewers" not in json.loads(environment.catalog_path.read_bytes())
        package = fixture.SKILLS / "hs-knowledge-maintain"
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


def test_apply_retains_actual_build_fingerprints_without_review_or_context_files(tmp_path, monkeypatch):
    environment = setup_environment(tmp_path, monkeypatch)
    try:
        applied = environment.invoke("hs-knowledge-apply", request={
            "operation_id": "op", "view_ref": environment.view_ref, "check_inputs": {},
        })
        (environment.root / environment.context_ref).unlink()
        (environment.root / environment.report_ref).unlink()
        request = {"operation_id": "op", "apply_result_ref": applied["data"]["apply_result_ref"]}
        assert environment.invoke("hs-knowledge-apply", action="verify-result", request=request)["data"]["result_verified"]
        (environment.root / "logs/evidence/build.bin").write_bytes(b"changed supplied build material\n")
        rejected = environment.invoke("hs-knowledge-apply", action="verify-result", request=request, expected=3)
        assert "CODE_BUILD_CHANGED" in rejected["diagnostics"][0]["message"]
    finally:
        environment.doCleanups()
