"""Frozen publication identities and bounded cleanup over explicit owned files."""

from __future__ import annotations

import base64
import copy
import json
import re

from .runtime import NodeError, canonical, digest, fixed_bytes, identifier, safe, sha, unique, write_bytes
from . import staging


PROTOCOL = "1.2"
PLAN_PROTOCOL = "1.0"


def manifest_ref(operation_id):
    return "logs/publications/" + identifier(operation_id) + "/manifest.json"


def completion_ref(operation_id):
    return "logs/publications/" + identifier(operation_id) + "/completion.json"


def _payload_target(root, ref):
    safe(root, ref, ["knowledge", "index.md", "governance/sources.lock.yaml", "logs/evidence/published"])
    if not (ref.startswith("knowledge/") or ref in {"index.md", "governance/sources.lock.yaml"}
            or ref.startswith("logs/evidence/published/")):
        raise NodeError("INVALID_PUBLICATION_TARGET", "Not a formal payload target", ref)
    return ref


def _raw_write(row):
    try:
        raw = base64.b64decode(row["bytes_b64"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise NodeError("INVALID_FINAL_BYTES", "Publication bytes are invalid", row.get("path")) from exc
    if sha(raw) != row.get("final_digest"):
        raise NodeError("FINAL_BYTES_CHANGED", "Publication byte fingerprint differs", row.get("path"))
    return raw


def _owned(root, rows):
    if not isinstance(rows, list):
        raise NodeError("INVALID_OWNED_FILES", "Owned files must be an explicit list")
    result = {}
    for item in rows:
        if not isinstance(item, dict):
            raise NodeError("INVALID_OWNED_FILE", "Owned file must be an object")
        row = copy.deepcopy(item)
        ref = row.get("path", row.get("stage_ref"))
        owner = identifier(row.get("owner_operation_id"))
        safe(root, ref, [".build/operations/" + owner])
        if not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise NodeError("INVALID_OWNED_FILE", "Owned file needs an exact SHA-256", ref)
        if type(row.get("bytes")) is not int or row["bytes"] < 0:
            raise NodeError("INVALID_OWNED_FILE", "Owned file needs an exact byte size", ref)
        row["path"] = ref
        if ref in result and result[ref] != row:
            raise NodeError("OWNERSHIP_CONFLICT", "Conflicting owned file observations", ref)
        result[ref] = row
    return [result[key] for key in sorted(result)]


def _dispositions(preview):
    if not preview:
        return []
    allowed = {"unit_id", "action", "reason", "observed_fingerprint", "adopted_fingerprint", "progress",
               "card_refs", "claim_refs", "record_action", "coverage", "outcome", "conditions"}
    return [{key: copy.deepcopy(value) for key, value in row.items() if key in allowed}
            for row in preview.get("dispositions", preview.get("units", []))]


def prepare_plan(ctx, view, *, staged_objects=None, event_proposals=None, disposition_preview=None):
    """Compute identities from adopted bytes; never publish or discover an operation."""
    if view.get("operation_id") != ctx.operation:
        raise NodeError("OPERATION_CHANGED", "Publication view belongs to another operation")
    entries = staging.validate_entries(ctx.root, copy.deepcopy(
        view.get("staged_objects", []) if staged_objects is None else staged_objects))
    proposals = copy.deepcopy(view.get("event_proposals", []) if event_proposals is None else event_proposals)
    if not isinstance(proposals, list):
        raise NodeError("INVALID_EVENT_PROPOSALS", "Event proposals must be an explicit list")
    payloads, expected = {}, {}
    for row in view.get("writes", []):
        path = _payload_target(ctx.root, row["path"])
        raw = _raw_write(row)
        if path in payloads:
            raise NodeError("DUPLICATE_TARGET", "Duplicate publication target", path)
        payloads[path] = {"path": path, "sha256": sha(raw), "bytes": len(raw), "kind": "content"}
        expected[path] = row.get("expected_old_digest")
    for item in entries:
        path = _payload_target(ctx.root, item["final_ref"])
        raw = staging.read_bytes(ctx.root, path, entries, expected_sha=item["sha256"], expected_size=item["bytes"])
        row = {"path": path, "sha256": sha(raw), "bytes": len(raw), "kind": item["kind"]}
        row.update({key: item[key] for key in ("source_id", "snapshot_id") if key in item})
        if path in payloads and any(payloads[path][key] != row[key] for key in ("sha256", "bytes")):
            raise NodeError("PUBLICATION_CONFLICT", "Staged object replaces different frozen bytes", path)
        if path not in payloads:
            payloads[path] = row
            target = safe(ctx.root, path)
            existing = fixed_bytes(ctx.root, path) if target.exists() else None
            if existing is not None and existing != raw:
                raise NodeError("PUBLICATION_CONFLICT", "Formal immutable object has different bytes", path)
            expected[path] = sha(existing) if existing is not None else None
    deletions = []
    for item in view.get("deletes", []):
        path = _payload_target(ctx.root, item["path"])
        if path == "governance/sources.lock.yaml" or path.startswith("logs/evidence/") or path in payloads:
            raise NodeError("INVALID_PUBLICATION_DELETE", "Invalid formal deletion", path)
        deletions.append({"path": path, "expected_old_digest": item.get("expected_old_digest")})
    content = {"payloads": [payloads[key] for key in sorted(payloads)],
               "deletes": sorted(deletions, key=lambda row: row["path"]),
               "source_refs": copy.deepcopy(view.get("source_refs", [])),
               "dispositions": _dispositions(disposition_preview),
               "batch_kind": view.get("batch_kind", "content")}
    plan = {"protocol_version": PLAN_PROTOCOL, "operation_id": ctx.operation,
            "staged_objects": entries, "event_proposals": proposals,
            "payloads": content["payloads"], "deletes": content["deletes"],
            "expected_old": expected, "dispositions": content["dispositions"],
            "content_digest": digest(content),
            "owned_files": _owned(ctx.root, view.get("owned_files", []))}
    plan["publication_plan_digest"] = digest(plan)
    return plan


def validate_plan(ctx, view):
    declared = view.get("publication_plan")
    if not isinstance(declared, dict):
        raise NodeError("PUBLICATION_PLAN_REQUIRED", "Frozen publication plan is required")
    preview = {"dispositions": declared.get("dispositions", [])}
    observed = prepare_plan(ctx, view, disposition_preview=preview)
    # Immutable evidence may already have been installed by this transaction.
    # Its original CAS expectation stays frozen, while bytes are still checked.
    for item in observed["staged_objects"]:
        path = item["final_ref"]
        if path not in {row["path"] for row in view.get("writes", [])}:
            observed["expected_old"][path] = declared.get("expected_old", {}).get(path)
    observed["publication_plan_digest"] = digest({key: value for key, value in observed.items()
                                                 if key != "publication_plan_digest"})
    if observed != declared or view.get("content_digest", observed["content_digest"]) != observed["content_digest"]:
        raise NodeError("PUBLICATION_PLAN_CHANGED", "Publication mapping or adopted byte identity changed")
    return declared


def transaction_rows(ctx, view, plan=None):
    """Use exact original payload bytes when extending the safe transaction view."""
    plan = plan or validate_plan(ctx, view)
    rows = copy.deepcopy(view.get("writes", []))
    selected = {row["path"] for row in rows}
    for item in plan["staged_objects"]:
        if item["final_ref"] in selected:
            continue
        raw = staging.read_bytes(ctx.root, item["final_ref"], plan["staged_objects"],
                                 expected_sha=item["sha256"], expected_size=item["bytes"])
        target = safe(ctx.root, item["final_ref"])
        existing = fixed_bytes(ctx.root, item["final_ref"]) if target.exists() else None
        if existing is not None and existing != raw:
            raise NodeError("PUBLICATION_CONFLICT", "Formal immutable object has different bytes", item["final_ref"])
        rows.append({"path": item["final_ref"], "expected_old_digest": plan["expected_old"][item["final_ref"]],
                     "final_digest": sha(raw), "bytes_b64": base64.b64encode(raw).decode()})
    return rows


def _file(ctx, path, *, kind="record"):
    raw = fixed_bytes(ctx.root, path, ["knowledge", "index.md", "governance/sources.lock.yaml", "logs"])
    return {"path": path, "sha256": sha(raw), "bytes": len(raw), "kind": kind}


def _projection(view):
    fields = ("review_mode", "batch_kind", "writes", "deletes", "source_refs", "target_queries",
              "review_requirements", "v3_required")
    return {key: copy.deepcopy(view[key]) for key in fields if key in view}


def publish_manifest(ctx, view, plan=None, *, processing_record=None, event_refs=(), applied=None, index_inputs=None):
    """Seal only the formal byte set already installed and checked by P6."""
    plan = plan or validate_plan(ctx, view)
    files = []
    for expected in plan["payloads"]:
        actual = _file(ctx, expected["path"], kind=expected["kind"])
        if any(actual[key] != expected[key] for key in ("sha256", "bytes")):
            raise NodeError("PUBLICATION_BYTES_CHANGED", "Published payload bytes differ", expected["path"])
        files.append(actual)
    for row in plan["deletes"]:
        if safe(ctx.root, row["path"]).exists():
            raise NodeError("PUBLICATION_BYTES_CHANGED", "Published deletion is still present", row["path"])
    processing = None
    if processing_record:
        path = processing_record if isinstance(processing_record, str) else processing_record["path"]
        safe(ctx.root, path, ["logs/ingest"])
        processing = _file(ctx, path, kind="ingest_record")
        files.append(processing)
    events = []
    for item in event_refs:
        ref = item if isinstance(item, str) else item["path"]
        safe(ctx.root, ref, ["logs/events"])
        events.append(ref)
        files.append(_file(ctx, ref, kind="maintenance_event"))
    state_ref = "logs/events/state.json"
    if safe(ctx.root, state_ref).is_file() and state_ref not in {row["path"] for row in files}:
        files.append(_file(ctx, state_ref, kind="maintenance_state"))
    projection = _projection(view)
    content_basis = {"payloads": copy.deepcopy(plan["payloads"]), "deletes": copy.deepcopy(plan["deletes"]),
                     "source_refs": copy.deepcopy(view.get("source_refs", [])),
                     "dispositions": copy.deepcopy(plan["dispositions"]),
                     "batch_kind": view.get("batch_kind", "content")}
    if digest(content_basis) != plan["content_digest"]:
        raise NodeError("PUBLICATION_PLAN_CHANGED", "Formal content basis differs from the frozen plan")
    index_inputs = copy.deepcopy(index_inputs) if index_inputs is not None else {key: copy.deepcopy(ctx.request[key]) for key in
                    ("channel", "code_contexts", "code_evidence", "knowledge_commit", "publication_receipt_ref", "expected_active")
                    if key in ctx.request}
    if view.get("input_snapshot"):
        from . import input_snapshot
        index_inputs["input_snapshot"] = input_snapshot.published_inputs(
            ctx, view["input_snapshot"], staged_objects=plan["staged_objects"])
    from . import input_snapshot
    dbox_scope = input_snapshot.execution_scope(input_snapshot.source_execution_files(view.get("input_snapshot")))
    applied_ref = None
    if applied is not None:
        applied_ref = "logs/publications/" + ctx.operation + "/apply-result.json"
        ctx.save(applied_ref, applied)
        files.append(_file(ctx, applied_ref, kind="apply_result"))
    manifest = ctx.seal({"purpose": "knowledge_publication", "protocol_version": PROTOCOL,
        "published": True, "content_digest": plan["content_digest"],
        "content_basis": content_basis,
        "publication_plan_digest": plan["publication_plan_digest"],
        "reviewed_view_digest": view["digest"], "batch_kind": view.get("batch_kind", "content"),
        "files": files, "deletes": copy.deepcopy(plan["deletes"]),
        "published_view": projection, "published_view_digest": digest(projection),
        "processing_record": processing, "event_refs": events,
        "apply_result": copy.deepcopy(applied), "apply_result_ref": applied_ref,
        "index_inputs": index_inputs,
        "dbox_execution_scope": dbox_scope,
        "trace": {"view_ref": ctx.request.get("view_ref"), "view_digest": view["digest"]}}, "artifact_manifest")
    ref = manifest_ref(ctx.operation)
    if safe(ctx.root, ref).exists():
        previous = read_manifest(ctx, ref)
        if previous != manifest:
            raise NodeError("PUBLICATION_CONFLICT", "Operation already published different formal facts", ref)
        return previous
    ctx.save(ref, manifest)
    return manifest


def publish_processing_record(ctx, view, reference, *, expected_digest=None):
    """Add actual apply facts only after P6 has verified its complete payload."""
    if not reference:
        return None
    safe(ctx.root, reference, [ctx.base])
    pending = ctx.record(reference, "ingest_record")
    if expected_digest is not None and pending["digest"] != expected_digest:
        raise NodeError("INGEST_RECORD_CHANGED", "Pending record changed after the transaction was prepared")
    if pending.get("operation_id") != ctx.operation:
        raise NodeError("INGEST_RECORD_CHANGED", "Pending record belongs to another operation")
    if pending.get("batch_kind") == "content" and pending.get("content_view_digest") != view["digest"]:
        raise NodeError("INGEST_RECORD_CHANGED", "Pending record describes another checked view")
    ctx.modules["records"].validate_ingest_record(pending, view=view, rules=ctx.rules)
    target = pending.get("target_path")
    if not isinstance(target, str) or not re.fullmatch(r"logs/ingest/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.yaml", target):
        raise NodeError("INVALID_INGEST_TARGET", "Pending record target is not one formal ingest record")
    result = copy.deepcopy(pending)
    result["status"] = "recorded" if pending["batch_kind"] == "record_only" else "applied"
    result["progress"] = {**pending.get("progress", {}), "apply": {
        "status": result["status"], "operation_id": ctx.operation, "view_digest": view["digest"]}}
    result.pop("acceptance", None)
    result.update(publication_ref=manifest_ref(ctx.operation), publication_protocol=PROTOCOL,
                  content_digest=view["publication_plan"]["content_digest"])
    result = ctx.modules["records"].seal(result)
    ctx.modules["records"].validate_ingest_record(result, view=view, rules=ctx.rules)
    raw = canonical(result) + b"\n"
    path = safe(ctx.root, target, ["logs/ingest"])
    existing = fixed_bytes(ctx.root, target) if path.exists() else None
    if existing == raw:
        return target
    if (sha(existing) if existing is not None else None) != pending.get("expected_old_digest"):
        raise NodeError("INGEST_RECORD_CONFLICT", "Formal processing record changed", target, blocked=True)
    write_bytes(ctx.root, target, raw, immutable=existing is None)
    if fixed_bytes(ctx.root, target) != raw:
        raise NodeError("PUBLICATION_BYTES_CHANGED", "Formal processing record read-back differs", target)
    return target


def owned_files(ctx, view=None):
    """Collect only declared mappings and operation-local writer registrations."""
    view = view or {}
    rows = list(view.get("publication_plan", {}).get("owned_files", []))
    for item in view.get("staged_objects", []):
        rows.append({"path": item["stage_ref"], "sha256": item["sha256"], "bytes": item["bytes"],
                     "owner_operation_id": item["owner_operation_id"],
                     **({"retain_reason": item["retain_reason"]} if item.get("retain_reason") else {})})
    result = {row["path"]: row for row in _owned(ctx.root, rows)}
    if callable(getattr(ctx, "owned_files", None)):
        for row in ctx.owned_files():
            previous = result.get(row["path"], {})
            result[row["path"]] = {**previous, **row}
    ledger_ref = ctx.base + "/owned-files.json"
    if safe(ctx.root, ledger_ref).is_file():
        raw = fixed_bytes(ctx.root, ledger_ref)
        result[ledger_ref] = {"path": ledger_ref, "sha256": sha(raw), "bytes": len(raw),
                              "owner_operation_id": ctx.operation}
    return _owned(ctx.root, list(result.values()))


def _read(ctx, ref, purpose):
    value = json.loads(fixed_bytes(ctx.root, ref, ["logs/publications"]), object_pairs_hook=unique)
    ctx.modules["records"].verify(value)
    ctx.modules["validation"].validate_shape("artifact_manifest", value, ctx.rules)
    if value.get("purpose") != purpose or value.get("protocol_version") not in {"1.0", "1.1", PROTOCOL}:
        raise NodeError("INVALID_PUBLICATION", "Unsupported publication record", ref)
    return value


def read_manifest(ctx, reference=None, *, operation_id=None, verify_files=False):
    ref = reference or manifest_ref(operation_id or ctx.operation)
    value = _read(ctx, ref, "knowledge_publication")
    if (ref != manifest_ref(value.get("operation_id")) or value.get("published") is not True
            or digest(value.get("published_view")) != value.get("published_view_digest")):
        raise NodeError("INVALID_PUBLICATION", "Manifest identity or business projection differs", ref)
    from . import input_snapshot
    if value["protocol_version"] in {"1.1", PROTOCOL}:
        input_snapshot.validate_execution_scope(value.get("dbox_execution_scope"))
    elif "dbox_execution_scope" in value:
        raise NodeError("INVALID_PUBLICATION", "Legacy publication format cannot carry current external scope", ref)
    if input_snapshot.source_execution_files(value.get("index_inputs", {}).get("input_snapshot")):
        raise NodeError("INVALID_PUBLICATION", "Public index inputs contain private external execution bindings", ref)
    basis = value.get("content_basis")
    if value["protocol_version"] == "1.2" and basis is None:
        raise NodeError("INVALID_PUBLICATION", "Current publications require their frozen content basis", ref)
    if basis is not None:
        if (not isinstance(basis, dict) or set(basis) != {
                "payloads", "deletes", "source_refs", "dispositions", "batch_kind"}
                or digest(basis) != value.get("content_digest")
                or any(not isinstance(basis[key], list)
                       for key in ("payloads", "deletes", "source_refs", "dispositions"))):
            raise NodeError("INVALID_PUBLICATION", "Frozen content basis does not match its original content digest", ref)
        payloads = {row.get("path"): row for row in basis["payloads"] if isinstance(row, dict)}
        if (len(payloads) != len(basis["payloads"])
                or any(not isinstance(path, str) or not path for path in payloads)):
            raise NodeError("INVALID_PUBLICATION", "Frozen payloads need unique paths", ref)
        projection = value["published_view"]
        writes = projection.get("writes", [])
        expected_writes = {row["path"] for row in payloads.values() if row.get("kind") == "content"}
        if (not isinstance(writes, list) or any(not isinstance(row, dict) for row in writes)
                or len(writes) != len({row.get("path") for row in writes})
                or {row.get("path") for row in writes} != expected_writes):
            raise NodeError("PUBLICATION_BYTES_CHANGED", "Published write set differs from its original content identity", ref)
        if (sorted(basis["deletes"], key=lambda row: row["path"])
                != sorted(projection.get("deletes", []), key=lambda row: row["path"])
                or basis["source_refs"] != projection.get("source_refs", [])
                or basis["batch_kind"] != projection.get("batch_kind", "content")):
            raise NodeError("INVALID_PUBLICATION", "Published projection differs from its frozen content basis", ref)
        if (value.get("batch_kind") != basis["batch_kind"]
                or sorted(value.get("deletes", []), key=lambda row: row["path"])
                   != sorted(basis["deletes"], key=lambda row: row["path"])):
            raise NodeError("INVALID_PUBLICATION", "Manifest execution fields differ from its frozen content basis", ref)
        for row in writes:
            raw = _raw_write(row)
            expected = payloads.get(row["path"], {})
            if sha(raw) != expected.get("sha256") or len(raw) != expected.get("bytes"):
                raise NodeError("PUBLICATION_BYTES_CHANGED", "Published body differs from its original content identity", row["path"])
        for expected in payloads.values():
            matches = [row for row in value.get("files", []) if row.get("path") == expected["path"]]
            if (len(matches) != 1 or any(matches[0].get(key) != expected.get(key)
                                         for key in ("sha256", "bytes", "kind"))):
                raise NodeError("PUBLICATION_BYTES_CHANGED", "Published payload differs from its frozen identity", expected["path"])
    for row in value.get("files", []):
        safe(ctx.root, row["path"], ["knowledge", "index.md", "governance/sources.lock.yaml", "logs"])
        if verify_files:
            actual = _file(ctx, row["path"], kind=row["kind"])
            if actual != row:
                raise NodeError("PUBLICATION_BYTES_CHANGED", "Current publication bytes changed", row["path"])
    if verify_files:
        for row in value.get("deletes", []):
            if safe(ctx.root, row["path"]).exists():
                raise NodeError("PUBLICATION_BYTES_CHANGED", "Current publication deletion changed", row["path"])
    return value


def published_view(manifest):
    """Return a business projection, never pretend it is the old sealed draft."""
    result = copy.deepcopy(manifest["published_view"])
    if digest(result) != manifest.get("published_view_digest"):
        raise NodeError("INVALID_PUBLICATION", "Published business view fingerprint differs")
    result.update(operation_id=manifest["operation_id"], content_digest=manifest["content_digest"],
                  reviewed_view_digest=manifest["reviewed_view_digest"])
    return result


def _retrieval_facts(ctx, manifest, completion):
    """Verify durable execution facts without requiring the old local index."""
    from . import query_regression
    from .runtime import OperationContext
    retrieval, data = completion.get("retrieval", {}), completion.get("data", {})
    if retrieval.get("complete") is not True:
        return
    if manifest["batch_kind"] == "record_only":
        if retrieval.get("scope") != "record_only" or data.get("activated") is True:
            raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Record-only retrieval scope changed")
        return
    producer = manifest["operation_id"]
    prefix = "logs/publications/" + producer
    report_ref, observation_ref = data.get("report_ref"), data.get("activation_observation_ref")
    if not (isinstance(report_ref, str) and report_ref.startswith(prefix + "/regression/")
            and isinstance(observation_ref, str) and observation_ref.startswith(prefix + "/activation/")):
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Formal retrieval facts are missing")
    rows = retrieval.get("files", [])
    if (not isinstance(rows, list) or len(rows) != 2
            or {row.get("path") for row in rows} != {report_ref, observation_ref}):
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Formal retrieval files changed")
    for row in rows:
        if row != _file(ctx, row["path"], kind="retrieval_record"):
            raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Formal retrieval bytes changed", row["path"])
    # Historical completion is evidence under its producer's rule identity,
    # never a qualification to build or activate under today's rules.
    producer_ctx = OperationContext(ctx.root, {"operation_id": producer}, modules=ctx.modules,
        rules=ctx.rules, tool=ctx.tool, rules_digest=manifest["rules_digest"])
    report = producer_ctx.record(report_ref, "query_regression")
    observation = producer_ctx.record(observation_ref, "artifact_manifest")
    baseline = manifest.get("index_inputs", {}).get("expected_active")
    generation = retrieval.get("generation_ref")
    if (report_ref != prefix + "/regression/" + report["digest"] + ".json"
            or observation_ref != prefix + "/activation/" + observation["digest"] + ".json"
            or report != retrieval.get("regression") or observation != retrieval.get("activation_observation")
            or observation.get("purpose") != "index_activation_observation"
            or observation.get("operation_id") != producer
            or observation.get("generation_ref") != generation or data.get("generation_ref") != generation
            or retrieval.get("expected_active") != baseline or data.get("expected_active") != baseline
            or observation.get("expected_active") != baseline
            or data.get("activated") is not True or data.get("passed") is not True
            or len(report.get("outcomes", [])) != len(report.get("cases", []))
            or any(row.get("passed") is not True or row.get("case_id") != case.get("id")
                   for row, case in zip(report.get("outcomes", []), report.get("cases", [])))):
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Persisted retrieval facts disagree")
    binding = query_regression.persisted_binding(producer_ctx, generation,
        {"digest": observation.get("manifest_digest"), "expected_active": baseline}, report_ref,
        cases=manifest["published_view"].get("target_queries"),
        publication_ref=manifest_ref(producer), publication_manifest=manifest)
    pointer = observation.get("active_pointer", {})
    ctx.modules["records"].verify(pointer)
    ctx.modules["validation"].validate_shape("index_manifest", pointer, ctx.rules)
    if (pointer.get("operation_id") != producer or pointer.get("rules_digest") != manifest["rules_digest"]
            or pointer.get("generation_ref") != generation
            or pointer.get("manifest_digest") != observation.get("manifest_digest")
            or pointer.get("channel") != manifest.get("index_inputs", {}).get("channel", "local")
            or pointer.get("previous_active_digest") != baseline
            or pointer.get("execution_binding") != binding or pointer.get("digest") != observation.get("active_digest")):
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Persisted activation does not bind this retrieval")


def read_completion(ctx, manifest=None, *, operation_id=None):
    manifest = manifest or read_manifest(ctx, operation_id=operation_id)
    ref = completion_ref(manifest["operation_id"])
    if not safe(ctx.root, ref).exists():
        return None
    value = _read(ctx, ref, "knowledge_publication_completion")
    if (value.get("operation_id") != manifest["operation_id"]
            or value.get("protocol_version") != manifest.get("protocol_version")
            or value.get("publication_ref") != manifest_ref(manifest["operation_id"])
            or value.get("publication_digest") != manifest["digest"]
            or value.get("content_digest") != manifest["content_digest"]):
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Completion describes another publication", ref)
    complete = value.get("retrieval", {}).get("complete") is True and value.get("cleanup", {}).get("status") == "done"
    expected_phase = ("recorded" if manifest["batch_kind"] == "record_only" else "completed") if complete else (
        "cleanup_pending" if value.get("retrieval", {}).get("complete") is True else "finalization_pending")
    if value.get("batch_complete") is not complete or value.get("phase") != expected_phase or value.get("published") is not True:
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Completion stages disagree with batch completion", ref)
    _retrieval_facts(ctx, manifest, value)
    return value


def write_completion(ctx, manifest, *, data, retrieval, owned_files, expected_digest=None,
                     cleanup_result=None):
    """CAS one completion observation; immutable business manifest stays unchanged."""
    from .maintenance import writer_lock
    if ctx.operation != manifest["operation_id"]:
        raise NodeError("OPERATION_CHANGED", "Completion writer belongs to another operation")
    ref = completion_ref(manifest["operation_id"])
    owned = _owned(ctx.root, owned_files)
    cleanup_result = copy.deepcopy(cleanup_result or {
        "status": "cleanup_pending", "owned": owned, "deleted": [], "retained": [], "failed": []})
    complete = retrieval.get("complete") is True and cleanup_result.get("status") == "done"
    result = ctx.seal({"purpose": "knowledge_publication_completion", "protocol_version": manifest["protocol_version"],
        "publication_ref": manifest_ref(manifest["operation_id"]), "publication_digest": manifest["digest"],
        "content_digest": manifest["content_digest"], "published": True, "batch_complete": complete,
        "phase": ("recorded" if manifest["batch_kind"] == "record_only" else "completed") if complete
                  else ("cleanup_pending" if retrieval.get("complete") is True else "finalization_pending"),
        "data": copy.deepcopy(data), "retrieval": copy.deepcopy(retrieval), "cleanup": cleanup_result},
        "artifact_manifest")
    with writer_lock(ctx):
        current = read_completion(ctx, manifest)
        if (current["digest"] if current else None) != expected_digest:
            raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Completion changed before CAS", ref, blocked=True)
        write_bytes(ctx.root, ref, canonical(result), immutable=False)
    return result


def cleanup(ctx, manifest, completion):
    """Remove only exact registered files; never enumerate an operation tree."""
    if completion.get("batch_complete") is True:
        return completion
    if completion.get("retrieval", {}).get("complete") is not True:
        raise NodeError("PUBLICATION_NOT_FINALIZED", "Retrieval must finish before cleanup", blocked=True)
    current = read_completion(ctx, manifest)
    if current is None or current["digest"] != completion["digest"]:
        raise NodeError("PUBLICATION_COMPLETION_CHANGED", "Completion changed before cleanup", blocked=True)
    for row in manifest["files"]:
        if row["path"].startswith(("logs/evidence/published/", "logs/ingest/")):
            actual = _file(ctx, row["path"], kind=row["kind"])
            if actual != row:
                raise NodeError("PUBLICATION_BYTES_CHANGED", "Formal recovery object changed", row["path"])
    deleted, retained, failed = [], [], []
    owned = _owned(ctx.root, completion["cleanup"]["owned"])
    approved = safe(ctx.root, ".build/operations/" + ctx.operation).resolve()
    for row in sorted(owned, key=lambda row: (row["path"].endswith("/owned-files.json"), row["path"])):
        ref = row["path"]
        if row["owner_operation_id"] != ctx.operation:
            retained.append({"path": ref, "reason": "borrowed_operation"})
            continue
        if row.get("retain_reason"):
            retained.append({"path": ref, "reason": row["retain_reason"]})
            continue
        try:
            path = safe(ctx.root, ref, [".build/operations/" + ctx.operation])
            resolved = path.resolve()
            if resolved == approved or not resolved.is_relative_to(approved):
                raise NodeError("UNSAFE_CLEANUP_PATH", "Cleanup escaped the approved operation", ref)
            if path.exists():
                if not path.is_file():
                    raise NodeError("UNSAFE_CLEANUP_PATH", "Cleanup target is not a regular file", ref)
                raw = fixed_bytes(ctx.root, ref)
                if sha(raw) != row["sha256"] or len(raw) != row["bytes"]:
                    raise NodeError("CLEANUP_INPUT_CHANGED", "Owned file bytes changed before cleanup", ref)
                # Recheck the absolute nonlinked path immediately before deleting
                # one file. No computed directory is recursively removed.
                if safe(ctx.root, ref).resolve() != resolved:
                    raise NodeError("UNSAFE_CLEANUP_PATH", "Cleanup path changed", ref)
                path.unlink()
            deleted.append(ref)
        except (OSError, ValueError) as exc:
            failed.append({"path": ref, "reason": str(exc)})
    outcome = {"status": "cleanup_pending" if failed else "done", "owned": owned,
               "deleted": deleted, "retained": retained, "failed": failed}
    return write_completion(ctx, manifest, data=completion["data"], retrieval=completion["retrieval"],
                            owned_files=owned, expected_digest=completion["digest"], cleanup_result=outcome)
