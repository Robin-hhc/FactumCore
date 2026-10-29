"""Declared query behavior against one generation, without another Skill process."""

from dataclasses import dataclass
from pathlib import Path

from .runtime import NodeError, digest, fork_context
from . import index_runtime, query_runtime


@dataclass(frozen=True)
class VerifiedRegression:
    """A real in-process query execution; serialized passed fields cannot create it."""

    root: Path
    rules_digest: str
    binding: tuple


def _execution_binding(generation_ref, manifest, report_ref, report):
    binding = {"generation_ref": generation_ref, "manifest_digest": manifest["digest"],
               "expected_active": report["expected_active"], "frozen_cases_digest": report["cases_digest"],
               "regression_report_ref": report_ref, "regression_report_digest": report["digest"],
               "view_ref": report.get("view_ref"), "view_digest": report.get("view_digest"),
               "apply_result_ref": report.get("apply_result_ref"), "apply_result_digest": report.get("apply_result_digest")}
    if report.get("publication_ref"):
        binding.update({key: report[key] for key in ("publication_ref", "publication_digest", "content_digest")})
    return binding


def persisted_binding(ctx, generation_ref, manifest, report_ref, *, view_ref=None, view=None,
                      apply_result_ref=None, applied=None, cases=None,
                      publication_ref=None, publication_manifest=None):
    report = ctx.record(report_ref, "query_regression")
    publication_ref = publication_ref or report.get("publication_ref")
    if publication_ref:
        from . import publication
        observed_publication = publication.read_manifest(ctx, publication_ref)
        if publication_manifest is not None and publication_manifest != observed_publication:
            raise NodeError("REGRESSION_BINDING_CHANGED", "Formal publication changed")
        frozen = publication.published_view(observed_publication).get("target_queries")
        if (report.get("publication_ref") != publication_ref
                or report.get("publication_digest") != observed_publication["digest"]
                or report.get("content_digest") != observed_publication["content_digest"]
                or report.get("cases") != frozen):
            raise NodeError("REGRESSION_BINDING_CHANGED", "Report differs from the formal publication")
    if (report.get("operation_id") != ctx.operation or report.get("passed") is not True
            or report.get("index_verified") is not True
            or report.get("generation_ref") != generation_ref
            or report.get("expected_active") != manifest.get("expected_active")
            or report.get("cases_digest") != digest(report.get("cases"))
            or (cases is not None and report.get("cases") != cases)
            or (view is not None and (report.get("view_ref") != view_ref
                                     or report.get("view_digest") != view["digest"]))
            or (applied is not None and (report.get("apply_result_ref") != apply_result_ref
                                        or report.get("apply_result_digest") != applied["digest"]))):
        raise NodeError("REGRESSION_BINDING_CHANGED", "Actual report differs from this exact batch execution")
    return _execution_binding(generation_ref, manifest, report_ref, report)


def reuse_regression(ctx, generation_ref, manifest, observed):
    if (not isinstance(observed, VerifiedRegression) or observed.root != ctx.root.resolve()
            or observed.rules_digest != ctx.args.rules_digest):
        raise NodeError("INVALID_REGRESSION_OBSERVATION", "A real matching in-process query execution is required")
    binding = dict(observed.binding)
    view_ref, applied_ref = binding.get("view_ref"), binding.get("apply_result_ref")
    current = persisted_binding(ctx, generation_ref, manifest, binding["regression_report_ref"],
        view_ref=view_ref, view=ctx.record(view_ref, "final_view") if view_ref else None,
        apply_result_ref=applied_ref, applied=ctx.record(applied_ref, "apply_result") if applied_ref else None,
        publication_ref=binding.get("publication_ref"))
    if current != binding:
        raise NodeError("REGRESSION_BINDING_CHANGED", "Verified query execution inputs or result changed")
    return binding


def _cases(request, view):
    cases = request.get("cases", view.get("target_queries") if view else None)
    if not isinstance(cases, list) or not cases:
        raise NodeError("REGRESSION_CASES_REQUIRED", "A nonempty declared case set is required")
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not case["id"] or case["id"] in seen
                or not isinstance(case.get("query"), str) or not case["query"].strip()):
            raise NodeError("INVALID_REGRESSION_CASE", "Unique case IDs and queries are required")
        seen.add(case["id"])
        if case.get("purpose", "current") not in ("current", "implementation", "guidance", "historical"):
            raise NodeError("INVALID_PURPOSE", "Invalid regression query purpose")
        for field in ("required", "forbidden", "expected_order", "expected_claim_ids", "forbidden_claim_ids"):
            if field in case and (not isinstance(case[field], list)
                    or any(not isinstance(value, str) or not value for value in case[field])
                    or len(case[field]) != len(set(case[field]))):
                raise NodeError("INVALID_REGRESSION_CASE", "Invalid " + field + " assertion")
        if not ("expected_order" in case or case.get("required") or case.get("forbidden")):
            raise NodeError("REGRESSION_ASSERTION_REQUIRED", "Each case must declare expected behavior")
    return cases


