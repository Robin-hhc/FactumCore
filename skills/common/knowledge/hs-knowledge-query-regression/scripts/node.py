"""Evaluate a fixed candidate generation, then use index-build's public CAS activation."""

from support import NodeError, digest


def execute(ctx):
    request = ctx.request
    verify_only = ctx.args.action == "verify"
    original = ctx.record(request["report_ref"], "query_regression") if verify_only else None
    if original is not None:
        request = {**original, **request}
    applied, view = None, None
    view_ref = request.get("view_ref")
    if not view_ref and request.get("apply_result_ref"):
        # Optional convenience: use the submitted batch's queries as input data.
        # Its workflow completion/proof chain is not an execution prerequisite.
        applied = ctx.record(request["apply_result_ref"], "apply_result")
        view_ref = applied["view_ref"]
    if view_ref:
        view = ctx.record(view_ref, "final_view")
        if applied and view["digest"] != applied["view_digest"]:
            raise NodeError("BATCH_VIEW_CHANGED", "Batch and supplied view digests differ")
    cases = request.get("cases")
    if cases is None and view is not None:
        cases = view.get("target_queries")
    if not isinstance(cases, list) or not cases:
        raise NodeError(
            "REGRESSION_CASES_REQUIRED", "A nonempty declared case set is required"
        )
    seen = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"]
            or case["id"] in seen
            or not isinstance(case.get("query"), str)
            or not case["query"].strip()
        ):
            raise NodeError(
                "INVALID_REGRESSION_CASE", "Unique case IDs and queries are required"
            )
        seen.add(case["id"])
        if case.get("purpose", "current") not in (
            "current", "implementation", "guidance", "historical"
        ):
            raise NodeError("INVALID_PURPOSE", "Invalid regression query purpose")
        for field in ("required", "forbidden", "expected_order"):
            if field in case and (
                not isinstance(case[field], list)
                or any(not isinstance(value, str) or not value for value in case[field])
                or len(case[field]) != len(set(case[field]))
            ):
                raise NodeError("INVALID_REGRESSION_CASE", f"Invalid {field} assertion")
        if not (
            "expected_order" in case or case.get("required") or case.get("forbidden")
        ):
            raise NodeError(
                "REGRESSION_ASSERTION_REQUIRED",
                "Each case must declare expected behavior",
            )
    checked = ctx.call(
        "hs-knowledge-index-build",
        {"operation_id": ctx.operation, "generation_ref": request["generation_ref"]},
        "verify",
    )["data"]
    outcomes = []
    for case in cases:
        payload = {
            "operation_id": ctx.operation,
            "generation_ref": request["generation_ref"],
            "evaluation": True,
            "channel": checked["channel"],
            "query": case["query"],
            "context": case.get("context", {}),
            "purpose": case.get("purpose", "current"),
            "top_k": case.get("top_k", 5),
        }
        result = ctx.call("hs-knowledge-query", payload, "search")["data"]
        ids = [row["card_id"] for row in result["matches"]]
        passed = (
            not result["candidate_scan_truncated"]
            and all(c in ids for c in case.get("required", []))
            and not set(ids) & set(case.get("forbidden", []))
            and ("expected_order" not in case or ids == case["expected_order"])
        )
        reads = []
        for hit in result["matches"]:
            body = ctx.call("hs-knowledge-query", {**payload, "card_id": hit["card_id"]}, "read")["data"]
            same = (body.get("generation_ref") == request["generation_ref"]
                    and body.get("card_digest") == hit.get("card_digest")
                    and {c["id"] for c in body.get("claims", [])} == set(hit.get("claim_ids", [])))
            passed = passed and same
            reads.append({"card_id": hit["card_id"], "passed": same, "receipt_ref": body["receipt_ref"]})
        claims = {hit["card_id"] + "#" + claim for hit in result["matches"] for claim in hit.get("claim_ids", [])}
        passed = passed and set(case.get("expected_claim_ids", [])) <= claims
        passed = passed and not set(case.get("forbidden_claim_ids", [])) & claims
        outcomes.append(
            {
                "case_id": case["id"],
                "passed": passed,
                "actual": ids,
                "receipt_ref": result["receipt_ref"],
                "same_generation_reads": reads,
            }
        )
    report = ctx.seal(
        {
            "generation_ref": request["generation_ref"],
            "cases": cases,
            "cases_digest": digest(cases),
            "outcomes": outcomes,
            "passed": all(row["passed"] for row in outcomes),
            **({"view_ref": view_ref, "view_digest": view["digest"]} if view is not None else {}),
            **({"apply_result_ref": request["apply_result_ref"],
                "apply_result_digest": applied["digest"]} if applied is not None else {}),
            "index_verified": True,
        },
        "query_regression",
    )
    ref = ctx.base + "/regression/" + report["digest"] + ".json"
    ctx.save(ref, report)
    if not report["passed"]:
        return {
            "report_ref": ref,
            "passed": False,
            "activated": False,
        }, "needs_revision"
    if verify_only:
        return {"report_ref": ref, "passed": True, "gate_verified": True,
                "generation_ref": request["generation_ref"],
                **({"view_digest": view["digest"]} if view is not None else {}),
                **({"apply_result_digest": applied["digest"]} if applied is not None else {})}, "verified"
    activation = ctx.call(
        "hs-knowledge-index-build",
        {
            "operation_id": ctx.operation,
            "generation_ref": request["generation_ref"],
            "expected_active": request.get("expected_active"),
        },
        "activate",
    )["data"]
    return {
        "report_ref": ref,
        "passed": True,
        "activated": activation["activated"],
        "generation_ref": request["generation_ref"],
    }, "checked"
