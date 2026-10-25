"""Source events and current validity state, independent from index generations."""

from __future__ import annotations

import base64
import copy
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
        "pending_events": [],
        "observed_sources": {},
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


def finish_pending(context, previous):
    events = previous.get("pending_events", [])
    if {e["event_id"] for e in events} != set(previous.get("pending_event_ids", [])):
        raise NodeError(
            "EVENT_RECOVERY_REQUIRED",
            "Pending event state lacks its complete durable payload",
            blocked=True,
        )
    if not events:
        return previous
    updated = copy.deepcopy(previous)
    processed = set(previous.get("processed_event_ids", []))
    observed = dict(previous.get("observed_sources", {}))
    for event in events:
        context.modules["records"].verify(event)
        context.modules["validation"].validate_shape(
            "maintenance_event", event, context.rules
        )
        if (
            event["event_id"] != digest(event["change"])
            or event["rules_digest"] != context.args.rules_digest
        ):
            raise NodeError(
                "EVENT_CONFLICT",
                "Pending event identity differs from its durable change",
            )
        snapshot = event["source_snapshot"]
        recovery = snapshot["recovery"]
        original = fixed_bytes(
            context.root,
            recovery.get("path", recovery.get("reference")),
            ["logs/evidence"],
        )
        if sha(original) != snapshot["sha256"] or len(original) != snapshot["bytes"]:
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "Pending event original bytes are unavailable"
            )
        context.save("logs/events/" + event["event_id"] + ".json", event)
        processed.add(event["event_id"])
        updated["impact_scan_watermark"] = event["event_id"]
        observed[event["change"]["source_id"]] = {
            "snapshot_id": event["change"]["new_snapshot_id"],
            "event_id": event["event_id"],
        }
    updated.update(
        processed_event_ids=sorted(processed),
        pending_event_ids=[],
        pending_events=[],
        observed_sources=observed,
    )
    return save_state(context, previous, updated)


