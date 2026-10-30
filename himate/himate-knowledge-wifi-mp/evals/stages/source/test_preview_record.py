"""P6 transcribes fixed business decisions without a passed-step credential."""

import importlib.util
from pathlib import Path


_flow_spec = importlib.util.spec_from_file_location(
    "source_scan_preview_flow_fixture", Path(__file__).resolve().parents[2] / "support/stages/source_flow.py",
)
_flow_fixture = importlib.util.module_from_spec(_flow_spec)
_flow_spec.loader.exec_module(_flow_fixture)
planned_flow = _flow_fixture.planned_flow


def test_preview_record_copies_authored_fields_without_review_ticket(planned_flow):
    flow = planned_flow
    flow.produce("materialized")
    state = flow.state
    response = flow.call("source", {"view_ref": state["view_ref"],
                         "disposition_preview_ref": state["disposition_preview_ref"]}, "record")
    record = flow.h.record(response["data"]["record_ref"])
    semantic = flow.h.record(state["semantic_plan_ref"])
    preview = flow.h.record(state["disposition_preview_ref"])
    assert record["authored_units"] == semantic["units"] == preview["units"]
    assert record["preview_card_decisions"] == preview["card_decisions"]
    assert record["dispositions"][0]["action"] == semantic["units"][0]["record_action"] == "create"
    assert record["dispositions"][0]["card_refs"] == semantic["units"][0]["card_refs"]
    assert record["dispositions"][0]["claim_refs"] == semantic["units"][0]["claim_refs"]
    assert record["status"] == "pending" and record["progress"] == {}
    assert not (flow.h.root / "logs/ingest").exists()


def test_preview_record_refuses_a_different_disposition(planned_flow):
    flow = planned_flow
    flow.produce("materialized")
    response = flow.h.run("source", {"operation_id": flow.operation, "view_ref": flow.state["view_ref"],
                          "disposition_preview_ref": flow.state["disposition_preview_ref"], "dispositions": []}, "record", expected=2)
    assert response["diagnostics"][0]["code"] == "DISPOSITION_PREVIEW_MISMATCH"
    assert not (flow.h.root / ".build/operations" / flow.operation / "ingest-record.yaml").exists()


def test_origin_label_alone_cannot_adopt_another_operation(planned_flow):
    flow = planned_flow
    flow.produce("materialized")
    response = flow.h.run("source", {"operation_id": "forged-round", "scan_ref": flow.state["scan_ref"],
                          "view_ref": flow.state["view_ref"], "origin_scan_operation_id": flow.operation}, "record", expected=2)
    assert response["diagnostics"][0]["code"] == "OPERATION_MISMATCH"
    assert not (flow.h.root / ".build/operations/forged-round/ingest-record.yaml").exists()


def test_record_only_preview_keeps_unresolved_raw_debt(harness):
    harness.write("docs-raw/specs/source.md", b"# Source needs additional authority\n")
    scan = harness.run("source", {"operation_id": "deferred"}, "scan")["data"]
    unit = harness.record(scan["scan_ref"])["units"][0]
    material = harness.run("source", {"operation_id": "deferred", "scan_ref": scan["scan_ref"]}, "prepare")["data"]
    plan = harness.run("change-plan", {"operation_id": "deferred", "scan_ref": scan["scan_ref"],
                       "material_ref": material["material_ref"], "author_id": "synthetic-author",
                       "units": [{"unit_id": unit["unit_id"], "outcome": "defer", "reason": "Missing authoritative scope",
                                  "owner": "synthetic-owner", "next_step": "Acquire exact supplementary material"}],
                       "claim_changes": [], "card_actions": [], "target_queries": []}, "plan")["data"]
    view = harness.run("view-materialize", {"operation_id": "deferred", "semantic_plan_ref": plan["semantic_plan_ref"],
                       "decisions": []})["data"]
    record = harness.run("source", {"operation_id": "deferred", "view_ref": view["view_ref"],
                         "disposition_preview_ref": view["disposition_preview_ref"]}, "record")["data"]
    value = harness.record(record["record_ref"])
    assert value["batch_kind"] == "record_only"
    assert value["dispositions"][0]["action"] == "defer"
    assert value["dispositions"][0]["progress"] == "blocked"
    assert value["dispositions"][0]["adopted_fingerprint"] is None
    assert value["authored_units"][0]["next_step"] == "Acquire exact supplementary material"
