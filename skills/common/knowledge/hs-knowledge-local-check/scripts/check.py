"""Read-only code evidence gate; a signed semantic reviewer supplies support."""
import base64
import importlib
import math
import os
import pathlib
import re
import subprocess
import time

from support import (Blocked, Invalid, canonical, checked_view, digest, safe_path,
                     strict_json)


class Incomplete(Blocked):
    pass


class Failed(Invalid):
    pass


def known(value):
    return value is not None and value not in ("", "unknown", "unavailable")


def git_read(root, arguments):
    """Only object/ref reads; no diff/status/filter/hook-capable commands."""
    if arguments[0] not in ("rev-parse", "cat-file"):
        raise Invalid("unapproved Git read operation")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat"})
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "-c", "diff.external=", "-c", "core.pager=cat", "-C", str(root), *arguments]
    result = subprocess.run(command, env=environment, check=False, capture_output=True, timeout=30)
    if result.returncode:
        raise Incomplete("registered code object/ref unavailable")
    return result.stdout


def read_configuration(ctx, context):
    path = ctx.root.parent / "config.yml"
    if not path.is_file() or ctx.domain is None:
        raise Incomplete("registered workspace configuration unavailable")
    raw = path.read_bytes()
    if context.get("config_digest") != digest(raw):
        raise Incomplete("code context does not fix current workspace configuration")
    config = ctx.domain.load_yaml(raw)
    ctx.domain.validate_shape("workspace", config, ctx.rules)
    declared = config.get("code_policy")
    trusted = ctx.catalog.get("code_policy")
    if not declared or not trusted or declared != trusted:
        raise Incomplete("protected code authorization and domain declaration are missing or differ")
    return config, trusted, raw