def register(context, *, code=False):
    bundle = context.record(context.request["bundle_ref"], "source_bundle")
    lock = load_yaml(fixed_bytes(context.root, "governance/sources.lock.yaml"))
    changes = []
    for snapshot in bundle["snapshots"]:
        recovery = snapshot["recovery"]
        data = fixed_bytes(
            context.root,
            recovery.get("path", recovery.get("reference")),
            ["logs/evidence"],
        )
        if sha(data) != snapshot["sha256"] or len(data) != snapshot["bytes"]:
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "New source snapshot bytes cannot be verified"
            )
        resource = next(
            r for r in bundle["resources"] if r["source_id"] == snapshot["source_id"]
        )
        if code:
            if resource.get("kind") != "code":
                raise NodeError(
                    "INVALID_SOURCE_KIND", "Code change needs a registered code bundle"
                )
            resolved = context.call(
                "hs-knowledge-source-capture",
                {
                    "operation_id": context.operation,
                    "bundle_ref": context.request["bundle_ref"],
                    "source_ref": {
                        "evidence_ref": "current-code",
                        "source_id": snapshot["source_id"],
                        "snapshot_id": snapshot["snapshot_id"],
                        "locator": {
                            "kind": "bytes",
                            "start": 0,
                            "end": snapshot["bytes"],
                        },
                    },
                },
                "resolve-source",
            )["data"]
            current = resolved.get("current_source_matches") is True
            if (
                resolved.get("source_kind") != "code"
                or resolved.get("resource") != resource
            ):
                raise NodeError(
                    "SOURCE_IDENTITY_CHANGED",
                    "Public resolver differs from code registration",
                )
        else:
            if resource.get("kind") not in {"raw", "attachment"}:
                raise NodeError(
                    "INVALID_SOURCE_KIND", "Use register-code-change for code"
                )
            current = (
                sha(fixed_bytes(context.root, resource["path"], ["docs-raw"]))
                == snapshot["sha256"]
            )
        if not current:
            raise NodeError(
                "SOURCE_CHANGED",
                "New source changed again before event registration",
                blocked=True,
            )
        previous = [
            s for s in lock["snapshots"] if s["source_id"] == snapshot["source_id"]
        ]
        prior_resources = [
            r for r in lock["resources"] if r["source_id"] == snapshot["source_id"]
        ]
        if previous and prior_resources != [resource]:
            raise NodeError(
                "SOURCE_IDENTITY_CHANGED",
                "Logical source cannot be moved to another resource",
            )
        if previous and snapshot["snapshot_id"] not in {
            s["snapshot_id"] for s in previous
        }:
            changes.append(
                {
                    "source_id": snapshot["source_id"],
                    "old_snapshot_ids": sorted(s["snapshot_id"] for s in previous),
                    "new_snapshot_id": snapshot["snapshot_id"],
                    "new_sha256": snapshot["sha256"],
                    **(
                        {
                            "source_kind": "code",
                            "repo_id": resource["repo_id"],
                            "path": resource["path"],
                        }
                        if code
                        else {}
                    ),
                }
            )
    with writer_lock(context):
        previous = finish_pending(context, state(context))
        updated = copy.deepcopy(previous)
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
                                "reason": "code_changed" if code else "source_changed",
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
                snapshot = next(
                    s
                    for s in bundle["snapshots"]
                    if s["snapshot_id"] == change["new_snapshot_id"]
                )
                resource = next(
                    r
                    for r in bundle["resources"]
                    if r["source_id"] == change["source_id"]
                )
                staged_event = context.seal(
                    {
                        "event_id": event_id,
                        "change": change,
                        "bundle_ref": context.request["bundle_ref"],
                        "bundle_digest": bundle["digest"],
                        "source_snapshot": snapshot,
                        "source_resource": resource,
                        "affected_claims": affected,
                    },
                    "maintenance_event",
                )
                updated["pending_events"] = [
                    *previous.get("pending_events", []),
                    staged_event,
                ]
                previous = save_state(context, previous, updated)
                updated = copy.deepcopy(previous)
            if safe(context.root, ref).exists():
                event = context.record(ref, "maintenance_event")
                if event.get("change") != change:
                    raise NodeError(
                        "EVENT_CONFLICT",
                        "Existing event differs from source transition",
                    )
            else:
                event = next(
                    e for e in updated["pending_events"] if e["event_id"] == event_id
                )
                context.save(ref, event)
            # Re-scan actual cards after a crash between event and state publication.
            updated["blocked_claims"] += [
                b for b in affected if b not in updated["blocked_claims"]
            ]
            processed.add(event_id)
            pending.discard(event_id)
            updated["pending_event_ids"] = sorted(pending)
            updated["pending_events"] = [
                e for e in updated["pending_events"] if e["event_id"] != event_id
            ]
            observed = dict(updated.get("observed_sources", {}))
            observed[change["source_id"]] = {
                "snapshot_id": change["new_snapshot_id"],
                "event_id": event_id,
            }
            updated["observed_sources"] = observed
            updated["impact_scan_watermark"] = event_id
            updated["processed_event_ids"] = sorted(processed)
            previous = save_state(context, previous, updated)
            updated = copy.deepcopy(previous)
        updated["processed_event_ids"] = sorted(processed)
        final = (
            save_state(context, previous, updated) if updated != previous else previous
        )
    return {
        "event_refs": refs,
        "validity_epoch": final["validity_epoch"],
        "blocked_claims": final["blocked_claims"],
    }, "registered"


