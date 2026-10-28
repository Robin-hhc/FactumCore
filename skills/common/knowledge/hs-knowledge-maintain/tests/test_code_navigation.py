"""Read-only maintenance distinguishes symbolic navigation from evidence bytes."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "maintenance_navigation_contract_helpers", ROOT / "himate-knowledge-wifi-mp/evals/contract_test_support.py"
)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def navigation_case(tmp_path):
    root = tmp_path / "knowledge-root"
    evidence = root / "logs/evidence"
    evidence.mkdir(parents=True)
    old = b"int selected(void) { return 1; }\n"
    current = b"// line inserted\nint selected(void) { return 2; }\n"
    (evidence / "source.c").write_bytes(old)
    (tmp_path / "config.yml").write_text("schema_version: '2.0'\n", encoding="utf-8")
    reference = {"evidence_ref": "e1", "source_id": "code", "snapshot_id": "old",
                 "locator": {"kind": "lines", "start": 1, "end": 1},
                 "code_ref": {"kind": "function", "name": "selected", "scope": []}}
    resource = {"source_id": "code", "kind": "code", "repo_id": "repo", "path": "file.c"}
    lock = {"schema_version": "2.0", "resources": [resource], "snapshots": [{
        "source_id": "code", "snapshot_id": "old", "sha256": sha(old), "bytes": len(old),
        "recovery": {"path": "logs/evidence/source.c"}, "extraction": {"extractor": "code-utf8:1"}}]}
    navigation = {"status": "resolved", "code": "CODE_SYMBOL_RESOLVED", "reason": "Unique function",
                  "path": "file.c", "sha256": sha(current), "range": {"start_line": 2, "end_line": 2},
                  "matches": [{"kind": "function", "name": "selected", "scope": [],
                               "parameter_types": [], "qualifiers": [],
                               "range": {"start_line": 2, "end_line": 2}}]}
    resolved = {"text": old.decode(), "current_source_matches": False,
                "current_source_sha256": sha(current), "code_navigation": navigation}
    claim = {"id": "c1", "usage": "guidance", "source_refs": ["e1"], "source_records": [reference]}
    card = {"path": "knowledge/rules/design.md", "sha256": "f" * 64,
            "metadata": {"id": "design", "claims": [claim], "relations": [], "sources": [reference]},
            "claims": [claim]}
    path = root / card["path"]
    path.parent.mkdir(parents=True)
    path.write_text("synthetic card transport fixture", encoding="utf-8")
    resources = HELPERS.module("source_resources")
    modules = {"validation": HELPERS.module("validation"),
               "source_resources": SimpleNamespace(
                   validate_source_ref=resources.validate_source_ref,
                   recover_snapshot=resources.recover_snapshot,
                   extract_code_text=resources.extract_code_text,
                   resolve_code_navigation=lambda *args, **kwargs: navigation),
               "source_operations": SimpleNamespace(
                   resolve_source=lambda *args: resolved,
                   symbol_cache=HELPERS.module("source_operations").symbol_cache),
               "knowledge": SimpleNamespace(decode_card=lambda *args: card)}
    context = SimpleNamespace(root=root, modules=modules, operation="navigation", rules={},
                              args=SimpleNamespace(rules_digest="fixture"),
                              record=lambda ref, kind: json.loads((root / ref).read_bytes()))
    observed = {"observation": "available", "current_sha256": sha(current), "raw": current}
    return context, card, reference, resource, lock, observed, resolved


def test_inspect_context_does_not_require_repair_for_guidance_with_resolved_symbol(navigation_case):
    context, *_ = navigation_case
    result, phase = HELPERS.module("maintenance").inspect_context(context)
    assert phase == "inspected"
    assert result["affected_claims"] == []


def test_inspect_context_reports_symbol_navigation_without_relabeling_the_hash(navigation_case):
    context, _, reference, _, _, observed, _ = navigation_case
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    observation = result["code_navigation"][0]
    assert observation["source_ref"] == reference
    assert observation["claim_ids"] == ["c1"]
    assert observation["code_navigation"]["status"] == "resolved"
    assert observation["current_source_matches"] is False
    assert observation["current_source_sha256"] == observed["current_sha256"]


def test_inspect_context_retains_durable_current_restriction_without_imposing_it_on_guidance(navigation_case):
    context, card, reference, *_ = navigation_case
    current = {**card["claims"][0], "id": "current", "usage": "current"}
    card["claims"].append(current)
    state = {"validity_epoch": 1, "blocked_claims": [{"card_id": "design", "claim_id": "*",
             "reason": "code_changed", "source_id": "code", "old_snapshot_ids": ["old"]}]}
    path = context.root / "logs/events/state.json"
    path.parent.mkdir(parents=True)
    original = json.dumps(state).encode()
    path.write_bytes(original)
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert {row["claim_id"] for row in result["affected_claims"]} == {"current"}
    assert result["state"] == state
    assert path.read_bytes() == original
    assert reference["snapshot_id"] == "old"


def test_reference_audit_keeps_changed_hash_without_requesting_resolved_guidance_repair(navigation_case):
    context, card, reference, resource, lock, observed, _ = navigation_case
    row = HELPERS.module("reference_audit").reference_row(
        context, card, reference, resource, lock, None, observed)
    assert row["observation"] == "changed"
    assert row["current_source_matches"] is False
    assert row["code_navigation"]["status"] == "resolved"
    assert row["code_navigation"]["range"] == {"start_line": 2, "end_line": 2}
    assert row["effect"] == "guidance_navigation_resolved"
    assert row["old_locator"] == {"kind": "lines", "start": 1, "end": 1}
    assert row["old_fragment"] == "int selected(void) { return 1; }\n"


@pytest.mark.parametrize("status", ["missing", "ambiguous", "unavailable"])
def test_inspect_context_reports_actual_symbol_problem_for_guidance(navigation_case, status):
    context, _, _, _, _, _, resolved = navigation_case
    resolved["code_navigation"]["status"] = status
    resolved["code_navigation"]["matches"] = []
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert [row["reason"] for row in result["affected_claims"]] == ["code_navigation_" + status]


@pytest.mark.parametrize("usage,expected", [("current", "current_reference_needs_review"),
                                           ("historical", "historical_reference")])
def test_audit_navigation_does_not_reclassify_current_or_historical_evidence(navigation_case, usage, expected):
    context, card, reference, resource, lock, observed, _ = navigation_case
    card["metadata"]["claims"][0]["usage"] = usage
    row = HELPERS.module("reference_audit").reference_row(context, card, reference, resource, lock, None, observed)
    assert row["effect"] == expected
    assert row["code_navigation"]["status"] == "resolved"
    assert row["current_source_matches"] is False


def test_legacy_guidance_retains_byte_drift_review_behavior(navigation_case):
    context, card, reference, resource, lock, observed, _ = navigation_case
    reference.pop("code_ref")
    inspection, _ = HELPERS.module("maintenance").inspect_context(context)
    assert [row["reason"] for row in inspection["affected_claims"]] == ["source_changed"]
    row = HELPERS.module("reference_audit").reference_row(context, card, reference, resource, lock, None, observed)
    assert "code_navigation" not in row
    assert row["effect"] == "guidance_navigation_needs_review"


def test_symbol_resolution_never_clears_an_unbound_semantic_restriction(navigation_case):
    context, *_ = navigation_case
    state = {"validity_epoch": 1, "blocked_claims": [{"card_id": "design", "claim_id": "c1",
             "reason": "code_changed"}]}
    path = context.root / "logs/events/state.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert [row["reason"] for row in result["affected_claims"]] == ["code_changed"]
    assert result["state"] == state


def test_audit_markdown_shows_current_symbol_position_separately_from_old_locator(navigation_case):
    context, card, reference, resource, lock, observed, _ = navigation_case
    audit = HELPERS.module("reference_audit")
    row = audit.reference_row(context, card, reference, resource, lock, None, observed)
    payload = {"status": "passed", "complete": True, "rules_digest": "fixture",
               "references": [row], "counts": {}, "gaps": []}
    report = audit.markdown(payload, ".build/audit.json").decode("utf-8")
    assert "当前符号导航：`resolved`" in report
    assert "file.c#L2-L2" in report
    assert "'start': 1, 'end': 1" in report


def test_public_audit_and_inspection_retain_guidance_after_source_body_and_line_change(harness):
    spec = importlib.util.spec_from_file_location(
        "navigation_public_audit_fixture", Path(__file__).with_name("test_reference_audit.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    source, old, _, checkout = fixture.code_fixture(harness, ("guidance",))
    path = harness.root / "knowledge/rules/audit-guidance.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(header)
    metadata["sources"][0]["code_ref"] = {"kind": "function", "name": "selected_fixture",
                                           "scope": [], "parameter_types": []}
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
    source.write_bytes(b"// position changed\n" + old.replace(b"1", b"2"))
    fixed = fixture.lint_report(harness, checkout)
    before = fixture.protected_bytes(harness)
    response = harness.run("maintain", {"operation_id": "symbol-audit", "lint_report_ref": fixed}, "audit-references")
    row = harness.record(response["data"]["audit_ref"])["references"][0]
    assert row["observation"] == "changed" and row["current_source_matches"] is False
    assert row["code_navigation"]["status"] == "resolved"
    assert row["code_navigation"]["range"]["start_line"] == 2
    assert row["effect"] == "guidance_navigation_resolved"
    inspection = harness.run("maintain", {"operation_id": "symbol-inspect"}, "inspect-context")["data"]
    assert inspection["affected_claims"] == []
    assert inspection["code_navigation"][0]["current_source_matches"] is False
    assert fixture.protected_bytes(harness) == before
