"""Controlled processing-record extension to the existing CAS transaction."""

import base64
import importlib
import pathlib
import re

from support import Blocked, Invalid, canonical, digest, seal, strict_json


def contracts(ctx, name):
    if ctx.domain is None:
        raise Blocked("versioned domain contracts are required for v3 admission")
    return importlib.import_module(ctx.domain.__package__ + "." + name)


def read_record(ctx, ref):
    path = ctx.path(ref, (".build/operations/", "logs/ingest"))
    record = ctx.domain.load_yaml(path.read_bytes())
    contracts(ctx, "records").verify(record)
    if record.get("rules_digest") != ctx.rules_digest:
        raise Invalid("processing record uses different rules")
    return record


def record_input(ctx, request, view=None, proof=None):
    ref = request.get("ingest_record_ref")
    if not ref:
        raise Blocked("v3 apply requires a validated shared ingest record")
    ctx.path(ref, (f".build/operations/{ctx.operation(request)}",))
    record = read_record(ctx, ref)
    if record.get("operation_id") != ctx.operation(request):
        raise Invalid("processing record operation mismatch")
    path = record.get("target_path")
    if not isinstance(path, str) or not re.fullmatch(r"logs/ingest/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.yaml", path):
        raise Invalid("processing record target must be one explicit logs/ingest YAML file")
    if record.get("batch_kind") not in {"content", "record_only"}:
        raise Invalid("explicit content or record_only batch kind required")
    if record["batch_kind"] == "record_only":
        if view and (view.get("writes") or view.get("deletes")):
            raise Invalid("record-only admission forbids all knowledge/navigation/source-lock writes")
        if any(row["action"] in {"create", "update", "merge", "split", "deprecate"} for row in record["dispositions"]):
            raise Invalid("record-only facts cannot claim a content-changing disposition")
    elif not view or record.get("content_view_digest") != view["digest"]:
        raise Invalid("processing record must bind the exact checked content view")
    records = contracts(ctx, "records")
    records.validate_ingest_record(record, view=view, rules=ctx.rules)
    final = dict(record)
    final["progress"] = {**record.get("progress", {}), "apply": {
        "status": "recorded" if record["batch_kind"] == "record_only" else "applied",
        "operation_id": record["operation_id"], "view_digest": view["digest"] if view else None,
    }}
    final["status"] = "recorded" if record["batch_kind"] == "record_only" else "applied"
    if record["batch_kind"] == "content" and proof is not None:
        final["acceptance"] = acceptance(ctx, view, proof)
    final = seal(final)
    records.validate_ingest_record(final, view=view, rules=ctx.rules)
    raw = canonical(final) + b"\n"
    ctx.path(path, ("logs/ingest",))
    expected = record.get("expected_old_digest")
    # A fresh record ID must never silently adopt an existing file as its baseline.
    return record, {"path": path, "expected_old_digest": expected,
                    "final_digest": digest(raw), "bytes_b64": base64.b64encode(raw).decode()}


def acceptance(ctx, view, proof):
    knowledge = contracts(ctx, "knowledge")
    cards = []
    for row in view["writes"]:
        path = row["path"]
        if not path.startswith("knowledge/") or pathlib.PurePosixPath(path).name in {"AGENTS.md", "index.md", "README.md"}:
            continue
        card = knowledge.parse_card(base64.b64decode(row["bytes_b64"], validate=True), path, ctx.rules)
        cards.append({"path": path, "card_id": card["metadata"]["id"], "sha256": row["final_digest"],
                      "review_mode": card["metadata"]["review_mode"], "claim_ids": [c["id"] for c in card["claims"]],
                      "review_result": "retired" if card["metadata"]["lifecycle"] == "deprecated" else
                      "approved" if card["metadata"]["review_mode"] == "manual_document" else "supported"})
    proofs = [proof]
    if proof.get("proof_refs"):
        proofs = [ctx.read(ref) for ref in proof["proof_refs"].values()]
    result = {"content_view_digest": view["digest"], "rules_digest": ctx.rules_digest,
              "cards": cards, "proof_digests": [p["digest"] for p in proofs],
              "verification_tiers": [p.get("verification_tier") for p in proofs]}
    code = next((p for p in proofs if p.get("record_kind") == "local_check"), None)
    if code:
        context = ctx.read(code["context_ref"])
        result.update(context_digest=code["context_digest"], code_identity=code["code_identity"])
        result["config_digest"] = context.get("configuration_digest") or context.get("config_digest")
        # code proof was already verified against current configuration bytes.
        if not result["config_digest"]:
            raise Blocked("verified code context has no configuration fingerprint")
    return result


