"""Read local execution facts; no repair, activation or upstream approval tickets."""

import base64
import json
from pathlib import PurePosixPath

from support import NodeError, digest, fixed_bytes, safe, sha

def observation_only(scan):
    """A complete no-op inventory is an observation, not a new work obligation."""
    current = scan.get("current_context", {})
    return (scan.get("complete") is True
            and all(unit.get("change") == "unchanged" for unit in scan.get("units", []))
            and not current.get("affected_claims") and not current.get("gaps")
            and current.get("complete", True) is True)


def read_saved(ctx, ref):
    value = json.loads(fixed_bytes(ctx.root, ref, [".build/operations", "logs", "artifacts/indexes"]))
    if not isinstance(value, dict):
        raise NodeError("INVALID_SAVED_RECORD", "Saved fact must be a JSON object", ref)
    if value.get("record_kind"):
        ctx.modules["records"].verify(value)
        ctx.modules["validation"].validate_shape(value["record_kind"], value, ctx.rules)
    else:
        ctx.modules["checks"].validate_report(value)
    return value


def paths(ctx, pattern):
    return [p.relative_to(ctx.root).as_posix() for p in sorted(ctx.root.glob(pattern))
            if safe(ctx.root, p.relative_to(ctx.root).as_posix()).is_file()]


def material_refs(ctx, operation):
    """Discover immutable material versions without inventing a latest version."""
    return paths(ctx, f".build/operations/{operation}/material.json") + paths(
        ctx, f".build/operations/{operation}/materials/*/material.json")


def adopted_successor(ctx, operation, view_ref=None, view_digest=None, scan_digest=None):
    """Find a finalized explicit descendant; missing private ancestry is unknown."""
    if not hasattr(ctx, "_adoption_records"):
        ctx._adoption_records = []
        for pattern in ("logs/ingest/*.yaml", "logs/ingest/*.yml", "logs/ingest/*.json"):
            for ref in paths(ctx, pattern):
                try:
                    value = read_saved(ctx, ref)
                    ctx.modules["records"].validate_ingest_record(value, rules=ctx.rules, require_final=True)
                    expected = "recorded" if value["batch_kind"] == "record_only" else "applied"
                    stage = value.get("progress", {}).get("apply", {})
                    finished = all((item["progress"].get("status") if isinstance(item["progress"], dict) else item["progress"])
                                   in {"completed", "skipped", "withdrawn"} for item in value["dispositions"])
                    if (finished and stage.get("operation_id") == value["operation_id"] and stage.get("status") == expected):
                        ctx._adoption_records.append((ref, value))
                except (OSError, ValueError, KeyError):
                    continue
    for ref, record in ctx._adoption_records:
        if record["operation_id"] == operation:
            continue
        found = (not view_ref and scan_digest is not None and record.get("origin_scan_operation_id") == operation
                 and record.get("scan_digest") == scan_digest)
        current, expected_digest, visited = record.get("previous_view_ref"), record.get("previous_view_digest"), set()
        while view_ref and current and current not in visited:
            if current == view_ref:
                found = expected_digest == view_digest
                break
            visited.add(current)
            try:
                previous = read_saved(ctx, current)
                if previous.get("record_kind") != "final_view" or previous["digest"] != expected_digest:
                    break
                current, expected_digest = previous.get("previous_view_ref"), previous.get("previous_view_digest")
            except (OSError, ValueError, KeyError):
                break
        if found:
            return {"operation_id": record["operation_id"], "record_ref": ref, "record_digest": record["digest"]}
    return None


