"""Shared synthetic document correction pipeline."""
import json
import yaml

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def frozen_harness(tmp_path):
    from support.stages.source import Harness
    harness = Harness(tmp_path)
    (tmp_path / "config.yml").write_text(
        yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8"
    )
    return harness


def complete_document_operation(harness, operation, decision, statement, *, expected_change="unchanged"):
    prepare_request = {"operation_id": operation, "source": "docs-raw/specs/source.md"}
    if decision == "update":
        prepare_request["candidate_card_ids"] = ["rule"]
    prepared = harness.run("source", prepare_request, "run")
    assert prepared["phase"] == "prepared"
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    scan = harness.record(scan_ref)
    assert len(scan["units"]) == 1
    unit = scan["units"][0]
    reason = ("Revalidate unchanged document under current rules" if expected_change == "unfinished"
              else "Requested document wording correction")
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                    "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "content",
                    "reason": "Revalidate the affected Claim under the current rules"}
                   for row in scan.get("current_context", {}).get("affected_claims", [])]
    input_units = [unit["unit_id"]] + [row["unit_id"] for row in maintenance]
    if decision == "update":
        assert unit["change"] == expected_change
    material = harness.record(material_ref)
    check_inputs = {}
    if decision == "update":
        assert material["unit_ids"] == [unit["unit_id"]]
        old_card = next(row for row in material["candidates"] if row["card_id"] == "rule")
        check_inputs["historical_card_objects"] = {
            old_card["card_digest"]: str(harness.root / old_card["card_ref"])
        }
    bundle = harness.record(material["bundle_ref"])
    semantic = harness.run("change-plan", {
        "operation_id": operation, "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "author",
        "units": [{"unit_id": unit["unit_id"], "outcome": "content",
                   "reason": reason if decision == "update" else "New document knowledge"}],
        "maintenance_units": maintenance,
        "claim_changes": [{"unit_ids": input_units, "card_id": "rule", "claim_id": "rule-claim",
                           "action": decision, "before": "Synthetic fixture statement." if decision == "update" else None,
                           "after": statement, "conditions": "Synthetic design guidance only",
                           "evidence": [{"source": bundle["snapshots"][0]["snapshot_id"], "locator": "L2"}],
                           "preserved": "Same assertion, applicability and source" if decision == "update" else "No old knowledge",
                           "reason": reason}],
        "card_actions": [{"card_id": "rule", "decision": decision, "author_id": "author",
                          "unit_ids": input_units, "reason": reason}],
        "target_queries": [{"id": "rule-query", "query": "Synthetic", "purpose": "guidance",
                            "required": ["rule"], "expected_claim_ids": ["rule#rule-claim"]}],
    }, "plan")["data"]["semantic_plan_ref"]
    card = harness.card("rule", bundle).replace(b"Synthetic fixture statement.", statement.encode())
    candidate = harness.write(f".build/operations/{operation}/candidate.md", card)
    view_ref = harness.run("view-materialize", {
        "operation_id": operation, "v3_required": True, "semantic_plan_ref": semantic,
        "bundle_ref": material["bundle_ref"],
        "decisions": [{"candidate_id": unit["unit_id"], "decision": decision,
                       "reason": reason, "card_inputs": [candidate]}],
    })["data"]["view_ref"]
    review_ref = harness.run("lint", {
        "operation_id": operation, "semantic_plan_ref": semantic, "view_ref": view_ref,
        "reviewer_id": "independent-reviewer", "independent_context": operation + "-review-context",
        "sampled_unit_ids": input_units, "unreviewed_unit_ids": [],
        "reason": "Read the exact candidate and unchanged original under current rules", "findings": [],
        "inputs": check_inputs,
    }, "review")["data"]["content_review_ref"]
    record_ref = harness.run("source", {
        "operation_id": operation, "scan_ref": scan_ref, "view_ref": view_ref,
        "semantic_plan_ref": semantic,
        "disposition_preview_ref": harness.record(view_ref)["disposition_preview_ref"],
    }, "record")["data"]["ingest_record_ref"]
    reviewed_view = harness.record(view_ref)
    review = harness.record(review_ref)
    batch = harness.run("apply", {
        "operation_id": operation, "v3_required": True, "view_ref": view_ref,
        "ingest_record_ref": record_ref,
        "check_inputs": check_inputs,
    }, "batch")
    assert batch["phase"] == "completed" and batch["data"]["activated"] is True
    applied, generation = batch["data"]["apply_result_ref"], batch["data"]["generation_ref"]
    search = harness.run("query", {"operation_id": operation + "-search", "query": "Synthetic", "purpose": "guidance"}, "search")["data"]
    assert search["matches"][0]["card_id"] == "rule"
    read = harness.run("query", {"operation_id": operation + "-read", "receipt_ref": search["receipt_ref"], "card_id": "rule"}, "read")["data"]
    assert read["generation_ref"] == search["generation_ref"]
    assert statement in (harness.root / "knowledge/rules/rule.md").read_text(encoding="utf-8")
    assert {claim["id"] for claim in read["claims"]} == {"rule-claim"}
    assert statement in read["claims"][0]["text"]
    assert read["card_digest"] == search["matches"][0]["card_digest"]
    return {"scan": scan, "view_ref": view_ref, "review_ref": review_ref, "generation_ref": generation,
            "reviewed_view": reviewed_view, "review": review, "apply_result_ref": applied,
            "publication_ref": batch["data"]["publication_ref"], "completion_ref": batch["data"]["completion_ref"]}
