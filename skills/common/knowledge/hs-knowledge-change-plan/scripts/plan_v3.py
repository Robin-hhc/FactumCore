"""Freeze authored reasoning and review scope; never infer domain semantics."""

from support import NodeError, digest


def require(value, code, message):
    if not value:
        raise NodeError(code, message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_queries(cases):
    require(isinstance(cases, list) and cases, "TARGET_QUERIES_REQUIRED", "Content plans need representative queries")
    ids = set()
    for case in cases:
        require(isinstance(case, dict) and text(case.get("id")) and case["id"] not in ids
                and text(case.get("query")), "INVALID_TARGET_QUERY", "Unique query IDs and questions are required")
        ids.add(case["id"])
        require(case.get("required") or case.get("forbidden") or "expected_order" in case,
                "INVALID_TARGET_QUERY", "A query needs independently declared expected behavior")
        require(case.get("purpose", "current") in ("current", "implementation", "guidance", "historical"),
                "INVALID_TARGET_QUERY_PURPOSE", "Declare current, implementation, guidance or historical query purpose")
    return cases


def author_plan(ctx, request):
    scan = ctx.record(request.get("scan_ref"), "source_inventory")
    ctx.modules["records"].validate_scan_manifest(scan, ctx.rules)
    material = ctx.record(request.get("material_ref"))
    require(material.get("purpose") == "source_materials"
            and scan["operation_id"] == ctx.operation and material["operation_id"] == ctx.operation
            and material.get("scan_digest") == scan["digest"], "MATERIAL_BINDING", "Materials must bind this fixed scan")
    units = request.get("units")
    fixed = {row["unit_id"] for row in scan["units"]}
    require(isinstance(units, list) and len(units) == len(fixed)
            and {row.get("unit_id") for row in units} == fixed,
            "PLAN_UNIT_COVERAGE", "Every frozen scan unit needs one source outcome")
    author = request.get("author_id")
    require(text(author), "PLAN_AUTHOR_REQUIRED", "Name the responsible author")
    for row in units:
        require(row.get("outcome") in {"content", "skip", "defer", "failed", "uncovered"}
                and text(row.get("reason")), "INVALID_SOURCE_OUTCOME", "Source outcome and reason are required")
    maintenance = request.get("maintenance_units", [])
    affected = {(row["card_id"], row["claim_id"]) for row in scan.get("current_context", {}).get("affected_claims", [])}
    require(isinstance(maintenance, list) and {(row.get("card_id"), row.get("claim_id")) for row in maintenance} == affected
            and len(maintenance) == len(affected), "MAINTENANCE_UNIT_COVERAGE", "Maintenance units must bind every affected context Claim without inventing raw files")
    for row in maintenance:
        require(row.get("unit_id") == "maintenance:" + row["card_id"] + "#" + row["claim_id"]
                and row.get("unit_id") not in fixed and row.get("outcome") in {"content", "skip", "defer", "failed", "uncovered"}
                and text(row.get("reason")), "INVALID_MAINTENANCE_UNIT", "Maintenance inputs need exact affected Claim identity, outcome and reason")
    fixed |= {row["unit_id"] for row in maintenance}
    claims, actions = request.get("claim_changes", []), request.get("card_actions", [])
    require(isinstance(claims, list) and isinstance(actions, list), "INVALID_CLAIM_PLAN", "Claim changes and card actions must be lists")
    content_units = {u["unit_id"] for u in units + maintenance if u["outcome"] == "content"}
    covered, claim_keys = set(), set()
    for row in claims:
        require(all(text(row.get(key)) for key in ("card_id", "claim_id", "action", "conditions", "reason"))
                and row["action"] in {"create", "update", "preserve", "retire"}
                and isinstance(row.get("unit_ids"), list) and row["unit_ids"]
                and set(row["unit_ids"]) <= fixed and row.get("evidence")
                and "before" in row and "after" in row and "preserved" in row,
                "INVALID_CLAIM_PLAN", "Explain each Claim's before/after, conditions, evidence and preserved scope")
        key = (row["card_id"], row["claim_id"])
        require(key not in claim_keys, "DUPLICATE_CLAIM_PLAN", "Fuse all source units into one judgment per Card/Claim")
        claim_keys.add(key)
        require(row["action"] == "preserve" or set(row["unit_ids"]) <= content_units,
                "CLAIM_SOURCE_OUTCOME", "Changed Claims can only adopt units marked content")
        if row["action"] != "preserve":
            covered.update(row["unit_ids"])
    require(content_units <= covered, "CLAIM_PLAN_COVERAGE", "Content units require explicit Claim comparisons")
    targets = set()
    for row in actions:
        require(text(row.get("card_id")) and row["card_id"] not in targets
                and row.get("decision") in {"create", "update", "merge", "split", "deprecate", "defer"}
                and text(row.get("author_id")) and text(row.get("reason"))
                and row.get("unit_ids") and set(row["unit_ids"]) <= fixed,
                "INVALID_CARD_PLAN", "Each target card has one responsible author and explicit action")
        targets.add(row["card_id"])
        require(row["decision"] == "defer" or set(row["unit_ids"]) <= content_units,
                "CARD_SOURCE_OUTCOME", "Card changes cannot silently adopt skip/defer/failed units")
    require({r["card_id"] for r in claims if r["action"] != "preserve"} <= targets,
            "CARD_PLAN_COVERAGE", "Changed Claims need an explicit card action")
    cases = validate_queries(request.get("target_queries")) if content_units else []
    for row in actions:
        if row["decision"] == "defer":
            continue
        eligible_cases = [case for case in cases if (row["card_id"] in case.get("forbidden", [])
                            and case.get("purpose", "current") == "current") or
                          (case.get("purpose") == "historical" and row["card_id"] in case.get("required", []))] if row["decision"] == "deprecate" else [
                              case for case in cases if row["card_id"] in case.get("required", []) + case.get("expected_order", [])]
        require(eligible_cases, "TARGET_QUERY_COVERAGE", "Batch queries must cover every applicable planned target card")
    known_claims = {card + "#" + claim for card, claim in claim_keys}
    for case in cases:
        require(set(case.get("expected_claim_ids", []) + case.get("forbidden_claim_ids", [])) <= known_claims,
                "TARGET_CLAIM_QUERY_INVALID", "Claim query expectations must refer to the authored Claim plan")
    plan = ctx.seal({"v3_required": True, "scan_ref": request["scan_ref"], "scan_digest": scan["digest"],
                     "material_ref": request["material_ref"], "material_digest": material["digest"],
                     "author_id": author, "units": units, "claim_changes": claims, "card_actions": actions,
                     "maintenance_units": maintenance,
                     "target_queries": cases, "request_digest": digest(request)}, "semantic_plan")
    ref = ctx.save(ctx.base + "/semantic-plan.json", plan)
    return {"semantic_plan_ref": ref, "semantic_plan_digest": plan["digest"],
            "target_queries": cases}, "content_planned"


def content_review(ctx, request):
    plan = ctx.record(request.get("semantic_plan_ref"), "semantic_plan")
    require(plan["operation_id"] == ctx.operation, "PLAN_OPERATION_MISMATCH", "Review must describe this operation's plan")
    identities = {key: request[key] for key in ("reviewer_id", "independent_context") if key in request}
    if plan.get("author_id") is not None:
        identities["author_id"] = plan["author_id"]
    scan = ctx.record(plan["scan_ref"], "source_inventory")
    applicable = {u["unit_id"] for u in plan["units"] + plan.get("maintenance_units", []) if u["outcome"] in {"skip", "content"}}
    planned_skips = {u["unit_id"] for u in plan["units"] if u["outcome"] == "skip"}
    scan_skip = {u["unit_id"] for u in scan["units"] if u["unit_id"] in planned_skips
                 and u.get("change") == "unchanged"
                 and u.get("progress") in {"completed", "skipped", "withdrawn"}}
    applicable -= scan_skip
    sampled, unreviewed = request.get("sampled_unit_ids", []), request.get("unreviewed_unit_ids", [])
    require(isinstance(sampled, list) and isinstance(unreviewed, list)
            and len(set(sampled + unreviewed)) == len(sampled + unreviewed)
            and set(sampled + unreviewed) == applicable and (not applicable or sampled)
            and text(request.get("reason")), "REVIEW_SCOPE_INVALID", "Record the risk sample and every unselected unit explicitly")
    findings = request.get("findings")
    require(isinstance(findings, list), "REVIEW_FINDINGS_REQUIRED", "Review must report findings, including an explicit empty list")
    for row in findings:
        require(row.get("unit_id") in sampled and row.get("return_to") in {"P2", "P3", "P4"}
                and text(row.get("reason")) and row.get("evidence"), "INVALID_REVIEW_FINDING", "Findings need location, evidence and return node")
    view_digest = None
    if request.get("view_ref"):
        view = ctx.record(request["view_ref"], "final_view")
        require(view.get("semantic_plan_digest") == plan["digest"], "REVIEW_VIEW_MISMATCH", "Review view differs from plan")
        view_digest = view["digest"]
    record = ctx.seal({"semantic_plan_ref": request["semantic_plan_ref"], "plan_digest": plan["digest"],
                       "scan_digest": scan["digest"], **identities, "sampled_unit_ids": sampled,
                       "unreviewed_unit_ids": unreviewed, "reason": request["reason"], "findings": findings,
                       "view_digest": view_digest, "status": "failed" if findings else "passed",
                       "verification_tier": "declared_content_review"}, "content_review")
    ref = ctx.save(ctx.base + "/content-review/" + record["digest"] + ".json", record)
    return {"content_review_ref": ref, "review_status": record["status"],
            "skip_sample": {**({"reviewer": identities["reviewer_id"]} if "reviewer_id" in identities else {}),
                            "reason": request["reason"],
                            "sampled_unit_ids": sampled, "unreviewed_unit_ids": unreviewed,
                            "report_ref": ref, "report_digest": record["digest"]}}, ("needs_revision" if findings else "reviewed")


def bind_plan(ctx, request):
    plan = ctx.record(request.get("semantic_plan_ref"), "semantic_plan")
    require(plan["operation_id"] == ctx.operation, "PLAN_OPERATION_MISMATCH", "Use this operation's authored plan")
    for ref, expected in ((plan["scan_ref"], plan["scan_digest"]), (plan["material_ref"], plan["material_digest"])):
        require(ctx.record(ref)["digest"] == expected, "STALE_PLAN_INPUT", "Plan material changed")
    return plan
