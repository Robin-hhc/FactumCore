"""Reconcile a portable record; P6 owns its eventual formal application."""

import json
import copy

from .support import NodeError, digest, fixed_bytes, identifier


def _preview_dispositions(context, request, scan, semantic, view, preview):
    """Transcribe authored outcomes; do not review or choose another outcome."""
    if (preview.get("purpose") != "disposition_preview" or preview["operation_id"] != context.operation
            or preview.get("semantic_plan_ref") != request["semantic_plan_ref"]
            or preview.get("semantic_plan_digest") != semantic["digest"]
            or preview.get("origin_scan_operation_id") != scan["operation_id"]
            or preview.get("units") != semantic.get("units")
            or preview.get("maintenance_units") != semantic.get("maintenance_units", [])
            or preview.get("card_decisions") != view.get("dispositions")
            or preview.get("input_snapshot_digest") != view.get("input_snapshot", {}).get("snapshot_digest")):
        raise NodeError("DISPOSITION_PREVIEW_MISMATCH", "P5 requires the exact P2/P3 disposition preview")
    observations = {unit["unit_id"]: unit for unit in scan["units"]}
    authored = preview["units"]
    if len(authored) != len(observations) or {unit["unit_id"] for unit in authored} != set(observations):
        raise NodeError("UNIT_COVERAGE_INVALID", "Authored outcomes must cover this exact fixed scan")
    decisions = preview["card_decisions"]
    result = []
    for planned in authored:
        identity, outcome = planned["unit_id"], planned.get("outcome")
        observation = observations[identity]
        actions = [row for row in semantic.get("card_actions", []) if identity in row.get("unit_ids", [])]
        actual_actions = set()
        for action in actions:
            matches = [row for row in decisions if action["card_id"] in row.get("card_ids", []) + row.get("replaces", [])
                       and row.get("decision") == action["decision"]]
            if action["decision"] != "defer" and not matches:
                raise NodeError("CARD_DECISION_MISMATCH", "Authored card action is absent from the exact preview", action["card_id"])
            for match in matches:
                actual_actions.add(match["decision"])
        if outcome == "content":
            if not actual_actions:
                raise NodeError("CONTENT_ACTION_REQUIRED", "Content outcome needs an actual authored card action", identity)
            action = planned.get("record_action")
            if action not in actual_actions:
                raise NodeError("PLAN_RECORD_ACTION_REQUIRED", "P2 must freeze record_action from this unit's actual content decisions", identity)
            if not isinstance(planned.get("card_refs"), list) or not isinstance(planned.get("claim_refs"), list):
                raise NodeError("PLAN_RECORD_REFS_REQUIRED", "P2 must freeze the actual card and Claim references", identity)
            adopted = observation.get("observed_fingerprint")
            withdrawn = (action == "deprecate" and scan.get("complete") is True
                         and observation.get("change") == "missing" and not observation.get("read_error")
                         and adopted is None)
            progress = "withdrawn" if withdrawn else "completed"
        elif outcome in {"skip", "defer", "failed", "uncovered"}:
            action, adopted = outcome, None
            progress = "skipped" if outcome == "skip" else "blocked"
        else:
            raise NodeError("INVALID_SOURCE_OUTCOME", "Cannot transcribe an unknown authored outcome", identity)
        row = {"unit_id": identity, "action": action, "reason": planned["reason"],
               "observed_fingerprint": observation.get("observed_fingerprint"), "adopted_fingerprint": adopted,
               "progress": progress, "card_refs": copy.deepcopy(planned.get("card_refs", [])),
               "claim_refs": copy.deepcopy(planned.get("claim_refs", []))}
        if outcome == "skip":
            row["kind"] = planned.get("kind", "substantive")
        for key in ("owner", "next_step", "coverage", "document_scope_reviewed"):
            if key in planned:
                row[key] = copy.deepcopy(planned[key])
        result.append(row)
    return result


