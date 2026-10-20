"""Latest-authorized-code check through the same pinned public evidence engine."""
import pathlib
import re
import secrets
import subprocess

from support import Blocked, Invalid, atomic_bytes, canonical, checked_view, package_digest


def merge_check(ctx, request):
    op = ctx.operation(request)
    view = checked_view(ctx, request)
    if view.get("review_mode") != "code_gate":
        raise Invalid("pure-document views are exempt from merge code checks")
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-local-check")
    if not spec or not ctx.catalog_path:
        raise Blocked("installed trusted code evidence engine is unavailable")
    package = pathlib.Path(spec["root"]).resolve()
    entry = (package / spec.get("entry", "scripts/cli.py")).resolve()
    if entry != package / "scripts/cli.py" or package_digest(package) != spec.get("package_digest"):
        raise Invalid("code evidence engine package identity mismatch")
    nonce = secrets.token_hex(12)
    request_ref = f".build/operations/{op}/merge-engine-{nonce}-request.json"
    response_ref = f".build/operations/{op}/merge-engine-{nonce}-response.json"
    atomic_bytes(ctx.path(request_ref), canonical(request))
    before_view = ctx.path(request["view_ref"]).read_bytes()
    source_lock = ctx.path("governance/sources.lock.yaml")
    before_lock = source_lock.read_bytes()
    completed = subprocess.run([spec["python"], str(entry), "--input", str(ctx.path(request_ref)), "--output", str(ctx.path(response_ref)), "--knowledge-root", str(ctx.root), "--rules-digest", ctx.rules_digest, "--catalog", ctx.catalog_path, "--action", "merge"], check=False, capture_output=True, timeout=120)
    if completed.returncode != 0 or not ctx.path(response_ref).is_file():
        raise Blocked("public merge evidence check is unavailable or invalid")
    response = ctx.read(response_ref)
    if response.get("status") != "ok" or response.get("tool_identity", {}).get("package_digest") != spec["package_digest"] or response.get("data", {}).get("mode") != "merge":
        raise Invalid("public merge evidence result binding mismatch")
    checked = ctx.read(response["data"]["merge_check_ref"])
    if checked.get("mode") != "merge" or checked.get("view_digest") != view["digest"] or checked.get("status") not in ("passed", "failed", "incomplete"):
        raise Invalid("merge proof has invalid exact-view status")
    if ctx.path(request["view_ref"]).read_bytes() != before_view or source_lock.read_bytes() != before_lock:
        raise Blocked("merge check inputs changed; no repair is attempted")
    attempt = request.get("workflow", {}).get("attempt_id")
    if attempt is not None and (not isinstance(attempt, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", attempt)):
        raise Invalid("invalid workflow attempt_id")
    suffix = "-" + attempt if attempt else ""
    ref = f"logs/operations/{op}/merge-check-handoff{suffix}.json"
    record = ctx.record("merge_check", op, view_ref=request["view_ref"], view_digest=view["digest"], status=checked["status"], mode="merge", claims=checked.get("claims", []), gaps=checked.get("gaps", []), delegated_proof_ref=response["data"]["merge_check_ref"], delegated_proof_digest=checked["digest"], delegated_result_ref=response_ref, code_identity=checked.get("code_identity"), verification_tier=checked.get("verification_tier", "incomplete"), ci_policy_installed=False)
    ctx.save(ref, record)
    return {"merge_check_ref": ref, "check_status": checked["status"], "mode": "merge", "phase": checked["status"]}
