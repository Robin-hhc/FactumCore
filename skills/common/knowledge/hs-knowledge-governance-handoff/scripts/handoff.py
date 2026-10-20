"""Immutable production-to-governance handoff, never implicit publication."""

from support import NodeError


def execute(context):
    ref = context.request["view_ref"]
    result = context.call(
        "hs-knowledge-candidate-inspect",
        {"operation_id": context.operation, "view_ref": ref},
    )
    if result["phase"] not in {"manual_ready", "code_ready"}:
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
            "target_workflow": "hs-knowledge-lint",
            "workflow": context.request.get("workflow"),
            "limitations": [
                "Governance has not run; no approval, stable apply, index activation or Git merge"
            ],
        },
        "handoff",
    )
    handoff_ref = context.save(context.base + "/handoff.json", record)
    return {
        "handoff_ref": handoff_ref,
        "handoff_digest": record["digest"],
        "target_workflow": "hs-knowledge-lint",
    }, "handed_off"
