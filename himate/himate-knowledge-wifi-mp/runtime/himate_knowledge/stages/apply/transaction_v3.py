"""Controlled processing-record extension to the existing CAS transaction."""

import base64
import importlib
from pathlib import Path
import re
from types import SimpleNamespace

from .support import Blocked, Invalid, canonical, digest, seal


def contracts(ctx, name):
    if ctx.domain is None:
        raise Blocked("versioned domain contracts are required for v3 admission")
    return importlib.import_module(ctx.domain.__package__ + "." + name)


def read_record(ctx, ref):
    path = ctx.path(ref, (".build/operations/", "logs/ingest"))
    record = ctx.domain.load_yaml(path.read_bytes())
    contracts(ctx, "records").verify(record)
    if record.get("rules_digest") != ctx.rules_digest:
        raise Invalid("processing record uses different rules")
    return record


def record_input(ctx, request, view=None, proof=None):
    ref = request.get("ingest_record_ref")
    if not ref:
        raise Blocked("v3 apply requires a validated shared ingest record")
    ctx.path(ref, (f".build/operations/{ctx.operation(request)}",))
    record = read_record(ctx, ref)
    if record.get("operation_id") != ctx.operation(request):
        raise Invalid("processing record operation mismatch")
    path = record.get("target_path")
    if not isinstance(path, str) or not re.fullmatch(r"logs/ingest/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.yaml", path):
        raise Invalid("processing record target must be one explicit logs/ingest YAML file")
    if record.get("batch_kind") not in {"content", "record_only"}:
        raise Invalid("explicit content or record_only batch kind required")
    if record["batch_kind"] == "record_only":
        if view and (view.get("writes") or view.get("deletes")):
            raise Invalid("record-only admission forbids all knowledge/navigation/source-lock writes")
        if any(row["action"] in {"create", "update", "merge", "split", "deprecate"} for row in record["dispositions"]):
            raise Invalid("record-only facts cannot claim a content-changing disposition")
    elif not view or record.get("content_view_digest") != view["digest"]:
        raise Invalid("processing record must bind the exact checked content view")
    records = contracts(ctx, "records")
    records.validate_ingest_record(record, view=view, rules=ctx.rules)
    final = dict(record)
    final["progress"] = {**record.get("progress", {}), "apply": {
        "status": "recorded" if record["batch_kind"] == "record_only" else "applied",
        "operation_id": record["operation_id"], "view_digest": view["digest"] if view else None,
    }}
    final["status"] = "recorded" if record["batch_kind"] == "record_only" else "applied"
    # Applying bytes does not certify a separate Agent review.
    final.pop("acceptance", None)
    final = seal(final)
    records.validate_ingest_record(final, view=view, rules=ctx.rules)
    raw = canonical(final) + b"\n"
    ctx.path(path, ("logs/ingest",))
    expected = record.get("expected_old_digest")
    # A fresh record ID must never silently adopt an existing file as its baseline.
    return record, {"path": path, "expected_old_digest": expected,
                    "final_digest": digest(raw), "bytes_b64": base64.b64encode(raw).decode()}


def validate_content_review(ctx, view, review):
    """Check only the integrity binding of optional review material."""
    if (review.get("operation_id") != view["operation_id"]
            or review.get("view_digest") != view["digest"]):
        raise Invalid("review material is not bound to this exact final view")
    return review


def check_admission(ctx, request, view):
    if ctx.domain is None:
        return
    checks = contracts(ctx, "checks")
    actual = checks.run(checks.prepare_view(ctx.root, view, mode="candidate", identity={"view_digest": view["digest"], "operation_id": view["operation_id"]}),
                        ctx.rules, request.get("check_inputs"), scope="full")
    checks.validate_report(actual, expected_rules=ctx.rules_digest, required_scope="full")
    if actual["exit_code"] != 0:
        findings = [finding for check in actual["checks"] for finding in check.get("findings", [])]
        details = "; ".join(str(item.get("code", "check")) + ": " + str(item.get("reason", ""))
                            for item in findings[:3])
        raise Blocked("actual fixed full-view checks must pass immediately before admission" + (": " + details if details else ""))
    for snapshot in view.get("source_refs", []):
        recovery = snapshot.get("recovery", {})
        if recovery.get("kind") != "git" and recovery.get("method") != "git":
            if (recovery.get("method") != "evidence_object"
                    or recovery.get("path") not in {
                        "logs/evidence/objects/" + str(snapshot.get("sha256")) + ".bin",
                        "logs/evidence/published/objects/" + str(snapshot.get("sha256")) + ".bin"}):
                raise Blocked("local admission requires an exact captured source object")
        try:
            # Local ingest precedes human Git submission. A hash/size checked,
            # captured immutable object is sufficient here; cross-clone source
            # availability is a separate publishing responsibility.
            contracts(ctx, "source_resources").recover_snapshot(ctx.root, snapshot,
                staged_objects=view.get("staged_objects"))
        except (ValueError, OSError) as exc:
            raise Blocked("exact source recovery is unavailable for local admission") from exc


