"""Persist only an authenticated, exactly bound human decision."""

from support import Blocked, Invalid, authenticated_event, checked_view, strict_json


def record_confirmation(ctx, request):
    op = ctx.operation(request)
    display_ref = request.get("display_ref")
    ctx.path(display_ref, (f".build/operations/{op}",))
    display = ctx.read(display_ref)
    if (
        display.get("record_kind") != "confirmation_display"
        or display.get("operation_id") != op
    ):
        raise Invalid("display identity mismatch")
    view = checked_view(ctx, {"operation_id": op, "view_ref": display.get("view_ref")})
    if (
        view.get("review_mode") != "manual_document"
        or view["digest"] != display.get("view_digest")
        or display.get("writes") != view.get("writes")
        or display.get("deletes") != view.get("deletes")
    ):
        raise Invalid("display no longer matches complete document view")
    event_ref = request.get("host_event_ref")
    if not event_ref:
        raise Blocked("awaiting authentic human decision; silence is not consent")
    event_path = ctx.path(event_ref, (f".build/operations/{op}", "logs/host-events"))
    if not event_path.is_file():
        raise Blocked("awaiting trusted host event")
    event = strict_json(event_path.read_text(encoding="utf-8"))
    tier = authenticated_event(ctx, display, event)
    decision = event["payload"]["decision"]
    proof = ctx.record(
        "manual_review",
        op,
        status="approved" if decision == "approve" else "rejected",
        view_ref=display["view_ref"],
        view_digest=display["view_digest"],
        display_ref=display_ref,
        display_digest=display["digest"],
        host_event=event,
        verification_tier=tier,
    )
    reference = f"logs/operations/{op}/manual-review.json"
    ctx.save(reference, proof)
    return {
        "manual_review_ref": reference,
        "manual_review_digest": proof["digest"],
        "phase": "approved" if decision == "approve" else "rejected",
    }
