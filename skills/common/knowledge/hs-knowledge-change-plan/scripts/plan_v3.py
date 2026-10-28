"""Freeze authored P3 decisions; byte production and independent review live elsewhere."""
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


def freeze_dispositions(units, actions, claims):
    """Freeze authored record data so P6 never chooses among mixed actions."""
    frozen = []
    for row in units:
        identity = row["unit_id"]
        linked_actions = [action for action in actions if identity in action["unit_ids"]]
        decisions = {action["decision"] for action in linked_actions if action["decision"] != "defer"}
        selected = row.get("record_action")
        if row["outcome"] == "content":
            require(decisions and (selected in decisions if selected is not None else len(decisions) == 1),
                    "PLAN_RECORD_ACTION_REQUIRED", "A mixed content unit needs an explicit actual card action",)
            selected = selected or next(iter(decisions))
        else:
            require(selected is None or selected == row["outcome"], "PLAN_RECORD_ACTION_REQUIRED",
                    "A non-content record action must equal its source outcome")
            selected = row["outcome"]
        frozen.append({**row, "record_action": selected,
                       "card_refs": sorted({action["card_id"] for action in linked_actions}),
                       "claim_refs": sorted({claim["card_id"] + "#" + claim["claim_id"] for claim in claims
                                             if identity in claim["unit_ids"]})})
    return frozen


def author_plan(ctx, request):
    material = ctx.record(request.get("material_ref"))
    previous = ctx.modules["production"].revision_view(ctx, request)
    scan_ref = request.get("scan_ref") or material.get("scan_ref")
    scan = ctx.record(scan_ref, "source_inventory") if scan_ref else None
    if scan:
        ctx.modules["records"].validate_scan_manifest(scan, ctx.rules)
    require(material.get("purpose") == "source_materials",
            "MATERIAL_BINDING", "Use this operation's actual reading materials")
    if material["operation_id"] != ctx.operation:
        require(previous and previous.get("material_ref") == request["material_ref"],
                "MATERIAL_BINDING", "Old materials require their exact previous candidate")
    previous_plan = None
    if material["operation_id"] != ctx.operation or (scan and scan["operation_id"] != ctx.operation):
        require(previous and previous.get("semantic_plan_ref"), "REVISION_CONTEXT_REQUIRED",
                "Adopting a previous round needs its actual authored plan")
        previous_plan = ctx.record(previous["semantic_plan_ref"], "semantic_plan")
        require(previous_plan["digest"] == previous.get("semantic_plan_digest")
                and previous_plan["material_ref"] == previous.get("material_ref"),
                "MATERIAL_BINDING", "The previous candidate must bind its exact authored material")
        if material["operation_id"] != ctx.operation:
            require(previous_plan["material_digest"] == material["digest"], "MATERIAL_BINDING",
                    "Do not rebind altered material under its previous reference")
    if scan:
        require(material.get("scan_digest") == scan["digest"],
                "MATERIAL_BINDING", "Materials must bind this fixed scan")
        if scan["operation_id"] != ctx.operation:
            require(previous and previous.get("scan_ref") == scan_ref,
                    "MATERIAL_BINDING", "An old scan must remain the exact observation of the previous candidate")
            require(previous_plan.get("scan_ref") == scan_ref and previous_plan.get("scan_digest") == scan["digest"],
                    "MATERIAL_BINDING", "The previous authored plan must bind the unchanged original scan")
            if material["operation_id"] == ctx.operation:
                require(material.get("previous_view_ref") == request["previous_view_ref"]
                        and material.get("previous_view_digest") == previous["digest"]
                        and material.get("previous_material_ref") == previous.get("material_ref")
                        and material.get("previous_material_digest") == previous_plan["material_digest"],
                        "MATERIAL_BINDING", "New material rounds must bind the previous candidate and exact adopted material")
    observations = scan["units"] if scan else material.get("units", [])
    require(isinstance(observations, list) and all(isinstance(row, dict) and text(row.get("unit_id")) for row in observations),
            "MATERIAL_UNITS_REQUIRED", "Materials need an explicit actual target inventory")
    require(len({row["unit_id"] for row in observations}) == len(observations),
            "MATERIAL_UNIT_CONFLICT", "Material observations have duplicate units")
    units = request.get("units")
    fixed = {row["unit_id"] for row in observations}
    require(isinstance(units, list) and len(units) == len(fixed)
            and {row.get("unit_id") for row in units} == fixed,
            "PLAN_UNIT_COVERAGE", "Every frozen scan unit needs one source outcome")
    author = request.get("author_id")
    require(text(author), "PLAN_AUTHOR_REQUIRED", "Name the responsible author")
    for row in units:
        require(row.get("outcome") in {"content", "skip", "defer", "failed", "uncovered"}
                and text(row.get("reason")), "INVALID_SOURCE_OUTCOME", "Source outcome and reason are required")
    maintenance = request.get("maintenance_units", [])
    observed_context = (scan or material).get("current_context", {})
    affected = {(row["card_id"], row["claim_id"]) for row in observed_context.get("affected_claims", [])}
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
    units = freeze_dispositions(units, actions, claims)
    maintenance = freeze_dispositions(maintenance, actions, claims)
    plan = ctx.seal({"v3_required": True,
                     **({"scan_ref": scan_ref, "scan_digest": scan["digest"],
                         "origin_scan_operation_id": scan["operation_id"]} if scan else
                        {"observation_digest": digest(observations), "observation_basis": "explicit_material_targets"}),
                     **({"previous_view_ref": request["previous_view_ref"], "revision_reason": request["revision_reason"],
                         "previous_view_digest": previous["digest"],
                         "previous_semantic_plan_ref": previous.get("semantic_plan_ref"),
                         "previous_semantic_plan_digest": previous.get("semantic_plan_digest")} if previous else {}),
                     "material_ref": request["material_ref"], "material_digest": material["digest"],
                     "author_id": author, "units": units, "claim_changes": claims, "card_actions": actions,
                     "maintenance_units": maintenance,
                     "target_queries": cases, "request_digest": digest(request)}, "semantic_plan")
    ref = ctx.save(ctx.base + "/semantic-plan.json", plan)
    return {"semantic_plan_ref": ref, "semantic_plan_digest": plan["digest"],
            "target_queries": cases,
            **({"previous_view_ref": request["previous_view_ref"], "revision_reason": request["revision_reason"]} if previous else {}),
            **({"origin_scan_operation_id": scan["operation_id"]} if scan else {})}, "content_planned"