def catalog(ctx):
    if hasattr(ctx, "_status_catalog"):
        return ctx._status_catalog
    result = {"generations": [], "regressions": [], "activations": [], "gaps": []}
    for key, pattern in (("generations", "artifacts/indexes/local/gen-*/manifest.json"),
                         ("regressions", ".build/operations/*/regression/*.json"),
                         ("activations", ".build/operations/*/activation/*.json")):
        for ref in paths(ctx, pattern):
            try:
                value = read_saved(ctx, ref)
                if value.get("rules_digest") != ctx.args.rules_digest:
                    raise NodeError("STALE_RULES", "Saved fact uses different rules", ref)
                result[key].append((ref, value))
            except (OSError, ValueError, KeyError) as exc:
                result["gaps"].append({"ref": ref, "reason": str(exc)})
    ctx._status_catalog = result
    return result


def catalog_gap(ctx, ref, error):
    gap = {"ref": ref, "reason": str(error)}
    values = catalog(ctx)["gaps"]
    if gap not in values:
        values.append(gap)


def generation_observation(ctx, ref, manifest):
    """Inspect saved build facts; exact database verification belongs to P7."""
    cache = catalog(ctx).setdefault("observed_generations", {})
    if ref in cache:
        return cache[ref]
    try:
        prefix = "artifacts/indexes/local/" + manifest["generation_id"]
        if ref != prefix + "/manifest.json" or manifest.get("channel") != "local":
            raise ValueError("Generation identity/path differs")
        if not safe(ctx.root, manifest["database_ref"], [prefix]).is_file():
            raise ValueError("Saved generation database is unavailable")
        receipt = manifest.get("index_verification", {})
        if receipt.get("complete") is not True or receipt.get("rules_digest") != ctx.args.rules_digest:
            raise ValueError("Saved build lacks its complete fixed verification result")
        cache[ref] = True
    except (OSError, ValueError, KeyError):
        cache[ref] = False
    return cache[ref]


def current_baseline(ctx):
    if hasattr(ctx, "_status_baseline"):
        return ctx._status_baseline
    refs = paths(ctx, "knowledge/**/*.md") + ["governance/sources.lock.yaml"]
    ctx._status_baseline = {ref: sha(fixed_bytes(ctx.root, ref)) for ref in sorted(refs)}
    return ctx._status_baseline


def view_targets(ctx, view):
    targets = {}
    for row in view.get("writes", []):
        path = row["path"]
        if path.startswith("knowledge/") and PurePosixPath(path).name not in {"index.md", "AGENTS.md"}:
            raw = base64.b64decode(row["bytes_b64"], validate=True)
            card = ctx.modules["knowledge"].decode_card(raw, path, ctx.rules)
            targets[card["metadata"]["id"]] = card["metadata"]["lifecycle"]
    return targets


def report_matches(ctx, report, view):
    if report.get("record_kind") != "query_regression" or report.get("view_digest") != view["digest"]:
        return False
    cases = report.get("cases", [])
    outcomes = report.get("outcomes", [])
    if (not cases or report.get("cases_digest") != digest(cases) or report.get("passed") is not True
            or report.get("index_verified") is not True
            or len(outcomes) != len(cases) or {r.get("case_id") for r in outcomes} != {c.get("id") for c in cases}
            or not all(row.get("passed") is True for row in outcomes)):
        return False
    if view.get("target_queries"):
        return cases == view["target_queries"]
    # Legacy views lack frozen queries. An explicitly view-bound actual report
    # must at least exercise every changed target, rather than arbitrary cases.
    targets = view_targets(ctx, view)
    return bool(targets) and all(any((identity in case.get("forbidden", []) and case.get("purpose", "current") == "current")
                   or (identity in case.get("required", []) and case.get("purpose") == "historical")
                   for case in cases) if lifecycle == "deprecated" else
               any(identity in case.get("required", []) + case.get("expected_order", []) for case in cases)
               for identity, lifecycle in targets.items())


def covers_view(files, view):
    return (all(files.get(row["path"]) == row["final_digest"] for row in view.get("writes", [])
                if row["path"].startswith("knowledge/") or row["path"] == "governance/sources.lock.yaml")
            and all((row["path"] if isinstance(row, dict) else row) not in files
                    for row in view.get("deletes", [])))


