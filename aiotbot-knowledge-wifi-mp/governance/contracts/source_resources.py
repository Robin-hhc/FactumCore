"""Exact logical-resource/snapshot resolution; source objects are always read-only."""

from .validation import ContractError, load_yaml, safe_path, sha256_bytes


def read_source_lock(knowledge_root):
    lock = load_yaml(safe_path(knowledge_root, "governance/sources.lock.yaml"))
    if lock.get("schema_version") != "2.0":
        raise ContractError("UNSUPPORTED_SOURCE_VERSION", "Expected 2.0")
    for field, key in (("resources", "source_id"), ("snapshots", "snapshot_id")):
        identities = [item[key] for item in lock[field]]
        if len(identities) != len(set(identities)):
            raise ContractError("DUPLICATE_SOURCE", field)
    resource_ids = {item["source_id"] for item in lock["resources"]}
    if any(item["source_id"] not in resource_ids for item in lock["snapshots"]):
        raise ContractError(
            "SOURCE_RESOURCE_MISSING", "Snapshot points to an unregistered resource"
        )
    return lock


def validate_source_ref(ref, lock, roots=None):
    if not isinstance(ref, dict) or not all(
        ref.get(k) for k in ("evidence_ref", "source_id", "snapshot_id", "locator")
    ):
        raise ContractError(
            "INCOMPLETE_EVIDENCE_REF", "Evidence, source, snapshot and locator required"
        )
    matches = [s for s in lock["snapshots"] if s["snapshot_id"] == ref["snapshot_id"]]
    if len(matches) != 1 or matches[0]["source_id"] != ref["source_id"]:
        raise ContractError("SOURCE_SNAPSHOT_MISMATCH", ref["snapshot_id"])
    if not any(s["source_id"] == ref["source_id"] for s in lock["resources"]):
        raise ContractError("SOURCE_RESOURCE_MISSING", ref["source_id"])
    return matches[0]


def validate_snapshot(bundle, expected=None):
    for key, value in (expected or {}).items():
        if bundle.get(key) != value:
            raise ContractError("SNAPSHOT_BINDING_MISMATCH", key)
    seen = set()
    for snapshot in bundle.get("snapshots", []):
        identity = snapshot.get("snapshot_id")
        if not identity or identity in seen:
            raise ContractError("DUPLICATE_SNAPSHOT", identity)
        if (
            not snapshot.get("sha256")
            or not isinstance(snapshot.get("bytes"), int)
            or snapshot["bytes"] < 0
        ):
            raise ContractError("INCOMPLETE_SNAPSHOT", identity)
        if not snapshot.get("recovery"):
            raise ContractError("UNRECOVERABLE_SNAPSHOT", identity)
        seen.add(identity)
    return bundle


def recover_snapshot(knowledge_root, snapshot):
    recovery = snapshot.get("recovery", {})
    path = recovery.get("path") if isinstance(recovery, dict) else recovery
    if not path:
        raise ContractError("UNSUPPORTED_RECOVERY", "Immutable local object required")
    data = safe_path(knowledge_root, path, ["logs/evidence"]).read_bytes()
    if sha256_bytes(data) != snapshot.get("sha256") or len(data) != snapshot.get(
        "bytes"
    ):
        raise ContractError("EVIDENCE_OBJECT_CHANGED", snapshot.get("snapshot_id"))
    return data