def code_identity(ctx, context, config, policy, mode):
    repos = context.get("repos")
    target = context.get("target")
    if not isinstance(repos, dict) or not repos or not isinstance(target, dict):
        raise Incomplete("fixed repositories and a real Target are required")
    registered = {item["repo_id"]: item for item in config["repos"]}
    targets = [item for item in config["targets"] if item["target_id"] == target.get("target_id")]
    if len(targets) != 1:
        raise Incomplete("Target is not uniquely registered")
    declared_target = targets[0]
    for field in ("target_id", "chip", "side", "build_profile"):
        if not known(target.get(field)) or target[field] != declared_target.get(field):
            raise Incomplete("Target/build profile is unknown or does not match registration")
    if not declared_target["module_roots"] or not declared_target["source_bindings"] or not isinstance(target.get("features"), list) or not isinstance(target.get("protocol_versions"), list) or not known(target.get("revision")):
        raise Incomplete("Target code bindings/macros/protocol/revision are incomplete")
    if not set(declared_target["required_features"]).issubset(target["features"]) or not set(declared_target["protocol_versions"]).issubset(target["protocol_versions"]):
        raise Incomplete("Target required macros or protocols are not fixed")
    build = context.get("build_evidence")
    if not isinstance(build, dict) or build.get("profile") != target["build_profile"] or not re.fullmatch(r"[0-9a-f]{64}", str(build.get("macro_digest", ""))) or not build.get("artifacts"):
        raise Incomplete("build/macro evidence is missing")
    build_files = {}
    for item in build["artifacts"]:
        path = ctx.path(item.get("path"), ("logs/evidence",))
        raw = path.read_bytes()
        if digest(raw) != item.get("sha256"):
            raise Incomplete("build evidence bytes changed")
        build_files[item["path"]] = item["sha256"]
    result = {"repos": {}, "target": target, "build_files": build_files, "macro_digest": build["macro_digest"]}
    for repo_id, item in repos.items():
        registered_repo = registered.get(repo_id)
        protected_root = policy.get("repo_roots", {}).get(repo_id)
        if not registered_repo or not known(registered_repo.get("root")) or not known(registered_repo.get("expected_identity")) or not protected_root:
            raise Incomplete("repository root/identity is not authorized")
        root = pathlib.Path(registered_repo["root"])
        root = (ctx.root.parent / root).resolve() if not root.is_absolute() else root.resolve()
        if root != pathlib.Path(protected_root).resolve() or root != pathlib.Path(item.get("root", "")).resolve() or item.get("identity") != registered_repo["expected_identity"]:
            raise Incomplete("repository path/identity differs from protected registration")
        if registered_repo["kind"] != "git" or not root.is_dir():
            raise Incomplete("a real registered Git checkout is required")
        if mode == "merge":
            allowed_ref = policy.get("allowed_ref")
            if not isinstance(allowed_ref, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", allowed_ref) or allowed_ref.startswith("-"):
                raise Incomplete("latest authorized merge ref is unknown")
            head = git_read(root, ["rev-parse", "--verify", allowed_ref + "^{commit}"]).decode("ascii").strip()
        else:
            head = git_read(root, ["rev-parse", "--verify", "HEAD^{commit}"]).decode("ascii").strip()
        if item.get("head") != head or target["revision"] != head:
            raise Incomplete("code revision differs from the fixed authorized identity")
        files = item.get("files")
        if not isinstance(files, dict) or not files:
            raise Incomplete("code file byte manifest missing")
        actual_files, dirty = {}, False
        for relative, expected in files.items():
            path = safe_path(root, relative)
            if not any(module == "." or relative == module or relative.startswith(module.rstrip("/") + "/") for module in declared_target["module_roots"]):
                raise Incomplete("code file is outside registered Target modules")
            committed = git_read(root, ["cat-file", "blob", head + ":" + relative])
            raw = committed if mode == "merge" else path.read_bytes()
            if digest(raw) != expected:
                raise Incomplete("code bytes differ from the fixed context")
            dirty = dirty or raw != committed
            actual_files[relative] = expected
        if mode == "local" and (not isinstance(item.get("dirty"), bool) or item["dirty"] != dirty):
            raise Incomplete("checked-file dirty state does not match fixed context")
        result["repos"][repo_id] = {"root": str(root), "head": head, "files": actual_files, "checked_files_dirty": dirty}
    return result


def claims_and_sources(ctx, view):
    knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
    resources = importlib.import_module(ctx.domain.__package__ + ".source_resources")
    source_lock = resources.read_source_lock(ctx.root)
    for row in view["writes"]:
        if row["path"] == "governance/sources.lock.yaml":
            source_lock = ctx.domain.load_yaml(base64.b64decode(row["bytes_b64"], validate=True))
            ctx.domain.validate_shape("sources", source_lock, ctx.rules)
    rules = {**ctx.rules, "source_lock": source_lock}
    claims = {}
    for row in view["writes"]:
        if not row["path"].startswith("knowledge/") or pathlib.PurePosixPath(row["path"]).name in ("AGENTS.md", "index.md", "README.md"):
            continue
        card = knowledge.parse_card(base64.b64decode(row["bytes_b64"], validate=True), row["path"], rules)
        if card["metadata"]["review_mode"] != "code_gate":
            raise Invalid("code view contains a document-review card")
        knowledge.validate_card(card, None, rules)
        for claim in card["claims"]:
            key = (card["metadata"]["id"], claim["id"])
            if key in claims:
                raise Invalid("duplicate Claim in code view")
            claims[key] = claim
    if not claims:
        raise Incomplete("code view contains no verifiable Claims")
    return claims, source_lock, resources


def verify_report(ctx, report, view, context, mode):
    trust = ctx.catalog.get("semantic_reviewers", {}).get(report.get("reviewer_id"))
    if not trust:
        raise Incomplete("trusted semantic reviewer is not available")
    if trust.get("synthetic"):
        marker = ctx.root / ".isolated-knowledge-fixture"
        if not trust.get("fixture_root") or pathlib.Path(trust["fixture_root"]).resolve() != ctx.root or not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "AIOTBOT_SYNTHETIC_FIXTURE_V2":
            raise Incomplete("synthetic semantic reviewer requires an isolated fixture")
    payload = report.get("payload")
    if report.get("schema_version") != "2.0" or report.get("record_kind") != "semantic_review" or not isinstance(payload, dict):
        raise Failed("invalid signed semantic report")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(trust["public_key_b64"], validate=True))
        public.verify(base64.b64decode(report["signature_b64"], validate=True), canonical(payload))
    except Exception as exc:
        raise Failed("semantic reviewer signature invalid") from exc
    if payload.get("view_digest") != view["digest"] or payload.get("context_digest") != context["digest"] or payload.get("mode") != mode:
        raise Failed("semantic report exact-view/context/mode binding mismatch")
    issued = payload.get("issued_at")
    if not isinstance(issued, (int, float)) or isinstance(issued, bool) or not math.isfinite(issued) or issued > time.time() + 60:
        raise Failed("semantic report timestamp invalid")
    return payload, "synthetic_code_reviewer" if trust.get("synthetic") else "authenticated_code_reviewer"