def check_execution_inputs(ctx, view, journal=None):
    """Compare business inputs, admitting only this transaction's observed installations."""
    snapshot = view.get("input_snapshot")
    if snapshot is None and view.get("batch_kind") == "record_only":
        return
    if snapshot is None:
        raise Invalid("the new batch action requires an exact input_snapshot")
    shared = SimpleNamespace(root=ctx.root, args=SimpleNamespace(rules_digest=ctx.rules_digest),
                             modules={"validation": ctx.domain,
                                      "source_resources": contracts(ctx, "source_resources")})
    try:
        contracts(ctx, "ingest_execution").compare_view_inputs(shared, view, journal)
    except (ValueError, OSError) as exc:
        raise Blocked("batch input observation is unavailable: " + str(exc)) from exc


def check_execution_view(ctx, view):
    """Decode written objects and recover declared inputs, without whole-library quality rules."""
    if ctx.domain is None:
        return
    knowledge = contracts(ctx, "knowledge")
    sources = contracts(ctx, "source_resources")
    for row in view.get("writes", []):
        raw = base64.b64decode(row["bytes_b64"], validate=True)
        path = row["path"]
        if path == "governance/sources.lock.yaml":
            ctx.domain.validate_shape("sources", ctx.domain.load_yaml(raw), ctx.rules)
        elif path.startswith("knowledge/") and Path(path).name not in {"AGENTS.md", "README.md", "index.md"}:
            if not path.endswith(".md"):
                raise Invalid("knowledge cards must be Markdown")
            knowledge.decode_card(raw, path, ctx.rules)
    for snapshot in view.get("source_refs", []):
        try:
            sources.recover_snapshot(ctx.root, snapshot, staged_objects=view.get("staged_objects"))
        except (ValueError, OSError) as exc:
            raise Blocked("exact source recovery is unavailable for batch execution") from exc


