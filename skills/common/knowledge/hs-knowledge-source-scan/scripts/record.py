"""Reconcile a portable record; P7 owns its eventual formal application."""

import json

from support import NodeError, digest, fixed_bytes, identifier


def record(context):
    request = context.request
    scan = context.record(request["scan_ref"], "source_inventory")
    if scan["operation_id"] != context.operation:
        raise NodeError("OPERATION_MISMATCH", "Inventory belongs to another operation")
    dispositions = request.get("dispositions")
    if not isinstance(dispositions, list):
        raise NodeError("DISPOSITIONS_REQUIRED", "Every scanned unit needs a disposition")
    maintenance = request.get("maintenance_dispositions", [])
    if request.get("semantic_plan_ref"):
        semantic = context.record(request["semantic_plan_ref"], "semantic_plan")
        if semantic["operation_id"] != context.operation or semantic.get("scan_digest") != scan["digest"]:
            raise NodeError("PLAN_SCAN_MISMATCH", "Maintenance dispositions must bind this exact scan and operation")
        planned = semantic.get("maintenance_units", [])
        if "maintenance_dispositions" in request and maintenance != planned:
            raise NodeError("MAINTENANCE_PLAN_MISMATCH", "P6 cannot rewrite authored maintenance decisions")
        maintenance = planned
    view = context.record(request["view_ref"], "final_view") if request.get("view_ref") else None
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
               "scan_ref": request["scan_ref"], "scan_digest": scan["digest"], "inventory": scan,
               "prior_record_digests": scan.get("prior_record_digests", []),
               "content_view_digest": view["digest"] if view else None,
               "dispositions": dispositions, "maintenance_dispositions": maintenance,
               "pending": request.get("pending", []) + [{"unit_id": d["unit_id"], "reason": d["reason"], "outcome": d["outcome"]}
                                                        for d in maintenance if d.get("outcome") in {"defer", "failed", "uncovered"}],
               "skip_sample": request.get("skip_sample"), "captured_at": scan.get("captured_at")}
    for key in ("plan_ref", "view_ref", "lint_ref", "semantic_plan_ref", "material_ref"):
        if request.get(key):
            payload[key] = request[key]
    if lint_digest:
        payload["lint_digest"] = lint_digest
    result = context.seal(payload, "ingest_record")
    validation_view = view if view is not None else {"writes": [], "deletes": []}
    context.modules["records"].validate_ingest_record(result, scan=scan, view=validation_view, rules=context.rules)
    ref = context.base + "/ingest-record.yaml"
    context.save(ref, result)
    return {"record_ref": ref, "ingest_record_ref": ref, "record_digest": result["digest"],
            "record_path": result["target_path"], "batch_kind": batch_kind}, "recorded"
