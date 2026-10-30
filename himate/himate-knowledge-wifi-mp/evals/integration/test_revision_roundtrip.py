"""Real public P4 backedges preserve the original observation and frozen rounds."""
import copy
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("revision_roundtrip_pipeline", Path(__file__).parents[1] / "support/pipeline.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def replan(pipeline, operation, old_plan, material_ref, previous):
    request = {key: copy.deepcopy(old_plan[key]) for key in (
        "author_id", "units", "maintenance_units", "claim_changes", "card_actions", "target_queries")}
    request.update(operation_id=operation, scan_ref=old_plan["scan_ref"], material_ref=material_ref, **previous)
    return request


@pytest.mark.parametrize("return_to", ["P1", "P2", "P3"])
def test_review_backedge_creates_a_new_frozen_round_without_rescanning_original(tmp_path, return_to):
    pipeline = fixture.Pipeline(tmp_path)
    calls, actual_call = [], pipeline.call

    def call(skill, request, action=None, expected=0):
        calls.append((skill, action))
        return actual_call(skill, request, action, expected)

    pipeline.call = call
    if return_to == "P1":
        seed_bundle_ref, seed_bundle = pipeline.capture("seed", b"# Older topic\nEarlier related protocol.\n", "seed-source")
        seed_view = pipeline.view("seed", seed_bundle_ref, "seed-rule", pipeline.card("seed-rule", seed_bundle))
        pipeline.apply("seed", seed_view)
    bundle_ref, bundle = pipeline.capture("round-a", b"# Source\nCapture marker is a documented rule.\n")
    first_view_ref = pipeline.view("round-a", bundle_ref, "roundtrip-rule", pipeline.card("roundtrip-rule", bundle))
    first_view = pipeline.record(first_view_ref)
    first_plan = pipeline.record(first_view["semantic_plan_ref"])
    material_ref, scan_ref = first_view["material_ref"], first_view["scan_ref"]
    unit_ids = [row["unit_id"] for row in first_plan["units"]]
    frozen_refs = (scan_ref, material_ref, first_view["semantic_plan_ref"], first_view_ref)
    frozen = {ref: (pipeline.root / ref).read_bytes() for ref in frozen_refs}
    failure = pipeline.call("knowledge-lint", {"operation_id": "round-a", "view_ref": first_view_ref,
        "semantic_plan_ref": first_view["semantic_plan_ref"], "sampled_unit_ids": unit_ids,
        "unreviewed_unit_ids": [], "reason": "Read the actual complete first candidate",
        "findings": [{"unit_id": unit_ids[0], "return_to": return_to,
            "reason": "Read the existing seed card" if return_to == "P1" else "Correct the authored judgment" if return_to == "P2" else "Clarify the candidate description",
            "evidence": [{"reference": "knowledge/rules/seed-rule.md" if return_to == "P1" else first_view_ref}]}]}, "review", expected=1)
    assert failure["data"]["return_to"] == [return_to]
    assert failure["data"]["fixed_checks_executed"] is False
    assert not (pipeline.root / "knowledge/rules/roundtrip-rule.md").exists()
    previous = {"previous_view_ref": first_view_ref, "revision_reason": "P4 returned this exact candidate to " + return_to}
    return_call_index = len(calls)
    if return_to == "P1":
        assert "seed-rule" not in {row["card_id"] for row in pipeline.record(material_ref)["candidates"]}
        supplemented = pipeline.call("knowledge-source", {"operation_id": "round-b",
            "existing_material_ref": material_ref, "scan_ref": scan_ref, "candidate_card_ids": ["seed-rule"],
            **previous}, "prepare")["data"]["material_ref"]
        materials = pipeline.record(supplemented)
        assert materials["previous_material_ref"] == material_ref and materials["scan_ref"] == scan_ref
        assert "seed-rule" in {row["card_id"] for row in materials["candidates"]}
        material_ref = supplemented
        semantic_ref = pipeline.call("knowledge-change-plan", replan(pipeline, "round-b", first_plan, material_ref, previous),
                                     "plan")["data"]["semantic_plan_ref"]
    elif return_to == "P2":
        request = replan(pipeline, "round-b", first_plan, material_ref, previous)
        missing = pipeline.call("knowledge-change-plan", {key: value for key, value in request.items()
            if key not in {"previous_view_ref", "revision_reason"}}, "plan", expected=2)
        assert missing["diagnostics"][0]["code"] == "MATERIAL_BINDING"
        request["card_actions"][0]["reason"] = "Corrected explicit grouping decision after reviewing the actual source"
        semantic_ref = pipeline.call("knowledge-change-plan", request, "plan")["data"]["semantic_plan_ref"]
    else:
        semantic_ref = first_view["semantic_plan_ref"]
        missing_view = pipeline.call("knowledge-view-materialize", {"operation_id": "round-b",
            "semantic_plan_ref": semantic_ref}, expected=2)
        assert missing_view["diagnostics"][0]["code"] == "PLAN_OPERATION_MISMATCH"
        missing = pipeline.call("knowledge-lint", {"operation_id": "round-b", "semantic_plan_ref": semantic_ref,
            "sampled_unit_ids": unit_ids, "unreviewed_unit_ids": [], "reason": "No candidate supplied", "findings": []},
            "record-review", expected=2)
        assert missing["diagnostics"][0]["code"] == "PLAN_OPERATION_MISMATCH"
    material = pipeline.record(material_ref)
    card = pipeline.card("roundtrip-rule", pipeline.record(material["bundle_ref"]))
    if return_to == "P3":
        card = card.replace(b"summary: Isolated capture marker rule", b"summary: Clarified candidate description")
    draft = pipeline.write(".build/candidates/round-b/roundtrip-rule.md", card)
    produced = pipeline.call("knowledge-view-materialize", {"operation_id": "round-b", "semantic_plan_ref": semantic_ref,
        "material_ref": material_ref, **previous, "decisions": [{"candidate_id": "roundtrip-rule", "decision": "create",
            "reason": "Exact authored candidate for the returned round", "card_inputs": [draft]}]}, "revise")
    second_view_ref = produced["data"]["view_ref"]
    second_view = pipeline.record(second_view_ref)
    assert second_view_ref != first_view_ref and second_view["previous_view_ref"] == first_view_ref
    assert second_view["scan_ref"] == scan_ref and second_view["origin_scan_operation_id"] == "round-a"
    assert [row["unit_id"] for row in pipeline.record(semantic_ref)["units"]] == unit_ids
    # The material-return route invokes only the independent prepare action;
    # the P1 source node must not restart a scan or default run.
    source_calls = [action for skill, action in calls[return_call_index:] if skill == "knowledge-source"]
    assert source_calls == (["prepare"] if return_to == "P1" else [])
    pipeline.review("round-b", second_view_ref)
    pending_ref = pipeline.pending_record("round-b", second_view_ref)
    pending = pipeline.record(pending_ref)
    assert pending["operation_id"] == "round-b" and pending["origin_scan_operation_id"] == "round-a"
    assert pending["scan_ref"] == scan_ref and pending["scan_digest"] == pipeline.record(scan_ref)["digest"]
    completed = pipeline.call("knowledge-apply", {"operation_id": "round-b", "view_ref": second_view_ref,
        "ingest_record_ref": pending_ref}, "batch")
    assert completed["phase"] == "completed" and completed["data"]["activated"] is True
    assert (pipeline.root / "knowledge/rules/roundtrip-rule.md").is_file()
    for ref, original in frozen.items():
        assert (pipeline.root / ref).read_bytes() == original
    for operation in ("after-round-one", "after-round-two"):
        scan = pipeline.call("knowledge-source", {"operation_id": operation}, "scan")["data"]
        assert scan["complete"] is True and scan["actionable_unit_ids"] == []
        assert scan["finalization_pending"] == []