def check_current_code(ctx, view, inputs):
    """Recheck current code references during resume without an upstream proof."""
    if ctx.domain is None:
        return inputs
    knowledge, sources = contracts(ctx, "knowledge"), contracts(ctx, "source_resources")
    lock = sources.read_source_lock(ctx.root)
    for row in view["writes"]:
        if row["path"] == "governance/sources.lock.yaml":
            lock = ctx.domain.load_yaml(base64.b64decode(row["bytes_b64"], validate=True))
    rules = {**ctx.rules, "source_lock": lock}
    resolved = dict(inputs or {})
    checkout = resolved.get("code_checkout")
    for row in view["writes"]:
        path = row["path"]
        if not path.startswith("knowledge/") or path.rsplit("/", 1)[-1] in {"AGENTS.md", "README.md", "index.md"}:
            continue
        card = knowledge.parse_card(base64.b64decode(row["bytes_b64"], validate=True), path, rules)
        meta = card["metadata"]
        current = [claim for claim in meta["claims"] if claim["usage"] == "current"]
        if meta["review_mode"] != "code_gate" or meta["lifecycle"] == "deprecated" or not current:
            continue
        context = None
        if not checkout or not resolved.get("code_context"):
            context_ref = view.get("context_ref")
            if context_ref:
                context = ctx.read(context_ref)
        if not checkout:
            configuration = ctx.domain.workspace_config_path(ctx.root)
            config_bytes = configuration.read_bytes()
            config = ctx.domain.normalize_workspace(ctx.domain.load_yaml(config_bytes), configuration.parent)
            repos = {}
            for mapping in config["repos"]:
                root = Path(mapping["root"])
                root = root if root.is_absolute() else configuration.parent / root
                fixed = (context or {}).get("repos", {}).get(mapping["repo_id"], {})
                commit = fixed.get("head")
                repos[mapping["repo_id"]] = {"root": str(root.resolve()), "commit": commit}
            checkout = {"configuration": str(configuration),
                        "config_digest": (context or {}).get("config_digest") or digest(config_bytes), "repos": repos}
            resolved["code_checkout"] = checkout
        if not resolved.get("code_context") and context:
            build = context.get("build_evidence") or {}
            resolved["code_context"] = {"basis": "source", "repos": {
                repo_id: {**repo, "checked_files_dirty": repo.get("dirty")}
                for repo_id, repo in context.get("repos", {}).items()},
                "target": context.get("target"),
                "build_files": {artifact["path"]: artifact["sha256"] for artifact in build.get("artifacts", [])},
                "macro_digest": build.get("macro_digest")}
        evidence = {ref for claim in current for ref in claim["source_refs"]}
        contexts = {ref for claim in current for ref in claim["context_ids"]}
        selected = {**card, "metadata": {**meta, "claims": current,
            "sources": [source for source in meta["sources"] if source["evidence_ref"] in evidence],
            "scope": {**meta["scope"], "contexts": [context for context in meta["scope"]["contexts"]
                                                    if context["context_id"] in contexts]}}}
        try:
            configuration = Path(checkout["configuration"])
            config = ctx.domain.normalize_workspace(ctx.domain.load_yaml(configuration.read_bytes()), configuration.parent)
            mappings = {mapping["repo_id"]: mapping for mapping in config["repos"]}
            resources = {resource["source_id"]: resource for resource in lock["resources"]}
            for reference in selected["metadata"]["sources"]:
                resource = resources[reference["source_id"]]
                if resource["kind"] != "code":
                    continue
                repo_id = reference["locator"].get("repo_id") or resource["repo_id"]
                repo = checkout["repos"].get(repo_id)
                if repo and mappings.get(repo_id, {}).get("kind") == "git" and repo.get("commit") in (None, "unknown", "unavailable"):
                    repo["commit"] = sources._fixed_code_git(Path(repo["root"]), ["rev-parse", "--verify", "HEAD^{commit}"]).decode("ascii").strip()
            sources.validate_code_references(selected, lock, checkout, rules)
            for reference in selected["metadata"]["sources"]:
                resource = resources[reference["source_id"]]
                if resource["kind"] != "code":
                    continue
                locator = reference["locator"]
                repo = checkout["repos"][locator.get("repo_id") or resource["repo_id"]]
                relative = locator.get("path") or resource["path"]
                raw = ctx.domain.safe_path(Path(repo["root"]), relative).read_bytes()
                snapshot = sources.validate_source_ref(reference, lock)
                if digest(raw) != snapshot["sha256"] or len(raw) != snapshot["bytes"]:
                    raise Invalid("current worktree source bytes differ from the card snapshot")
            if resolved.get("code_context"):
                sources.validate_current_code_identity(resolved["code_context"], configuration,
                    checkout["config_digest"], rules, config.get("code_policy"))
        except (ValueError, OSError) as exc:
            raise Blocked("current code references changed: " + str(exc)) from exc
    return resolved


def record_only_view(ctx, request):
    record, _ = record_input(ctx, request)
    if record["batch_kind"] != "record_only":
        raise Invalid("a content batch requires its reviewed content view")
    op = ctx.operation(request)
    view = ctx.record("final_view", op, review_mode="record_only", writes=[], deletes=[], source_refs=[],
                      plan_ref=record["scan_ref"], plan_digest=record["scan_digest"], baseline_digest=digest({"files": {}}),
                      batch_kind="record_only", ingest_record_ref=request["ingest_record_ref"])
    if ctx.domain is not None:
        publication = contracts(ctx, "publication")
        public = SimpleNamespace(root=ctx.root, operation=op)
        view["staged_objects"], view["event_proposals"] = [], []
        view["publication_plan"] = publication.prepare_plan(public, view, disposition_preview=record)
        view["content_digest"] = view["publication_plan"]["content_digest"]
        view = seal(view)
    view_ref = f".build/operations/{op}/record-only-view.json"
    ctx.save(view_ref, view)
    from .transaction import register_owned
    register_owned(ctx, view_ref, op)
    return {**request, "view_ref": view_ref}
