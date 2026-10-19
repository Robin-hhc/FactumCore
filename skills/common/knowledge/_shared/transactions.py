"""Apply reviewed document bytes with a durable, recoverable write-ahead journal.

This is a local cooperative writer protocol, not a filesystem-wide transaction or ACL.
It never performs semantic lint, creates a human decision, or invokes Git.
"""

import os
import re
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from . import changes, contracts, receipts


@contextmanager
def domain_write_lock(knowledge_root):
    """One nonblocking OS lock for cooperating processes using this real domain root."""
    root = Path(knowledge_root).resolve(strict=True)
    relative = "logs/operations/.writer.lock"
    path = changes.safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = changes.safe_path(root, relative)
    stream = path.open("a+b")
    acquired = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise changes.ChangeError(
                "BUSY", "Another domain writer holds the lock", relative
            ) from exc
        acquired = True
        changes.safe_path(root, relative)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _record(root, path, value):
    changes.atomic_write(root, path, changes.json_bytes(value))


def _operation_paths(operation_id):
    changes.operation_dir(operation_id)
    directory = f"logs/operations/{operation_id}"
    return directory, f"{directory}/journal.json", f"{directory}/result.json"


def _reject_incomplete_journals(root):
    operations = changes.safe_path(root, "logs/operations")
    if not operations.exists():
        return
    for directory in operations.iterdir():
        if directory.name == ".writer.lock":
            continue
        relative = directory.relative_to(root).as_posix()
        changes.safe_path(root, relative)
        if not directory.is_dir():
            continue
        journal_ref = relative + "/journal.json"
        journal = changes.safe_path(root, journal_ref)
        if not journal.exists():
            if any(directory.iterdir()):
                changes.fail(
                    "RECOVERY_REQUIRED",
                    "Transaction artifacts exist without a journal",
                    journal_ref,
                )
            continue
        try:
            value = changes.read_json(root, journal_ref)
            _validate_journal(root, value, directory.name)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise changes.ChangeError(
                "RECOVERY_REQUIRED", "Unreadable operation journal", journal_ref
            ) from exc
        if value.get("state") not in {"committed", "rolled_back"}:
            changes.fail("RECOVERY_REQUIRED", "Incomplete domain transaction", journal_ref)


def _validate_journal(root, value, operation_id):
    """A terminal state string alone does not establish a complete transaction."""
    if not isinstance(value, dict):
        raise ValueError("Journal must be an object")
    if value.get("schema_version") != "1.0" or value.get("operation_id") != operation_id:
        raise ValueError("Journal identity is missing or inconsistent")
    targets = value["targets"]
    if not isinstance(targets, list):
        raise ValueError("Journal targets must be a list")
    digests = {entry["path"]: entry["new_digest"] for entry in targets}
    _target_paths(digests)
    if len(digests) != len(targets):
        raise ValueError("Journal target identities are duplicated")
    for key in ("changeset_digest", "review_digest", "backup_manifest_digest"):
        if not isinstance(value[key], str) or not re.fullmatch("[0-9a-f]{64}", value[key]):
            raise ValueError("Journal digest is missing or malformed")
    for key in ("written", "attempted"):
        if not isinstance(value[key], list) or not set(value[key]).issubset(digests):
            raise ValueError("Journal progress does not name the declared targets")
    if not isinstance(value["review_ref"], str):
        raise ValueError("Journal review reference is missing")
    directory = f"logs/operations/{operation_id}"
    manifest = changes.read_json(root, directory + "/backup-manifest.json")
    if (
        manifest != {"schema_version": "1.0", "targets": targets}
        or receipts.digest_json(manifest) != value["backup_manifest_digest"]
    ):
        raise ValueError("Backup manifest differs from journal")
    for entry in targets:
        old = entry["old_digest"]
        if old is None:
            if entry["backup_ref"] is not None:
                raise ValueError("Absent target cannot name an existing-byte backup")
            continue
        expected_ref = f"{directory}/backups/{receipts.digest_bytes(entry['path'].encode())}.bin"
        if entry["backup_ref"] != expected_ref or changes.file_digest(root, expected_ref) != old:
            raise ValueError("Journal backup reference or bytes differ")
    if value.get("state") == "committed":
        if set(value["written"]) != set(digests) or set(value["attempted"]) != set(digests):
            raise ValueError("Committed journal has incomplete progress")
        if not isinstance(value["result_digest"], str) or not re.fullmatch(
            "[0-9a-f]{64}", value["result_digest"]
        ):
            raise ValueError("Committed journal has no result binding")
        result_bytes = changes.safe_path(root, directory + "/result.json").read_bytes()
        result = contracts.load_document_bytes(result_bytes)
        if (
            not isinstance(result, dict)
            or receipts.digest_bytes(result_bytes) != value["result_digest"]
            or result.get("operation_id") != operation_id
            or result.get("phase") != "applied"
            or result.get("review_ref") != value["review_ref"]
            or result.get("target_file_digests") != digests
        ):
            raise ValueError("Committed result bytes or identity differ from the journal")


