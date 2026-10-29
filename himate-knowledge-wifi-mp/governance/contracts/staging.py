"""Explicit immutable stage-to-final bindings, never operation discovery."""

from __future__ import annotations

import re

from .runtime import NodeError, fixed_bytes, identifier, safe, sha, write_bytes


def validate_entries(root, entries):
    if not isinstance(entries, list):
        raise NodeError("INVALID_STAGED_OBJECTS", "staged_objects must be a list")
    for item in entries:
        if not isinstance(item, dict):
            raise NodeError("INVALID_STAGED_OBJECT", "Expected an explicit object binding")
        owner = identifier(item.get("owner_operation_id"))
        stage = item.get("stage_ref")
        safe(root, stage, [".build/operations"])
        if not stage.startswith(".build/operations/" + owner + "/"):
            raise NodeError("STAGING_OWNER_MISMATCH", "Stage path does not belong to its declared operation", stage)
        safe(root, item.get("final_ref"), ["knowledge", "governance", "logs/evidence/published"])
        identifier(item.get("kind"))
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise NodeError("INVALID_STAGED_OBJECT", "Expected a SHA-256 digest", stage)
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise NodeError("INVALID_STAGED_OBJECT", "Expected a nonnegative byte size", stage)
    return merge_entries(entries)


def merge_entries(*groups):
    result = {}
    folded = {}
    for group in groups:
        for item in group:
            key = item["final_ref"]
            alias = folded.get(key.casefold())
            if alias is not None and alias != key:
                raise NodeError("STAGING_CONFLICT", "Final target has a case alias", key)
            folded[key.casefold()] = key
            previous = result.get(key)
            if previous is not None:
                # Equal payloads from explicitly adopted operations are equivalent;
                # retain the first physical binding and its real ownership.
                if any(previous[field] != item[field] for field in ("sha256", "bytes", "kind")):
                    raise NodeError("STAGING_CONFLICT", "Two staged objects disagree on the same final target", key)
            else:
                result[key] = dict(item)
    return [result[key] for key in sorted(result)]


def entries_from_bundle(bundle):
    entries = bundle.get("staged_objects", []) if bundle is not None else []
    if not isinstance(entries, list):
        raise NodeError("INVALID_STAGED_OBJECTS", "staged_objects must be a list")
    return entries


def stage_bytes(ctx, final_ref, data, *, kind, source_id=None, snapshot_id=None):
    if not isinstance(data, bytes):
        raise NodeError("INVALID_STAGED_OBJECT", "Staged payload must be bytes")
    identifier(kind)
    payload_hash = sha(data)
    entry = {"stage_ref": ctx.base + "/staged/" + kind + "/" + payload_hash,
             "final_ref": final_ref, "kind": kind, "sha256": payload_hash,
             "bytes": len(data), "owner_operation_id": ctx.operation}
    for field, value in (("source_id", source_id), ("snapshot_id", snapshot_id)):
        if value is not None:
            entry[field] = value
    validate_entries(ctx.root, [entry])
    write_bytes(ctx.root, entry["stage_ref"], data)
    if hasattr(ctx, "register_owned"):
        ctx.register_owned(entry["stage_ref"], data)
    return entry


def read_bytes(root, ref, entries=None, *, expected_sha=None, expected_size=None):
    """Read only a declared binding or the exact supplied physical reference."""
    bindings = validate_entries(root, [] if entries is None else entries)
    matches = [item for item in bindings if item["final_ref"] == ref]
    item = matches[0] if matches else None
    data = fixed_bytes(root, item["stage_ref"] if item else ref)
    if item and (sha(data) != item["sha256"] or len(data) != item["bytes"]):
        raise NodeError("STAGED_OBJECT_CHANGED", "Staged object differs from its explicit binding", ref)
    if (expected_sha is not None and sha(data) != expected_sha) or (expected_size is not None and len(data) != expected_size):
        raise NodeError("STAGED_OBJECT_CHANGED", "Object differs from its frozen expected bytes", ref)
    return data
