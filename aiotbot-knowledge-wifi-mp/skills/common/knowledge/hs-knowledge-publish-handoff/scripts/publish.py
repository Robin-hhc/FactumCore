"""Describe verified local state and explicit external publishing obligations."""

import pathlib
import secrets
import subprocess
import re

from support import Blocked, Invalid, atomic_bytes, canonical, package_digest, digest


def verify_query_gate(ctx, op, report_ref):
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-query-regression")
    if not spec or not ctx.catalog_path:
        raise Blocked("installed public batch query verifier is required")
    package = pathlib.Path(spec["root"]).resolve()
    entry = (package / spec.get("entry", "scripts/cli.py")).resolve()
    if entry != package / "scripts/cli.py" or package_digest(package) != spec.get("package_digest"):
        raise Invalid("batch query verifier package identity mismatch")
    nonce = secrets.token_hex(12)
    incoming = f".build/operations/{op}/query-gate-{nonce}-input.json"
    outgoing = f".build/operations/{op}/query-gate-{nonce}-output.json"
    atomic_bytes(ctx.path(incoming), canonical({"operation_id": op, "report_ref": report_ref}))
    done = subprocess.run([spec["python"], str(entry), "--input", str(ctx.path(incoming)),
                           "--output", str(ctx.path(outgoing)), "--knowledge-root", str(ctx.root),
                           "--rules-digest", ctx.rules_digest, "--catalog", ctx.catalog_path,
                           "--action", "verify"], check=False, capture_output=True, timeout=120)
    if done.returncode != 0 or not ctx.path(outgoing).is_file():
        raise Blocked("batch index and target query gate has not passed")
    result = ctx.read(outgoing)
    if (result.get("status") != "ok" or result.get("phase") != "verified"
            or result.get("tool_identity", {}).get("package_digest") != spec["package_digest"]
            or result.get("data", {}).get("gate_verified") is not True):
        raise Blocked("batch query gate did not return verified evidence")
    return result["data"]


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
    if entry != package / "scripts/cli.py" or package_digest(package) != spec.get(
        "package_digest"
    ):
        raise Invalid("apply verifier package identity mismatch")
    nonce = secrets.token_hex(12)
    req_ref = f".build/operations/{op}/publish-verify-{nonce}-request.json"
    response_ref = f".build/operations/{op}/publish-verify-{nonce}-response.json"
    atomic_bytes(
        ctx.path(req_ref),
        canonical({"operation_id": op, "apply_result_ref": apply_ref}),
    )
    completed = subprocess.run(
        [
            spec["python"],
            str(entry),
            "--input",
            str(ctx.path(req_ref)),
            "--output",
            str(ctx.path(response_ref)),
            "--knowledge-root",
            str(ctx.root),
            "--rules-digest",
            ctx.rules_digest,
            "--catalog",
            ctx.catalog_path,
            "--action",
            "verify-result",
        ],
        check=False,
        capture_output=True,
        timeout=120,
    )
    if completed.returncode != 0 or not ctx.path(response_ref).is_file():
        raise Blocked("local transaction authenticity could not be verified")
    response = ctx.read(response_ref)
    verified = response.get("data", {})
    if (
        response.get("status") != "ok"
        or verified.get("result_verified") is not True
        or response.get("tool_identity", {}).get("package_digest")
        != spec["package_digest"]
        or verified.get("view_digest") != applied.get("view_digest")
    ):
        raise Blocked("local transaction is not verified")
    view = ctx.read(verified["view_ref"])
    if request.get("v3_required") or view.get("v3_required") or applied.get("batch_kind") == "record_only":
        kind = applied.get("batch_kind", "content")
        if kind != "record_only":
            if not request.get("query_report_ref"):
                raise Blocked("passing batch target query report is required before submit")
            gate = verify_query_gate(ctx, op, request["query_report_ref"])
            if gate.get("apply_result_digest") != applied["digest"] or gate.get("view_digest") != view["digest"]:
                raise Invalid("query gate belongs to another applied batch")
        if not applied.get("ingest_record_path"):
            raise Blocked("shared processing record must be applied before submit")
        for row in verified.get("write_manifest", []):
            path = ctx.path(row["path"], ("knowledge", "governance/sources.lock.yaml", "index.md", "logs/ingest"))
            if not path.is_file() or digest(path.read_bytes()) != row["sha256"]:
                raise Blocked("batch changed after apply; inspect before submit: " + row["path"])
        for ref in verified.get("delete_manifest", []):
            if ctx.path(ref).exists():
                raise Blocked("batch deletion changed after apply")
        phase = "record_only_ready" if kind == "record_only" else "ready_to_submit"
        files = [row["path"] for row in verified["write_manifest"]] + verified["delete_manifest"]
        obligations = [{"owner": "authorized_committer", "action": "commit exactly commit_files", "status": "pending"},
                       {"owner": "fixed_ci", "action": "reuse lint deterministic checks on submitted content", "status": "pending"}]
        if kind != "record_only":
            obligations.append({"owner": "authorized_committer",
                                "action": "provide exact originals and portable recovery locations for CI and other clones",
                                "status": "pending"})
        record = ctx.record("publish_handoff", op, status=phase, apply_result_ref=apply_ref,
                            apply_result_digest=applied["digest"], view_ref=verified["view_ref"],
                            view_digest=view["digest"], proof_ref=verified["proof_ref"],
                            verification_tier=verified["verification_tier"], batch_kind=kind,
                            query_report_ref=request.get("query_report_ref"), commit_files=files,
                            write_manifest=verified["write_manifest"], delete_manifest=verified["delete_manifest"],
                            git_merge_verified=False, remote_push_verified=False,
                            external_obligations=obligations)
        reference = f"logs/operations/{op}/submit-ready.json"
        ctx.save(reference, record)
        return {"publish_handoff_ref": reference, "publication_status": phase,
                "commit_files": files, "batch_kind": kind, "phase": phase}
    obligations = [
        {
            "owner": "authorized_committer",
            "action": "review scoped diff and create commit",
            "status": "pending",
        },
        {
            "owner": "authorized_committer",
            "action": "push and verify remote commit identity",
            "status": "pending",
        },
        {
            "owner": "index_and_regression_workflow",
            "action": "verify and activate the corresponding immutable index generation",
            "status": "pending",
        },
    ]
    if view.get("review_mode") == "code_gate":
        obligations.append(
            {
                "owner": "external_ci",
                "action": "run fixed deterministic format/index/source/code-reference checks on the submitted commit",
                "status": "pending",
            }
        )
    record = ctx.record(
        "publish_handoff",
        op,
        status="awaiting_external_publish",
        apply_result_ref=apply_ref,
        apply_result_digest=applied["digest"],
        view_ref=verified["view_ref"],
        view_digest=view["digest"],
        proof_ref=verified["proof_ref"],
        verification_tier=verified["verification_tier"],
        local_verification_ref=response_ref,
        local_verification_digest=response["digest"],
        external_obligations=obligations,
        git_merge_verified=False,
        remote_push_verified=False,
    )
    reference = f"logs/operations/{op}/publish-handoff.json"
    # Child verifier response references vary per invocation. A repeat returns
    # the prior immutable handoff only after freshly verifying the same apply.
    if ctx.path(reference).exists():
        prior = ctx.read(reference)
        if (
            prior.get("apply_result_digest") != applied["digest"]
            or prior.get("view_digest") != view["digest"]
        ):
            raise Invalid("operation already handed off another result")
        return {
            "publish_handoff_ref": reference,
            "publication_status": prior["status"],
            "phase": "awaiting_external_publish",
        }
    ctx.save(reference, record)
    return {
        "publish_handoff_ref": reference,
        "publication_status": record["status"],
        "phase": "awaiting_external_publish",
    }


