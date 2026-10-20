"""Recovery orchestration over the catalog-pinned public apply CLI."""

import pathlib
import re
import secrets
import subprocess

from support import Blocked, Invalid, atomic_bytes, canonical, package_digest


def recover(ctx, request, action):
    mode = request.get("mode") if action == "run" else action
    if mode not in ("inspect", "resume", "rollback"):
        raise Invalid("recovery action must be inspect, resume or rollback")
    op = ctx.operation(request)
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-apply")
    if not spec:
        raise Blocked("catalog-pinned apply engine is not installed")
    package = pathlib.Path(spec["root"]).resolve()
    entry = (package / spec.get("entry", "scripts/cli.py")).resolve()
    if entry != package / "scripts/cli.py" or package_digest(package) != spec.get(
        "package_digest"
    ):
        raise Invalid("installed apply package identity mismatch")
    if not ctx.catalog_path:
        raise Blocked("trusted installed catalog path is required")
    attempt = request.get("workflow", {}).get("attempt_id", "standalone")
    if not isinstance(attempt, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", attempt
    ):
        raise Invalid("invalid workflow attempt_id")
    stem = f".build/operations/{op}/recover-{mode}-{attempt}"
    request_ref, response_ref = (
        stem + "-request.json",
        stem + "-response-" + secrets.token_hex(12) + ".json",
    )
    child_request = {"operation_id": op}
    for ref, value in ((request_ref, child_request),):
        path = ctx.path(ref)
        raw = canonical(value)
        if path.exists() and path.read_bytes() != raw:
            raise Blocked("recovery attempt input changed; use a new attempt ID")
        if not path.exists():
            atomic_bytes(path, raw)
    response_path = ctx.path(response_ref)
    if not response_path.exists():
        command = [
            spec["python"],
            str(entry),
            "--input",
            str(ctx.path(request_ref)),
            "--output",
            str(response_path),
            "--knowledge-root",
            str(ctx.root),
            "--rules-digest",
            ctx.rules_digest,
            "--catalog",
            ctx.catalog_path,
            "--action",
            mode,
        ]
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, timeout=120
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Blocked("public apply recovery process unavailable") from exc
        if completed.returncode not in (0, 2, 3) or not response_path.is_file():
            raise Blocked("public apply recovery process produced no valid result")
    response = ctx.read(response_ref)
    if (
        response.get("record_kind") != "result"
        or response.get("tool_identity", {}).get("skill") != "hs-knowledge-apply"
        or response["tool_identity"].get("package_digest") != spec["package_digest"]
    ):
        raise Invalid("public apply result identity mismatch")
    record = ctx.record(
        "recovery_result",
        op,
        mode=mode,
        delegated_result_ref=response_ref,
        delegated_result_digest=response["digest"],
        apply_tool_identity=response["tool_identity"],
        status=response["status"],
        data=response.get("data", {}),
    )
    result_ref = stem + "-result.json"
    ctx.save(result_ref, record)
    if response.get("status") == "blocked":
        raise Blocked(
            "apply recovery is blocked; inspect delegated result " + response_ref
        )
    if response.get("status") != "ok":
        raise Invalid("apply recovery rejected the request; see " + response_ref)
    return {
        "recovery_result_ref": result_ref,
        "delegated_result_ref": response_ref,
        **response.get("data", {}),
        "phase": response.get("phase", "recovered"),
    }
