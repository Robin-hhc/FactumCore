"""Persist P5's declared review coverage; never certify reviewer identity.

This is a business-record operation used in the same process as P5 lint.  A
saved review alone does not mean fixed checks or the complete P5 stage passed.
"""

from .runtime import NodeError


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _require(value, code, message):
    if not value:
        raise NodeError(code, message)


def content_review(ctx, request):
    plan = ctx.record(request.get("semantic_plan_ref"), "semantic_plan")
    view = ctx.record(request["view_ref"], "final_view") if request.get("view_ref") else None
    if view:
        _require(view["operation_id"] == ctx.operation and view.get("semantic_plan_ref") == request["semantic_plan_ref"]
                 and view.get("semantic_plan_digest") == plan["digest"], "REVIEW_VIEW_MISMATCH",
                 "Review must bind this exact plan and final candidate")
    if plan["operation_id"] != ctx.operation:
        _require(view is not None, "PLAN_OPERATION_MISMATCH", "Adopting an old plan needs this round's actual candidate")
        previous = ctx.modules["production"].revision_view(ctx, view, required=True)
        _require(previous.get("semantic_plan_ref") == request["semantic_plan_ref"]
                 and previous.get("semantic_plan_digest") == plan["digest"],
                 "PLAN_OPERATION_MISMATCH", "This candidate must explicitly adopt the exact unchanged previous plan")
    identities = {key: request[key] for key in ("reviewer_id", "independent_context") if key in request}
    if plan.get("author_id") is not None:
        identities["author_id"] = plan["author_id"]
    scan = ctx.record(plan["scan_ref"], "source_inventory") if plan.get("scan_ref") else None
    if scan:
        _require(scan["operation_id"] == plan.get("origin_scan_operation_id", plan["operation_id"])
                 and scan["digest"] == plan.get("scan_digest"),
                 "REVIEW_SCAN_MISMATCH", "Review must use the exact scan adopted by this authored plan")
    # A deferred/failed/uncovered disposition is itself a reviewable authored
    # decision. A record-only batch must not pass with an empty review scope.
    applicable = {unit["unit_id"] for unit in plan["units"] + plan.get("maintenance_units", [])}
    planned_skips = {unit["unit_id"] for unit in plan["units"] if unit["outcome"] == "skip"}
    # Only a real saved P1 observation can establish an already-processed scan
    # skip. Explicit P2 targets do not invent change/progress/full-scan facts.
    scan_skips = {unit["unit_id"] for unit in (scan or {}).get("units", [])
                  if unit["unit_id"] in planned_skips and unit.get("change") == "unchanged"
                  and unit.get("progress") in {"completed", "skipped", "withdrawn"}}
    applicable -= scan_skips
    sampled, unreviewed = request.get("sampled_unit_ids", []), request.get("unreviewed_unit_ids", [])
    _require(isinstance(sampled, list) and isinstance(unreviewed, list)
             and all(isinstance(unit, str) for unit in sampled + unreviewed)
             and len(set(sampled + unreviewed)) == len(sampled + unreviewed)
             and set(sampled + unreviewed) == applicable and (not applicable or sampled)
             and _text(request.get("reason")), "REVIEW_SCOPE_INVALID",
             "Record the actual risk sample and every unselected unit explicitly")
    findings = request.get("findings")
    _require(isinstance(findings, list), "REVIEW_FINDINGS_REQUIRED",
             "Report actual findings, including an explicitly empty list")
    for row in findings:
        _require(isinstance(row, dict) and row.get("unit_id") in sampled
                 and row.get("return_to") in {"P2", "P3", "P4"}
                 and _text(row.get("reason")) and row.get("evidence"),
                 "INVALID_REVIEW_FINDING", "Findings need a location, evidence and return stage")
    view_digest = None
    if view:
        view_digest = view["digest"]
    record = ctx.seal({"semantic_plan_ref": request["semantic_plan_ref"],
                       "plan_digest": plan["digest"],
                       **({"scan_digest": scan["digest"], "origin_scan_operation_id": scan["operation_id"]} if scan else {
                           "observation_basis": plan.get("observation_basis", "explicit_material_targets"),
                           "observation_digest": plan.get("observation_digest")}),
                       **identities, "sampled_unit_ids": sampled, "unreviewed_unit_ids": unreviewed,
                       "reason": request["reason"], "findings": findings, "view_digest": view_digest,
                       "status": "failed" if findings else "passed",
                       "verification_tier": "declared_content_review"}, "content_review")
    ref = ctx.save(ctx.base + "/content-review/" + record["digest"] + ".json", record)
    return {"content_review_ref": ref, "review_status": record["status"],
            "skip_sample": {**({"reviewer": identities["reviewer_id"]} if "reviewer_id" in identities else {}),
                            "reason": request["reason"], "sampled_unit_ids": sampled,
                            "unreviewed_unit_ids": unreviewed, "report_ref": ref,
                            "report_digest": record["digest"]}}, ("needs_revision" if findings else "reviewed")
