"""Real local-index checks and retrieval for the governance patrol.

This module deliberately calls the shared contracts in process. A saved
``passed`` field is never a replacement for executing a query and reading its
result from the same verified generation.
"""
from __future__ import annotations

from .runtime import NodeError, digest, fixed_bytes, fork_context, sha
from . import index_runtime, query_regression


def current(ctx, channel="local"):
    pointer = index_runtime.active(ctx, channel)
    if pointer is None:
        raise NodeError("PATROL_INDEX_MISSING", "No active index exists")
    observed = index_runtime.verify_generation(ctx, pointer["generation_ref"])
    manifest = observed.manifest
    if (pointer["manifest_digest"] != manifest["digest"]
            or manifest["knowledge_baseline"] != digest(index_runtime.baseline(ctx))
            or manifest["validity_epoch"] != index_runtime.state(ctx)["validity_epoch"]):
        raise NodeError("PATROL_INDEX_STALE", "Active index does not describe the current formal library")
    return pointer, observed


def closure(ctx, retrieval):
    """Capture exact bytes only after real full verification and query execution."""
    pointer, observed = current(ctx)
    files = dict(observed.file_fingerprints)
    ref = retrieval.get("report_ref")
    if ref:
        files[ref] = sha(fixed_bytes(ctx.root, ref))
    lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
    adopted = {(source["source_id"], source["snapshot_id"]) for card in observed.cards
               for source in card["metadata"]["sources"]}
    snapshots = [row for row in lock["snapshots"] if (row["source_id"], row["snapshot_id"]) in adopted]
    for snapshot in snapshots:
        if sha(ctx.modules["source_resources"].recover_snapshot(ctx.root, snapshot)) != snapshot["sha256"]:
            raise NodeError("PATROL_ADOPTED_SOURCE_CHANGED", "Verified historical source bytes differ")
    return {"active_digest": pointer["digest"], "generation_ref": pointer["generation_ref"],
            "manifest_digest": observed.manifest["digest"], "rules_digest": ctx.args.rules_digest,
            "files": files, "adopted_snapshots": snapshots}


def unchanged_closure(ctx, previous):
    """Byte-check the successful verification closure; never accept it from a request."""
    if not previous or previous.get("rules_digest") != ctx.args.rules_digest:
        return False
    try:
        pointer = index_runtime.active(ctx, "local")
        if (not pointer or pointer["digest"] != previous["active_digest"]
                or pointer["generation_ref"] != previous["generation_ref"]
                or pointer["manifest_digest"] != previous["manifest_digest"]):
            return False
        if any(sha(fixed_bytes(ctx.root, ref)) != expected for ref, expected in previous["files"].items()):
            return False
        if any(sha(ctx.modules["source_resources"].recover_snapshot(ctx.root, snapshot)) != snapshot["sha256"]
               for snapshot in previous.get("adopted_snapshots", [])):
            return False
        manifest = ctx.record(pointer["generation_ref"], "index_manifest")
        return (manifest["digest"] == previous["manifest_digest"]
                and manifest["knowledge_baseline"] == digest(index_runtime.baseline(ctx))
                and manifest["validity_epoch"] == index_runtime.state(ctx)["validity_epoch"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def cases(ctx, cards):
    """Existence assertions, with declared historical scope rather than invented applicability."""
    if ctx.request.get("cases") is not None:
        return ctx.request["cases"]
    result = []
    for card in cards:
        if card["metadata"]["lifecycle"] not in {"stable", "deprecated"}:
            continue
        identity = card["metadata"]["id"]
        context = None
        for claim in card["claims"]:
            scope = claim.get("scope", {})
            candidates = [{}] if scope.get("applicability", "unknown") != "constrained" else [
                {**{key: group[key] for key in ("target_id", "chip", "side", "build_profile", "pairing_id", "revision")
                    if group.get(key) is not None},
                 "features": group.get("features_all", []), "protocol_versions": group.get("protocol_versions", [])}
                for group in scope.get("contexts", [])]
            context = next((value for value in candidates
                            if ctx.modules["knowledge"].match_scope(claim, value, "historical")), None)
            if context is not None:
                break
        if context is None:
            raise NodeError("PATROL_QUERY_CONTEXT_REQUIRED", "Cannot construct an existence query from declared scope", identity)
        result.append({"id": "patrol-" + identity, "query": identity, "purpose": "historical",
                       "context": context, "required": [identity], "top_k": 100})
    # The exact empty result exercises the actual reader and empty collection.
    return result or [{"id": "patrol-empty", "query": "patrol-empty-library-probe", "purpose": "historical",
                       "expected_order": []}]


def check_queries(ctx, cards, *, build=False, inputs=None):
    request = {**(inputs or {}), "operation_id": ctx.operation, "channel": ctx.request.get("channel", "local")}
    if request["channel"] != "local":
        raise NodeError("PATROL_LOCAL_INDEX_REQUIRED", "Automatic patrol index maintenance is local; shared publication needs its existing receipt flow")
    if build:
        index_ctx = fork_context(ctx, request=request, action="build")
        built, _ = index_runtime.execute(index_ctx)
        observed = index_ctx.verified_generation
        generation_ref, expected = built["generation_ref"], built["expected_active"]
        pointer = index_runtime.active(ctx, request["channel"])
        already_active = (pointer is not None and pointer["generation_ref"] == generation_ref
                          and pointer["manifest_digest"] == observed.manifest["digest"]
                          and pointer.get("previous_active_digest") == expected)
    else:
        pointer, observed = current(ctx, request["channel"])
        generation_ref = pointer["generation_ref"]
        expected = observed.manifest["expected_active"]
        already_active = True
    query_ctx = fork_context(ctx, request={**request, "generation_ref": generation_ref,
        "expected_active": expected, "cases": cases(ctx, cards)}, action="regression")
    # A host may lose the response after the real activation. Re-execute the
    # queries against that exact active generation without repeating its CAS
    # against the generation's original predecessor.
    data, phase = query_regression.execute(query_ctx, verified_generation=observed, activate=build and not already_active)
    if data.get("passed") is not True:
        raise NodeError("PATROL_QUERY_FAILED", "Actual patrol retrieval or same-generation read failed", data["report_ref"], blocked=True)
    # Check the current control plane again after the potentially expensive query.
    pointer, _ = current(ctx, request["channel"])
    if pointer["generation_ref"] != generation_ref:
        raise NodeError("PATROL_INDEX_CHANGED", "Active generation changed during patrol verification", blocked=True)
    return {**data, "activated": bool(build or data.get("activated")), "active_digest": pointer["digest"],
            "verification_tier": "actual_index_and_historical_existence_queries"}