def _review_bytes(root, review_ref):
    parts = PurePosixPath(review_ref).parts if isinstance(review_ref, str) else ()
    if (
        len(parts) != 3
        or parts[:2] != ("logs", "document-reviews")
        or not parts[2].endswith(".json")
    ):
        changes.fail("UNSAFE_PATH", "Expected a document-review record reference", review_ref)
    try:
        return changes.safe_path(root, review_ref).read_bytes()
    except OSError as exc:
        raise changes.ChangeError(
            "REVIEW_STALE", "Human-review record is unavailable", review_ref
        ) from exc


def _target_paths(digests):
    if not isinstance(digests, dict) or len(digests) != 3:
        changes.fail("UNSAFE_TARGET", "Expected one Card, its index and the source lock")
    cards = []
    for path, digest in digests.items():
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or not re.fullmatch("[0-9a-f]{64}", digest)
        ):
            changes.fail("UNSAFE_TARGET", "Invalid target or digest", path)
        if path == "governance/sources.lock.yaml" or path.endswith("/index.md"):
            continue
        if (
            not path.endswith(".md")
            or PurePosixPath(path).name.lower() in {"agents.md", "index.md"}
            or not any(
                path.startswith(f"knowledge/{prefix}/") for prefix in changes.PROFILE_PATHS.values()
            )
        ):
            changes.fail("UNSAFE_TARGET", "Target is not a Card profile path", path)
        cards.append(path)
    if len(cards) != 1 or set(digests) != {
        cards[0],
        str(PurePosixPath(cards[0]).parent / "index.md"),
        "governance/sources.lock.yaml",
    }:
        changes.fail(
            "UNSAFE_TARGET", "Target list is not one Card and its explicit companion files"
        )
    if len({path.casefold() for path in digests}) != len(digests):
        changes.fail("UNSAFE_TARGET", "Case-aliased targets are forbidden")
    return cards[0]


def _replay_committed(root, operation_id, review_ref, prior, result_ref):
    if prior.get("operation_id") != operation_id or prior.get("review_ref") != review_ref:
        changes.fail("REVIEW_STALE", "Committed operation/review reference differs")
    if receipts.digest_bytes(_review_bytes(root, review_ref)) != prior.get("review_digest"):
        changes.fail("REVIEW_STALE", "Committed human-review bytes changed", review_ref)
    try:
        result = changes.read_json(root, result_ref)
        if receipts.digest_json(result) != prior["result_digest"]:
            raise ValueError("Committed result digest differs")
        targets = {target["path"]: target["new_digest"] for target in prior["targets"]}
        _target_paths(targets)
        if (
            len(targets) != len(prior["targets"])
            or result["target_file_digests"] != targets
            or result["operation_id"] != operation_id
            or result["phase"] != "applied"
            or result["review_ref"] != review_ref
        ):
            raise ValueError("Committed result identity differs")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise changes.ChangeError(
            "RECOVERY_REQUIRED", "Invalid committed result", result_ref
        ) from exc
    for target, digest in targets.items():
        if changes.file_digest(root, target) != digest:
            changes.fail("APPLIED_STATE_CHANGED", "Applied target changed", target)
    return result