def _adoption(context, request, scan, semantic, semantic_ref, view):
    """Bind a new round to actual predecessor data, never an origin flag alone."""
    origin = scan["operation_id"]
    if request.get("origin_scan_operation_id", origin) != origin:
        raise NodeError("PLAN_SCAN_MISMATCH", "Requested origin differs from the actual inventory")
    result = {"origin_scan_operation_id": origin}
    previous = None
    if view and view.get("previous_view_ref"):
        previous_ref = view["previous_view_ref"]
        if request.get("previous_view_ref", previous_ref) != previous_ref or request.get("revision_reason", view.get("revision_reason")) != view.get("revision_reason"):
            raise NodeError("REVISION_CONTEXT_REQUIRED", "Record and candidate must name the same explicit return")
        previous = context.modules["production"].revision_view(context, {
            **request, "previous_view_ref": previous_ref, "revision_reason": view.get("revision_reason")}, required=True)
        if not view.get("revision_ref"):
            raise NodeError("REVISION_CONTEXT_REQUIRED", "Candidate must retain its exact revision record")
        revision = context.record(view["revision_ref"], "artifact_manifest")
        if (revision.get("purpose") != "candidate_revision" or revision.get("previous_view_ref") != previous_ref
                or revision.get("previous_view_digest") != previous["digest"]
                or revision.get("view_ref") != request["view_ref"] or revision.get("view_digest") != view["digest"]
                or revision.get("revision_reason") != view.get("revision_reason")):
            raise NodeError("REVISION_CONTEXT_REQUIRED", "Candidate revision does not bind its exact predecessor")
        if view.get("previous_view_digest") != previous["digest"]:
            raise NodeError("REVISION_CONTEXT_REQUIRED", "Candidate predecessor digest differs from its actual prior view")
        result.update(previous_view_ref=previous_ref, previous_view_digest=previous["digest"],
                      revision_reason=view["revision_reason"], revision_ref=view["revision_ref"], revision_digest=revision["digest"])
    if scan["operation_id"] != context.operation and (not previous or not semantic or not view):
        raise NodeError("OPERATION_MISMATCH", "A new round needs its actual previous candidate to adopt the original scan")
    if semantic:
        if (semantic.get("scan_digest") != scan["digest"] or semantic.get("scan_ref") != request["scan_ref"]
                or semantic.get("origin_scan_operation_id", semantic["operation_id"]) != origin):
            raise NodeError("PLAN_SCAN_MISMATCH", "Authored decisions must adopt the exact original scan")
        if semantic["operation_id"] != context.operation:
            if (not previous or previous.get("semantic_plan_ref") != semantic_ref
                    or previous.get("semantic_plan_digest") != semantic["digest"]):
                raise NodeError("PLAN_SCAN_MISMATCH", "Adopt an old authored plan only through its exact previous candidate")
        elif previous and (semantic.get("previous_view_ref") != result["previous_view_ref"]
                          or semantic.get("previous_semantic_plan_ref") != previous.get("semantic_plan_ref")
                          or semantic.get("previous_semantic_plan_digest") != previous.get("semantic_plan_digest")):
            raise NodeError("PLAN_SCAN_MISMATCH", "The new authored plan and candidate must retain the same predecessor")
        if view and (view.get("semantic_plan_ref") != semantic_ref or view.get("semantic_plan_digest") != semantic["digest"]
                     or view.get("scan_ref") != request["scan_ref"] or view.get("origin_scan_operation_id", view["operation_id"]) != origin):
            raise NodeError("PLAN_SCAN_MISMATCH", "The new candidate must adopt this exact authored plan and scan")
        material_ref = request.get("material_ref") or (view or {}).get("material_ref") or semantic.get("material_ref")
        material = context.record(material_ref, "artifact_manifest")
        if (material_ref != semantic.get("material_ref") or material["digest"] != semantic.get("material_digest")
                or (view and (view.get("material_ref") != material_ref or view.get("material_digest") != material["digest"]))):
            raise NodeError("MATERIAL_BINDING", "Record, candidate and authored plan must use the same actual material")
        result.update(semantic_plan_ref=semantic_ref, semantic_plan_digest=semantic["digest"],
                      material_ref=material_ref, material_digest=material["digest"])
    return result


