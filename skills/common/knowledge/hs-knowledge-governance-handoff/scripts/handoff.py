"""Describe an exact content view without deciding Workflow readiness."""

from support import NodeError


def execute(context):
    ref = context.request["view_ref"]
    view = context.record(ref, "final_view")
    if view["operation_id"] != context.operation:
        raise NodeError("OPERATION_MISMATCH", "View belongs to another operation")
    record = context.seal(
        {
            "view_ref": ref,
            "view_digest": view["digest"],
            "plan_ref": view["plan_ref"],
            "plan_digest": view["plan_digest"],
            "source_set_digest": view["source_set_digest"],
            "source_refs": view["source_refs"],
            "bundle_ref": view["bundle_ref"],
            "context_ref": view.get("context_ref"),
            "review_mode": view["review_mode"],
            "baseline_digest": view["baseline_digest"],
            "target_workflow": "hs-knowledge-ingest",
            "target_phase": "P4",
            "next_action": "content_review_then_applicable_code_check_then_P5_lint",
            "limitations": [
                "Describes view content only; OpenFlow decides Workflow readiness"
            ],
        },
        "handoff",
    )
    handoff_ref = context.save(context.base + "/handoff.json", record)
    return {
        "handoff_ref": handoff_ref,
        "handoff_digest": record["digest"],
        "target_workflow": "hs-knowledge-ingest",
        "target_phase": "P4",
    }, "handed_off"
