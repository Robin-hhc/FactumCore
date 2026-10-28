"""Read local execution facts; no repair, activation or upstream approval tickets."""

import base64
import json
import sqlite3
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


def generation_integrity(ctx, ref, manifest):
    """Reuse the fixed full-index verifier, without executing a sibling CLI."""
    cache = catalog(ctx).setdefault("verified_generations", {})
    if ref in cache:
        return cache[ref]
    try:
        prefix = "artifacts/indexes/local/" + manifest["generation_id"]
        if ref != prefix + "/manifest.json" or manifest.get("channel") != "local":
            raise ValueError("Generation identity/path differs")
        if sha(fixed_bytes(ctx.root, manifest["database_ref"], [prefix])) != manifest["database_digest"]:
            raise ValueError("Index bytes differ")
        cards = [ctx.modules["indexing"].read_document(
            fixed_bytes(ctx.root, row["blob_ref"], [prefix]), row["path"], ctx.rules,
            card_id=card_id, sha256=row["sha256"])
            for card_id, row in manifest["documents"].items()]
        checked = ctx.modules["indexing"].verify_database(cards, ctx.args.rules_digest,
                                                       safe(ctx.root, manifest["database_ref"], [prefix]))
        if checked != manifest["index_verification"]:
            raise ValueError("Full-index result differs")
        cache[ref] = True
    except (OSError, ValueError, KeyError, sqlite3.Error):
        cache[ref] = False
    return cache[ref]


def current_baseline(ctx):
    refs = paths(ctx, "knowledge/**/*.md") + ["governance/sources.lock.yaml"]
    return {ref: sha(fixed_bytes(ctx.root, ref)) for ref in sorted(refs)}


def view_targets(ctx, view):
    targets = {}
    for row in view.get("writes", []):
        path = row["path"]
        if path.startswith("knowledge/") and PurePosixPath(path).name not in {"index.md", "AGENTS.md"}:
            raw = base64.b64decode(row["bytes_b64"], validate=True)
            card = ctx.modules["knowledge"].parse_card(raw, path, ctx.rules)
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


def pointer_matches(ctx, manifest_ref, manifest, observation):
    pointer = observation.get("active_pointer", {})
    try:
        ctx.modules["records"].verify(pointer)
        return (observation.get("purpose") == "index_activation_observation"
                and observation.get("generation_ref") == manifest_ref
                and observation.get("manifest_digest") == manifest["digest"]
                and observation.get("active_digest") == pointer["digest"]
                and pointer.get("rules_digest") == ctx.args.rules_digest
                and pointer.get("channel") == "local"
                and pointer.get("generation_id") == manifest["generation_id"]
                and pointer.get("generation_ref") == manifest_ref
                and pointer.get("manifest_digest") == manifest["digest"])
    except (ValueError, KeyError):
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
                or not report_matches(ctx, report, view) or not generation_integrity(ctx, manifest_ref, manifest)):
            continue
        observed = next((ref for ref, value in data["activations"] if pointer_matches(ctx, manifest_ref, manifest, value)), None)
        currently_active = bool(active and active.get("generation_ref") == manifest_ref
                                and active.get("manifest_digest") == manifest["digest"])
        if observed or currently_active:
            return {**result, "status": "complete", "next_action": None, "generation_ref": manifest_ref,
                    "regression_ref": report_ref, "activation_ref": observed or active_ref,
                    "currently_active": currently_active, "verification": "saved_report_and_observed_activation"}
    baseline = current_baseline(ctx)
    if not covers_view(baseline, view):
        return {**result, "next_action": "inspect_context", "reason": "Applied content changed; do not replay the old view or CAS baseline"}
    epoch_ref = "logs/events/state.json"
    epoch = read_saved(ctx, epoch_ref).get("validity_epoch") if safe(ctx.root, epoch_ref).is_file() else 0
    candidates = [(ref, value) for ref, value in data["generations"]
                  if value.get("file_baseline") == baseline and value.get("validity_epoch") == epoch
                  and generation_integrity(ctx, ref, value)]
    if not candidates:
        return {**result, "status": "pending", "next_action": "rebuild_index",
                "reason": "No verified generation for the current files and validity epoch"}
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
