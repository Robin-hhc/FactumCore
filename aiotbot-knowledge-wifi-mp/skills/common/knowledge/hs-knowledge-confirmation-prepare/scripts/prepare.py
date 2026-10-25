"""Freeze an exact human display; never manufactures a decision."""

import base64
import importlib
from pathlib import Path
import secrets
import subprocess
import time

from support import (
    Blocked,
    Invalid,
    atomic_bytes,
    canonical,
    checked_view,
    package_digest,
)


def source_call(ctx, request, payload, action):
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-source-capture")
    if not spec or not ctx.catalog_path:
        raise Blocked(
            "installed source resolver is required before real-source confirmation"
        )
    package = Path(spec["root"]).resolve()
    entry = (package / spec["entry"]).resolve()
    if (
        entry != package / "scripts/cli.py"
        or package_digest(package) != spec["package_digest"]
    ):
        raise Invalid("source resolver differs from trusted catalog")
    base = f".build/operations/{ctx.operation(request)}/source-display-{secrets.token_hex(16)}"
    incoming, outgoing = base + "-request.json", base + "-response.json"
    atomic_bytes(ctx.path(incoming), canonical(payload))
    completed = subprocess.run(
        [
            spec["python"],
            str(entry),
            "--input",
            str(ctx.path(incoming)),
            "--output",
            str(ctx.path(outgoing)),
            "--knowledge-root",
            str(ctx.root),
            "--rules-digest",
            ctx.rules_digest,
            "--catalog",
            ctx.catalog_path,
            "--action",
            action,
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode or not ctx.path(outgoing).is_file():
        raise Blocked("fixed source cannot be resolved for human display")
    response = ctx.read(outgoing)
    if (
        response.get("status") != "ok"
        or response.get("tool_identity", {}).get("package_digest")
        != spec["package_digest"]
        or package_digest(package) != spec["package_digest"]
    ):
        raise Invalid("source display response identity mismatch")
    return response["data"], response["tool_identity"]


def source_bundle_display(ctx, request, view):
    if not view.get("bundle_ref"):
        return None
    data, identity = source_call(
        ctx,
        request,
        {"operation_id": ctx.operation(request), "bundle_ref": view["bundle_ref"]},
        "resolve",
    )
    if data.get("bundle_ref") != view["bundle_ref"]:
        raise Invalid("resolved bundle reference differs from final view")
    bundle = data["bundle"]
    return {
        "bundle_ref": view["bundle_ref"],
        "bundle_digest": bundle["digest"],
        "resources": bundle["resources"],
        "snapshots": bundle["snapshots"],
        "extractions": bundle.get("extractions", []),
        "limitations": bundle.get("limitations", []),
        "resolver_identity": identity,
    }


def source_displays(ctx, request, view):
    if ctx.domain is None:
        if view.get("source_refs"):
            raise Blocked(
                "domain validation is required to display fixed source evidence"
            )
        return []
    knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
    references = {}
    for row in view["writes"]:
        path = row["path"]
        if (
            not path.startswith("knowledge/")
            or not path.endswith(".md")
            or Path(path).name in ("AGENTS.md", "index.md")
        ):
            continue
        card = knowledge.parse_card(
            base64.b64decode(row["bytes_b64"], validate=True), path, ctx.rules
        )
        for source in card["metadata"]["sources"]:
            references[canonical(source)] = source
    if not references:
        return []
    lock = ctx.domain.load_yaml(ctx.path("governance/sources.lock.yaml").read_bytes())
    registered = {item["snapshot_id"] for item in lock["snapshots"]}
    result = []
    for source in references.values():
        payload = {"operation_id": ctx.operation(request), "source_ref": source}
        if source["snapshot_id"] not in registered:
            if not view.get("bundle_ref"):
                raise Blocked("new source has no fixed capture bundle")
            payload["bundle_ref"] = view["bundle_ref"]
        data, identity = source_call(ctx, request, payload, "resolve-source")
        if data.get("source_ref") != source:
            raise Invalid("resolved source does not match exact card reference")
        result.append({**data, "resolver_identity": identity})
    return result


def prepare(ctx, request):
    view = checked_view(ctx, request)
    if view.get("review_mode") not in {"manual_document", "mixed"}:
        raise Blocked("code views require code evidence, not manual-document review")
    if view.get("v3_required") or request.get("v3_required"):
        if ctx.domain is None:
            raise Blocked("versioned fixed checks are required before human display")
        import importlib

        checks = importlib.import_module(ctx.domain.__package__ + ".checks")
        checked = checks.prepare_view(ctx.root, view, mode="candidate", identity={"view_digest": view["digest"]})
        report = checks.run(checked, ctx.rules, request.get("check_inputs"), scope="full")
        checks.validate_report(report, expected_rules=ctx.rules_digest, required_scope="full")
        if report["exit_code"] != 0:
            raise Blocked("fixed preflight must pass before presenting the exact view")
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
    bundle_display = source_bundle_display(ctx, request, view)
    if bundle_display is not None:
        sections.append(
            "FIXED SOURCE BUNDLE AND ATTACHMENT LIMITATIONS\n"
            + canonical(bundle_display).decode()
        )
    sources = source_displays(ctx, request, view)
    for source in sources:
        sections.append(
            "SOURCE "
            + canonical(source["source_ref"]).decode()
            + "\n"
            + (
                source.get("text")
                or "Opaque attachment: preserved bytes; no extracted-text claim"
            )
            + "\nLIMITATIONS "
            + canonical(source.get("limitations", [])).decode()
        )
    if checked_view(ctx, request)["digest"] != view["digest"]:
        raise Blocked("view changed while preparing source display")
    record = ctx.record(
        "confirmation_display",
        op,
        source_displays=sources,
        source_bundle_display=bundle_display,
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
