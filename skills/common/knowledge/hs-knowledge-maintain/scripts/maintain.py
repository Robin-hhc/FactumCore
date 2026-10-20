"""Source events and current validity state, independent from index generations."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import os

from support import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
    read_json,
    safe,
    sha,
    write_bytes,
)


@contextmanager
def writer_lock(context):
    path = safe(context.root, "logs/operations/.writer.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
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
            raise NodeError(
                "BUSY", "Another cooperating domain writer holds the lock", blocked=True
            ) from exc
        acquired = True
        safe(context.root, "logs/operations/.writer.lock")
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


def state(context):
    path = safe(context.root, "logs/events/state.json")
    if path.exists():
        result = context.record("logs/events/state.json", "maintenance_state")
        if (
            not isinstance(result.get("validity_epoch"), int)
            or result["validity_epoch"] < 0
        ):
            raise NodeError(
                "INVALID_VALIDITY_STATE", "Validity epoch must be nonnegative"
            )
        return result
    return {
        "validity_epoch": 0,
        "blocked_claims": [],
        "processed_event_ids": [],
        "pending_event_ids": [],
        "impact_scan_watermark": None,
        "knowledge_apply_watermark": None,
    }


def save_state(context, previous, payload):
    path = safe(context.root, "logs/events/state.json")
    if (
        path.exists()
        and context.record("logs/events/state.json", "maintenance_state") != previous
    ):
        raise NodeError(
            "VALIDITY_CONFLICT", "Validity state changed outside the writer protocol"
        )
    clean = {
        k: v
        for k, v in payload.items()
        if k
        not in {
            "schema_version",
            "record_kind",
            "digest",
            "operation_id",
            "rules_digest",
            "tool_identity",
        }
    }
    sealed = context.seal(clean, "maintenance_state")
    write_bytes(
        context.root, "logs/events/state.json", canonical(sealed), immutable=False
    )
    return sealed


def domain_cards(context):
    root = safe(context.root, "knowledge")
    cards = []
    if root.exists():
        for path in sorted(root.rglob("*.md")):
            if path.name in {"AGENTS.md", "index.md"}:
                continue
            ref = path.relative_to(context.root).as_posix()
            cards.append(
                context.modules["knowledge"].parse_card(
                    fixed_bytes(context.root, ref), ref, context.rules
                )
            )
    return cards


def register(context):
    bundle = context.record(context.request["bundle_ref"], "source_bundle")
    lock = load_yaml(fixed_bytes(context.root, "governance/sources.lock.yaml"))
    changes = []
    for snapshot in bundle["snapshots"]:
        recovery = snapshot["recovery"]
        data = fixed_bytes(context.root, recovery["reference"], ["logs/evidence"])
        if sha(data) != snapshot["sha256"] or len(data) != snapshot["bytes"]:
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "New source snapshot bytes cannot be verified"
            )
        resource = next(
            r for r in bundle["resources"] if r["source_id"] == snapshot["source_id"]
        )
        if (
            sha(fixed_bytes(context.root, resource["path"], ["docs-raw"]))
            != snapshot["sha256"]
        ):
            raise NodeError(
                "SOURCE_CHANGED",
                "New source changed again before event registration",
                blocked=True,
            )
        previous = [
            s for s in lock["snapshots"] if s["source_id"] == snapshot["source_id"]
        ]
        if previous and snapshot["snapshot_id"] not in {
            s["snapshot_id"] for s in previous
        }:
            changes.append(
                {
                    "source_id": snapshot["source_id"],
                    "old_snapshot_ids": sorted(s["snapshot_id"] for s in previous),
                    "new_snapshot_id": snapshot["snapshot_id"],
                    "new_sha256": snapshot["sha256"],
                }
            )
    with writer_lock(context):
        previous = state(context)
        updated = dict(previous)
        updated["blocked_claims"] = list(previous["blocked_claims"])
        processed = set(previous.get("processed_event_ids", []))
        pending = set(previous.get("pending_event_ids", []))
        refs = []
        cards = domain_cards(context)
        for change in changes:
            event_id = digest(change)
            ref = "logs/events/" + event_id + ".json"
            refs.append(ref)
            if event_id in processed:
                continue
            affected = []
            for card in cards:
                if card["metadata"]["lifecycle"] != "stable":
                    continue
                sources = {s["evidence_ref"]: s for s in card["metadata"]["sources"]}
                for claim in card["metadata"]["claims"]:
                    if any(
                        sources[r]["source_id"] == change["source_id"]
                        and sources[r]["snapshot_id"] in change["old_snapshot_ids"]
                        for r in claim["source_refs"]
                    ):
                        affected.append(
                            {
                                "card_id": card["metadata"]["id"],
                                "claim_id": claim["id"],
                                "reason": "source_changed",
                                "event_id": event_id,
                                "source_id": change["source_id"],
                                "old_snapshot_ids": change["old_snapshot_ids"],
                                "new_snapshot_id": change["new_snapshot_id"],
                                "conditions": card["metadata"]["scope"],
                            }
                        )
            # Persist blocks/epoch before the event publish: a hard kill can never leave
            # an observed change consumable merely because its event write was interrupted.
            if event_id not in pending:
                updated["blocked_claims"] += [
                    b for b in affected if b not in updated["blocked_claims"]
                ]
                updated["validity_epoch"] += 1
                pending.add(event_id)
                updated["pending_event_ids"] = sorted(pending)
                previous = save_state(context, previous, updated)
                updated = dict(previous)
            if safe(context.root, ref).exists():
                event = context.record(ref, "maintenance_event")
                if event.get("change") != change:
                    raise NodeError(
                        "EVENT_CONFLICT",
                        "Existing event differs from source transition",
                    )
            else:
                event = context.seal(
                    {
                        "event_id": event_id,
                        "change": change,
                        "bundle_ref": context.request["bundle_ref"],
                        "affected_claims": affected,
                    },
                    "maintenance_event",
                )
                context.save(ref, event)
            # Re-scan actual cards after a crash between event and state publication.
            updated["blocked_claims"] += [
                b for b in affected if b not in updated["blocked_claims"]
            ]
            processed.add(event_id)
            pending.discard(event_id)
            updated["pending_event_ids"] = sorted(pending)
            updated["impact_scan_watermark"] = event_id
        updated["processed_event_ids"] = sorted(processed)
        final = (
            save_state(context, previous, updated) if updated != previous else previous
        )
    return {
        "event_refs": refs,
        "validity_epoch": final["validity_epoch"],
        "blocked_claims": final["blocked_claims"],
    }, "registered"


def advance(context):
    request = context.request
    if not request.get("apply_result_ref") or not request.get("generation_ref"):
        raise NodeError(
            "VERIFIED_REVIEW_REQUIRED",
            "Applied review and actual activated generation are required",
            blocked=True,
        )
    with writer_lock(context):
        previous = state(context)
        if previous.get("pending_event_ids"):
            raise NodeError(
                "EVENT_RECOVERY_REQUIRED",
                "Source event publication must finish before clearing blocks",
                blocked=True,
            )
        applied = context.record(request["apply_result_ref"], "apply_result")
        verification = context.call(
            "hs-knowledge-apply",
            {
                "operation_id": applied["operation_id"],
                "apply_result_ref": request["apply_result_ref"],
            },
            "verify-result",
        )
        if not verification["data"].get("result_verified"):
            raise NodeError(
                "VERIFIED_REVIEW_REQUIRED",
                "Apply authority could not be verified",
                blocked=True,
            )
        generation = context.call(
            "hs-knowledge-index-build",
            {
                "operation_id": context.operation,
                "generation_ref": request["generation_ref"],
            },
            "verify",
        )["data"]
        if (
            not generation.get("verified")
            or generation.get("validity_epoch") != previous["validity_epoch"]
        ):
            raise NodeError(
                "STALE_GENERATION",
                "Reviewed generation does not bind the current validity epoch",
                blocked=True,
            )
        active_ref = "artifacts/indexes/" + generation["channel"] + "/active.json"
        active = read_json(safe(context.root, active_ref))
        if (
            active.get("generation_ref") != request["generation_ref"]
            or active.get("generation_id") != generation["generation_id"]
        ):
            raise NodeError(
                "GENERATION_NOT_ACTIVE",
                "Review generation is not actually active",
                blocked=True,
            )
        view = context.record(applied["view_ref"], "final_view")
        if view["digest"] != applied["view_digest"]:
            raise NodeError("APPLIED_VIEW_CHANGED", "Apply proof and exact view differ")
        reviewed_cards = {}
        for write in view["writes"]:
            path = write["path"]
            if not path.startswith("knowledge/") or path.endswith("/index.md"):
                continue
            raw = base64.b64decode(write["bytes_b64"], validate=True)
            if (
                sha(raw) != write["final_digest"]
                or fixed_bytes(context.root, path) != raw
            ):
                raise NodeError(
                    "APPLIED_CARD_CHANGED",
                    "Reviewed Card bytes differ from current knowledge",
                    path,
                )
            card = context.modules["knowledge"].parse_card(raw, path, context.rules)
            reviewed_cards[card["metadata"]["id"]] = card
        remaining, cleared = [], []
        for block in previous["blocked_claims"]:
            card = reviewed_cards.get(block["card_id"])
            if card is None:
                remaining.append(block)
                continue
            metadata = card["metadata"]
            if metadata["lifecycle"] == "deprecated":
                cleared.append(block)
                continue
            claim = next(
                (c for c in metadata["claims"] if c["id"] == block["claim_id"]), None
            )
            if claim is None:
                cleared.append(
                    block
                )  # exact accepted write explicitly removed this old Claim.
                continue
            sources = {s["evidence_ref"]: s for s in metadata["sources"]}
            refs = [
                sources[r]
                for r in claim["source_refs"]
                if sources[r]["source_id"] == block["source_id"]
            ]
            if not refs or any(
                r["snapshot_id"] != block["new_snapshot_id"] for r in refs
            ):
                remaining.append(block)
                continue
            for ref in refs:
                resolved = context.call(
                    "hs-knowledge-source-capture",
                    {"operation_id": context.operation, "source_ref": ref},
                    "resolve-source",
                )["data"]
                lock = load_yaml(
                    fixed_bytes(context.root, "governance/sources.lock.yaml")
                )
                resource = next(
                    r for r in lock["resources"] if r["source_id"] == ref["source_id"]
                )
                if (
                    sha(fixed_bytes(context.root, resource["path"], ["docs-raw"]))
                    != resolved["sha256"]
                ):
                    raise NodeError(
                        "SOURCE_CHANGED_AGAIN",
                        "Reviewed source changed again; keep current block",
                        blocked=True,
                    )
            cleared.append(block)
        updated = dict(previous)
        updated["blocked_claims"] = remaining
        updated["knowledge_apply_watermark"] = applied["digest"]
        if cleared:
            updated["validity_epoch"] += 1
        result = save_state(context, previous, updated)
    return {
        "cleared_claims": cleared,
        "blocked_claims": remaining,
        "validity_epoch": result["validity_epoch"],
        "knowledge_apply_watermark": result["knowledge_apply_watermark"],
    }, "advanced"


def execute(context):
    action = context.args.action or "status"
    if action == "status":
        return {"state": state(context)}, "inspected"
    if action == "register-source-change":
        return register(context)
    if action == "advance":
        return advance(context)
    raise NodeError(
        "INVALID_ACTION", "Choose status, register-source-change or advance"
    )
