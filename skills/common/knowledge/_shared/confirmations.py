"""Interactive document review adapter. Terminal access is a host trust boundary, not an ACL."""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import changes, contracts, receipts, sources

DECISIONS = {
    "accepted",
    "confirmed_no_impact",
    "partially_accepted",
    "returned",
    "deferred",
    "deprecated",
}


def _visible(value):
    return "".join(
        char if char in "\n\t" or (ord(char) >= 32 and ord(char) != 127) else f"\\u{ord(char):04x}"
        for char in value
    )


def _bindings(view):
    return {
        key: view[key]
        for key in (
            "baseline_digest",
            "target_file_digests",
            "source_set_digest",
            "scope_digest",
            "source_snapshot_refs",
            "card_ids",
        )
    }


def confirm_document(
    knowledge_root,
    operation_id,
    *,
    decision,
    confirmed_by,
    input_stream=None,
    output_stream=None,
    claim_ids=None,
):
    root = Path(knowledge_root).resolve(strict=True)
    terminal = sys.stdin if input_stream is None else input_stream
    output = sys.stderr if output_stream is None else output_stream
    if not getattr(terminal, "isatty", lambda: False)():
        changes.fail(
            "HUMAN_ACTION_REQUIRED", "Run interactive confirmation in a human-controlled terminal"
        )
    if (
        decision not in DECISIONS
        or not isinstance(confirmed_by, str)
        or not confirmed_by.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in confirmed_by)
    ):
        changes.fail(
            "INVALID_REVIEW", "Choose an explicit review decision and self-declared contributor"
        )
    view = changes.checked_view(root, operation_id)
    changes.check_baseline(root, view["baseline"])
    claim_ids = list(view["claim_ids"] if claim_ids is None else claim_ids)
    if not set(claim_ids) <= set(view["claim_ids"]) or len(set(claim_ids)) != len(claim_ids):
        changes.fail("INVALID_REVIEW", "Unknown or repeated selected Claim ID")
    if decision in {"accepted", "confirmed_no_impact"} and set(claim_ids) != set(view["claim_ids"]):
        changes.fail("INVALID_REVIEW", "Use partially_accepted to select a strict Claim subset")
    selected_claims = set(claim_ids)
    claim_ids = [cid for cid in view["claim_ids"] if cid in selected_claims]
    if decision == "partially_accepted" and (
        not claim_ids or set(claim_ids) == set(view["claim_ids"])
    ):
        # Selection can also be deferred to explicit narrowed final-view authoring.
        claim_ids = []
    directory = changes.operation_dir(operation_id)
    request = changes.load_plan(root, operation_id)["request"]
    capture = sources.load_capture(root, request["bundle_ref"], request["manifest_digest"])
    print(f"Operation: {operation_id}\nFinal view SHA256: {view['final_view_digest']}", file=output)
    print(
        "Review exact proposed files, source text and opaque attachment limitations below.",
        file=output,
    )
    for path, digest in view["target_file_digests"].items():
        data = changes.safe_path(root, f"{directory}/final-view/{path}").read_bytes()
        if receipts.digest_bytes(data) != digest:
            changes.fail("REVIEW_STALE", "Displayed bytes differ from the fixed view", path)
        print(_visible(f"\n--- {path} SHA256={digest} ---\n" + data.decode("utf-8")), file=output)
    for member in capture["members"]:
        print(
            _visible(f"\n--- Source {member['raw_path']} SHA256={member['object_digest']} ---"),
            file=output,
        )
        if member.get("text") is None:
            print(
                "Opaque attachment: original bytes retained; text/OCR not extracted or verified.",
                file=output,
            )
        else:
            print(_visible(member["text"]), file=output)
    print(
        "Contributor may self-confirm. This does not verify current product code or identity.",
        file=output,
    )
    phrase = f"{decision} {view['final_view_digest'][:12]}"
    print(f"Type exactly: {phrase}", file=output, flush=True)
    action = terminal.readline()
    if not action:
        changes.fail("HUMAN_ACTION_REQUIRED", "No action received; still awaiting confirmation")
    if action.rstrip("\r\n") != phrase:
        changes.fail("CONFIRMATION_MISMATCH", "Decision or final-view challenge did not match")
    # Re-read after the human may have spent time reviewing; no stale action can cover new bytes.
    if changes.checked_view(root, operation_id) != view:
        changes.fail("REVIEW_STALE", "Final view changed while reviewing")
    changes.check_baseline(root, view["baseline"])
    review_id = "review-" + uuid.uuid4().hex
    ref = f"logs/document-reviews/{review_id}.json"
    record = {
        "schema_version": "1.0",
        "record_kind": "manual_review",
        "review_id": review_id,
        "operation_id": operation_id,
        "review_mode": "manual_document",
        **_bindings(view),
        "claim_decisions": [{"claim_id": cid, "decision": decision} for cid in claim_ids],
        "decision": decision,
        "confirmed_by": confirmed_by,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "confirmation_ref": f"interactive-terminal:{review_id}",
        "limitations": [
            "Self-declared identity; host controls who operates the terminal and writes records.",
            "Document semantics are confirmed by the contributor; no code lint or current-code proof.",
        ],
        "extensions": {
            "changeset_digest": receipts.digest_json(view),
            "final_view_digest": view["final_view_digest"],
            "fingerprints": view["fingerprints"],
            "plan_digest": view["plan_digest"],
            "human_channel": "interactive_terminal",
            "challenge": phrase,
            "requires_new_view": decision == "partially_accepted",
        },
    }
    if contracts.validate_document("record", record, root):
        changes.fail("INVALID_REVIEW", "Review does not satisfy locked record contract")
    changes.atomic_write(root, ref, changes.json_bytes(record))
    return {
        "operation_id": operation_id,
        "review_ref": ref,
        "review_digest": receipts.digest_json(record),
        "decision": decision,
        "phase": "confirmed"
        if decision in {"accepted", "confirmed_no_impact"}
        else "needs_new_view"
        if decision == "partially_accepted"
        else decision,
    }


