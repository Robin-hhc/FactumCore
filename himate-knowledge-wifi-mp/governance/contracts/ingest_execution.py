"""P7 business execution over exact bytes, with independently durable substeps."""

import base64
import copy

from .runtime import NodeError, canonical, digest, fixed_bytes, fork_context, safe, sha
from . import index_runtime, input_snapshot, publication, query_regression, submission


def checked_view(ctx, request):
    op = request.get("operation_id")
    if op != ctx.operation:
        raise NodeError("OPERATION_CHANGED", "Request and operation differ")
    ref = request.get("view_ref")
    safe(ctx.root, ref, [ctx.base])
    view = ctx.record(ref, "final_view")
    if view.get("operation_id") != op:
        raise NodeError("BATCH_VIEW_CHANGED", "Final view belongs to another operation")
    paths = set()
    for row in view.get("writes", []) + view.get("deletes", []):
        path = row.get("path")
        safe(ctx.root, path, ["knowledge", "governance/sources.lock.yaml", "index.md"])
        if path.casefold() in paths:
            raise NodeError("DUPLICATE_TARGET", "Duplicate write/delete path", path)
        paths.add(path.casefold())
        old = row.get("expected_old_digest")
        if old is not None and (not isinstance(old, str) or len(old) != 64
                                or any(char not in "0123456789abcdef" for char in old)):
            raise NodeError("INVALID_OLD_DIGEST", "Expected old digest is invalid", path)
    if any(row["path"] == "governance/sources.lock.yaml" for row in view.get("deletes", [])):
        raise NodeError("INVALID_TARGET", "Source registry cannot be deleted")
    for row in view.get("writes", []):
        try:
            raw = base64.b64decode(row["bytes_b64"], validate=True)
        except (ValueError, KeyError) as exc:
            raise NodeError("INVALID_FINAL_BYTES", "Final bytes are invalid", row.get("path", "")) from exc
        if sha(raw) != row.get("final_digest"):
            raise NodeError("FINAL_BYTES_CHANGED", "Final bytes differ from their digest", row["path"])
    if not view.get("writes") and not view.get("deletes"):
        if not (view.get("review_mode") == "record_only" and view.get("batch_kind") == "record_only"):
            raise NodeError("EMPTY_CONTENT_BATCH", "Empty writes require an explicit record-only view")
    return view


def _saved(ctx, ref, kind=None):
    return ctx.record(ref, kind) if safe(ctx.root, ref).is_file() else None


def _stage(ctx, ref, fields):
    record = ctx.seal(fields, "artifact_manifest")
    ctx.save(ref, record)
    return record


def _postwrite(ctx, prewrite):
    observed = input_snapshot.capture_inputs(ctx, stage="postwrite")
    # The formal tree now includes this transaction. The chosen immutable
    # materials/current code remain the inputs actually adopted before writing.
    if prewrite is not None:
        for key in ("business_records", "adopted_objects", "current_files"):
            observed[key] = copy.deepcopy(prewrite[key])
    observed["snapshot_digest"] = digest({key: value for key, value in observed.items()
                                         if key != "snapshot_digest"})
    result = input_snapshot.compare_inputs(ctx, observed, stage="postwrite")
    if not result["unchanged"]:
        raise NodeError("BATCH_INPUT_CHANGED", "Adopted inputs changed after local application", blocked=True)
    return observed


def compare_view_inputs(ctx, view, journal=None):
    """Allow only this batch's exact installations when comparing its old formal tree."""
    snapshot = view.get("input_snapshot")
    if snapshot is None and view.get("batch_kind") == "record_only":
        return
    if snapshot is None:
        raise NodeError("INPUT_SNAPSHOT_REQUIRED", "Batch execution requires its adopted inputs")
    comparison = input_snapshot.compare_inputs(ctx, snapshot)
    installed = {entry["path"]: entry["new_digest"] for entry in (journal or {}).get("entries", [])}
    for change in comparison["changes"]:
        path, actual = change.get("path"), change.get("actual")
        actual_digest = actual.get("sha256") if isinstance(actual, dict) else None
        if change["group"] == "formal_files" and path in installed and actual_digest == installed[path]:
            continue
        raise NodeError("BATCH_INPUT_CHANGED", "Batch inputs changed", path or change["group"], blocked=True)


