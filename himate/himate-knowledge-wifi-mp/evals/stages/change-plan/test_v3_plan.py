import hashlib
import json
import pytest


def sealed(harness, path, kind, **value):
    record = {
        "schema_version": "2.0", "record_kind": kind,
        "operation_id": "op", "rules_digest": harness.rules,
        "tool_identity": {"skill": "hs-fixture", "package_digest": "a" * 64,
                          "runtime": "synthetic", "requirements_digest": "b" * 64}, **value,
    }
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    record["digest"] = hashlib.sha256(raw).hexdigest()
    harness.write(path, json.dumps(record).encode())
    return path


def request(harness):
    scan = sealed(harness, ".build/operations/op/scan.json", "source_inventory",
                  scope=["docs-raw/specs"], full_scan=True, complete=True,
                  units=[{"unit_id": "u1", "path": "docs-raw/specs/source.md", "source_id": "source",
                          "change": "modified", "observed_fingerprint": "a" * 64,
                          "previous_fingerprint": "b" * 64, "read_error": None, "progress": "pending"}])
    material = sealed(harness, ".build/operations/op/material.json", "artifact_manifest",
                      purpose="source_materials", scan_ref=scan, scan_digest=harness.record(scan)["digest"])
    return {
        "operation_id": "op", "v3_required": True,
        "scan_ref": scan, "material_ref": material, "author_id": "author",
        "units": [{"unit_id": "u1", "outcome": "content", "reason": "Timeout requirement changed"}],
        "claim_changes": [{"unit_ids": ["u1"], "card_id": "timeout", "claim_id": "limit",
                           "action": "update", "before": "5 seconds", "after": "8 seconds",
                           "conditions": "chip12 Host", "evidence": [{"source": "new", "locator": "L2"}],
                           "preserved": "Other chips unchanged", "reason": "New exact requirement"}],
        "card_actions": [{"card_id": "timeout", "decision": "update", "author_id": "author",
                          "unit_ids": ["u1"], "reason": "Same topic"}],
        "target_queries": [{"id": "timeout", "query": "timeout limit", "required": ["timeout"]}],
    }


def test_plan_precedes_draft_and_binds_claim_changes(harness):
    value = request(harness)
    result = harness.run("change-plan", value, action="plan")
    plan = harness.record(result["data"]["semantic_plan_ref"])
    assert result["phase"] == "content_planned"
    assert plan["claim_changes"][0]["after"] == "8 seconds"
    assert plan["units"][0]["record_action"] == "update"
    assert plan["units"][0]["card_refs"] == ["timeout"]
    assert plan["units"][0]["claim_refs"] == ["timeout#limit"]
    assert plan["target_queries"][0]["required"] == ["timeout"]
    assert not (harness.root / "knowledge").exists()


def test_plan_cannot_omit_frozen_scan_unit(harness):
    value = request(harness)
    value["units"] = []
    result = harness.run("change-plan", value, action="plan", expected=2)
    assert result["diagnostics"][0]["code"] == "PLAN_UNIT_COVERAGE"


@pytest.mark.parametrize("purpose", ["gudiance", "", None, 17, ["guidance"]])
def test_plan_rejects_invalid_query_purpose_before_freezing_view(harness, purpose):
    value = request(harness)
    value["target_queries"][0]["purpose"] = purpose
    result = harness.run("change-plan", value, action="plan", expected=2)
    assert result["diagnostics"][0]["code"] == "INVALID_TARGET_QUERY_PURPOSE"
    assert not (harness.root / ".build/operations/op/semantic-plan.json").exists()


@pytest.mark.parametrize("purpose", ["current", "implementation", "guidance", "historical"])
def test_plan_preserves_declared_query_purpose(harness, purpose):
    value = request(harness)
    value["target_queries"][0]["purpose"] = purpose
    result = harness.run("change-plan", value, action="plan")
    plan = harness.record(result["data"]["semantic_plan_ref"])
    assert plan["target_queries"][0]["purpose"] == purpose


@pytest.mark.parametrize("change,error", [("duplicate", "DUPLICATE_CLAIM_PLAN"), ("skip_write", "CLAIM_SOURCE_OUTCOME"), ("unrelated_query", "TARGET_QUERY_COVERAGE")])
def test_plan_rejects_conflicting_claims_skipped_writes_and_unrelated_queries(harness, change, error):
    value = request(harness)
    if change == "duplicate":
        value["claim_changes"].append({**value["claim_changes"][0], "after": "Conflicting claim"})
    elif change == "skip_write":
        value["units"][0]["outcome"] = "skip"
    else:
        value["target_queries"][0]["required"] = ["unrelated-old-card"]
    result = harness.run("change-plan", value, action="plan", expected=2)
    assert result["diagnostics"][0]["code"] == error