def validate_review(
    knowledge_root, operation_id, review_ref, *, allowed_decisions=None, record_bytes=None
):
    root = Path(knowledge_root).resolve(strict=True)
    if (
        not isinstance(review_ref, str)
        or not review_ref.startswith("logs/document-reviews/review-")
        or not review_ref.endswith(".json")
        or len(Path(review_ref).parts) != 3
    ):
        changes.fail("REVIEW_STALE", "Expected a persistent manual review reference")
    data = (
        changes.safe_path(root, review_ref).read_bytes() if record_bytes is None else record_bytes
    )
    if not isinstance(data, bytes):
        changes.fail("REVIEW_STALE", "Expected fixed review bytes")
    record = contracts.load_document_bytes(data, review_ref)
    if (
        contracts.validate_document("record", record, root)
        or record.get("record_kind") != "manual_review"
    ):
        changes.fail("REVIEW_STALE", "Invalid manual review record")
    view = changes.checked_view(root, operation_id)
    try:
        changes.check_baseline(root, view["baseline"])
    except changes.ChangeError as exc:
        if exc.code == "BASELINE_CHANGED":
            changes.fail("REVIEW_STALE", "Relevant baseline changed after confirmation", exc.path)
        raise
    if record["operation_id"] != operation_id or any(
        record[k] != v for k, v in _bindings(view).items()
    ):
        changes.fail("REVIEW_STALE", "Review belongs to different inputs or operation")
    extensions = record.get("extensions", {})
    expected = {
        "changeset_digest": receipts.digest_json(view),
        "final_view_digest": view["final_view_digest"],
        "fingerprints": view["fingerprints"],
        "plan_digest": view["plan_digest"],
    }
    if any(extensions.get(k) != v for k, v in expected.items()):
        changes.fail("REVIEW_STALE", "Review binding differs from the exact view")
    if extensions.get("human_channel") != "interactive_terminal" or not record[
        "confirmation_ref"
    ].startswith("interactive-terminal:"):
        changes.fail("HUMAN_ACTION_REQUIRED", "No supported human-action adapter reference")
    if (
        record["confirmation_ref"] != f"interactive-terminal:{record['review_id']}"
        or review_ref != f"logs/document-reviews/{record['review_id']}.json"
        or extensions.get("challenge") != f"{record['decision']} {view['final_view_digest'][:12]}"
    ):
        changes.fail("REVIEW_STALE", "Human-action receipt identity differs")
    allowed = (
        {"accepted", "confirmed_no_impact"} if allowed_decisions is None else set(allowed_decisions)
    )
    if record["decision"] not in allowed:
        changes.fail("REVIEW_NOT_ACCEPTED", "This decision does not authorize apply")
    if record["decision"] in {"accepted", "confirmed_no_impact"} and record["claim_decisions"] != [
        {"claim_id": cid, "decision": record["decision"]} for cid in view["claim_ids"]
    ]:
        changes.fail("REVIEW_STALE", "Accepted decision must cover the entire exact view")
    if changes.safe_path(root, review_ref).read_bytes() != data:
        changes.fail("REVIEW_STALE", "Review file changed while verifying the captured bytes")
    return record


