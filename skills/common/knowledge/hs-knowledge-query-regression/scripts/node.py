"""Evaluate a fixed candidate generation, then use index-build's public CAS activation."""

from support import NodeError, digest


def execute(ctx):
    request = ctx.request
    cases = request.get("cases")
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
        outcomes.append(
            {
                "case_id": case["id"],
                "passed": passed,
                "actual": ids,
                "receipt_ref": result["receipt_ref"],
            }
        )
    report = ctx.seal(
        {
            "generation_ref": request["generation_ref"],
            "cases_digest": digest(cases),
            "outcomes": outcomes,
            "passed": all(row["passed"] for row in outcomes),
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
