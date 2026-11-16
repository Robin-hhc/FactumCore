"""Read-only adapter for source objects referenced by historical bundles."""

from .runtime import NodeError, fixed_bytes, safe, sha


def read_bytes(root, ref, entries=None, *, expected_sha=None, expected_size=None):
    matches = [item for item in (entries or []) if item.get("final_ref") == ref]
    if len(matches) > 1:
        raise NodeError("STAGING_CONFLICT", "Historical object has multiple bindings", ref)
    item = matches[0] if matches else None
    actual = item["stage_ref"] if item else ref
    safe(root, actual, [".build", "logs", "docs-raw"])
    data = fixed_bytes(root, actual)
    wanted_hash = expected_sha or (item.get("sha256") if item else None)
    wanted_size = expected_size if expected_size is not None else item.get("bytes") if item else None
    if wanted_hash is not None and sha(data) != wanted_hash or wanted_size is not None and len(data) != wanted_size:
        raise NodeError("EVIDENCE_OBJECT_CHANGED", "Historical source bytes do not match", ref)
    return data
