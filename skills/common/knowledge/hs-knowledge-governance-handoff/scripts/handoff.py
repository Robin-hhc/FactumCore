"""Retain an inspected P4 view and continuation within the same ingest."""

from support import NodeError


def execute(context):
    ref = context.request["view_ref"]
    result = context.call(
        "hs-knowledge-candidate-inspect",
        {"operation_id": context.operation, "view_ref": ref},
    )
    if result["phase"] not in {"manual_ready", "code_ready", "mixed_ready"}:
        raise NodeError(
            "GOVERNANCE_NOT_READY",
            "Candidate needs recovery before handoff",
            blocked=True,
        )
    view = context.record(ref, "final_view")
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
            "next_action": "content_review_then_confirmation_then_P5_lint",
            "workflow": context.request.get("workflow"),
            "limitations": [
                "P4 continuation only; confirmation, final lint, application and submission remain explicit"
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