def check_admission(ctx, request, view):
    if not view.get("v3_required") and not request.get("v3_required"):
        return
    checks = contracts(ctx, "checks")
    path = ctx.path(request.get("lint_report_ref"), (f".build/operations/{view['operation_id']}",))
    report = strict_json(path.read_text(encoding="utf-8"))
    checks.validate_report(report, expected_rules=ctx.rules_digest, required_scope="full")
    if report.get("status") != "passed" or report.get("object", {}).get("view_digest") != view["digest"]:
        raise Blocked("a complete passing lint report for the exact view is required")
    actual = checks.run(checks.prepare_view(ctx.root, view, mode="candidate", identity={"view_digest": view["digest"], "operation_id": view["operation_id"]}),
                        ctx.rules, request.get("check_inputs"), scope="full")
    checks.validate_report(actual, expected_rules=ctx.rules_digest, required_scope="full")
    if actual["exit_code"] != 0:
        raise Blocked("actual fixed full-view checks must pass immediately before admission")
    review = ctx.read(request.get("content_review_ref"))
    if (review.get("record_kind") != "content_review" or review.get("status") != "passed"
            or review.get("view_digest") != view["digest"]
            or review.get("plan_digest") != view.get("semantic_plan_digest")):
        raise Blocked("independent content review must bind this exact view and authored plan")
    plan = ctx.read(view["semantic_plan_ref"])
    authors = {plan["author_id"], *(row["author_id"] for row in plan["card_actions"])}
    if (plan.get("digest") != view.get("semantic_plan_digest") or review.get("reviewer_id") in authors
            or not review.get("independent_context") or review.get("findings") != []
            or review.get("scan_digest") != plan.get("scan_digest")):
        raise Blocked("content review has an author conflict or unresolved findings")
    for snapshot in view.get("source_refs", []):
        recovery = snapshot.get("recovery", {})
        if recovery.get("kind") != "git" or not recovery.get("commit") or not recovery.get("path"):
            raise Blocked("formal source must be recoverable across clones from an exact Git original")
        try:
            contracts(ctx, "source_resources").recover_snapshot(ctx.root, snapshot, allow_local_fallback=False)
        except (ValueError, OSError) as exc:
            raise Blocked("portable exact Git recovery is unavailable; retained local bytes only support historical reading") from exc


def record_only_view(ctx, request):
    record, _ = record_input(ctx, request)
    if record["batch_kind"] != "record_only":
        raise Invalid("a content batch requires its reviewed content view")
    op = ctx.operation(request)
    view = ctx.record("final_view", op, review_mode="record_only", writes=[], deletes=[], source_refs=[],
                      plan_ref=record["scan_ref"], plan_digest=record["scan_digest"], baseline_digest=digest({"files": {}}),
                      batch_kind="record_only", ingest_record_ref=request["ingest_record_ref"])
    view_ref = f".build/operations/{op}/record-only-view.json"
    ctx.save(view_ref, view)
    proof = ctx.record("confirmation_review", op, status="passed", view_digest=view["digest"],
                       batch_kind="record_only", ingest_record_ref=request["ingest_record_ref"],
                       ingest_record_digest=record["digest"], verification_tier="record_only_fixed_validation")
    proof_ref = f".build/operations/{op}/record-only-proof.json"
    ctx.save(proof_ref, proof)
    return {**request, "view_ref": view_ref, "proof_ref": proof_ref}