def _technical_view(root, outputs):
    """Read current Cards plus proposed overrides, independently of touched paths."""
    from .cards import parse_card

    lock = contracts.load_document_bytes(outputs["governance/sources.lock.yaml"])
    errors = contracts.validate_document("sources", lock, root)
    if errors:
        changes.fail("INVALID_SOURCE_LOCK", str(errors))
    resources = [item["source_id"] for item in lock["resources"]]
    snapshots = [item["snapshot_id"] for item in lock["snapshots"]]
    if len(resources) != len(set(resources)) or len(snapshots) != len(set(snapshots)):
        changes.fail("DUPLICATE_SOURCE_ID", "Source identities must be unique")
    for snapshot in lock["snapshots"]:
        if snapshot["source_id"] not in resources:
            changes.fail("UNKNOWN_SOURCE_REF", "Snapshot resource is absent", snapshot["source_id"])
    paths = set()
    base = changes.safe_path(root, "knowledge")
    if base.exists():
        for parent, directories, files in os.walk(base, followlinks=False):
            for name in directories:
                changes.safe_path(root, (Path(parent) / name).relative_to(root).as_posix())
            for name in files:
                if name.lower().endswith(".md") and name.lower() not in {"index.md", "agents.md"}:
                    paths.add((Path(parent) / name).relative_to(root).as_posix())
    paths.update(
        path for path in outputs if path.startswith("knowledge/") and not path.endswith("/index.md")
    )
    if len({path.casefold() for path in paths}) != len(paths):
        changes.fail("UNSAFE_PATH", "Card paths contain case aliases")
    cards, claims = {}, {}
    for path in sorted(paths):
        data = outputs[path] if path in outputs else changes.safe_path(root, path).read_bytes()
        metadata = parse_card(data, root, source_snapshots=lock["snapshots"])["metadata"]
        if path in outputs and (
            metadata["lifecycle"] != "stable"
            or metadata["review_mode"] != "manual_document"
            or not path.startswith(f"knowledge/{changes.PROFILE_PATHS[metadata['profile']]}/")
        ):
            changes.fail(
                "INVALID_DOCUMENT_TARGET",
                "Final Card must be stable/manual_document at its Profile path",
                path,
            )
        if not path.startswith(f"knowledge/{changes.PROFILE_PATHS[metadata['profile']]}/"):
            changes.fail("INVALID_CARD_PATH", "A Card is outside its registered Profile path", path)
        card_id = metadata["id"]
        if card_id in cards:
            changes.fail("DUPLICATE_CARD_ID", "Card ID exists at multiple paths", path)
        cards[card_id] = metadata
        for claim in metadata["claims"]:
            if claim["id"] in claims:
                changes.fail("DUPLICATE_CLAIM_ID", "Claim ID exists in multiple Cards", path)
            claims[claim["id"]] = card_id
    graphs = {"requires": {}, "replacement": {}}
    for card_id, metadata in cards.items():
        replacements = metadata.get("replacement", [])
        graphs["replacement"][card_id] = []
        graphs["requires"][card_id] = []
        relations = metadata["relations"] + [
            {"type": "replacement", "target_card_id": identity} for identity in replacements
        ]
        for relation in relations:
            target_card = relation["target_card_id"]
            if target_card not in cards:
                changes.fail("UNRESOLVED_CARD_REF", "Relation target Card is absent", target_card)
            target_claim = relation.get("target_claim_id")
            if target_claim is not None and claims.get(target_claim) != target_card:
                changes.fail(
                    "UNRESOLVED_CLAIM_REF", "Claim does not belong to relation target", target_claim
                )
            if relation["type"] in graphs:
                graphs[relation["type"]][card_id].append(target_card)
    for kind, graph in graphs.items():
        # Kahn's algorithm is bounded by the graph, without recursive stack limits.
        incoming = {identity: 0 for identity in cards}
        for targets in graph.values():
            for target in targets:
                incoming[target] += 1
        ready = [identity for identity, count in incoming.items() if count == 0]
        visited = 0
        while ready:
            identity = ready.pop()
            visited += 1
            for target in graph.get(identity, []):
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
        if visited != len(cards):
            changes.fail("CYCLIC_CARD_RELATION", f"{kind} relations must be acyclic")


