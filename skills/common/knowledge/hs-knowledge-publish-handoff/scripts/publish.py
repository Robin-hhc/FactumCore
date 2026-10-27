"""Describe exact local files and verify actual Git objects on explicit request."""

import pathlib
import subprocess
import re

from support import Blocked, Invalid, checked_view, digest, native_path


def publish_handoff(ctx, request):
    op = ctx.operation(request)
    apply_ref = request.get("apply_result_ref")
    applied = None
    if apply_ref:
        ctx.path(apply_ref, (f"logs/operations/{op}",))
        applied = ctx.read(apply_ref)
        if applied.get("record_kind") != "apply_result":
            raise Invalid("apply_result_ref must name an apply result")
    view_ref = request.get("view_ref") or (applied or {}).get("view_ref")
    if not view_ref:
        raise Blocked("final view bytes are required to describe the local change set")
    view = checked_view(ctx, {"operation_id": op, "view_ref": view_ref})
    if applied and applied.get("view_digest") != view["digest"]:
        raise Invalid("apply result and selected view describe different bytes")
    writes = []
    deletes = [row["path"] for row in view.get("deletes", [])]
    for row in view.get("writes", []):
        path = ctx.path(row["path"], ("knowledge", "governance/sources.lock.yaml", "index.md"))
        if not path.is_file() or digest(pathlib.Path(native_path(path)).read_bytes()) != row["final_digest"]:
            raise Blocked("local file differs from the selected final bytes: " + row["path"])
        writes.append({"path": row["path"], "sha256": row["final_digest"]})
    for ref in deletes:
        if ctx.path(ref).exists():
            raise Blocked("selected deletion is still present: " + ref)
    ingest = (applied or {}).get("ingest_record_path")
    if ingest:
        path = ctx.path(ingest, ("logs/ingest",))
        if not path.is_file():
            raise Blocked("declared processing record is unavailable: " + ingest)
        writes.append({"path": ingest, "sha256": digest(pathlib.Path(native_path(path)).read_bytes())})
    kind = (applied or {}).get("batch_kind", view.get("batch_kind", "content"))
    batch = request.get("v3_required") or view.get("v3_required") or kind == "record_only"
    phase = ("record_only_ready" if kind == "record_only" else "ready_to_submit") if batch else "awaiting_external_publish"
    files = [row["path"] for row in writes] + deletes
    obligations = [
        {"owner": "authorized_committer", "action": "review scoped diff and create commit", "status": "pending"},
        {"owner": "fixed_ci", "action": "reuse lint deterministic checks on submitted content", "status": "pending"},
        {"owner": "authorized_committer", "action": "push and verify remote commit identity", "status": "pending"},
    ]
    record = ctx.record(
        "publish_handoff", op, status=phase, view_ref=view_ref, view_digest=view["digest"],
        **({"apply_result_ref": apply_ref, "apply_result_digest": applied["digest"]} if applied else {}),
        batch_kind=kind, commit_files=files, write_manifest=writes, delete_manifest=deletes,
        external_obligations=obligations, git_merge_verified=False, remote_push_verified=False,
    )
    reference = f"logs/operations/{op}/" + ("submit-ready.json" if batch else "publish-handoff.json")
    if ctx.path(reference).exists():
        prior = ctx.read(reference)
        if prior.get("view_digest") != view["digest"] or prior.get("write_manifest") != writes or prior.get("delete_manifest") != deletes:
            raise Invalid("operation already describes a different local change set")
    else:
        ctx.save(reference, record)
    return {"publish_handoff_ref": reference, "publication_status": phase,
            "commit_files": files, "batch_kind": kind, "phase": phase}

def verify_submission(ctx, request):
    """Read actual Git objects; a claimed SHA or ready receipt is insufficient."""
    ready = publish_handoff(ctx, {**request, "v3_required": True})
    handoff = ctx.read(ready["publish_handoff_ref"])
    commit = request.get("commit_sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", commit):
        raise Blocked("actual exact Git commit SHA is required; batch remains pending submission")
    try:
        workspace = ctx.domain.workspace_config_path(ctx.root).parent
    except (ValueError, OSError):
        # Legacy fixture/publication calls without a project registration keep
        # Git's own ownership check; do not invent a trusted parent directory.
        workspace = None

    def git(arguments, *, optional=False):
        trust = ["-c", "safe.directory=" + workspace.as_posix()] if workspace is not None else []
        done = subprocess.run(["git", "--no-optional-locks", *trust, "-C", str(ctx.root),
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