def record(context):
    request = context.request
    view = context.record(request["view_ref"], "final_view") if request.get("view_ref") else None
    semantic_ref = request.get("semantic_plan_ref") or (view or {}).get("semantic_plan_ref")
    semantic = context.record(semantic_ref, "semantic_plan") if semantic_ref else None
    scan_ref = request.get("scan_ref") or (semantic or {}).get("scan_ref") or (view or {}).get("scan_ref")
    if not scan_ref:
        raise NodeError("SOURCE_INVENTORY_REQUIRED", "A portable processing record needs an actual fixed source inventory")
    scan = context.record(scan_ref, "source_inventory")
    adopted = _adoption(context, {**request, "scan_ref": scan_ref}, scan, semantic, semantic_ref, view)
    dispositions = request.get("dispositions")
    preview_ref = request.get("disposition_preview_ref") or (view or {}).get("disposition_preview_ref")
    preview = context.record(preview_ref, "artifact_manifest") if preview_ref else None
    if preview and not semantic and not request.get("disposition_preview_ref") and isinstance(dispositions, list):
        # Standalone P3 byte production has no authored P2 decisions. Preserve
        # the independent explicit-record utility without asserting review.
        preview = None
    if preview:
        if (not view or not semantic or view.get("disposition_preview_ref") != preview_ref
                or view.get("semantic_plan_ref") != semantic_ref or view.get("semantic_plan_digest") != semantic["digest"]):
            raise NodeError("DISPOSITION_PREVIEW_MISMATCH", "Preview needs its exact view and authored plan")
        derived = _preview_dispositions(context, {**request, "semantic_plan_ref": semantic_ref}, scan, semantic, view, preview)
        if dispositions is not None and dispositions != derived:
            raise NodeError("DISPOSITION_PREVIEW_MISMATCH", "P5 cannot replace authored dispositions")
        dispositions = derived
    elif not isinstance(dispositions, list):
        raise NodeError("DISPOSITIONS_REQUIRED", "Supply a bound P3 preview or explicit independent dispositions")
    maintenance = request.get("maintenance_dispositions", [])
    if semantic:
        planned = semantic.get("maintenance_units", [])
        if "maintenance_dispositions" in request and maintenance != planned:
            raise NodeError("MAINTENANCE_PLAN_MISMATCH", "P5 cannot rewrite authored maintenance decisions")
        maintenance = planned
    if view and view["operation_id"] != context.operation:
        raise NodeError("OPERATION_MISMATCH", "Content view belongs to another operation")
    batch_kind = "content" if view and (view.get("writes") or view.get("deletes")) else "record_only"
    lint_digest = None
    if batch_kind == "content" and request.get("lint_ref"):
        lint_ref = request["lint_ref"]
        report = json.loads(fixed_bytes(context.root, lint_ref, [".build/operations", "logs"]))
        object_binding = report.get("object", {})
        checked_view = report.get("view_digest") or object_binding.get("view_digest") or object_binding.get("digest")
        if checked_view != view["digest"]:
            raise NodeError("LINT_VIEW_MISMATCH", "Final lint must bind this exact view")
        lint_digest = digest(report)
    elif batch_kind == "record_only" and (any(d.get("action") in {"create", "update", "merge", "split", "deprecate"} for d in dispositions) or any(d.get("outcome") == "content" for d in maintenance)):
        raise NodeError("CONTENT_VIEW_REQUIRED", "Content dispositions cannot be hidden in a record-only batch")
    record_id = identifier(request.get("record_id", context.operation))
    payload = {"record_id": record_id, "target_path": "logs/ingest/" + record_id + ".yaml",
               "batch_kind": batch_kind, "status": "pending", "phase": "recorded", "progress": {},
               "scan_ref": scan_ref, "scan_digest": scan["digest"], "inventory": scan,
               "prior_record_digests": scan.get("prior_record_digests", []),
               "content_view_digest": view["digest"] if view else None,
               "dispositions": dispositions, "maintenance_dispositions": maintenance,
               "pending": request.get("pending", []) + [{"unit_id": d["unit_id"], "reason": d["reason"], "outcome": d["outcome"]}
                                                        for d in maintenance if d.get("outcome") in {"defer", "failed", "uncovered"}],
               "skip_sample": request.get("skip_sample"), "captured_at": scan.get("captured_at")}
    for key in ("plan_ref", "view_ref", "lint_ref", "semantic_plan_ref", "material_ref"):
        if request.get(key):
            payload[key] = request[key]
    if preview:
        payload.update(disposition_preview_ref=preview_ref, disposition_preview_digest=preview["digest"],
                       semantic_plan_ref=semantic_ref, semantic_plan_digest=semantic["digest"],
                       authored_units=copy.deepcopy(preview["units"]), preview_card_decisions=copy.deepcopy(preview["card_decisions"]))
    if lint_digest:
        payload["lint_digest"] = lint_digest
    payload.update(adopted)
    result = context.seal(payload, "ingest_record")
    validation_view = view if view is not None else {"writes": [], "deletes": []}
    context.modules["records"].validate_ingest_record(result, scan=scan, view=validation_view, rules=context.rules)
    ref = context.base + "/ingest-record.yaml"
    context.save(ref, result)
    return {"record_ref": ref, "ingest_record_ref": ref, "record_digest": result["digest"],
            "record_path": result["target_path"], "batch_kind": batch_kind}, "recorded"
