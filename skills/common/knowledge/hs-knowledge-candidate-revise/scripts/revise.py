"""Revision creates a new capture, plan and exact view for independent review."""

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
            "Explicit user correction or reviewer return reason required",
        )
    v3 = request.get("v3_required") or previous.get("v3_required")
    if v3:
        semantic = context.record(request.get("semantic_plan_ref"), "semantic_plan")
        if semantic["operation_id"] != context.operation:
            raise NodeError("NEW_PLAN_REQUIRED", "Revision requires a newly authored plan for the new operation")
        materials = context.record(semantic["material_ref"])
        capture = {"data": {"bundle_ref": materials["bundle_ref"]}}
    else:
        capture = recapture(context, request, previous)
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
            **({"v3_required": True, "semantic_plan_ref": request["semantic_plan_ref"]} if v3 else {}),
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
            "content_review_required": True,
        },
        "operation_status",
    )
    ref = context.save(context.base + "/revision.json", record)
    return {
        **materialized["data"],
        "revision_ref": ref,
        "content_review_required": True,
    }, "ready"


def recapture(context, request, previous):
    bundle = context.call(
        "hs-knowledge-source-capture",
        {"operation_id": context.operation, "bundle_ref": previous["bundle_ref"]},
        "resolve",
    )["data"]["bundle"]
    resource = bundle["resources"][0]
    primary = bundle["snapshots"][0]
    return context.call(
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