def _committed(ctx, view, journal):
    if journal.get("view_digest") != view["digest"] or journal.get("operation_id") != ctx.operation:
        raise NodeError("BATCH_VIEW_CHANGED", "Committed transaction binds another view")
    expected = {row["path"]: {"path": row["path"], "old_digest": row["expected_old_digest"],
                              "new_digest": row.get("final_digest"), "bytes_b64": row.get("bytes_b64")}
                for row in view.get("writes", []) + view.get("deletes", [])}
    if journal.get("ingest_record_ref"):
        if journal["ingest_record_ref"] != ctx.request.get("ingest_record_ref"):
            raise NodeError("JOURNAL_RECORD_CHANGED", "Committed transaction names another processing record")
        pending = ctx.record(journal["ingest_record_ref"], "ingest_record")
        if pending["digest"] != journal.get("ingest_record_digest"):
            raise NodeError("JOURNAL_RECORD_CHANGED", "Processing-record input changed")
        final = copy.deepcopy(pending)
        final["progress"] = {**pending.get("progress", {}), "apply": {
            "status": "recorded" if pending["batch_kind"] == "record_only" else "applied",
            "operation_id": ctx.operation, "view_digest": view["digest"]}}
        final["status"] = "recorded" if pending["batch_kind"] == "record_only" else "applied"
        final.pop("acceptance", None)
        raw = canonical(ctx.modules["records"].seal(final)) + b"\n"
        expected[pending["target_path"]] = {"path": pending["target_path"],
            "old_digest": pending.get("expected_old_digest"), "new_digest": sha(raw),
            "bytes_b64": base64.b64encode(raw).decode()}
    entries = journal.get("entries", [])
    if (len(entries) != len(expected)
            or any({key: row.get(key) for key in ("path", "old_digest", "new_digest", "bytes_b64")}
                   != expected.get(row.get("path")) for row in entries)
            or len({row["path"] for row in entries}) != len(entries)):
        raise NodeError("JOURNAL_VIEW_MISMATCH", "Committed write set differs from the exact candidate bytes")
    compare_view_inputs(ctx, view, journal)
    for row in journal["entries"]:
        path = safe(ctx.root, row["path"], ["knowledge", "governance/sources.lock.yaml", "index.md", "logs/ingest"])
        actual = sha(path.read_bytes()) if path.exists() else None
        if actual != row["new_digest"]:
            raise NodeError("APPLIED_BYTES_CHANGED", "The applied batch bytes changed", row["path"], blocked=True)
    record = ctx.record(journal["result_ref"], "apply_result")
    if (record.get("view_digest") != view["digest"] or record.get("status") != "committed"
            or record.get("operation_id") != ctx.operation
            or record.get("writes") != [row["path"] for row in entries if row["new_digest"] is not None]
            or record.get("deletes") != [row["path"] for row in entries if row["new_digest"] is None]):
        raise NodeError("APPLY_RESULT_CHANGED", "Apply result differs from its committed transaction")
    return {"apply_result_ref": journal["result_ref"], "apply_result_digest": record["digest"],
            "transaction_status": "committed", "phase": "committed",
            "batch_kind": journal.get("batch_kind", "content")}


def _activation_observation(ctx, manifest, expected_active, execution_binding):
    # Saved .build JSON is an observation, not activation authority. Recreate
    # it only from the real current pointer or its linked immutable history.
    pointer = index_runtime.activated_pointer(ctx, manifest["channel"], manifest["generation_ref"],
                                               manifest["manifest_digest"], expected_active,
                                               execution_binding=execution_binding)
    if pointer is None:
        return None
    observation = ctx.seal({"purpose": "index_activation_observation", **manifest,
                            "expected_active": expected_active,
                            "active_digest": pointer["digest"], "active_pointer": pointer}, "artifact_manifest")
    ref = ctx.base + "/activation/" + observation["digest"] + ".json"
    ctx.save(ref, observation)
    return ref


def _journal_ref(ctx):
    current = ctx.base + "/transaction/journal.json"
    legacy = "logs/operations/" + ctx.operation + "/journal.json"
    if safe(ctx.root, current).exists() and safe(ctx.root, legacy).exists():
        raise NodeError("TRANSACTION_CONFLICT", "Both current and legacy journals exist for this operation")
    return legacy if safe(ctx.root, legacy).exists() else current


