"""Behavioral cases; shared synthetic materials live under evals/support."""

import pytest
from support.stages.source_flow import (
    PLANNED_DOCUMENT_NODES,
)


def test_complete_planned_document_nodes_then_three_noop_runs(planned_flow):
    flow = planned_flow
    flow.produce()
    assert flow.trace == PLANNED_DOCUMENT_NODES
    assert flow.current == "__end__"
    protected = flow.protected_bytes()
    indexes = {p.relative_to(flow.h.root).as_posix(): p.read_bytes()
               for p in (flow.h.root / "artifacts/indexes").rglob("*") if p.is_file()}
    original_records = sorted((flow.h.root / "logs/ingest").glob("*.yaml"))
    assert len(original_records) == 1
    for attempt in range(3):
        result, inventory = flow.scan_new_run("complete-noop-" + str(attempt))
        assert inventory["complete"] is True
        assert [row["change"] for row in inventory["units"]] == ["unchanged"]
        assert result["actionable_unit_ids"] == []
        assert result["finalization_pending"] == []
        flow.take("unchanged")
        assert flow.current == "__end__"
    assert flow.protected_bytes() == protected
    assert {p.relative_to(flow.h.root).as_posix(): p.read_bytes()
            for p in (flow.h.root / "artifacts/indexes").rglob("*") if p.is_file()} == indexes
    assert sorted((flow.h.root / "logs/ingest").glob("*.yaml")) == original_records


@pytest.mark.parametrize("stop", ["applied", "built"])
def test_explicit_current_p7_stop_resumes_without_p1_history_route(planned_flow, stop):
    next_node, prefix_count = "apply_view", 6
    flow = planned_flow
    flow.produce(stop)
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count]
    assert flow.current == next_node
    protected = flow.protected_bytes()
    journal = flow.h.record(".build/operations/" + flow.operation + "/transaction/journal.json")
    assert journal["status"] == "committed"
    if stop == "built":
        assert flow.state["expected_active"] is None  # no initial generation in this fixture
        assert flow.h.record(flow.state["generation_ref"])["expected_active"] is None
    scan_result = flow.h.run("source", {"operation_id": "resume-check-" + stop}, "scan")["data"]
    assert scan_result["actionable_unit_ids"] == []
    assert scan_result["finalization_pending"] == []
    assert scan_result["execution_history"] == {"status": "not_inspected"}
    details = flow.h.run("source", {"operation_id": "explicit-stop", "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert details["completion"]["published"] is True
    assert details["completion"]["batch_complete"] is False
    assert details["completion"]["next_action"] == "resume_batch"
    # Resume the explicitly known current P7, without a new Workflow adopting it.
    assert flow.current == next_node
    flow.finish()
    assert flow.trace == PLANNED_DOCUMENT_NODES[:prefix_count] + ["apply_view"]
    assert flow.trace.count("apply_view") == 2 and flow.trace.count("record_ingest") == 1
    assert flow.protected_bytes() == protected
    status = flow.h.run("source", {"operation_id": "saved-stop-status", "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert {row["stage"] for row in status["facts"]} == {"publication", "publication_completion"}
    assert status["completion"]["retrieval"]["complete"] is True
    assert status["completion"]["cleanup"]["status"] == "done"
