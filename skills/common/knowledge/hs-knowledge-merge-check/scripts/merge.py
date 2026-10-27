"""Check current code against the exact view through the installed business checker."""

import pathlib
import secrets
import subprocess
import sys

from support import (
    Blocked,
    Invalid,
    atomic_bytes,
    canonical,
    checked_view,
)


def merge_check(ctx, request):
    op = ctx.operation(request)
    view = checked_view(ctx, request)
    if view.get("review_mode") != "code_gate":
        raise Invalid("pure-document views are exempt from merge code checks")
    package = pathlib.Path(__file__).resolve().parents[2] / "hs-knowledge-local-check"
    if not (package / "scripts/cli.py").is_file():
        spec = ctx.catalog.get("skills", {}).get("hs-knowledge-local-check", {})
        package = pathlib.Path(spec.get("root", package))
    entry = package / "scripts/cli.py"
    if not entry.is_file():
        raise Blocked("installed code evidence Skill is unavailable")
    nonce = secrets.token_hex(12)
    request_ref = f".build/operations/{op}/merge-engine-{nonce}-request.json"
    response_ref = f".build/operations/{op}/merge-engine-{nonce}-response.json"
    child_request = {key: value for key, value in request.items() if key != "workflow"}
    atomic_bytes(ctx.path(request_ref), canonical(child_request))
    before_view = ctx.path(request["view_ref"]).read_bytes()
    source_lock = ctx.path("governance/sources.lock.yaml")
    before_lock = source_lock.read_bytes()
    completed = subprocess.run(
        [
            sys.executable,
            str(entry),
            "--input",
            str(ctx.path(request_ref)),
            "--output",
            str(ctx.path(response_ref)),
            "--knowledge-root",
            str(ctx.root),
            "--rules-digest",
            ctx.rules_digest,
            "--action",
            "merge",
        ],
        check=False,
        capture_output=True,
        timeout=120,
    )
    if completed.returncode != 0 or not ctx.path(response_ref).is_file():
        raise Blocked("public merge evidence check is unavailable or invalid")
    response = ctx.read(response_ref)
    if (
        response.get("status") != "ok"
        or response.get("data", {}).get("mode") != "merge"
    ):
        raise Invalid("public merge evidence result binding mismatch")
    checked = ctx.read(response["data"]["merge_check_ref"])
    if (
        checked.get("mode") != "merge"
        or checked.get("view_digest") != view["digest"]
        or checked.get("status") not in ("passed", "failed", "incomplete")
    ):
        raise Invalid("merge proof has invalid exact-view status")
    if (
        ctx.path(request["view_ref"]).read_bytes() != before_view
        or source_lock.read_bytes() != before_lock
    ):
        raise Blocked("merge check inputs changed; no repair is attempted")
    ref = f"logs/operations/{op}/merge-check-{nonce}.json"
    record = ctx.record(
        "merge_check",
        op,
        view_ref=request["view_ref"],
        view_digest=view["digest"],
        status=checked["status"],
        mode="merge",
        claims=checked.get("claims", []),
        gaps=checked.get("gaps", []),
        delegated_proof_ref=response["data"]["merge_check_ref"],
        delegated_proof_digest=checked["digest"],
        delegated_result_ref=response_ref,
        code_identity=checked.get("code_identity"),
        verification_tier=checked.get("verification_tier", "incomplete"),
        ci_policy_installed=False,
    )
    ctx.save(ref, record)
    return {
        "merge_check_ref": ref,
        "check_status": checked["status"],
        "mode": "merge",
        "phase": checked["status"],
    }