def apply_document(knowledge_root, operation_id, review_ref):
    """Place the exact accepted final view; an incomplete journal requires T08 recovery."""
    root = Path(knowledge_root).resolve(strict=True)
    with domain_write_lock(root):
        return _apply_locked(root, operation_id, review_ref)


def _apply_locked(root, operation_id, review_ref):
    directory, journal_ref, result_ref = _operation_paths(operation_id)
    _reject_incomplete_journals(root)
    journal_path = changes.safe_path(root, journal_ref)
    if journal_path.exists():
        prior = changes.read_json(root, journal_ref)
        if prior.get("state") != "committed":
            changes.fail("RECOVERY_REQUIRED", "Operation journal is not committed", journal_ref)
        return _replay_committed(root, operation_id, review_ref, prior, result_ref)

    plan = changes.load_plan(root, operation_id)
    if plan["decision"] not in {"create", "update"}:
        changes.fail(
            "DEFERRED_OPERATION",
            "This decision is planned only; cross-Card apply is not implemented",
        )
    view = changes.checked_view(root, operation_id)
    if view.get("operation_id") != operation_id or view.get("review_mode") != "manual_document":
        changes.fail("INVALID_DOCUMENT_TARGET", "Operation is not this manual-document ChangeSet")
    if view.get("decision") not in {"create", "update"}:
        changes.fail("DEFERRED_OPERATION", "Only single-Card create/update apply is implemented")
    review_bytes = _review_bytes(root, review_ref)
    verified = changes.validate_review(root, operation_id, review_ref, record_bytes=review_bytes)
    if verified != contracts.load_document_bytes(review_bytes, review_ref):
        changes.fail("REVIEW_STALE", "Validated record differs from the captured review bytes")
    if _review_bytes(root, review_ref) != review_bytes:
        changes.fail("REVIEW_STALE", "Review changed during verification", review_ref)
    _target_paths(view["target_file_digests"])
    changes.check_baseline(root, view["baseline"])
    entries = []
    final_bytes = {}
    previous_bytes = {}
    for target, digest in sorted(view["target_file_digests"].items()):
        changes.safe_path(root, target)
        if target not in view["baseline"]:
            changes.fail("BASELINE_CHANGED", "Target has no explicit baseline", target)
        data = changes.safe_path(root, f".build/{operation_id}/final-view/{target}").read_bytes()
        if receipts.digest_bytes(data) != digest:
            changes.fail("REVIEW_STALE", "Final-view bytes changed", target)
        final_bytes[target] = data
        old_digest = view["baseline"][target]
        backup_ref = None
        if old_digest is not None:
            previous = changes.safe_path(root, target).read_bytes()
            if receipts.digest_bytes(previous) != old_digest:
                changes.fail("BASELINE_CHANGED", "Target changed during backup", target)
            backup_ref = f"{directory}/backups/{receipts.digest_bytes(target.encode())}.bin"
            previous_bytes[backup_ref] = previous
        entries.append(
            {
                "path": target,
                "old_digest": old_digest,
                "new_digest": digest,
                "backup_ref": backup_ref,
            }
        )
    _technical_view(root, final_bytes)
    manifest = {"schema_version": "1.0", "targets": entries}
    journal = {
        "schema_version": "1.0",
        "operation_id": operation_id,
        "review_ref": review_ref,
        "review_digest": receipts.digest_bytes(review_bytes),
        "changeset_digest": receipts.digest_json(view),
        "state": "prepared",
        "targets": entries,
        "written": [],
        "attempted": [],
        "backup_manifest_digest": receipts.digest_json(manifest),
    }
    try:
        for backup_ref, data in previous_bytes.items():
            changes.atomic_write(root, backup_ref, data)
            if changes.safe_path(root, backup_ref).read_bytes() != data:
                changes.fail("BACKUP_CHANGED", "Backup bytes failed verification", backup_ref)
        _record(root, f"{directory}/backup-manifest.json", manifest)
        if changes.read_json(root, f"{directory}/backup-manifest.json") != manifest:
            changes.fail("BACKUP_CHANGED", "Backup manifest failed verification")
        changes.check_baseline(root, view["baseline"])
        _record(root, journal_ref, journal)
        _technical_view(root, final_bytes)
        for entry in entries:
            target = entry["path"]
            journal.update(state="replacing", current=target)
            _record(root, journal_ref, journal)
            if changes.file_digest(root, target) != entry["old_digest"]:
                changes.fail("BASELINE_CHANGED", "Target changed before replacement", target)
            journal["attempted"].append(target)
            _record(root, journal_ref, journal)
            changes.atomic_write(root, target, final_bytes[target])
            journal["written"].append(target)
            _record(root, journal_ref, journal)
        for entry in entries:
            if changes.file_digest(root, entry["path"]) != entry["new_digest"]:
                changes.fail("INPUT_CHANGED", "Applied target changed", entry["path"])
        _technical_view(root, final_bytes)
        if _review_bytes(root, review_ref) != review_bytes:
            changes.fail("REVIEW_STALE", "Human review changed during transaction", review_ref)
        if (
            receipts.digest_json(changes.checked_view(root, operation_id))
            != journal["changeset_digest"]
        ):
            changes.fail("REVIEW_STALE", "Materialized view changed during transaction")
        result = {
            "schema_version": "1.0",
            "operation_id": operation_id,
            "phase": "applied",
            "final_view_digest": view["final_view_digest"],
            "target_file_digests": view["target_file_digests"],
            "journal_ref": journal_ref,
            "review_ref": review_ref,
            "index_activated": False,
        }
        _record(root, result_ref, result)
        journal.update(state="committed", result_digest=receipts.digest_json(result))
        _record(root, journal_ref, journal)
    except Exception as exc:
        if not journal_path.exists():
            # No write-ahead journal means no formal target was replaced.
            if isinstance(exc, changes.ChangeError):
                raise
            raise changes.ChangeError("TRANSACTION_FAILED", str(exc), journal_ref) from exc
        _rollback(root, journal_ref, journal, exc)
    return result


