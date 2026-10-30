"""Migrated declared review coverage through lint's public record-review action."""
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


def change_record(harness, ref, **changes):
    record = harness.record(ref)
    record.update(changes)
    record.pop("digest")
    record["digest"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    harness.write(ref, json.dumps(record).encode())
    return record


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


def test_substantive_skip_review_records_unselected_scope(harness):
    value = request(harness)
    value['units'][0]['outcome'] = 'skip'
    value['claim_changes'], value['card_actions'] = ([], [])
    plan = harness.run('change-plan', value, action='plan')['data']['semantic_plan_ref']
    result = harness.run('lint', {'operation_id': 'op', 'semantic_plan_ref': plan, 'reviewer_id': 'reviewer', 'independent_context': 'fresh-context', 'sampled_unit_ids': ['u1'], 'unreviewed_unit_ids': [], 'reason': 'Changed numeric requirement is high risk', 'findings': []}, action='record-review')
    review = harness.record(result['data']['content_review_ref'])
    assert review['sampled_unit_ids'] == ['u1']
    assert review['status'] == 'passed'
    assert review['verification_tier'] == 'declared_content_review'


@pytest.mark.parametrize("outcome", ["defer", "failed", "uncovered"])
@pytest.mark.parametrize("maintenance", [False, True], ids=["source", "maintenance"])
def test_record_only_dispositions_have_real_review_scope_and_can_be_returned(harness, outcome, maintenance):
    value = request(harness)
    value["units"][0]["outcome"] = outcome
    value["claim_changes"], value["card_actions"] = [], []
    sampled = ["u1"]
    target = "u1"
    if maintenance:
        target = "maintenance:existing#c1"
        scan = change_record(harness, value["scan_ref"], current_context={
            "affected_claims": [{"card_id": "existing", "claim_id": "c1"}]})
        change_record(harness, value["material_ref"], scan_digest=scan["digest"])
        value["maintenance_units"] = [{"unit_id": target, "card_id": "existing", "claim_id": "c1",
                                       "outcome": outcome, "reason": "Required exact material is unavailable"}]
        sampled.append(target)
    plan = harness.run("change-plan", value, "plan")["data"]["semantic_plan_ref"]
    review_request = {"operation_id": "op", "semantic_plan_ref": plan,
                     "sampled_unit_ids": sampled, "unreviewed_unit_ids": [],
                     "reason": "Read the recorded gap, its evidence and required next step", "findings": []}
    accepted = harness.run("lint", review_request, "record-review")
    actual = harness.record(accepted["data"]["content_review_ref"])
    assert accepted["phase"] == "reviewed" and target in actual["sampled_unit_ids"]
    empty = harness.run("lint", {**review_request, "sampled_unit_ids": [], "unreviewed_unit_ids": sampled},
                        "record-review", expected=2)
    assert empty["diagnostics"][0]["code"] == "REVIEW_SCOPE_INVALID"
    finding = {"unit_id": target, "return_to": "P2", "reason": "The recorded gap needs a precise next step",
               "evidence": [{"reference": value["material_ref"], "locator": "gaps"}]}
    returned = harness.run("lint", {**review_request, "findings": [finding]}, "record-review", expected=1)
    record = harness.record(returned["data"]["content_review_ref"])
    assert returned["phase"] == "needs_revision" and record["findings"] == [finding]
    assert not (harness.root / "logs/ingest/op.yaml").exists()

@pytest.mark.parametrize('identities', [{}, {'reviewer_id': 'author', 'independent_context': ''}])
def test_review_checks_content_without_role_separation_gate(harness, identities):
    value = request(harness)
    plan = harness.run('change-plan', value, action='plan')['data']['semantic_plan_ref']
    result = harness.run('lint', {'operation_id': 'op', 'semantic_plan_ref': plan, 'sampled_unit_ids': ['u1'], 'unreviewed_unit_ids': [], 'reason': 'Read the exact changed scope', 'findings': [], **identities}, action='record-review')
    review = harness.record(result['data']['content_review_ref'])
    assert review['status'] == 'passed'
    assert review['plan_digest'] == harness.record(plan)['digest']
    assert 'independent' not in result['data']['skip_sample']
    for key, expected in identities.items():
        assert review[key] == expected
    if not identities:
        assert 'reviewer_id' not in review and 'independent_context' not in review

def test_review_still_rejects_missing_business_scope_and_findings(harness):
    value = request(harness)
    plan = harness.run('change-plan', value, action='plan')['data']['semantic_plan_ref']
    base = {'operation_id': 'op', 'semantic_plan_ref': plan, 'reason': 'Read the exact changed scope'}
    scope = harness.run('lint', {**base, 'findings': []}, action='record-review', expected=2)
    assert scope['diagnostics'][0]['code'] == 'REVIEW_SCOPE_INVALID'
    findings = harness.run('lint', {**base, 'sampled_unit_ids': ['u1']}, action='record-review', expected=2)
    assert findings['diagnostics'][0]['code'] == 'REVIEW_FINDINGS_REQUIRED'

def test_mixed_batch_does_not_review_completed_unchanged_scan_skip_again(harness):
    value = request(harness)
    original = harness.record(value['scan_ref'])
    old = {**original['units'][0], 'unit_id': 'u2', 'path': 'docs-raw/specs/unchanged.md', 'change': 'unchanged', 'progress': 'skipped'}
    scan = sealed(harness, value['scan_ref'], 'source_inventory', scope=original['scope'], full_scan=True, complete=True, units=original['units'] + [old])
    sealed(harness, value['material_ref'], 'artifact_manifest', purpose='source_materials', scan_ref=scan, scan_digest=harness.record(scan)['digest'])
    value['units'].append({'unit_id': 'u2', 'outcome': 'skip', 'reason': 'P1 unchanged completed scan skip'})
    plan = harness.run('change-plan', value, 'plan')['data']['semantic_plan_ref']
    reviewed = harness.run('lint', {'operation_id': 'op', 'semantic_plan_ref': plan, 'reviewer_id': 'reviewer', 'independent_context': 'fresh', 'sampled_unit_ids': ['u1'], 'unreviewed_unit_ids': [], 'reason': 'Only changed input needs review', 'findings': []}, 'record-review')
    assert reviewed['phase'] == 'reviewed'


def test_explicit_material_skip_review_uses_actual_scope_without_scan_exemption(harness):
    value = request(harness)
    del value["scan_ref"]
    sealed(harness, value["material_ref"], "artifact_manifest", purpose="source_materials", units=[{
        "unit_id": "u1", "origin": "explicit_target", "target_id": "u1", "source_kind": "raw",
        "path": "docs-raw/specs/source.md", "observed_fingerprint": "a" * 64}])
    value["units"][0]["outcome"] = "skip"
    value["claim_changes"], value["card_actions"] = [], []
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    review_request = {"operation_id": "op", "semantic_plan_ref": plan, "sampled_unit_ids": ["u1"],
        "unreviewed_unit_ids": [], "reason": "Read explicit target before accepting its skip", "findings": []}
    result = harness.run("lint", review_request, action="record-review")
    review = harness.record(result["data"]["content_review_ref"])
    assert review["observation_basis"] == "explicit_material_targets"
    assert "scan_digest" not in review
    missing = harness.run("lint", {**review_request, "sampled_unit_ids": [], "unreviewed_unit_ids": ["u1"]},
                          action="record-review", expected=2)
    assert missing["diagnostics"][0]["code"] == "REVIEW_SCOPE_INVALID"


@pytest.mark.parametrize("return_to", ["P1", "P2", "P3"])
def test_review_findings_keep_evidence_and_explicit_return_stage(harness, return_to):
    value = request(harness)
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    finding = {"unit_id": "u1", "return_to": return_to, "reason": "Exact scope requires correction",
               "evidence": [{"source": "actual reviewed material", "locator": "L2"}]}
    result = harness.run("lint", {"operation_id": "op", "semantic_plan_ref": plan,
        "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Read actual changed scope",
        "findings": [finding]}, action="record-review", expected=1)
    review = harness.record(result["data"]["content_review_ref"])
    assert result["phase"] == "needs_revision" and review["status"] == "failed"
    assert review["findings"] == [finding]


def test_review_rejects_the_former_candidate_stage_number(harness):
    value = request(harness)
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    result = harness.run("lint", {"operation_id": "op", "semantic_plan_ref": plan,
        "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Read actual changed scope",
        "findings": [{"unit_id": "u1", "return_to": "P4", "reason": "The old candidate stage is obsolete",
                      "evidence": [{"source": "actual reviewed material", "locator": "L2"}]}]},
        action="record-review", expected=2)
    assert result["diagnostics"][0]["code"] == "INVALID_REVIEW_FINDING"
    assert not list((harness.root / ".build/operations/op/content-review").glob("*.json"))


@pytest.mark.parametrize("foreign_operation", [False, True])
def test_review_rejects_changed_or_foreign_actual_scan(harness, foreign_operation):
    value = request(harness)
    plan_ref = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    scan = change_record(harness, value["scan_ref"], operation_id="foreign" if foreign_operation else "op",
                         scope=["docs-raw/specs/source.md"])
    if foreign_operation:
        change_record(harness, plan_ref, scan_digest=scan["digest"])
    result = harness.run("lint", {"operation_id": "op", "semantic_plan_ref": plan_ref,
        "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Actual scan must stay bound",
        "findings": []}, action="record-review", expected=2)
    assert result["diagnostics"][0]["code"] == "REVIEW_SCAN_MISMATCH"


def test_review_binds_actual_complete_view_and_rejects_another_operation(harness):
    value = request(harness)
    plan_ref = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    plan = harness.record(plan_ref)
    view_ref, _ = harness.view()
    view = change_record(harness, view_ref, semantic_plan_ref=plan_ref, semantic_plan_digest=plan["digest"])
    review_request = {"operation_id": "op", "semantic_plan_ref": plan_ref, "view_ref": view_ref,
        "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Read exact complete draft", "findings": []}
    result = harness.run("lint", review_request, action="record-review")
    assert harness.record(result["data"]["content_review_ref"])["view_digest"] == view["digest"]
    change_record(harness, view_ref, operation_id="foreign")
    rejected = harness.run("lint", review_request, action="record-review", expected=2)
    assert rejected["diagnostics"][0]["code"] == "REVIEW_VIEW_MISMATCH"
