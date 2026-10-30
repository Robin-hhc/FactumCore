"""P4 executes the author's cases before any reviewed content is published."""

import copy
import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("p5_query_pipeline", Path(__file__).parents[1] / "support/pipeline.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def formal_bytes(root):
    return {path.relative_to(root).as_posix(): fixture.sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file() and path.relative_to(root).parts[0] != ".build"}


def review(pipeline, operation, view_ref, expected):
    view = pipeline.record(view_ref)
    plan = pipeline.record(view["semantic_plan_ref"])
    material = pipeline.record(view["material_ref"])
    historical = {row["card_digest"]: str(pipeline.root / row["card_ref"])
                  for row in material.get("candidates", []) if row.get("card_ref")}
    return pipeline.call("knowledge-lint", {"operation_id": operation, "view_ref": view_ref,
        "semantic_plan_ref": view["semantic_plan_ref"],
        "sampled_unit_ids": [row["unit_id"] for row in plan["units"] + plan.get("maintenance_units", [])],
        "unreviewed_unit_ids": [], "reason": "Synthetic full content review of this exact candidate", "findings": [],
        "inputs": {"historical_card_objects": historical}},
        "review", expected=expected)


def case(purpose, card="design-rule", **changes):
    return {"id": "find-design", "query": "capture", "purpose": purpose,
            "required": [card], "expected_claim_ids": [card + "#c1"], **changes}


def query_check(result):
    return next(row for row in result["checks"] if row["check_id"] == "index.build")["candidate_queries"]


def test_wrong_purpose_is_blocked_before_publish_and_a_new_p2_round_can_correct_it(tmp_path):
    pipeline = fixture.Pipeline(tmp_path)
    pipeline.catalog_path.unlink()
    (pipeline.root / ".isolated-knowledge-fixture").unlink()
    bundle_ref, bundle = pipeline.capture("wrong", b"# Source\nCapture marker is a documented design rule.\n")
    card = pipeline.card("design-rule", bundle, "Capture marker is a documented design rule.")
    first_ref = pipeline.view("wrong", bundle_ref, "design-rule", card, queries=[case("implementation")])
    first = pipeline.record(first_ref)
    old_plan = pipeline.record(first["semantic_plan_ref"])
    frozen_refs = (first["scan_ref"], first["material_ref"], first["semantic_plan_ref"], first_ref)
    frozen = {ref: (pipeline.root / ref).read_bytes() for ref in frozen_refs}
    before = formal_bytes(pipeline.root)
    rejected = review(pipeline, "wrong", first_ref, expected=1)
    assert rejected["status"] == "failed"
    assert rejected["data"]["return_to"] == ["P2"]
    assert any(row["code"] == "TARGET_QUERY_EXPECTATION_FAILED" for row in rejected["findings"])
    failed_case = query_check(rejected)["outcomes"][0]
    assert failed_case["case_id"] == "find-design" and failed_case["purpose"] == "implementation"
    assert failed_case["actual"] == [] and failed_case["actual_claim_ids"] == []
    assert formal_bytes(pipeline.root) == before
    assert not (pipeline.root / "knowledge/rules/design-rule.md").exists()
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()

    previous = {"previous_view_ref": first_ref, "revision_reason": "Correct the frozen query purpose after P4"}
    request = {key: copy.deepcopy(old_plan[key]) for key in (
        "author_id", "units", "maintenance_units", "claim_changes", "card_actions", "target_queries")}
    request.update(operation_id="corrected", scan_ref=first["scan_ref"], material_ref=first["material_ref"], **previous)
    request["target_queries"][0]["purpose"] = "current"
    planned = pipeline.call("knowledge-change-plan", request, "plan")["data"]["semantic_plan_ref"]
    draft = pipeline.write(".build/candidates/corrected/design-rule.md", card)
    second_ref = pipeline.call("knowledge-view-materialize", {"operation_id": "corrected",
        "semantic_plan_ref": planned, "material_ref": first["material_ref"], **previous,
        "decisions": [{"candidate_id": "design-rule", "decision": "create", "reason": "Same card, corrected query",
                       "card_inputs": [draft]}]}, "revise")["data"]["view_ref"]
    passed = review(pipeline, "corrected", second_ref, expected=0)
    assert query_check(passed)["passed"] is True
    assert query_check(passed)["outcomes"][0]["actual_claim_ids"] == ["design-rule#c1"]
    assert formal_bytes(pipeline.root) == before
    record_ref = pipeline.pending_record("corrected", second_ref)
    completed = pipeline.call("knowledge-apply", {"operation_id": "corrected", "view_ref": second_ref,
        "ingest_record_ref": record_ref}, "batch")
    assert completed["phase"] == "completed" and completed["data"]["batch_complete"] is True
    assert completed["data"]["activated"] is True
    assert all((pipeline.root / ref).read_bytes() == raw for ref, raw in frozen.items())


def test_p4_uses_the_candidate_instead_of_the_existing_active_generation(tmp_path):
    pipeline = fixture.Pipeline(tmp_path)
    old_bundle_ref, old_bundle = pipeline.capture("seed", b"# Source\nCapture marker is the original design.\n")
    old_ref = pipeline.view("seed", old_bundle_ref, "design-rule", pipeline.card("design-rule", old_bundle))
    pipeline.apply("seed", old_ref)
    pointer = (pipeline.root / "artifacts/indexes/local/active.json").read_bytes()
    bundle_ref, bundle = pipeline.capture("candidate", b"# Source\nBrandnewcandidateword is a new design revision.\n")
    new_card = pipeline.card("design-rule", bundle, "Brandnewcandidateword is a new design revision.")
    view_ref = pipeline.view("candidate", bundle_ref, "design-rule", new_card, decision="update",
        queries=[case("current", query="Brandnewcandidateword")])
    before = formal_bytes(pipeline.root)
    passed = review(pipeline, "candidate", view_ref, expected=0)
    outcome = query_check(passed)["outcomes"][0]
    assert outcome["actual"] == ["design-rule"] and outcome["actual_claim_ids"] == ["design-rule#c1"]
    assert formal_bytes(pipeline.root) == before
    assert (pipeline.root / "artifacts/indexes/local/active.json").read_bytes() == pointer
    record_ref = pipeline.pending_record("candidate", view_ref)
    published = pipeline.call("knowledge-apply", {"operation_id": "candidate", "view_ref": view_ref,
        "ingest_record_ref": record_ref}, "batch")
    assert published["data"]["batch_complete"] is True and published["data"]["activated"] is True
    actual_regression = pipeline.record(published["data"]["report_ref"])
    assert actual_regression["outcomes"][0]["actual"] == outcome["actual"]
