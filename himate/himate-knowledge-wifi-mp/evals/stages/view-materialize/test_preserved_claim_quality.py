"""Independent public counterexample: authored preservation must survive P4."""
import copy
import hashlib
import json
import pytest
import yaml


@pytest.mark.parametrize("draft_change", ["remove", "change_text", "change_usage"])
def test_draft_cannot_remove_a_claim_that_the_authored_plan_preserves(harness, draft_change):
    bundle_ref, bundle = harness.capture()
    old = harness.card("rule", bundle, lifecycle="stable", claim="edited")
    _, frontmatter, body = old.decode().split("---", 2)
    meta = yaml.safe_load(frontmatter)
    preserved = copy.deepcopy(meta["claims"][0])
    preserved.update(id="kept", text_ref="#kept")
    meta["claims"].append(preserved)
    old = ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body + '\n<a id="kept"></a>\nPreserve this independent scope.\n').encode()
    harness.write("knowledge/rules/rule.md", old)
    def sealed(kind, ref, **fields):
        record = {"schema_version": "2.0", "record_kind": kind, "operation_id": "op", "rules_digest": harness.rules, "tool_identity": bundle["tool_identity"], **fields}
        raw = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        record["digest"] = hashlib.sha256(raw).hexdigest()
        harness.write(ref, json.dumps(record).encode())
        return ref
    unit = "u1"
    scan_ref = sealed("source_inventory", ".build/operations/op/scan.json", scope=["docs-raw/specs"], full_scan=True, complete=True, units=[{"unit_id": unit, "path": "docs-raw/specs/source.md", "source_id": "synthetic", "observed_fingerprint": bundle["snapshots"][0]["sha256"], "previous_fingerprint": None, "change": "new", "read_error": None, "progress": None}])
    material_ref = sealed("source_materials", ".build/operations/op/material.json", purpose="source_materials", scan_ref=scan_ref, scan_digest=harness.record(scan_ref)["digest"])
    common = {"unit_ids": [unit], "card_id": "rule", "conditions": "fixture scope", "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}], "reason": "Explicit scope comparison", "preserved": "Keep independent scope"}
    semantic = harness.run("change-plan", {"operation_id": "op", "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "author", "units": [{"unit_id": unit, "outcome": "content", "reason": "Update one Claim"}],
        "claim_changes": [{**common, "claim_id": "edited", "action": "update", "before": "old", "after": "new"}, {**common, "claim_id": "kept", "action": "preserve", "before": "independent scope", "after": "independent scope"}],
        "card_actions": [{"card_id": "rule", "decision": "update", "author_id": "author", "unit_ids": [unit], "reason": "Only the first Claim changes"}], "target_queries": [{"id": "rule", "query": "rule", "required": ["rule"]}]}, "plan")["data"]["semantic_plan_ref"]
    if draft_change == "remove":
        candidate = harness.card("rule", bundle, claim="edited")
    elif draft_change == "change_text":
        candidate = old.replace(b"Preserve this independent scope.", b"Silently replace the preserved conclusion.")
    else:
        changed = copy.deepcopy(meta)
        changed["claims"][1]["usage"] = "current"
        candidate = ("---\n" + yaml.safe_dump(changed, sort_keys=False) + "---" + old.decode().split("---", 2)[2]).encode()
    draft = harness.write(".build/candidates/rule.md", candidate)
    result = harness.run("view-materialize", {"operation_id": "op", "v3_required": True, "semantic_plan_ref": semantic, "bundle_ref": bundle_ref,
        "decisions": [{"candidate_id": unit, "decision": "update", "reason": "Authored one-Claim update", "card_inputs": [draft]}]})
    report = harness.lint(result["data"]["view_ref"], expected=1)
    assert "PRESERVED_CLAIM_CHANGED" in json.dumps(report)
