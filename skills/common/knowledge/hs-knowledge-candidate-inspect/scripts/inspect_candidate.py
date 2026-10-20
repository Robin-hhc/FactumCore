"""Technical candidate inspection; raw documents do not invoke code lint."""

import base64

from support import NodeError, digest, fixed_bytes, load_yaml, safe, sha


def execute(context):
    request = context.request
    view = context.record(request["view_ref"], "final_view")
    if view["operation_id"] != context.operation:
        raise NodeError("OPERATION_MISMATCH", "Final-view belongs to another operation")
    journals = safe(context.root, "logs/operations")
    if journals.exists():
        for path in journals.glob("*/journal.json"):
            record = context.record(path.relative_to(context.root).as_posix())
            if record.get("status") not in {"committed", "rolled_back"}:
                return {
                    "view_ref": request["view_ref"],
                    "operation_id": record["operation_id"],
                    "journal_ref": path.relative_to(context.root).as_posix(),
                }, "recovery_required"
    plan = context.call(
        "hs-knowledge-change-plan",
        {"operation_id": context.operation, "plan_ref": view["plan_ref"]},
        "verify",
    )["data"]["plan"]
    if plan["digest"] != view["plan_digest"]:
        raise NodeError("PLAN_CHANGED", "Final-view refers to another exact plan")
    targets, baseline, card_writes = {}, {}, {}
    for write in view["writes"]:
        path = write["path"]
        safe(context.root, path, ["knowledge", "governance/sources.lock.yaml"])
        if path in targets or path.casefold() in {p.casefold() for p in targets}:
            raise NodeError("DUPLICATE_WRITE", "Write paths overlap or alias", path)
        raw = base64.b64decode(write["bytes_b64"], validate=True)
        if sha(raw) != write["final_digest"]:
            raise NodeError(
                "FINAL_BYTES_CHANGED", "Final bytes do not match digest", path
            )
        if fixed_bytes(context.root, context.base + "/final-view/" + path) != raw:
            raise NodeError(
                "FINAL_BYTES_CHANGED",
                "Displayed file differs from exact FinalView",
                path,
            )
        targets[path] = raw
        baseline[path] = write["expected_old_digest"]
        if (
            path.startswith("knowledge/")
            and path.endswith(".md")
            and not path.endswith("/index.md")
        ):
            card = context.modules["knowledge"].parse_card(raw, path, context.rules)
            if card["metadata"]["lifecycle"] not in {"stable", "deprecated"}:
                raise NodeError(
                    "INVALID_LIFECYCLE",
                    "Final bytes must already be stable or deprecated",
                )
            card_writes[card["metadata"]["id"]] = card
    for deletion in view["deletes"]:
        ref = deletion["path"]
        if ref in targets:
            raise NodeError(
                "CONFLICTING_WRITE", "Path cannot be both written and deleted", ref
            )
        safe(context.root, ref, ["knowledge"])
        baseline[ref] = deletion["expected_old_digest"]
    if digest({"files": baseline}) != view["baseline_digest"]:
        raise NodeError("BASELINE_CHANGED", "Final-view baseline binding differs")
    for ref, expected in baseline.items():
        path = safe(context.root, ref)
        if (sha(path.read_bytes()) if path.exists() else None) != expected:
            raise NodeError(
                "BASELINE_CHANGED", "Official target changed since planning", ref
            )
    lock = load_yaml(targets["governance/sources.lock.yaml"])
    if (
        digest(lock["snapshots"]) != view["source_set_digest"]
        or lock["snapshots"] != view["source_refs"]
    ):
        raise NodeError("SOURCE_SET_CHANGED", "Final-view source-set binding differs")
    cards = {}
    knowledge = safe(context.root, "knowledge")
    if knowledge.exists():
        for path in knowledge.rglob("*.md"):
            ref = path.relative_to(context.root).as_posix()
            if path.name in {"index.md", "AGENTS.md"} or ref in baseline:
                continue
            card = context.modules["knowledge"].parse_card(
                fixed_bytes(context.root, ref), ref, context.rules
            )
            identity = card["metadata"]["id"]
            if identity in cards or identity in card_writes:
                raise NodeError(
                    "DUPLICATE_CARD_ID",
                    "Current domain contains duplicate Card IDs",
                    identity,
                )
            cards[identity] = card
    cards.update(card_writes)
    rules = {**context.rules, "source_lock": lock}
    claim_ids = set()
    for card in cards.values():
        for claim in card["metadata"]["claims"]:
            claim_identity = (card["metadata"]["id"], claim["id"])
            if claim_identity in claim_ids:
                raise NodeError(
                    "DUPLICATE_CLAIM_ID",
                    "Current domain contains duplicate Claim IDs",
                    claim["id"],
                )
            claim_ids.add(claim_identity)
        context.modules["knowledge"].validate_card(card, None, rules)
    context.modules["knowledge"].validate_relations(cards)
    modes = {c["metadata"]["review_mode"] for c in card_writes.values()}
    if modes != {view["review_mode"]}:
        raise NodeError(
            "REVIEW_MODE_CHANGED", "Final-view and card review modes differ"
        )
    reproduced = context.call(
        "hs-knowledge-view-materialize",
        {"operation_id": context.operation, "plan_ref": view["plan_ref"]},
    )
    if (
        reproduced["data"].get("view_ref") != request["view_ref"]
        or reproduced["data"].get("view_digest") != view["digest"]
    ):
        raise NodeError(
            "VIEW_CHANGED", "Exact view is not reproducible from its fixed plan"
        )
    return {
        "view_ref": request["view_ref"],
        "view_digest": view["digest"],
        "review_mode": view["review_mode"],
        "source_set_digest": view["source_set_digest"],
        "card_ids": sorted(card_writes),
    }, ("manual_ready" if view["review_mode"] == "manual_document" else "code_ready")