def verify_submission(ctx, request):
    """Read actual Git objects; a claimed SHA or ready receipt is insufficient."""
    ready = publish_handoff(ctx, {**request, "v3_required": True})
    handoff = ctx.read(ready["publish_handoff_ref"])
    commit = request.get("commit_sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", commit):
        raise Blocked("actual exact Git commit SHA is required; batch remains pending submission")

    def git(arguments, *, optional=False):
        done = subprocess.run(["git", "--no-optional-locks", "-c", "safe.directory=" + ctx.root.parent.resolve().as_posix(), "-C", str(ctx.root),
                               "-c", "core.hooksPath=__disabled_knowledge_hooks__", *arguments],
                              check=False, capture_output=True, timeout=60)
        if done.returncode and not optional:
            raise Blocked("actual Git submission could not be verified")
        return done.returncode, done.stdout

    _, raw_root = git(["rev-parse", "--show-toplevel"])
    repository = pathlib.Path(raw_root.decode("utf-8").strip()).resolve()
    try:
        prefix = ctx.root.relative_to(repository).as_posix()
    except ValueError as exc:
        raise Invalid("knowledge root escapes the actual Git workspace") from exc
    prefix = "" if prefix == "." else prefix + "/"
    _, head = git(["rev-parse", "--verify", "HEAD^{commit}"])
    _, actual = git(["rev-parse", "--verify", commit + "^{commit}"])
    if head.strip().decode() != commit or actual.strip().decode() != commit:
        raise Blocked("submitted batch commit must be the actual current HEAD")
    for row in handoff["write_manifest"]:
        _, raw = git(["cat-file", "blob", commit + ":" + prefix + row["path"]])
        if digest(raw) != row["sha256"]:
            raise Invalid("Git commit does not contain the exact applied batch file")
    for ref in handoff["delete_manifest"]:
        code, _ = git(["cat-file", "-e", commit + ":" + prefix + ref], optional=True)
        if code == 0:
            raise Invalid("Git commit retains a batch deletion")
    _, names = git(["diff-tree", "--no-ext-diff", "--no-textconv", "--no-commit-id", "--name-only", "-z", "-r", "--root", commit])
    changed = {name.decode("utf-8") for name in names.split(b"\0") if name}
    allowed = {prefix + ref for ref in handoff["commit_files"]}
    if not changed or not changed <= allowed:
        raise Invalid("Git submission contains files outside the exact authorized batch")
    record = ctx.record("publish_handoff", ctx.operation(request),
                        **{key: value for key, value in handoff.items() if key not in {
                            "digest", "schema_version", "record_kind", "operation_id", "rules_digest", "tool_identity", "status"}},
                        status="submitted", commit_sha=commit, repository_root=str(repository),
                        actual_changed_files=sorted(changed), git_commit_verified=True)
    ref = f"logs/operations/{ctx.operation(request)}/submission-{commit}.json"
    ctx.save(ref, record)
    return {"submission_ref": ref, "commit_sha": commit, "commit_files": handoff["commit_files"],
            "publication_status": "submitted", "phase": "submitted"}
