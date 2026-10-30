"""Deterministic P5 data checks; the host supplies the independent reviewer."""

from pathlib import Path


def context(root, request, args, modules, rules):
    from .support import tool_identity

    return modules["runtime"].OperationContext(
        root, request, modules=modules, rules=rules,
        tool=tool_identity(Path(__file__).resolve().parent),
        rules_digest=args.rules_digest, action=args.action,
        package=Path(__file__).resolve().parent, catalog=args.catalog,
    )


def add_finding(report, check_id, code, reason, *, incomplete=False, path=""):
    row = next(item for item in report["checks"] if item["check_id"] == check_id)
    finding = {"check_id": check_id, "code": code, "severity": "error",
               "path": str(path), "line": None, "reason": str(reason)}
    row["findings"].append(finding)
    report["findings"].append(finding)
    if not incomplete or row["status"] != "failed":
        row["status"] = "incomplete" if incomplete else "failed"


def finish(report, modules):
    states = {row["status"] for row in report["checks"]}
    report["status"] = "failed" if "failed" in states else "incomplete" if "incomplete" in states else "passed"
    report["complete"] = modules["checks"].report_complete(report)
    report["exit_code"] = {"passed": 0, "failed": 1, "incomplete": 2}[report["status"]]
    report["phase"] = report["status"]
    report["digest"] = modules["validation"].digest_payload(report)
    return report


def code_check(ctx, request, action="code-check"):
    modules = ctx.modules
    adapter = modules["legacy_runtime"].Context(
        ctx.root, ctx.args.rules_digest, ctx.tool,
        domain=modules["validation"], rules=ctx.rules,
    )
    mode = {"code-check": "run", "code-recheck": "merge", "verify-evidence": "verify-proof"}[action]
    return modules["code_review"].local_check(adapter, request, mode)


def special_action(ctx, action):
    """Retain standalone review/code-evidence utilities without another Skill."""
    if action == "record-review":
        data, phase = ctx.modules["review_inputs"].content_review(ctx, ctx.request)
        code = 1 if data["review_status"] == "failed" else 0
    else:
        data = code_check(ctx, ctx.request, action)
        phase = data.get("phase", "verified")
        code = {"passed": 0, "failed": 1, "incomplete": 2}.get(data.get("check_status"), 0)
    result = {"schema_version": "2.0", "record_kind": "result", "status": "ok",
              "phase": phase, "data": data, "diagnostics": [],
              "tool_identity": ctx.tool, "rules_digest": ctx.args.rules_digest}
    result["digest"] = ctx.modules["runtime"].digest(result)
    return result, code


def query_code_contexts(ctx, details):
    """Expose this check's actual material inputs, never its passing status."""
    reference = details.get("local_check_ref")
    if not reference:
        return {}
    record = ctx.record(reference)
    if not record.get("code_identity"):
        return {}
    context_record = ctx.record(record["context_ref"])
    result = {}
    for claim in record.get("claims", []):
        context = result.setdefault(claim["card_id"], {
            "code_identity": record["code_identity"], "config_digest": context_record.get("config_digest"),
            "claim_evidence": {}})
        context["claim_evidence"][claim["claim_id"]] = claim.get("verification_evidence", [])
    return result


def run(ctx):
    """Record this review and run fixed checks once against this actual view."""
    request, modules = ctx.request, ctx.modules
    view = ctx.record(request["view_ref"], "final_view")
    semantic_ref = request.get("semantic_plan_ref") or view.get("semantic_plan_ref")
    if not semantic_ref:
        raise modules["runtime"].NodeError("SEMANTIC_PLAN_REQUIRED", "P5 needs the actual authored plan")
    review_request = {**request, "semantic_plan_ref": semantic_ref}
    review_data, _ = modules["review_inputs"].content_review(ctx, review_request)
    review_record = ctx.record(review_data["content_review_ref"], "content_review")
    candidate = modules["checks"].prepare_view(
        ctx.root, view, mode="candidate",
        identity={"view_digest": view["digest"], "operation_id": view["operation_id"]},
    )
    if review_data["review_status"] == "failed":
        report = {"report_version": "1.0", "object": candidate["identity"],
                  "rules_digest": ctx.args.rules_digest, "mode": "candidate",
                  "scope": {"kind": "full", "paths": []}, "findings": [],
                  "checks": [{"check_id": key, "group": group, "status": "incomplete",
                              "findings": [], "reason": "Not run: content review found blocking issues"}
                             for key, group in modules["checks"].CHECKS]}
        for finding in review_record["findings"]:
            add_finding(report, "view.inputs", "CONTENT_REVIEW_FINDING", finding["reason"])
        fixed_executed = False
    else:
        details, code_error = None, None
        check_inputs = dict(request.get("inputs", request.get("check_inputs")) or {})
        if view.get("review_mode") in {"code_gate", "mixed"} and isinstance(request.get("code_review"), dict):
            try:
                details = code_check(ctx, {**request["code_review"], "operation_id": ctx.operation,
                                          "view_ref": request["view_ref"]})
                direct_contexts = query_code_contexts(ctx, details)
                if direct_contexts and "code_contexts" not in check_inputs and "code_evidence" not in check_inputs:
                    check_inputs["code_contexts"] = direct_contexts
            except (ValueError, OSError, KeyError) as exc:
                code_error = exc
        report = modules["checks"].run(candidate, ctx.rules,
                                       inputs=check_inputs,
                                       scope="full", query_context=ctx)
        fixed_executed = True
        if view.get("review_mode") in {"code_gate", "mixed"}:
            code_request = request.get("code_review")
            if not isinstance(code_request, dict):
                add_finding(report, "source.references", "CODE_REVIEW_MATERIAL_REQUIRED",
                            "Provide this review's exact code/context/Claim evidence", incomplete=True)
            else:
                if code_error is None:
                    report["code_review"] = details
                    if details["check_status"] != "passed":
                        add_finding(report, "source.references", "CODE_REVIEW_" + details["check_status"].upper(),
                                    "Code review evidence did not pass; inspect the exact saved report",
                                    incomplete=details["check_status"] == "incomplete")
                else:
                    add_finding(report, "source.references", getattr(code_error, "code", "CODE_REVIEW_UNAVAILABLE"),
                                str(code_error), incomplete=True)
    query_returns = {"P3" for row in report["findings"] if row.get("code") == "TARGET_QUERY_EXPECTATION_FAILED"}
    report["review"] = {**review_data, "fixed_checks_executed": fixed_executed,
                        "sampled_unit_ids": review_record["sampled_unit_ids"],
                        "unreviewed_unit_ids": review_record["unreviewed_unit_ids"],
                        "findings": review_record["findings"],
                        "return_to": sorted({row["return_to"] for row in review_record["findings"]} | query_returns)}
    finish(report, modules)
    modules["checks"].validate_report(report, expected_rules=ctx.args.rules_digest)
    return report
