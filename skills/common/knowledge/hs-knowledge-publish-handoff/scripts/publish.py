"""Describe verified local state and explicit external publishing obligations."""
import pathlib
import secrets
import subprocess

from support import Blocked, Invalid, atomic_bytes, canonical, package_digest


def publish_handoff(ctx, request):
    op = ctx.operation(request)
    apply_ref = request.get("apply_result_ref")
    ctx.path(apply_ref, (f"logs/operations/{op}",))
    applied = ctx.read(apply_ref)
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-apply")
    if not spec or not ctx.catalog_path:
        raise Blocked("installed public apply verifier is required")
    package = pathlib.Path(spec["root"]).resolve()
    entry = (package / spec.get("entry", "scripts/cli.py")).resolve()
    if entry != package / "scripts/cli.py" or package_digest(package) != spec.get("package_digest"):
        raise Invalid("apply verifier package identity mismatch")
    nonce = secrets.token_hex(12)
    req_ref = f".build/operations/{op}/publish-verify-{nonce}-request.json"
    response_ref = f".build/operations/{op}/publish-verify-{nonce}-response.json"
    atomic_bytes(ctx.path(req_ref), canonical({"operation_id": op, "apply_result_ref": apply_ref}))
    completed = subprocess.run([spec["python"], str(entry), "--input", str(ctx.path(req_ref)), "--output", str(ctx.path(response_ref)), "--knowledge-root", str(ctx.root), "--rules-digest", ctx.rules_digest, "--catalog", ctx.catalog_path, "--action", "verify-result"], check=False, capture_output=True, timeout=120)
    if completed.returncode != 0 or not ctx.path(response_ref).is_file():
        raise Blocked("local transaction authenticity could not be verified")
    response = ctx.read(response_ref)
    verified = response.get("data", {})
    if response.get("status") != "ok" or verified.get("result_verified") is not True or response.get("tool_identity", {}).get("package_digest") != spec["package_digest"] or verified.get("view_digest") != applied.get("view_digest"):
        raise Blocked("local transaction is not verified")
    view = ctx.read(verified["view_ref"])
    obligations = [{"owner": "authorized_committer", "action": "review scoped diff and create commit", "status": "pending"}, {"owner": "authorized_committer", "action": "push and verify remote commit identity", "status": "pending"}, {"owner": "index_and_regression_workflow", "action": "verify and activate the corresponding immutable index generation", "status": "pending"}]
    if view.get("review_mode") == "code_gate":
        obligations.append({"owner": "external_ci", "action": "run latest-authorized-code read-only merge-check before accepting the commit", "status": "pending"})
    record = ctx.record("publish_handoff", op, status="awaiting_external_publish", apply_result_ref=apply_ref, apply_result_digest=applied["digest"], view_ref=verified["view_ref"], view_digest=view["digest"], proof_ref=verified["proof_ref"], verification_tier=verified["verification_tier"], local_verification_ref=response_ref, local_verification_digest=response["digest"], external_obligations=obligations, git_merge_verified=False, remote_push_verified=False)
    reference = f"logs/operations/{op}/publish-handoff.json"
    # Child verifier response references vary per invocation. A repeat returns
    # the prior immutable handoff only after freshly verifying the same apply.
    if ctx.path(reference).exists():
        prior = ctx.read(reference)
        if prior.get("apply_result_digest") != applied["digest"] or prior.get("view_digest") != view["digest"]:
            raise Invalid("operation already handed off another result")
        return {"publish_handoff_ref": reference, "publication_status": prior["status"], "phase": "awaiting_external_publish"}
    ctx.save(reference, record)
    return {"publish_handoff_ref": reference, "publication_status": record["status"], "phase": "awaiting_external_publish"}