def pointer_matches(ctx, manifest_ref, manifest, observation, execution_binding):
    """Require the real activation to bind this exact persisted query execution."""
    pointer = observation.get("active_pointer", {})
    try:
        if ("expected_active" not in manifest or "expected_active" not in observation
                or not isinstance(execution_binding, dict)):
            return False
        ctx.modules["records"].verify(pointer)
        actual = ctx.modules["index_runtime"].activated_pointer(
            ctx, "local", manifest_ref, manifest["digest"], manifest["expected_active"],
            execution_binding=execution_binding)
        return (observation.get("purpose") == "index_activation_observation"
                and observation.get("generation_ref") == manifest_ref
                and observation.get("manifest_digest") == manifest["digest"]
                and observation["expected_active"] == manifest["expected_active"]
                and observation.get("active_digest") == pointer["digest"]
                and pointer.get("rules_digest") == ctx.args.rules_digest
                and pointer.get("channel") == "local"
                and pointer.get("generation_id") == manifest["generation_id"]
                and pointer.get("generation_ref") == manifest_ref
                and pointer.get("manifest_digest") == manifest["digest"]
                and actual is not None and actual == pointer)
    except (OSError, ValueError, KeyError):
        return False


def finalization(ctx, journal, view):
    result = {"status": "unknown", "next_action": "inspect_finalization"}
    if journal.get("status") == "rolled_back":
        return {"status": "not_applicable", "scope": "rolled_back", "next_action": "prepare_material",
                "reason": "Original transaction is terminal; a requested retry needs new materials and a new operation"}
    if journal.get("status") != "committed":
        return {"status": "pending", "next_action": "recover_transaction"}
    if journal.get("batch_kind") == "record_only":
        return {"status": "complete", "next_action": None, "scope": "record_only"}
    result.update(view_ref=journal.get("view_ref"), view_digest=journal.get("view_digest"))
    if journal.get("rules_digest") != ctx.args.rules_digest or view is None:
        return {**result, "next_action": "inspect_context", "reason": "Missing exact view or current rules binding"}
    if view["digest"] != journal.get("view_digest"):
        return {**result, "reason": "Applied view binding differs"}
    data = catalog(ctx)
    generations = dict(data["generations"])
    active_ref = "artifacts/indexes/local/active.json"
    try:
        active = read_saved(ctx, active_ref) if safe(ctx.root, active_ref).is_file() else None
        if active and active.get("rules_digest") != ctx.args.rules_digest:
            active = None
    except (OSError, ValueError, KeyError):
        active = None
    # A saved successful activation observation preserves historical completion
    # when a later generation is activated. The report itself precedes activation.
    for report_ref, report in data["regressions"]:
        manifest_ref = report.get("generation_ref")
        manifest = generations.get(manifest_ref)
        if (manifest is None or not covers_view(manifest.get("file_baseline", {}), view)
                or not report_matches(ctx, report, view) or not generation_observation(ctx, manifest_ref, manifest)):
            continue
        try:
            # Independent legacy regressions may belong to another operation and
            # omit an apply-result reference. Preserve their actual binding; if
            # supplied, the result must be this transaction's real committed one.
            applied_ref = report.get("apply_result_ref")
            applied = read_saved(ctx, journal["result_ref"]) if applied_ref else None
            if applied_ref and (applied_ref != journal["result_ref"] or applied.get("status") != "committed"
                                or applied.get("view_digest") != view["digest"]):
                continue
            report_ctx = ctx.modules["runtime"].fork_context(ctx, operation_id=report["operation_id"])
            binding = ctx.modules["query_regression"].persisted_binding(
                report_ctx, manifest_ref, manifest, report_ref, view_ref=journal["view_ref"], view=view,
                apply_result_ref=applied_ref, applied=applied, cases=view.get("target_queries") or report["cases"])
        except (OSError, ValueError, KeyError):
            continue
        observed = next((ref for ref, value in data["activations"]
                         if pointer_matches(ctx, manifest_ref, manifest, value, binding)), None)
        currently_active = bool(active and pointer_matches(ctx, manifest_ref, manifest, {
            "purpose": "index_activation_observation", "generation_ref": manifest_ref,
            "manifest_digest": manifest["digest"], "expected_active": manifest.get("expected_active"),
            "active_digest": active["digest"], "active_pointer": active}, binding))
        if observed or currently_active:
            return {**result, "status": "complete", "next_action": None, "generation_ref": manifest_ref,
                    "regression_ref": report_ref, "activation_ref": observed or active_ref,
                    "currently_active": currently_active, "verification": "saved_facts_only", "index_health": "not_examined"}
    baseline = current_baseline(ctx)
    if not covers_view(baseline, view):
        return {**result, "next_action": "inspect_context", "reason": "Applied content changed; do not replay the old view or CAS baseline"}
    epoch_ref = "logs/events/state.json"
    epoch = read_saved(ctx, epoch_ref).get("validity_epoch") if safe(ctx.root, epoch_ref).is_file() else 0
    candidates = [(ref, value) for ref, value in data["generations"]
                  if value.get("file_baseline") == baseline and value.get("validity_epoch") == epoch
                  and generation_observation(ctx, ref, value)]
    if not candidates:
        return {**result, "status": "pending", "next_action": "rebuild_index",
                "reason": "No saved verified-build generation for the observed files and validity epoch"}
    # Only reuse a uniquely identified candidate and its original CAS baseline.
    if len(candidates) != 1:
        return {**result, "reason": "Several candidate generations need explicit selection"}
    ref, manifest = candidates[0]
    result["generation_ref"] = ref
    if "expected_active" not in manifest:
        return {**result, "reason": "Original expected_active was not saved; do not invent a CAS baseline"}
    result["expected_active"] = manifest["expected_active"]
    if active and active.get("generation_ref") == ref:
        return {**result, "reason": "Already active, but no exact batch regression is bound; inspect rather than replay activation"}
    return {**result, "status": "pending", "next_action": "resume_queries"}