def _publication_result(ctx, manifest, completion):
    data = {**completion.get("data", {}), "publication_ref": publication.manifest_ref(ctx.operation),
            "publication_digest": manifest["digest"], "content_digest": manifest["content_digest"],
            "completion_ref": publication.completion_ref(ctx.operation), "published": True,
            "batch_complete": completion["batch_complete"], "cleanup": completion["cleanup"],
            "batch_kind": manifest["batch_kind"], "apply_result_ref": manifest.get("apply_result_ref"),
            "apply_result_digest": (manifest.get("apply_result") or {}).get("digest")}
    if completion["batch_complete"]:
        data["commit_files"] = sorted({row["path"] for row in manifest["files"]}
            | {row["path"] for row in completion.get("retrieval", {}).get("files", [])}
            | {row["path"] for row in manifest.get("deletes", [])}
            | {publication.manifest_ref(ctx.operation), publication.completion_ref(ctx.operation)})
    return data, completion["phase"]


def _publication_intent(ctx, view):
    """Freeze the first actual activation baseline before any content writes."""
    request = ctx.request
    keys = ("code_contexts", "code_evidence", "knowledge_commit", "publication_receipt_ref")
    record_ref = request.get("ingest_record_ref")
    fields = {"purpose": "batch_execution_intent", "protocol_version": "1.0",
              "view_ref": request["view_ref"], "view_digest": view["digest"],
              "ingest_record_ref": record_ref,
              "ingest_record_digest": ctx.record(record_ref, "ingest_record")["digest"] if record_ref else None,
              "cases": view.get("target_queries"), "channel": request.get("channel", "local"),
              "index_inputs": {key: copy.deepcopy(request[key]) for key in keys if key in request}}
    ref = ctx.base + "/batch-intent.json"
    previous = _saved(ctx, ref, "artifact_manifest")
    if previous is not None:
        if any(previous.get(key) != value for key, value in fields.items()):
            raise NodeError("BATCH_INPUT_CHANGED", "The original batch intent freezes different inputs")
        baseline = previous["expected_active"]
        if "expected_active" in request and request["expected_active"] != baseline:
            raise NodeError("ACTIVE_CHANGED", "Request replaces the first batch activation baseline", blocked=True)
    else:
        pointer = index_runtime.active(ctx, fields["channel"])
        baseline = request.get("expected_active", pointer["digest"] if pointer else None)
        if baseline is not None and (not isinstance(baseline, str) or len(baseline) != 64
                or any(value not in "0123456789abcdef" for value in baseline)):
            raise NodeError("INVALID_ACTIVE_BASELINE", "Expected active must be null or an exact pointer digest")
        previous = _stage(ctx, ref, {**fields, "expected_active": baseline,
                                    "baseline_was_explicit": "expected_active" in request})
    return {**fields["index_inputs"], "channel": fields["channel"], "expected_active": baseline}


