"""Source events and current validity state, independent from index generations."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import os

from .runtime import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
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
                context.modules["knowledge"].decode_card(
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
        change = event["change"]
        resource = event.get("source_resource", {})
        if (
            snapshot.get("source_id") != change.get("source_id")
            or snapshot.get("snapshot_id") != change.get("new_snapshot_id")
            or snapshot.get("sha256") != change.get("new_sha256")
            or resource.get("source_id") != change.get("source_id")
            or (
                change.get("source_kind") == "code"
                and any(resource.get(key) != change.get(key) for key in ("repo_id", "path"))
            )
            or (change.get("source_kind") == "code" and resource.get("kind") != "code")
        ):
            raise NodeError(
                "EVENT_CONFLICT",
                "Pending source payload differs from its durable change",
            )
        recovery = snapshot["recovery"]
        try:
            original = fixed_bytes(
                context.root,
                recovery.get("path", recovery.get("reference")),
                ["logs/evidence"],
            )
        except (OSError, ValueError) as exc:
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "Pending event original bytes are unavailable"
            ) from exc
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
        data = context.modules["source_operations"].recovered_bytes(context, snapshot)
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
            resolved = context.modules["source_operations"].resolve_source(context, ({'operation_id': context.operation, 'bundle_ref': context.request['bundle_ref'], 'source_ref': {'evidence_ref': 'current-code', 'source_id': snapshot['source_id'], 'snapshot_id': snapshot['snapshot_id'], 'locator': {'kind': 'bytes', 'start': 0, 'end': snapshot['bytes']}}})["source_ref"], bundle=bundle)
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


def advance(context):
    """Recheck stale-source restrictions from current cards and actual sources."""
    with writer_lock(context):
        previous = state(context)
        if previous.get("pending_event_ids"):
            raise NodeError(
                "EVENT_RECOVERY_REQUIRED",
                "Source event publication must finish before updating restrictions",
                blocked=True,
            )
        cards = {card["metadata"]["id"]: card for card in domain_cards(context)}
        source_lock = context.modules["source_resources"].read_source_lock(context.root)
        rules = {**context.rules, "source_lock": source_lock}
        for card in cards.values():
            context.modules["knowledge"].validate_card(card, cards, rules)
        context.modules["knowledge"].validate_relations(cards)
        before = {card["path"]: card["sha256"] for card in cards.values()}
        remaining, cleared = [], []
        freshness_reasons = {"source_changed", "code_changed", "code_source_changed"}
        for block in previous["blocked_claims"]:
            # Source-byte checks cannot clear semantic/applicability restrictions.
            if block.get("reason") not in freshness_reasons or block["card_id"] == "*":
                remaining.append(block)
                continue
            card = cards.get(block["card_id"])
            if card is None or card["metadata"]["lifecycle"] == "deprecated":
                cleared.append(block)
                continue
            claim = next((row for row in card["claims"] if row["id"] == block["claim_id"]), None)
            if claim is None and block["claim_id"] != "*":
                cleared.append(block)
                continue
            claims = [claim] if claim is not None else card["claims"]
            refs = [source for row in claims for source in row["source_records"]
                    if not block.get("source_id") or source["source_id"] == block["source_id"]]
            latest = previous.get("observed_sources", {}).get(block.get("source_id"), {}).get("snapshot_id")
            if not refs or (latest and any(source["snapshot_id"] != latest for source in refs)):
                remaining.append(block)
                continue
            current = True
            for source in refs:
                try:
                    resolved = context.modules["source_operations"].resolve_source(context, ({'operation_id': context.operation, 'source_ref': source})["source_ref"])
                    current = current and resolved.get("current_source_matches") is True
                except (ValueError, OSError, KeyError):
                    current = False
            (cleared if current else remaining).append(block)
        for path, expected in before.items():
            if sha(fixed_bytes(context.root, path)) != expected:
                raise NodeError("KNOWLEDGE_CHANGED", "Cards changed while checking restrictions", path, blocked=True)
        updated = copy.deepcopy(previous)
        updated["blocked_claims"] = remaining
        if cleared:
            updated["validity_epoch"] += 1
        result = save_state(context, previous, updated)
    return {
        "cleared_claims": cleared,
        "blocked_claims": remaining,
        "validity_epoch": result["validity_epoch"],
        "knowledge_apply_watermark": result["knowledge_apply_watermark"],
        "verification_tier": "current_source_bytes_only",
    }, "advanced"


def inspect_context(context):
    """Reconstruct current restrictions; no event registration or knowledge writes."""
    cards = domain_cards(context)
    try:
        config_path = context.modules["validation"].workspace_config_path(context.root)
        config_digest = sha(config_path.read_bytes())
    except (ValueError, OSError):
        config_digest = None
    cached, affected, gaps, navigation_observations = {}, [], [], {}
    record_root = context.root / "logs/ingest"
    if record_root.exists():
        for path in sorted(record_root.iterdir()):
            if path.suffix not in {".yaml", ".yml", ".json"}:
                continue
            ref = path.relative_to(context.root).as_posix()
            try:
                record = load_yaml(fixed_bytes(context.root, ref, ["logs/ingest"]))
                context.modules["records"].validate_ingest_record(record, rules=context.rules)
            except (ValueError, OSError, KeyError) as exc:
                gaps.append({"code": "PROCESSING_RECORD_UNAVAILABLE", "path": ref, "reason": str(exc)})
    persisted = state(context)
    for card in cards:
        card_id = card["metadata"]["id"]
        for claim in card["claims"]:
            reasons = []
            for source in claim["source_records"]:
                key = digest(source)
                if key not in cached:
                    try:
                        resolved = context.modules["source_operations"].resolve_source(context, ({'operation_id': context.operation, 'source_ref': source})["source_ref"])
                        cached[key] = (None if resolved.get("current_source_matches") is True else "source_changed",
                                       None, resolved)
                    except (ValueError, OSError, KeyError) as exc:
                        cached[key] = ("source_unavailable", str(exc), None)
                reason, details, resolved = cached[key]
                navigation = (resolved or {}).get("code_navigation")
                if "code_ref" in source and navigation is not None:
                    observation = navigation_observations.setdefault((card_id, key), {
                        "card_id": card_id, "claim_ids": [], "source_ref": source,
                        "current_source_matches": resolved.get("current_source_matches"),
                        "current_source_sha256": resolved.get("current_source_sha256"),
                        "code_navigation": navigation,
                    })
                    observation["claim_ids"].append(claim["id"])
                if claim["usage"] == "guidance" and "code_ref" in source and reason != "source_unavailable":
                    if navigation and navigation.get("status") == "resolved":
                        reason = None
                    else:
                        reason = "code_navigation_" + (navigation or {}).get("status", "unavailable")
                        details = (navigation or {}).get("reason", "Current symbolic navigation is unavailable")
                # A recovered historical snapshot need not match today's file.
                # Keep the cached resolver fact shared across all Claim usages.
                if reason and not (claim["usage"] == "historical" and reason == "source_changed"):
                    reasons.append({"reason": reason, "source_id": source["source_id"], "details": details})
            for block in persisted.get("blocked_claims", []):
                if block.get("card_id") in {card_id, "*"} and block.get("claim_id") in {claim["id"], "*"}:
                    if (claim["usage"] == "guidance"
                            and block.get("reason") in {"source_changed", "code_changed", "code_source_changed"}
                            and (block.get("source_id") or block.get("old_snapshot_ids"))):
                        navigation_sources = [source for source in claim["source_records"]
                            if (not block.get("source_id") or source["source_id"] == block["source_id"])
                            and (not block.get("old_snapshot_ids") or source["snapshot_id"] in block["old_snapshot_ids"])]
                        if navigation_sources and all(
                                "code_ref" in source
                                and cached[digest(source)][0] != "source_unavailable"
                                and (cached[digest(source)][2] or {}).get("code_navigation", {}).get("status") == "resolved"
                                for source in navigation_sources):
                            # A navigation observation never clears the durable event
                            # or weakens its effect on current implementation Claims.
                            continue
                    if (claim["usage"] == "historical"
                            and block.get("reason") in {"source_changed", "code_changed", "code_source_changed"}
                            and (block.get("source_id") or block.get("old_snapshot_ids"))):
                        historical_sources = [source for source in claim["source_records"]
                            if (not block.get("source_id") or source["source_id"] == block["source_id"])
                            and (not block.get("old_snapshot_ids") or source["snapshot_id"] in block["old_snapshot_ids"])]
                        if historical_sources and all(cached[digest(source)][0] != "source_unavailable"
                                                      for source in historical_sources):
                            # This source-specific freshness event does not change
                            # recoverable history. Retain the durable event/state.
                            continue
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
    result = {"complete": not gaps, "affected_claims": affected, "gaps": gaps,
              "rules_digest": context.args.rules_digest, "config_digest": config_digest,
              "state": persisted}
    if navigation_observations:
        result["code_navigation"] = list(navigation_observations.values())
    return result, "inspected"


def execute(context):
    action = context.args.action or "inspect-context"
    if action == "audit-references":
        from .reference_audit import audit_references
        return audit_references(context)
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


def register_source_change(ctx, request):
    """Register the same exact raw-source event without a sibling process."""
    from .runtime import fork_context
    return register(fork_context(ctx, request, action="register-source-change"), code=False)[0]