def _rollback(root, journal_ref, journal, cause):
    """Restore only bytes still owned by this attempted transaction."""
    errors = []
    for entry in reversed(journal["targets"]):
        target, old, new = entry["path"], entry["old_digest"], entry["new_digest"]
        try:
            current = changes.file_digest(root, target)
            if current == old:
                continue
            if target not in journal["attempted"]:
                raise ValueError("Unattempted target was changed externally; preserved")
            if current != new:
                raise ValueError("External target edit preserved")
            if old is None:
                changes.safe_path(root, target).unlink()
            else:
                data = changes.safe_path(root, entry["backup_ref"]).read_bytes()
                if receipts.digest_bytes(data) != old:
                    raise ValueError("Backup digest differs")
                changes.atomic_write(root, target, data)
            if changes.file_digest(root, target) != old:
                raise ValueError("Restored target differs from prior bytes")
        except Exception as exc:
            errors.append({"path": target, "message": str(exc)})
    journal.update(
        state="recovery_required" if errors else "rolled_back",
        failure={"code": getattr(cause, "code", "WRITE_FAILED"), "message": str(cause)},
        recovery_diagnostics=errors,
    )
    try:
        _record(root, journal_ref, journal)
    except Exception as exc:
        raise changes.ChangeError(
            "RECOVERY_REQUIRED", "Unable to persist rollback outcome", journal_ref
        ) from exc
    if errors:
        changes.fail(
            "RECOVERY_REQUIRED", "External edits or recovery failures preserved", journal_ref
        )
    raise changes.ChangeError("TRANSACTION_ROLLED_BACK", str(cause), journal_ref) from cause