def _publish_batch(ctx, transact, view=None):
    """New frozen publication path; legacy views keep their existing execution."""
    ref = publication.manifest_ref(ctx.operation)
    existing = safe(ctx.root, ref).is_file()
    completion = None
    if existing:
        manifest = publication.read_manifest(ctx, ref)
        if (ctx.request.get("publication_ref", ref) != ref
                or (ctx.request.get("view_ref") and ctx.request["view_ref"] != manifest["trace"].get("view_ref"))):
            raise NodeError("BATCH_INPUT_CHANGED", "Operation already published another checked view")
        frozen_inputs = manifest.get("index_inputs", {})
        if "expected_active" in ctx.request and ctx.request["expected_active"] != frozen_inputs.get("expected_active"):
            raise NodeError("ACTIVE_CHANGED", "Request replaces the publication's original active baseline", blocked=True)
        completion = publication.read_completion(ctx, manifest)
        if completion and (completion["batch_complete"] or completion["retrieval"].get("complete") is True):
            if not completion["batch_complete"]:
                completion = publication.cleanup(ctx, manifest, completion)
            return _publication_result(ctx, manifest, completion)
        business_view = publication.published_view(manifest)
    else:
        view = view or checked_view(ctx, ctx.request)
        if view.get("v3_required") and not ctx.request.get("ingest_record_ref"):
            raise NodeError("INGEST_RECORD_REQUIRED", "Content and processing record must publish together")
        plan = publication.validate_plan(ctx, view)
        if view.get("batch_kind", "content") != "record_only":
            query_regression._cases({"cases": view.get("target_queries")}, view)
        if "cases" in ctx.request and ctx.request["cases"] != view.get("target_queries"):
            raise NodeError("BATCH_CASES_CHANGED", "Batch cannot replace the frozen query cases")
        frozen_inputs = _publication_intent(ctx, view)
        journal = _saved(ctx, _journal_ref(ctx), "transaction_journal")
        if journal and journal.get("status") == "committed":
            if journal.get("view_digest") != view["digest"]:
                raise NodeError("BATCH_VIEW_CHANGED", "Committed transaction describes another view")
            applied = ctx.record(journal["result_ref"], "apply_result")
        else:
            result = transact("resume" if journal and journal.get("status") != "rolled_back" else "run")
            applied = ctx.record(result["apply_result_ref"], "apply_result")
            journal = ctx.record(_journal_ref(ctx), "transaction_journal")
        if (journal.get("status") != "committed" or applied.get("status") != "committed"
                or applied.get("view_digest") != view["digest"]):
            raise NodeError("PUBLICATION_NOT_COMMITTED", "The actual content transaction is not committed")
        if journal.get("ingest_record_ref") != ctx.request.get("ingest_record_ref"):
            raise NodeError("INGEST_RECORD_CHANGED", "Transaction freezes another processing record")
        with index_runtime.writer(ctx):
            compare_view_inputs(ctx, view, journal)
            expected = publication.transaction_rows(ctx, view, plan) + view.get("deletes", [])
            if ({row["path"]: row.get("final_digest") for row in expected}
                    != {row["path"]: row["new_digest"] for row in journal["entries"]}):
                raise NodeError("JOURNAL_VIEW_MISMATCH", "Committed transaction differs from frozen publication")
            for row in expected:
                path = safe(ctx.root, row["path"])
                actual = sha(fixed_bytes(ctx.root, row["path"])) if path.exists() else None
                if actual != row.get("final_digest"):
                    raise NodeError("PUBLICATION_BYTES_CHANGED", "Installed content changed before formal success", row["path"])
            # Verify the formal recovery closure before making success durable.
            # Re-capture it after record/events when preparing the index inputs.
            if view.get("input_snapshot"):
                input_snapshot.published_inputs(ctx, view["input_snapshot"], staged_objects=plan["staged_objects"])
            # Empty proposals can still resolve an existing mechanical block
            # after a real content revision; record-only is handled by the API.
            events = ctx.modules["maintenance"].publish_changes(ctx, plan["event_proposals"])
            processing = publication.publish_processing_record(ctx, view, ctx.request.get("ingest_record_ref"),
                expected_digest=journal.get("ingest_record_digest"))
            manifest = publication.publish_manifest(ctx, view, plan, processing_record=processing,
                event_refs=events.get("event_refs", []), applied=applied, index_inputs=frozen_inputs)
        business_view = publication.published_view(manifest)
    content = manifest["batch_kind"] != "record_only"
    if not content:
        finished = publication.write_completion(ctx, manifest, data={"transaction_status": "committed"},
            retrieval={"complete": True, "scope": "record_only"},
            owned_files=publication.owned_files(ctx, view), expected_digest=(completion or {}).get("digest"))
        finished = publication.cleanup(ctx, manifest, finished)
        return _publication_result(ctx, manifest, finished)
    cases = business_view.get("target_queries")
    if "cases" in ctx.request and ctx.request["cases"] != cases:
        raise NodeError("BATCH_CASES_CHANGED", "Batch cannot replace its published query cases")
    inputs = dict(manifest.get("index_inputs", {}))
    built_ref = ctx.base + "/batch-build.json"
    built = _saved(ctx, built_ref, "artifact_manifest")
    if built is None:
        request = {**inputs, "operation_id": ctx.operation, "publication_ref": ref}
        index_ctx = fork_context(ctx, request, action="build")
        indexed, _ = index_runtime.execute(index_ctx)
        observed = index_ctx.verified_generation
        built = _stage(ctx, built_ref, {"purpose": "batch_index", "publication_ref": ref,
            "publication_digest": manifest["digest"], "generation_ref": indexed["generation_ref"],
            "expected_active": indexed["expected_active"]})
    else:
        if built.get("publication_digest") != manifest["digest"]:
            raise NodeError("BATCH_BUILD_CHANGED", "Saved generation belongs to another publication")
        observed = index_runtime.verify_generation(ctx, built["generation_ref"])
    generation_ref, expected_active = built["generation_ref"], built["expected_active"]
    if "expected_active" in inputs and inputs["expected_active"] != expected_active:
        raise NodeError("ACTIVE_CHANGED", "Generation replaces the original publication baseline", blocked=True)
    request = {"operation_id": ctx.operation, "publication_ref": ref, "generation_ref": generation_ref,
               "expected_active": expected_active, "cases": cases}
    regression_ctx = fork_context(ctx, request, action="run")
    regression, _ = query_regression.execute(regression_ctx, verified_generation=observed, activate=False)
    if not regression["passed"]:
        return {**regression, "published": True, "batch_complete": False, "publication_ref": ref}, "needs_revision"
    execution = query_regression.reuse_regression(ctx, generation_ref, observed.manifest, regression_ctx.verified_regression)
    evidence = {"generation_ref": generation_ref, "manifest_digest": observed.manifest["digest"],
                "channel": observed.manifest["channel"]}
    observation_ref = _activation_observation(ctx, evidence, expected_active, execution)
    if observation_ref is None:
        activation, _ = index_runtime.execute(fork_context(ctx, request, action="activate"),
            verified_generation=observed, verified_regression=regression_ctx.verified_regression)
        observation_ref = activation["activation_observation_ref"]
    observation = ctx.record(observation_ref, "artifact_manifest")
    formal_observation_ref = "logs/publications/" + ctx.operation + "/activation/" + observation["digest"] + ".json"
    ctx.save(formal_observation_ref, observation)
    retrieval_files = []
    for path in (regression["report_ref"], formal_observation_ref):
        raw = fixed_bytes(ctx.root, path)
        retrieval_files.append({"path": path, "sha256": sha(raw), "bytes": len(raw), "kind": "retrieval_record"})
    # Completion persists the actual retrieval facts before any stage deletion.
    finished = publication.write_completion(ctx, manifest, data={**regression, "transaction_status": "committed",
        "generation_ref": generation_ref, "expected_active": expected_active, "activated": True,
        "activation_observation_ref": formal_observation_ref},
        retrieval={"complete": True, "generation_ref": generation_ref, "expected_active": expected_active,
                   "activation_observation": observation, "files": retrieval_files,
                   "regression": ctx.record(regression["report_ref"], "query_regression")},
        owned_files=publication.owned_files(ctx, view), expected_digest=(completion or {}).get("digest"))
    finished = publication.cleanup(ctx, manifest, finished)
    return _publication_result(ctx, manifest, finished)