def narrow_document(knowledge_root, operation_id, *, review_ref, new_operation_id, candidate):
    """Author an explicit smaller card, then require a new human action on its exact view."""
    root = Path(knowledge_root).resolve(strict=True)
    review = validate_review(
        root, operation_id, review_ref, allowed_decisions={"partially_accepted"}
    )
    old = changes.checked_view(root, operation_id)
    request = changes.load_plan(root, operation_id)["request"]
    capture = sources.load_capture(root, request["bundle_ref"], request["manifest_digest"])
    lock = changes.merged_sources(root, capture)
    from .cards import parse_card

    parsed = parse_card(candidate, root, source_snapshots=lock["snapshots"])
    meta = parsed["metadata"]
    previous = parse_card(
        changes.safe_path(
            root, f"{changes.operation_dir(operation_id)}/final-view/{request['target_path']}"
        ).read_bytes(),
        root,
        source_snapshots=lock["snapshots"],
    )
    subset = {claim["id"] for claim in meta["claims"]}
    if [meta["id"]] != old["card_ids"] or not subset < set(old["claim_ids"]):
        changes.fail(
            "INVALID_PARTIAL_VIEW", "Narrowing requires the same card and a strict Claim subset"
        )
    selected = {item["claim_id"] for item in review["claim_decisions"]}
    if selected and subset != selected:
        changes.fail("INVALID_PARTIAL_VIEW", "New view must match the human-selected Claim set")
    old_claims = {claim["id"]: claim for claim in previous["metadata"]["claims"]}
    if meta["scope"] != previous["metadata"]["scope"] or not set(meta["sources"]) <= set(
        previous["metadata"]["sources"]
    ):
        changes.fail(
            "INVALID_PARTIAL_VIEW", "Partial selection cannot change scope or introduce sources"
        )
    for claim in meta["claims"]:
        cid = claim["id"]
        span, old_span = parsed["claim_spans"][cid], previous["claim_spans"][cid]
        if (
            claim != old_claims[cid]
            or parsed["body"][span["start"] : span["end"]].strip()
            != previous["body"][old_span["start"] : old_span["end"]].strip()
        ):
            changes.fail(
                "INVALID_PARTIAL_VIEW",
                "Retained Claim must remain unchanged; revisions need a new explicit plan",
            )
    changes.create_plan(
        root,
        operation_id=new_operation_id,
        bundle_ref=request["bundle_ref"],
        manifest_digest=request["manifest_digest"],
        decision=request["decision"],
        rationale=f"Narrowed after {review_ref}; new confirmation required.",
        target_path=request["target_path"],
        candidate=candidate,
    )
    result = changes.materialize(root, new_operation_id)
    return {**result, "parent_operation_id": operation_id, "requires_new_confirmation": True}