def validate_generation_baseline(context, generation):
    paths = [
        path for path in (context.root / "knowledge").rglob("*.md") if path.is_file()
    ]
    paths.append(context.root / "governance/sources.lock.yaml")
    files = {
        path.relative_to(context.root).as_posix(): sha(
            fixed_bytes(context.root, path.relative_to(context.root).as_posix())
        )
        for path in sorted(paths)
    }
    if generation.get("knowledge_baseline") != digest(files):
        raise NodeError(
            "STALE_GENERATION",
            "Active generation does not represent current exact knowledge and source-lock bytes",
            blocked=True,
        )


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
                "purpose": "current",
                **(
                    {"current_code_proof_ref": request["current_code_proof_ref"]}
                    if request.get("current_code_proof_ref")
                    else {}
                ),
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
        validate_generation_baseline(context, generation)
        view = context.record(applied["view_ref"], "final_view")
        if view["digest"] != applied["view_digest"]:
            raise NodeError("APPLIED_VIEW_CHANGED", "Apply proof and exact view differ")
        reviewed_cards = {}
        reviewed_paths = {}
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
            reviewed_paths[card["metadata"]["id"]] = path
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
            if block.get("reason") == "code_changed":
                current_proof = request.get("current_code_proof_ref")
                path = reviewed_paths[block["card_id"]]
                eligible = verification["data"].get("eligible_files", [])
                if (
                    view["review_mode"] != "code_gate"
                    or not current_proof
                    or verification["data"].get("current_code_proof_ref")
                    != current_proof
                    or not any(
                        row.get("path") == path
                        and row.get("sha256") == sha(card["raw"])
                        for row in eligible
                    )
                ):
                    remaining.append(block)
                    continue
                # A fresh signed semantic proof for this exact view establishes
                # current applicability; historical code evidence stays immutable.
                cleared.append(block)
                continue
            sources = {s["evidence_ref"]: s for s in metadata["sources"]}
            refs = [
                sources[r]
                for r in claim["source_refs"]
                if sources[r]["source_id"] == block["source_id"]
            ]
            latest = (
                previous.get("observed_sources", {})
                .get(block["source_id"], {})
                .get("snapshot_id", block["new_snapshot_id"])
            )
            if not refs or any(r["snapshot_id"] != latest for r in refs):
                remaining.append(block)
                continue
            for ref in refs:
                resolved = context.call(
                    "hs-knowledge-source-capture",
                    {"operation_id": context.operation, "source_ref": ref},
                    "resolve-source",
                )["data"]
                if resolved.get("current_source_matches") is not True:
                    raise NodeError(
                        "SOURCE_CHANGED_AGAIN",
                        "Reviewed source changed again; keep current block",
                        blocked=True,
                    )
            cleared.append(block)
        updated = copy.deepcopy(previous)
        updated["blocked_claims"] = remaining
        updated["knowledge_apply_watermark"] = applied["digest"]
        if cleared:
            updated["validity_epoch"] += 1
        validate_generation_baseline(context, generation)
        result = save_state(context, previous, updated)
    return {
        "cleared_claims": cleared,
        "blocked_claims": remaining,
        "validity_epoch": result["validity_epoch"],
        "knowledge_apply_watermark": result["knowledge_apply_watermark"],
    }, "advanced"


