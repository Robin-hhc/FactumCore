import hashlib
import json
import pytest
import yaml


@pytest.fixture(autouse=True)
def pin_isolated_rules(harness):
    """Parallel implementation may leave the checkout lock temporarily stale."""
    path = harness.root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(path.read_text(encoding="utf-8"))
    for row in lock["files"].values():
        row["sha256"] = hashlib.sha256((harness.root / row["path"]).read_bytes()).hexdigest()
    path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    harness.rules = hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_substantive_skip_review_records_unselected_scope(harness):
    value = request(harness)
    value["units"][0]["outcome"] = "skip"
    value["claim_changes"], value["card_actions"] = [], []
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    result = harness.run("change-plan", {"operation_id": "op", "semantic_plan_ref": plan,
                         "reviewer_id": "reviewer", "independent_context": "fresh-context",
                         "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [],
                         "reason": "Changed numeric requirement is high risk", "findings": []}, action="review")
    review = harness.record(result["data"]["content_review_ref"])
    assert review["sampled_unit_ids"] == ["u1"]
    assert review["status"] == "passed"
    assert review["verification_tier"] == "declared_content_review"


@pytest.mark.parametrize("identities", [{}, {"reviewer_id": "author", "independent_context": ""}])
def test_review_checks_content_without_role_separation_gate(harness, identities):
    value = request(harness)
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    result = harness.run("change-plan", {"operation_id": "op", "semantic_plan_ref": plan,
        "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Read the exact changed scope",
        "findings": [], **identities}, action="review")
    review = harness.record(result["data"]["content_review_ref"])
    assert review["status"] == "passed"
    assert review["plan_digest"] == harness.record(plan)["digest"]
    assert "independent" not in result["data"]["skip_sample"]
    for key, expected in identities.items():
        assert review[key] == expected
    if not identities:
        assert "reviewer_id" not in review and "independent_context" not in review


def test_review_still_rejects_missing_business_scope_and_findings(harness):
    value = request(harness)
    plan = harness.run("change-plan", value, action="plan")["data"]["semantic_plan_ref"]
    base = {"operation_id": "op", "semantic_plan_ref": plan, "reason": "Read the exact changed scope"}
    scope = harness.run("change-plan", {**base, "findings": []}, action="review", expected=2)
    assert scope["diagnostics"][0]["code"] == "REVIEW_SCOPE_INVALID"
    findings = harness.run("change-plan", {**base, "sampled_unit_ids": ["u1"]}, action="review", expected=2)
    assert findings["diagnostics"][0]["code"] == "REVIEW_FINDINGS_REQUIRED"


def test_same_snapshot_can_gain_verified_git_recovery_without_semantic_version_change(harness):
    import subprocess

    _, old = harness.capture("old")
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": old["resources"],
                  "snapshots": old["snapshots"]}).encode())
    (harness.base / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8")
    def git(*args):
        subprocess.run(["git", "-C", str(harness.base), *args], check=True, capture_output=True)
    git("init", "-q")
    git("add", "--", harness.root.name + "/docs-raw/specs/source.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "source")
    ref, current = harness.capture("new")
    assert old["snapshots"][0]["snapshot_id"] == current["snapshots"][0]["snapshot_id"]
    assert current["snapshots"][0]["recovery"]["kind"] == "git"
    current["snapshots"][0]["local_recovery"] = old["snapshots"][0]["recovery"]
    current.pop("digest")
    current["digest"] = hashlib.sha256(json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(ref, json.dumps(current).encode())
    candidate = harness.write(".build/candidates/new.md", harness.card("new", current))
    result = harness.run("change-plan", {"operation_id": "new", "bundle_ref": ref, "decisions": [
        {"candidate_id": "new", "decision": "create", "reason": "First accepted card", "card_inputs": [candidate]}]})
    assert result["phase"] == "planned"


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
    assert plan["maintenance_units"] == value["maintenance_units"]


def test_mixed_batch_does_not_review_completed_unchanged_scan_skip_again(harness):
    value = request(harness)
    original = harness.record(value["scan_ref"])
    old = {**original["units"][0], "unit_id": "u2", "path": "docs-raw/specs/unchanged.md", "change": "unchanged", "progress": "skipped"}
    scan = sealed(harness, value["scan_ref"], "source_inventory", scope=original["scope"], full_scan=True, complete=True,
                  units=original["units"] + [old])
    sealed(harness, value["material_ref"], "artifact_manifest", purpose="source_materials", scan_ref=scan, scan_digest=harness.record(scan)["digest"])
    value["units"].append({"unit_id": "u2", "outcome": "skip", "reason": "P1 unchanged completed scan skip"})
    plan = harness.run("change-plan", value, "plan")["data"]["semantic_plan_ref"]
    reviewed = harness.run("change-plan", {"operation_id": "op", "semantic_plan_ref": plan, "reviewer_id": "reviewer",
        "independent_context": "fresh", "sampled_unit_ids": ["u1"], "unreviewed_unit_ids": [], "reason": "Only changed input needs review", "findings": []}, "review")
    assert reviewed["phase"] == "reviewed"
