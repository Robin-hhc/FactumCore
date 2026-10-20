"""Revision creates a new capture, plan and exact view; old approvals are never reused."""

from support import NodeError


def execute(context):
    request = context.request
    previous = context.record(request["previous_view_ref"], "final_view")
    if previous["operation_id"] == context.operation:
        raise NodeError(
            "NEW_OPERATION_REQUIRED", "Revision must use a new operation identity"
        )
    if (
        not isinstance(request.get("revision_reason"), str)
        or not request["revision_reason"].strip()
    ):
        raise NodeError(
            "REVISION_REASON_REQUIRED",
            "Explicit return/partial-acceptance reason required",
        )
    bundle = context.call(
        "hs-knowledge-source-capture",
        {"operation_id": context.operation, "bundle_ref": previous["bundle_ref"]},
        "resolve",
    )["data"]["bundle"]
    resource = bundle["resources"][0]
    primary = bundle["snapshots"][0]
    capture = context.call(
        "hs-knowledge-source-capture",
        {
            "operation_id": context.operation,
            "source_path": resource["path"],
            "source_id": resource["source_id"],
            "version": primary.get("version"),
            "attachments": [r["path"] for r in bundle["resources"][1:]],
            "context_ref": request.get("context_ref", previous.get("context_ref")),
        },
    )
    planned = context.call(
        "hs-knowledge-change-plan",
        {
            "operation_id": context.operation,
            "bundle_ref": capture["data"]["bundle_ref"],
            "candidate_ids": request.get(
                "candidate_ids", [d["candidate_id"] for d in request["decisions"]]
            ),
            "decisions": request["decisions"],
            "context_ref": request.get("context_ref", previous.get("context_ref")),
        },
    )
    if planned["phase"] == "deferred":
        return {
            "plan_ref": planned["data"]["plan_ref"],
            "previous_view_ref": request["previous_view_ref"],
        }, "deferred"
    materialized = context.call(
        "hs-knowledge-view-materialize",
        {"operation_id": context.operation, "plan_ref": planned["data"]["plan_ref"]},
    )
    record = context.seal(
        {
            "previous_view_ref": request["previous_view_ref"],
            "previous_view_digest": previous["digest"],
            "revision_reason": request["revision_reason"],
            "view_ref": materialized["data"]["view_ref"],
            "view_digest": materialized["data"]["view_digest"],
            "confirmation_required": True,
        },
        "operation_status",
    )
    ref = context.save(context.base + "/revision.json", record)
    return {
        **materialized["data"],
        "revision_ref": ref,
        "confirmation_required": True,
    }, "ready"