def test_code_only_maintenance_plan_does_not_invent_a_raw_processing_unit(harness):
    value = request(harness)
    scan = sealed(harness, value["scan_ref"], "source_inventory", scope=["docs-raw/specs"], full_scan=True, complete=True,
                  units=[], current_context={"affected_claims": [{"card_id": "timeout", "claim_id": "limit", "reason": "code_changed"}]})
    sealed(harness, value["material_ref"], "artifact_manifest", purpose="source_materials", scan_ref=scan, scan_digest=harness.record(scan)["digest"])
    value["units"] = []
    maintenance_id = "maintenance:timeout#limit"
    value["maintenance_units"] = [{"unit_id": maintenance_id, "card_id": "timeout", "claim_id": "limit",
                                  "outcome": "content", "reason": "Actual code context changed"}]
    value["claim_changes"][0]["unit_ids"] = [maintenance_id]
    value["card_actions"][0]["unit_ids"] = [maintenance_id]
    result = harness.run("change-plan", value, action="plan")
    plan = harness.record(result["data"]["semantic_plan_ref"])
    assert plan["units"] == []
    assert plan["maintenance_units"] == [{**value["maintenance_units"][0], "record_action": "update",
                                           "card_refs": ["timeout"], "claim_refs": ["timeout#limit"]}]


@pytest.mark.parametrize("selected", [None, "defer", "split"])
def test_mixed_content_unit_requires_an_authored_record_action(harness, selected):
    value = request(harness)
    value["card_actions"].append({**value["card_actions"][0], "card_id": "new-topic", "decision": "create"})
    value["claim_changes"].append({**value["claim_changes"][0], "card_id": "new-topic", "action": "create"})
    value["target_queries"][0]["required"].append("new-topic")
    if selected is not None:
        value["units"][0]["record_action"] = selected
    result = harness.run("change-plan", value, action="plan", expected=2)
    assert result["diagnostics"][0]["code"] == "PLAN_RECORD_ACTION_REQUIRED"
    assert not (harness.root / ".build/operations/op/semantic-plan.json").exists()


def test_mixed_content_unit_freezes_all_refs_and_selected_actual_action(harness):
    value = request(harness)
    value["card_actions"].append({**value["card_actions"][0], "card_id": "new-topic", "decision": "create"})
    value["claim_changes"].append({**value["claim_changes"][0], "card_id": "new-topic", "action": "create"})
    value["target_queries"][0]["required"].append("new-topic")
    value["units"][0]["record_action"] = "create"
    result = harness.run("change-plan", value, action="plan")
    unit = harness.record(result["data"]["semantic_plan_ref"])["units"][0]
    assert unit["record_action"] == "create"
    assert unit["card_refs"] == ["new-topic", "timeout"]
    assert unit["claim_refs"] == ["new-topic#limit", "timeout#limit"]


def test_explicit_material_targets_need_no_scan_or_scan_semantics(harness):
    value = request(harness)
    del value["scan_ref"]
    sealed(harness, value["material_ref"], "artifact_manifest", purpose="source_materials", units=[{
        "unit_id": "u1", "origin": "explicit_target", "target_id": "u1", "source_kind": "raw",
        "path": "docs-raw/specs/source.md", "observed_fingerprint": "a" * 64}])
    result = harness.run("change-plan", value, action="plan")
    plan = harness.record(result["data"]["semantic_plan_ref"])
    assert plan["observation_basis"] == "explicit_material_targets"
    assert "scan_ref" not in plan and "scan_digest" not in plan
    assert plan["units"][0]["record_action"] == "update"


@pytest.mark.parametrize("outcome", ["skip", "defer", "failed", "uncovered"])
def test_noncontent_unit_freezes_its_actual_outcome_for_recording(harness, outcome):
    value = request(harness)
    value["units"][0]["outcome"] = outcome
    value["claim_changes"], value["card_actions"] = [], []
    result = harness.run("change-plan", value, action="plan")
    unit = harness.record(result["data"]["semantic_plan_ref"])["units"][0]
    assert unit["record_action"] == outcome
    assert unit["card_refs"] == [] and unit["claim_refs"] == []
