"""Delegate transaction recovery to the installed public apply CLI."""

import pathlib
import secrets
import subprocess
import sys

from support import Blocked, Invalid, atomic_bytes, canonical, native_path


def recover(ctx, request, action):
    mode = request.get("mode") if action == "run" else action
    if mode not in ("inspect", "resume", "rollback"):
        raise Invalid("recovery action must be inspect, resume or rollback")
    op = ctx.operation(request)
    package = pathlib.Path(__file__).resolve().parents[2] / "hs-knowledge-apply"
    if not (package / "scripts/cli.py").is_file():
        spec = ctx.catalog.get("skills", {}).get("hs-knowledge-apply", {})
        package = pathlib.Path(spec.get("root", package))
    entry = package / "scripts/cli.py"
    if not entry.is_file():
        raise Blocked("installed apply Skill is unavailable")
    stem = f".build/operations/{op}/recover-{mode}-{secrets.token_hex(8)}"
    request_ref, response_ref = (
        stem + "-request.json",
        stem + "-response-" + secrets.token_hex(12) + ".json",
    )
    child_request = {"operation_id": op}
    for ref, value in ((request_ref, child_request),):
        path = ctx.path(ref)
        native_request = pathlib.Path(native_path(path))
        raw = canonical(value)
        if native_request.exists() and native_request.read_bytes() != raw:
            raise Blocked("recovery attempt input changed; use a new attempt ID")
        if not native_request.exists():
            atomic_bytes(path, raw)
    response_path = ctx.path(response_ref)
    native_response = pathlib.Path(native_path(response_path))
    if not native_response.exists():
        command = [
            sys.executable,
            str(entry),
            "--input",
            str(ctx.path(request_ref)),
            "--output",
            str(response_path),
            "--knowledge-root",
            str(ctx.root),
            "--rules-digest",
            ctx.rules_digest,
            "--action",
            mode,
        ]
        if ctx.catalog_path:
            command += ["--catalog", ctx.catalog_path]
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, timeout=120
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Blocked("public apply recovery process unavailable") from exc
        if completed.returncode not in (0, 2, 3) or not native_response.is_file():
            raise Blocked("public apply recovery process produced no valid result")
    response = ctx.read(response_ref)
    if (
        response.get("record_kind") != "result"
        or response.get("tool_identity", {}).get("skill") != "hs-knowledge-apply"
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
