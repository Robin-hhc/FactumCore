"""Carry the exact source bytes checked in P4 into the published reference view."""

import json
from pathlib import PurePosixPath

from . import source_resources
from .catalog import atomic_write
from .validation import ContractError, _workspace_no_links, canonical_bytes, safe_path, sha256_bytes


RECEIPT = ".build/citation-versions.json"
STAGED = ".build/materials/citation-sources"
RETAINED = "logs/evidence/objects"
MISSING_VERSION = {"SOURCE_INPUT_UNAVAILABLE", "GIT_SOURCE_UNAVAILABLE", "PATH_OUTSIDE_ALLOWED_ROOT",
                   "RECOVERY_CONFIG_REQUIRED", "RECOVERY_CONFIG_MISMATCH", "RECOVERY_REPO_UNKNOWN",
                   "RECOVERY_REPO_MISMATCH"}


def _path(root, relative, prefix):
    path = safe_path(root, relative, [prefix])
    _workspace_no_links(path)
    return path


def invalidate(root):
    _path(root, RECEIPT, ".build").unlink(missing_ok=True)


def _binding(card, reference):
    markdown = card["raw"].replace(b"\r\n", b"\n")
    return {"card_id": card["id"], "card_sha256": sha256_bytes(markdown),
            "reference_sha256": sha256_bytes(canonical_bytes(reference))}


def _key(binding):
    return binding["card_id"], binding["card_sha256"], binding["reference_sha256"]


def _write_exact(path, data):
    if not path.is_file() or path.read_bytes() != data:
        atomic_write(path, data)


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def retained_bytes(root, snapshot):
    digest = snapshot["sha256"]
    if not _digest(digest):
        raise ContractError("CITATION_SOURCE_UNAVAILABLE", "Invalid retained citation digest")
    path = _path(root, f"{RETAINED}/{digest}.bin", RETAINED)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if len(data) != snapshot["bytes"] or sha256_bytes(data) != digest:
        raise ContractError("EVIDENCE_OBJECT_CHANGED", snapshot["snapshot_id"])
    return data


def stage(root, checked, task_bytes):
    """Record only references that passed the mechanical check in this task."""
    rows, written = [], set()
    for card, reference, source, data, extractor in checked:
        digest = sha256_bytes(data)
        if digest not in written:
            path = _path(root, f"{STAGED}/{digest}.bin", STAGED)
            _write_exact(path, data)
            written.add(digest)
        rows.append({**_binding(card, reference), "source_id": source["source_id"],
                     "sha256": digest, "bytes": len(data), "extractor": extractor})
    atomic_write(_path(root, RECEIPT, ".build"),
                 canonical_bytes({"task_sha256": sha256_bytes(task_bytes), "references": rows}))


def _snapshot(root, source, digest, data, extractor):
    identity = source["source_id"]
    recovery = source_resources.git_recovery_for_current(root, source["path"], data) if source["kind"] == "raw" else None
    if recovery is None:
        retained = f"{RETAINED}/{digest}.bin"
        path = _path(root, retained, RETAINED)
        _write_exact(path, data)
        recovery = {"method": "evidence_object", "path": retained}
    snapshot = {"source_id": identity, "snapshot_id": "citation-" + sha256_bytes(canonical_bytes([identity, digest]))[:40],
                "sha256": digest, "bytes": len(data), "recovery": recovery,
                "format": PurePosixPath(source["path"]).suffix.lower()}
    if extractor is not None:
        snapshot["extraction"] = {"extractor": extractor}
    return snapshot


def persist(root, catalog, drafts, task_bytes):
    """Attach exact proof to registry snapshots while the P5 writer is held."""
    receipt = _path(root, RECEIPT, ".build")
    if not receipt.is_file():
        return False
    value = json.loads(receipt.read_bytes())
    if value["task_sha256"] != sha256_bytes(task_bytes):
        return False
    expected = {_key(_binding(card, ref)): ref[kind + "_id"]
                for card in drafts for kind in ("doc", "code") for ref in card[kind + "_ref"]
                if not ref.get("snapshot_id")}
    snapshots = {(row["source_id"], row["sha256"]): row for row in catalog.registry["snapshots"]}
    _, associations = project_index(catalog.registry)
    checked, available = {}, set()
    changed = False
    for row in value["references"]:
        key = _key(row)
        identity = row["source_id"]
        if expected.get(key) != identity:
            continue
        digest = row["sha256"]
        if not _digest(digest):
            raise ContractError("CITATION_SOURCE_UNAVAILABLE", "Invalid P4 source digest", identity)
        source = catalog.get_file(identity)
        if source is None:
            raise ContractError("UNKNOWN_SOURCE_ID", identity)
        if digest not in checked:
            path = _path(root, f"{STAGED}/{digest}.bin", STAGED)
            try:
                data = path.read_bytes()
            except FileNotFoundError as error:
                raise ContractError("CITATION_SOURCE_UNAVAILABLE", "P4 source bytes are missing", identity) from error
            if sha256_bytes(data) != digest:
                raise ContractError("CITATION_SOURCE_UNAVAILABLE", "P4 source bytes changed", identity)
            checked[digest] = data
        data = checked[digest]
        if len(data) != row["bytes"]:
            raise ContractError("CITATION_SOURCE_UNAVAILABLE", "P4 source length changed", identity)
        snapshot = snapshots.get((identity, digest))
        if snapshot is None:
            snapshot = _snapshot(root, source, digest, data, row["extractor"])
            catalog.registry["snapshots"].append(snapshot)
            snapshots[identity, digest] = snapshot
        elif (identity, digest) not in available:
            try:
                source_resources.recover_snapshot(root, snapshot)
            except ContractError as error:
                if error.code not in MISSING_VERSION:
                    raise
                _write_exact(_path(root, f"{RETAINED}/{digest}.bin", RETAINED), data)
        available.add((identity, digest))
        association = {key: row[key] for key in ("card_id", "card_sha256", "reference_sha256")}
        bindings = snapshot.setdefault("card_references", [])
        for previous in associations.get(key, []):
            if previous is not snapshot:
                previous["card_references"] = [item for item in previous["card_references"] if _key(item) != key]
                changed = True
        if association not in bindings:
            bindings.append(association)
            changed = True
    return changed


def project_index(registry):
    snapshots = {row["snapshot_id"]: row for row in registry.get("snapshots", [])}
    bindings = {}
    for snapshot in snapshots.values():
        for binding in snapshot.get("card_references", []):
            bindings.setdefault(_key(binding), []).append(snapshot)
    return snapshots, bindings


def project_reference(card, kind, reference, index):
    snapshots, bindings = index
    identity = reference[kind + "_id"]
    declared = reference.get("snapshot_id")
    if declared is not None:
        snapshot = snapshots.get(declared)
        candidates = [snapshot] if snapshot and snapshot.get("source_id") == identity else []
    else:
        candidates = [row for row in bindings.get(_key(_binding(card, reference)), [])
                      if row.get("source_id") == identity]
    if len(candidates) == 1:
        return {**reference, "snapshot_id": candidates[0]["snapshot_id"],
                "source_sha256": candidates[0]["sha256"], "source_version": "bound"}
    return {**reference, "source_version": "unavailable" if declared is not None or candidates else "unknown"}