def batch_finalization(ctx, values):
    """Locate a new P7 stop from durable local facts, without re-executing it."""
    intent = values.get("batch_intent")
    built = values.get("batch_build")
    completed = values.get("batch_complete")
    journal = values.get("transaction")
    result = {"status": "unknown", "next_action": "inspect_finalization",
              "resume_action": "hs-knowledge-apply.batch", "verification": "saved_facts_only",
              "index_health": "not_examined"}
    if journal and journal.get("status") == "rolled_back":
        return {**result, "status": "not_applicable", "scope": "rolled_back", "next_action": "prepare_material",
                "reason": "A rolled-back transaction is terminal; requested content needs a new operation"}
    if intent is None or intent.get("purpose") != "batch_execution_intent":
        return {**result, "reason": "A local batch substep has no matching durable batch intent"}
    result.update(view_ref=intent.get("view_ref"), view_digest=intent.get("view_digest"))
    if intent.get("rules_digest") != ctx.args.rules_digest:
        return {**result, "next_action": "inspect_context", "reason": "Recover historical work with its original paired rules"}
    if journal and journal.get("view_digest") != intent.get("view_digest"):
        return {**result, "reason": "Transaction differs from the saved batch intent"}
    if completed is not None:
        data = completed.get("data", {})
        if (completed.get("purpose") != "batch_completion" or completed.get("view_digest") != intent.get("view_digest")
                or completed.get("rules_digest") != ctx.args.rules_digest or completed.get("phase") not in {"completed", "recorded"}
                or data.get("batch_complete") is not True or data.get("transaction_status") != "committed"):
            return {**result, "reason": "Saved batch completion lacks its exact terminal binding"}
        if journal and journal.get("status") != "committed":
            return {**result, "next_action": "recover_transaction", "reason": "Completion conflicts with the actual local writer journal"}
        applied = values.get("apply")
        if applied and data.get("apply_result_digest") != applied["digest"]:
            return {**result, "reason": "Completion differs from the local apply result"}
        if completed["phase"] == "completed" and (not data.get("generation_ref") or data.get("activated") is not True
                                                     or not data.get("report_ref") or not data.get("activation_observation_ref")):
            return {**result, "reason": "Content completion lacks its saved index/query/activation references"}
        if built and (built.get("purpose") != "batch_index" or built.get("view_digest") != intent.get("view_digest")
                      or built.get("generation_ref") != data.get("generation_ref")
                      or built.get("apply_result_digest") != data.get("apply_result_digest")
                      or "expected_active" not in built or built["expected_active"] != data.get("expected_active")):
            return {**result, "reason": "Completion differs from its saved index or original CAS binding"}
        if completed["phase"] == "completed":
            try:
                view = values.get("view")
                report = read_saved(ctx, data["report_ref"])
                manifest = read_saved(ctx, data["generation_ref"])
                activation = read_saved(ctx, data["activation_observation_ref"])
                if (view is None or journal is None or journal.get("status") != "committed"
                        or applied is None or applied.get("status") != "committed"
                        or applied.get("view_digest") != view["digest"]
                        or data.get("apply_result_ref") != journal["result_ref"]
                        or built is None or built.get("apply_result_ref") != journal["result_ref"]
                        or built.get("expected_active") != manifest.get("expected_active")
                        or not report_matches(ctx, report, view)
                        or report.get("generation_ref") != data["generation_ref"]
                        or not generation_observation(ctx, data["generation_ref"], manifest)):
                    raise ValueError("Saved completion references do not bind the frozen batch queries and activation")
                report_ctx = ctx.modules["runtime"].fork_context(ctx, operation_id=intent["operation_id"])
                binding = ctx.modules["query_regression"].persisted_binding(
                    report_ctx, data["generation_ref"], manifest, data["report_ref"],
                    view_ref=intent["view_ref"], view=view, apply_result_ref=journal["result_ref"],
                    applied=applied, cases=view.get("target_queries"))
                if not pointer_matches(ctx, data["generation_ref"], manifest, activation, binding):
                    raise ValueError("Real activation does not bind this exact batch query execution")
            except (OSError, ValueError, KeyError) as exc:
                return {**result, "reason": str(exc)}
        return {**result, "status": "complete", "next_action": None,
                "scope": "record_only" if completed["phase"] == "recorded" else "content",
                **{key: data[key] for key in ("generation_ref", "expected_active", "report_ref", "activation_observation_ref") if key in data}}
    if not journal:
        return {**result, "status": "pending", "next_action": "resume_batch", "reason": "Batch intent is saved before any local transaction"}
    if journal.get("status") != "committed":
        return {**result, "status": "pending", "next_action": "recover_transaction"}
    if journal.get("batch_kind") == "record_only":
        return {**result, "status": "pending", "scope": "record_only", "next_action": "resume_batch",
                "reason": "The record is committed; rebuild only the missing terminal batch result"}
    if not built:
        return {**result, "status": "pending", "next_action": "rebuild_index"}
    if (built.get("purpose") != "batch_index" or built.get("view_digest") != intent.get("view_digest")
            or built.get("rules_digest") != ctx.args.rules_digest or "expected_active" not in built):
        return {**result, "reason": "Saved index stop lacks its original view or CAS binding"}
    applied = values.get("apply")
    if applied and built.get("apply_result_digest") != applied["digest"]:
        return {**result, "reason": "Saved index stop differs from the local apply result"}
    return {**result, "status": "pending", "next_action": "resume_queries",
            "generation_ref": built.get("generation_ref"), "expected_active": built["expected_active"]}