def inspect_context(context):
    """Reconstruct current restrictions; no event registration or knowledge writes."""
    cards = domain_cards(context)
    lock = context.modules["source_resources"].read_source_lock(context.root)
    resources = {row["source_id"]: row for row in lock["resources"]}
    config_path = context.root.parent / "config.yml"
    config_digest = sha(config_path.read_bytes()) if config_path.is_file() else None
    cached, affected, gaps, processing_records = {}, [], [], []
    summaries = {}
    record_root = context.root / "logs/ingest"
    if record_root.exists():
        for path in sorted(record_root.iterdir()):
            if path.suffix not in {".yaml", ".yml", ".json"}:
                continue
            ref = path.relative_to(context.root).as_posix()
            try:
                record = load_yaml(fixed_bytes(context.root, ref, ["logs/ingest"]))
                context.modules["records"].validate_ingest_record(record, rules=context.rules)
                processing_records.append(record)
                acceptance = record.get("acceptance", {})
                for row in acceptance.get("cards", []):
                    summaries.setdefault((row.get("path"), row.get("sha256")), []).append(acceptance)
            except (ValueError, OSError, KeyError) as exc:
                gaps.append({"code": "PROCESSING_RECORD_UNAVAILABLE", "path": ref, "reason": str(exc)})
    persisted = state(context)
    shared = context.modules["records"].rebuild_restrictions(processing_records, context.rules, cards=cards)
    gaps.extend(shared["gaps"])
    affected.extend(shared["blocked_claims"])
    for card in cards:
        card_id = card["metadata"]["id"]
        accepted = summaries.get((card["path"], card["sha256"]), [])
        code_context_problem = None
        if card["metadata"]["review_mode"] == "code_gate":
            verified_context = False
            for acceptance in accepted:
                try:
                    context.modules["source_resources"].validate_current_code_identity(
                        acceptance.get("code_identity"), config_path, acceptance.get("config_digest"),
                        context.rules, read_json(context.args.catalog).get("code_policy"),
                    )
                    verified_context = True
                except (ValueError, OSError, KeyError) as exc:
                    code_context_problem = str(exc)
            if not verified_context:
                code_context_problem = code_context_problem or "No exact current code identity in processing records"
            else:
                code_context_problem = None
        for claim in card["claims"]:
            reasons = []
            if code_context_problem:
                reasons.append({"reason": "code_context_unknown_or_changed", "details": code_context_problem})
            for source in claim["source_records"]:
                key = digest(source)
                if key not in cached:
                    try:
                        resolved = context.call(
                            "hs-knowledge-source-capture",
                            {"operation_id": context.operation, "source_ref": source},
                            "resolve-source",
                        )["data"]
                        cached[key] = (None if resolved.get("current_source_matches") is True else "source_changed", None)
                    except (ValueError, OSError, KeyError) as exc:
                        cached[key] = ("source_unavailable", str(exc))
                reason, details = cached[key]
                if reason:
                    reasons.append({"reason": reason, "source_id": source["source_id"], "details": details})
                if resources.get(source["source_id"], {}).get("kind") == "code":
                    identities = {row.get("config_digest") for row in accepted}
                    if not config_digest or config_digest not in identities:
                        reasons.append({"reason": "code_context_unknown_or_changed", "source_id": source["source_id"]})
            if accepted and not any(row.get("rules_digest") == context.args.rules_digest for row in accepted):
                reasons.append({"reason": "rules_changed"})
            for block in persisted.get("blocked_claims", []):
                if block.get("card_id") in {card_id, "*"} and block.get("claim_id") in {claim["id"], "*"}:
                    reasons.append({"reason": block.get("reason", "pending_review")})
            affected.extend({"card_id": card_id, "claim_id": claim["id"], **row} for row in reasons)
    # Explicit dependencies propagate restrictions. Ordinary links never do.
    blocked_cards = {row["card_id"] for row in affected}
    changed = True
    while changed:
        changed = False
        for card in cards:
            card_id = card["metadata"]["id"]
            if card_id in blocked_cards:
                continue
            targets = {row["target_card_id"] for row in card["metadata"]["relations"]
                       if row["type"] in {"requires", "derived_from"} and row["target_card_id"] in blocked_cards}
            if targets:
                affected.extend({"card_id": card_id, "claim_id": claim["id"], "reason": "dependency_not_qualified",
                                 "dependencies": sorted(targets)} for claim in card["claims"])
                blocked_cards.add(card_id)
                changed = True
    return {"complete": not gaps, "affected_claims": affected, "gaps": gaps,
            "rules_digest": context.args.rules_digest, "config_digest": config_digest,
            "state": persisted}, "inspected"


def execute(context):
    action = context.args.action or "status"
    if action == "status":
        return {"state": state(context)}, "inspected"
    if action == "inspect-context":
        return inspect_context(context)
    if action == "register-source-change":
        return register(context)
    if action == "register-code-change":
        return register(context, code=True)
    if action == "recover-events":
        with writer_lock(context):
            recovered = finish_pending(context, state(context))
        return {"state": recovered}, "recovered"
    if action == "advance":
        return advance(context)
    raise NodeError(
        "INVALID_ACTION",
        "Choose status, inspect-context, register-source-change, register-code-change, recover-events or advance",
    )