def evaluate(ctx, request, view, mode, report_override=None):
    context_ref = request.get("context_ref") or view.get("context_ref")
    if not context_ref:
        raise Incomplete("fixed real code context is missing")
    context = ctx.read(context_ref)
    if context.get("record_kind") != "project_context":
        raise Incomplete("code context is not a project context")
    config, policy, config_raw = read_configuration(ctx, context)
    before = code_identity(ctx, context, config, policy, mode)
    claims, source_lock, resources = claims_and_sources(ctx, view)
    report_ref = request.get("semantic_report_ref")
    if report_override is None and not report_ref:
        raise Incomplete("positive signed semantic evidence is missing")
    report = report_override if report_override is not None else strict_json(ctx.path(report_ref, ("logs/semantic-reviews", f".build/operations/{view['operation_id']}")).read_text(encoding="utf-8"))
    payload, tier = verify_report(ctx, report, view, context, mode)
    rows = payload.get("claims")
    if not isinstance(rows, list) or len(rows) != len(claims):
        raise Incomplete("semantic evidence does not cover every Claim exactly once")
    seen, verified_claims = set(), []
    resource_map = {item["source_id"]: item for item in source_lock["resources"]}
    for row in rows:
        key = (row.get("card_id"), row.get("claim_id"))
        if key not in claims or key in seen:
            raise Failed("duplicate or unexpected semantic Claim")
        seen.add(key)
        knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
        if not knowledge.match_scope(claims[key], context["target"], "implementation"):
            raise Incomplete("Claim applicability is not supported by this fixed Target/build context")
        if row.get("status") != "supported":
            raise Failed("semantic reviewer did not support every Claim")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise Incomplete("zero findings do not constitute positive evidence")
        claim_sources = claims[key]["source_records"]
        code_support = False
        for ref in claim_sources:
            matching = [item for item in evidence if item.get("source_id") == ref["source_id"] and item.get("snapshot_id") == ref["snapshot_id"] and item.get("locator") == ref["locator"]]
            if not matching:
                raise Incomplete("Claim source locator is not positively covered")
            snapshot = resources.validate_source_ref(ref, source_lock)
            raw = resources.recover_snapshot(ctx.root, snapshot)
            if any(item.get("sha256") != digest(raw) for item in matching):
                raise Failed("signed evidence digest does not match immutable snapshot")
            resource = resource_map[ref["source_id"]]
            if resource["kind"] == "code":
                repo_id = ref["locator"].get("repo_id") or resource.get("repo_id")
                relative = ref["locator"].get("path") or resource.get("path")
                actual = before["repos"].get(repo_id, {}).get("files", {}).get(relative)
                if actual != snapshot["sha256"]:
                    raise Incomplete("code evidence is not the fixed authorized code bytes")
                code_support = True
        if not code_support:
            raise Incomplete("code Claims require positive code-snapshot support")
        verified_claims.append(row)
    after = code_identity(ctx, context, config, policy, mode)
    if before != after or (ctx.root.parent / "config.yml").read_bytes() != config_raw or ctx.read(context_ref)["digest"] != context["digest"] or checked_view(ctx, request)["digest"] != view["digest"]:
        raise Incomplete("read-only gate inputs changed while checking")
    return {"context_ref": context_ref, "context_digest": context["digest"], "code_identity": before, "claims": verified_claims, "semantic_report": report, "verification_tier": tier}


def local_check(ctx, request, action="run"):
    op = ctx.operation(request)
    view = checked_view(ctx, request)
    if view.get("review_mode") != "code_gate":
        raise Invalid("pure-document views are exempt and reject code-gate invocation")
    if action not in ("run", "merge", "verify-proof"):
        raise Invalid("unsupported code-gate action")
    if action == "verify-proof":
        proof = ctx.read(request.get("proof_ref"))
        if proof.get("record_kind") != "local_check" or proof.get("status") != "passed" or proof.get("mode") != "local" or proof.get("view_digest") != view["digest"]:
            raise Blocked("proof is not a passing local check for this view")
        verified = evaluate(ctx, {**request, "context_ref": proof.get("context_ref")}, view, "local", proof.get("semantic_report"))
        if verified["claims"] != proof.get("claims") or verified["context_digest"] != proof.get("context_digest") or verified["code_identity"] != proof.get("code_identity"):
            raise Invalid("code proof differs from current authenticated evidence")
        return {"proof_verified": True, "mode": "local", "view_digest": view["digest"], "verification_tier": verified["verification_tier"], "phase": "verified"}
    mode = "merge" if action == "merge" else "local"
    details, gaps, status = {}, [], "passed"
    try:
        details = evaluate(ctx, request, view, mode)
    except Incomplete as exc:
        status, gaps = "incomplete", [str(exc)]
    except Failed as exc:
        status, gaps = "failed", [str(exc)]
    record = ctx.record("merge_check" if mode == "merge" else "local_check", op, status=status, mode=mode, view_ref=request["view_ref"], view_digest=view["digest"], claims=details.pop("claims", []), gaps=gaps, **details)
    attempt = request.get("workflow", {}).get("attempt_id")
    if attempt is not None and (not isinstance(attempt, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", attempt)):
        raise Invalid("invalid workflow attempt_id")
    suffix = "-" + attempt if attempt else ""
    ref = f"logs/operations/{op}/{mode}-check{suffix}.json"
    ctx.save(ref, record)
    return {"merge_check_ref" if mode == "merge" else "local_check_ref": ref, "check_status": status, "mode": mode, "phase": status}
