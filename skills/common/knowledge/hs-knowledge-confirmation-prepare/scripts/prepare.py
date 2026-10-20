"""Freeze an exact human display; never manufactures a decision."""

import base64
import secrets
import time

from support import Blocked, checked_view


def prepare(ctx, request):
    view = checked_view(ctx, request)
    if view.get("review_mode") != "manual_document":
        raise Blocked("code views require code evidence, not manual-document review")
    op = ctx.operation(request)
    reference = f".build/operations/{op}/confirmation-display.json"
    if ctx.path(reference).exists():
        prior = ctx.read(reference)
        if prior.get("view_digest") != view["digest"]:
            raise Blocked("display already binds another view; create a new operation")
        return {
            "display_ref": reference,
            "display_digest": prior["digest"],
            "phase": "awaiting_human",
        }
    now = time.time()
    sections = ["Exact final view: " + view["digest"]]
    for row in view["writes"]:
        content = base64.b64decode(row["bytes_b64"], validate=True)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = "BASE64 EXACT BINARY:\n" + row["bytes_b64"]
        sections.append(
            "WRITE "
            + row["path"]
            + "\nOLD "
            + str(row["expected_old_digest"])
            + "\nFINAL "
            + row["final_digest"]
            + "\n"
            + text
        )
    for row in view.get("deletes", []):
        sections.append(
            "DELETE " + row["path"] + "\nOLD " + str(row["expected_old_digest"])
        )
    record = ctx.record(
        "confirmation_display",
        op,
        view_ref=request["view_ref"],
        view_digest=view["digest"],
        source_refs=view.get("source_refs", []),
        source_set_digest=view.get("source_set_digest"),
        source_tool_identity=view.get("tool_identity"),
        writes=view["writes"],
        deletes=view.get("deletes", []),
        display_text="\n\n".join(sections),
        challenge=secrets.token_hex(32),
        created_at=now,
        expires_at=now + 86400,
        display_encoding="utf8-plus-base64-exact-bytes",
        warning="Human must inspect every exact write and deletion before host approval.",
    )
    ctx.save(reference, record)
    return {
        "display_ref": reference,
        "display_digest": record["digest"],
        "phase": "awaiting_human",
    }