def execute_batch(ctx, *, transact):
    """transact(action) invokes this package's transaction engine in-process."""
    request = ctx.request
    if request.get("channel", "local") not in ("local", "shared"):
        raise NodeError("INVALID_CHANNEL", "Choose local or shared index channel")
    if safe(ctx.root, publication.manifest_ref(ctx.operation)).is_file():
        return _publish_batch(ctx, transact)
    view = checked_view(ctx, request)
    if view.get("publication_plan"):
        return _publish_batch(ctx, transact, view)
    if view.get("v3_required") and not request.get("ingest_record_ref"):
        raise NodeError("INGEST_RECORD_REQUIRED", "The content and its processing record must be applied together")
    content = view.get("batch_kind", "content") != "record_only"
    cases = view.get("target_queries")
    if content:
        query_regression._cases({"cases": cases}, view)
        if "cases" in request and request["cases"] != cases:
            raise NodeError("BATCH_CASES_CHANGED", "Batch execution cannot replace the author's frozen queries")
        if not isinstance(view.get("input_snapshot"), dict):
            raise NodeError("INPUT_SNAPSHOT_REQUIRED", "Batch execution requires the adopted business inputs")
    intent_ref, build_ref, complete_ref = (
        ctx.base + "/batch-intent.json", ctx.base + "/batch-build.json", ctx.base + "/batch-complete.json")
    intent_fields = {"purpose": "batch_execution_intent", "view_ref": request["view_ref"],
                     "view_digest": view["digest"], "ingest_record_ref": request.get("ingest_record_ref"),
                     "cases": cases, "channel": request.get("channel", "local"),
                     "index_inputs": {key: request[key] for key in
                                      ("code_contexts", "code_evidence", "knowledge_commit", "publication_receipt_ref")
                                      if key in request},
                     **({"requested_expected_active": request["expected_active"]} if "expected_active" in request else {})}
    prior_intent = _saved(ctx, intent_ref, "artifact_manifest")
    if prior_intent and any(prior_intent.get(key) != value for key, value in intent_fields.items()):
        raise NodeError("BATCH_INPUT_CHANGED", "The same operation cannot execute a different batch")
    if prior_intent is None:
        prior_intent = _stage(ctx, intent_ref, intent_fields)
    explicit_baseline = "requested_expected_active" in prior_intent
    original_baseline = prior_intent.get("requested_expected_active")
    completed = _saved(ctx, complete_ref, "artifact_manifest")
    journal = _saved(ctx, _journal_ref(ctx), "transaction_journal")
    if completed is not None:
        if (not journal or journal.get("status") != "committed"
                or journal.get("view_digest") != view["digest"]
                or completed.get("view_digest") != view["digest"]
                or journal.get("result_ref") != completed.get("data", {}).get("apply_result_ref")):
            raise NodeError("BATCH_COMPLETION_CHANGED", "Completion does not describe the committed transaction")
        if content:
            built = _saved(ctx, build_ref, "artifact_manifest")
            if (not built or built.get("view_digest") != view["digest"]
                    or built.get("generation_ref") != completed.get("data", {}).get("generation_ref")):
                raise NodeError("BATCH_COMPLETION_CHANGED", "Completion does not bind the saved generation")
            manifest = ctx.record(built["generation_ref"], "index_manifest")
            applied_record = ctx.record(journal["result_ref"], "apply_result")
            if (built.get("apply_result_ref") != journal["result_ref"]
                    or built.get("apply_result_digest") != applied_record["digest"]
                    or applied_record.get("status") != "committed"
                    or applied_record.get("view_digest") != view["digest"]):
                raise NodeError("BATCH_COMPLETION_CHANGED", "Completion does not bind this actual apply result")
            binding = query_regression.persisted_binding(ctx, built["generation_ref"], manifest,
                completed.get("data", {}).get("report_ref"), view_ref=request["view_ref"], view=view,
                apply_result_ref=journal["result_ref"], applied=applied_record, cases=cases)
            if (built.get("expected_active") != manifest.get("expected_active")
                    or (explicit_baseline and built["expected_active"] != original_baseline)
                    or not index_runtime.activated_pointer(ctx, manifest["channel"], built["generation_ref"],
                                                           manifest["digest"], built["expected_active"],
                                                           execution_binding=binding)):
                raise NodeError("BATCH_COMPLETION_CHANGED", "Completion has no actual activation history", blocked=True)
        return completed["data"], completed["phase"]
    if journal and journal.get("status") == "committed":
        applied = _committed(ctx, view, journal)
    elif journal and journal.get("status") not in {"committed", "rolled_back"}:
        if journal.get("execution_checks") != "safety_only":
            raise NodeError("LEGACY_RECOVERY_REQUIRED", "Recover the old transaction with its matching entry before P7", blocked=True)
        applied = transact("resume")
    else:
        applied = transact("run")
    applied_ref = applied["apply_result_ref"]
    applied_record = ctx.record(applied_ref, "apply_result")
    if applied_record.get("view_digest") != view["digest"]:
        raise NodeError("BATCH_VIEW_CHANGED", "Committed transaction binds another view")
    result = {**applied, "batch_intent_ref": intent_ref, "batch_complete": False}
    if not content:
        ready = submission.publish_handoff(ctx, {**request, "apply_result_ref": applied_ref})
        data = {**result, "commit_files": ready["commit_files"], "batch_complete": True,
                "batch_completion_ref": complete_ref, "batch_kind": "record_only"}
        _stage(ctx, complete_ref, {"purpose": "batch_completion", "view_digest": view["digest"],
                                  "data": data, "phase": "recorded"})
        return data, "recorded"
    built = _saved(ctx, build_ref, "artifact_manifest")
    if built is None:
        postwrite = _postwrite(ctx, view["input_snapshot"])
        index_request = {**request, "operation_id": ctx.operation, "input_snapshot": postwrite}
        if explicit_baseline:
            index_request["expected_active"] = original_baseline
        index_ctx = fork_context(ctx, index_request, action="build")
        indexed, _ = index_runtime.execute(index_ctx)
        observed = index_ctx.verified_generation
        built = _stage(ctx, build_ref, {"purpose": "batch_index", "view_digest": view["digest"],
                                      "apply_result_ref": applied_ref, "apply_result_digest": applied_record["digest"],
                                      "generation_ref": indexed["generation_ref"],
                                      "expected_active": indexed["expected_active"]})
    else:
        if (built.get("view_digest") != view["digest"]
                or built.get("apply_result_digest") != applied_record["digest"]):
            raise NodeError("BATCH_BUILD_CHANGED", "Saved index belongs to a different applied batch")
        observed = index_runtime.verify_generation(ctx, built["generation_ref"])
    generation_ref, expected_active = built["generation_ref"], built["expected_active"]
    if explicit_baseline and expected_active != original_baseline:
        raise NodeError("ACTIVE_CHANGED", "Saved index replaces the batch intent's original active baseline", blocked=True)
    if "expected_active" in request and request["expected_active"] != expected_active:
        raise NodeError("ACTIVE_CHANGED", "Request replaces the batch's original active baseline", blocked=True)
    regression_request = {"operation_id": ctx.operation, "generation_ref": generation_ref,
                          "expected_active": expected_active, "cases": cases,
                          "view_ref": request["view_ref"], "apply_result_ref": applied_ref}
    regression_ctx = fork_context(ctx, regression_request, action="run")
    regression, _ = query_regression.execute(regression_ctx, verified_generation=observed, activate=False)
    result.update({**regression, "generation_ref": generation_ref, "expected_active": expected_active,
                   "batch_build_ref": build_ref})
    if not regression["passed"]:
        return result, "needs_revision"
    evidence = {"generation_ref": generation_ref, "manifest_digest": observed.manifest["digest"],
                "channel": observed.manifest["channel"]}
    execution = query_regression.reuse_regression(ctx, generation_ref, observed.manifest, regression_ctx.verified_regression)
    observation_ref = _activation_observation(ctx, evidence, expected_active, execution)
    if observation_ref is None:
        activated, _ = index_runtime.execute(fork_context(ctx, regression_request, action="activate"),
                                              verified_generation=observed,
                                              verified_regression=regression_ctx.verified_regression)
        observation_ref = activated["activation_observation_ref"]
    ready = submission.publish_handoff(ctx, {**request, "apply_result_ref": applied_ref})
    data = {**result, "activated": True, "activation_observation_ref": observation_ref,
            "batch_complete": True, "batch_completion_ref": complete_ref, "commit_files": ready["commit_files"]}
    _stage(ctx, complete_ref, {"purpose": "batch_completion", "view_digest": view["digest"],
                              "data": data, "phase": "completed"})
    return data, "completed"


def execute(ctx, *, transact=None):
    action = ctx.args.action
    if action == "batch":
        if transact is None:
            raise NodeError("TRANSACTION_ENGINE_REQUIRED", "Batch requires its own in-process transaction engine")
        return execute_batch(ctx, transact=transact)
    if action in {"index-build", "index-verify", "index-activate"}:
        return index_runtime.execute(fork_context(ctx, action=action.removeprefix("index-")))
    if action in {"regression", "regression-verify"}:
        return query_regression.execute(fork_context(ctx, action="verify" if action.endswith("-verify") else "run"))
    if action in {"prepare-submission", "verify-submission"}:
        function = submission.verify_submission if action == "verify-submission" else submission.publish_handoff
        data = function(ctx, ctx.request)
        phase = data.pop("phase")
        return data, phase
    raise NodeError("INVALID_ACTION", "Unknown P7 public action", action)