def execute(ctx, *, verified_generation=None, activate=True):
    request = dict(ctx.request)
    verify_only = ctx.args.action in {"verify", "regression-verify"}
    original = ctx.record(request["report_ref"], "query_regression") if verify_only else None
    if original is not None:
        if digest(original["cases"]) != original.get("cases_digest"):
            raise NodeError("REGRESSION_CASES_CHANGED", "Original query cases differ from their digest")
        for key in ("cases", "generation_ref", "expected_active"):
            if key in request and request[key] != original.get(key):
                raise NodeError("REGRESSION_INPUT_CHANGED", "Verification cannot replace the original " + key)
        request = {**original, **request}
    publication_manifest = None
    publication_ref = request.get("publication_ref")
    if publication_ref:
        from . import publication
        if request.get("view_ref") or request.get("apply_result_ref"):
            raise NodeError("REGRESSION_INPUT_CHANGED", "Publication regression cannot substitute private draft inputs")
        publication_manifest = publication.read_manifest(ctx, publication_ref)
        view = publication.published_view(publication_manifest)
        if "cases" in request and request["cases"] != view.get("target_queries"):
            raise NodeError("REGRESSION_CASES_CHANGED", "Publication queries are frozen")
        applied, view_ref = None, None
    else:
        applied = ctx.record(request["apply_result_ref"], "apply_result") if request.get("apply_result_ref") else None
        view = None
        view_ref = request.get("view_ref") or (applied or {}).get("view_ref")
    if view_ref:
        view = ctx.record(view_ref, "final_view")
        if applied and view["digest"] != applied["view_digest"]:
            raise NodeError("BATCH_VIEW_CHANGED", "Batch and supplied view digests differ")
    cases = _cases(request, view)
    ref = request["generation_ref"]
    observed = verified_generation or index_runtime.verify_generation(ctx, ref)
    manifest = index_runtime.reuse_generation(ctx, ref, observed)
    index_runtime.expected_baseline(ctx, manifest, request, current=activate and not verify_only)
    outcomes = []
    for case in cases:
        payload = {"operation_id": ctx.operation, "generation_ref": ref, "evaluation": True,
                   "channel": manifest["channel"], "query": case["query"],
                   "context": case.get("context", {}), "purpose": case.get("purpose", "current"),
                   "top_k": case.get("top_k", 5)}
        result = query_runtime.search(ctx, payload, verified_generation=observed)
        ids = [row["card_id"] for row in result["matches"]]
        passed = (not result["candidate_scan_truncated"]
                  and all(card in ids for card in case.get("required", []))
                  and not set(ids) & set(case.get("forbidden", []))
                  and ("expected_order" not in case or ids == case["expected_order"]))
        reads = []
        for hit in result["matches"]:
            body = query_runtime.read(ctx, {**payload, "card_id": hit["card_id"]}, verified_generation=observed)
            same = (body.get("generation_ref") == ref
                    and body.get("card_digest") == hit.get("card_digest")
                    and {claim["id"] for claim in body.get("claims", [])} == set(hit.get("claim_ids", [])))
            passed = passed and same
            reads.append({"card_id": hit["card_id"], "passed": same, "receipt_ref": body["receipt_ref"]})
        claims = {hit["card_id"] + "#" + claim for hit in result["matches"] for claim in hit.get("claim_ids", [])}
        passed = passed and set(case.get("expected_claim_ids", [])) <= claims
        passed = passed and not set(case.get("forbidden_claim_ids", [])) & claims
        outcomes.append({"case_id": case["id"], "passed": bool(passed), "actual": ids,
                         "receipt_ref": result["receipt_ref"], "same_generation_reads": reads})
    report = ctx.seal({"generation_ref": ref, "expected_active": request.get("expected_active"),
                      "cases": cases, "cases_digest": digest(cases), "outcomes": outcomes,
                      "passed": all(row["passed"] for row in outcomes), "index_verified": True,
                      **({"view_ref": view_ref, "view_digest": view["digest"]} if view_ref else {}),
                      **({"apply_result_ref": request["apply_result_ref"], "apply_result_digest": applied["digest"]}
                         if applied is not None else {}),
                      **({"publication_ref": publication_ref, "publication_digest": publication_manifest["digest"],
                          "content_digest": publication_manifest["content_digest"]} if publication_manifest else {})}, "query_regression")
    report_ref = (("logs/publications/" + publication_manifest["operation_id"]) if publication_manifest else ctx.base)
    report_ref += "/regression/" + report["digest"] + ".json"
    ctx.save(report_ref, report)
    data = {"report_ref": report_ref, "passed": report["passed"], "activated": False, "generation_ref": ref}
    if not report["passed"]:
        return data, "needs_revision"
    binding = _execution_binding(ref, manifest, report_ref, report)
    ctx.verified_regression = VerifiedRegression(ctx.root.resolve(), ctx.args.rules_digest, tuple(sorted(binding.items())))
    if verify_only or not activate:
        return {**data, "gate_verified": verify_only}, "verified"
    activation_request = {"operation_id": ctx.operation, "generation_ref": ref,
                          "expected_active": request.get("expected_active")}
    activation, _ = index_runtime.execute(fork_context(ctx, activation_request, action="activate"),
                                          verified_generation=observed, verified_regression=ctx.verified_regression)
    return {**data, **activation, "passed": True}, "checked"
