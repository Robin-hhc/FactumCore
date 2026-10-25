"""Read-only code evidence gate; a signed semantic reviewer supplies support."""

import base64
import importlib
import math
import os
import pathlib
import re
import subprocess
import time

from support import (
    Blocked,
    Invalid,
    canonical,
    checked_view,
    digest,
    safe_path,
    strict_json,
    atomic_bytes,
)


class Incomplete(Blocked):
    pass


class Failed(Invalid):
    pass


def known(value):
    return value is not None and value not in ("", "unknown", "unavailable")


def git_read(root, arguments):
    """Only object/ref reads; no diff/status/filter/hook-capable commands."""
    if arguments[0] not in ("rev-parse", "cat-file") and arguments != [
        "config",
        "--local",
        "--get",
        "remote.origin.url",
    ]:
        raise Invalid("unapproved Git read operation")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_NO_LAZY_FETCH": "1",
        }
    )
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "diff.external=",
        "-c",
        "core.pager=cat",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.file.allow=never",
        "-C",
        str(root),
        *arguments,
    ]
    result = subprocess.run(
        command, env=environment, check=False, capture_output=True, timeout=30
    )
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
        raise Incomplete(
            "protected code authorization and domain declaration are missing or differ"
        )
    return config, trusted, raw


def code_identity(ctx, context, config, policy, mode):
    repos = context.get("repos")
    target = context.get("target")
    if not isinstance(repos, dict) or not repos or not isinstance(target, dict):
        raise Incomplete("fixed repositories and a real Target are required")
    registered = {item["repo_id"]: item for item in config["repos"]}
    targets = [
        item
        for item in config["targets"]
        if item["target_id"] == target.get("target_id")
    ]
    if len(targets) != 1:
        raise Incomplete("Target is not uniquely registered")
    declared_target = targets[0]
    for field in ("target_id", "chip", "side", "build_profile"):
        if not known(target.get(field)) or target[field] != declared_target.get(field):
            raise Incomplete(
                "Target/build profile is unknown or does not match registration"
            )
    if (
        not declared_target["module_roots"]
        or not declared_target["source_bindings"]
        or not isinstance(target.get("features"), list)
        or not isinstance(target.get("protocol_versions"), list)
        or not known(target.get("revision"))
    ):
        raise Incomplete("Target code bindings/macros/protocol/revision are incomplete")
    if not set(declared_target["required_features"]).issubset(
        target["features"]
    ) or not set(declared_target["protocol_versions"]).issubset(
        target["protocol_versions"]
    ):
        raise Incomplete("Target required macros or protocols are not fixed")
    build = context.get("build_evidence")
    if (
        not isinstance(build, dict)
        or build.get("profile") != target["build_profile"]
        or build.get("source_revision") != target["revision"]
        or not re.fullmatch(r"[0-9a-f]{64}", str(build.get("macro_digest", "")))
        or not build.get("artifacts")
    ):
        raise Incomplete("build/macro evidence is missing")
    build_files = {}
    for item in build["artifacts"]:
        path = ctx.path(item.get("path"), ("logs/evidence",))
        raw = path.read_bytes()
        if digest(raw) != item.get("sha256"):
            raise Incomplete("build evidence bytes changed")
        build_files[item["path"]] = item["sha256"]
    result = {
        "repos": {},
        "target": target,
        "build_files": build_files,
        "macro_digest": build["macro_digest"],
    }
    for repo_id, item in repos.items():
        registered_repo = registered.get(repo_id)
        protected_root = policy.get("repo_roots", {}).get(repo_id)
        if (
            not registered_repo
            or not known(registered_repo.get("root"))
            or not known(registered_repo.get("expected_identity"))
            or not protected_root
        ):
            raise Incomplete("repository root/identity is not authorized")
        root = pathlib.Path(registered_repo["root"])
        root = (
            (ctx.root.parent / root).resolve()
            if not root.is_absolute()
            else root.resolve()
        )
        if (
            root != pathlib.Path(protected_root).resolve()
            or root != pathlib.Path(item.get("root", "")).resolve()
            or item.get("identity") != registered_repo["expected_identity"]
        ):
            raise Incomplete(
                "repository path/identity differs from protected registration"
            )
        if registered_repo["kind"] != "git" or not root.is_dir():
            raise Incomplete("a real registered Git checkout is required")
        actual_root = pathlib.Path(
            git_read(root, ["rev-parse", "--show-toplevel"]).decode("utf-8").strip()
        ).resolve()
        actual_identity = (
            git_read(root, ["config", "--local", "--get", "remote.origin.url"])
            .decode("utf-8")
            .strip()
        )
        if (
            actual_root != root
            or actual_identity != registered_repo["expected_identity"]
        ):
            raise Incomplete("actual Git root/origin differs from registered identity")
        if mode == "merge":
            allowed_ref = policy.get("allowed_ref")
            if (
                not isinstance(allowed_ref, str)
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", allowed_ref)
                or allowed_ref.startswith("-")
            ):
                raise Incomplete("latest authorized merge ref is unknown")
            head = (
                git_read(root, ["rev-parse", "--verify", allowed_ref + "^{commit}"])
                .decode("ascii")
                .strip()
            )
        else:
            head = (
                git_read(root, ["rev-parse", "--verify", "HEAD^{commit}"])
                .decode("ascii")
                .strip()
            )
        if item.get("head") != head or target["revision"] != head:
            raise Incomplete("code revision differs from the fixed authorized identity")
        files = item.get("files")
        if not isinstance(files, dict) or not files:
            raise Incomplete("code file byte manifest missing")
        actual_files, dirty = {}, False
        for relative, expected in files.items():
            path = safe_path(root, relative)
            if not any(
                module == "."
                or relative == module
                or relative.startswith(module.rstrip("/") + "/")
                for module in declared_target["module_roots"]
            ):
                raise Incomplete("code file is outside registered Target modules")
            committed = git_read(root, ["cat-file", "blob", head + ":" + relative])
            raw = committed if mode == "merge" else path.read_bytes()
            if digest(raw) != expected:
                raise Incomplete("code bytes differ from the fixed context")
            dirty = dirty or raw != committed
            actual_files[relative] = expected
        if mode == "local" and (
            not isinstance(item.get("dirty"), bool) or item["dirty"] != dirty
        ):
            raise Incomplete("checked-file dirty state does not match fixed context")
        result["repos"][repo_id] = {
            "root": str(root),
            "head": head,
            "files": actual_files,
            "checked_files_dirty": dirty,
        }
    return result


def claims_and_sources(ctx, view):
    knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
    resources = importlib.import_module(ctx.domain.__package__ + ".source_resources")
    source_lock = resources.read_source_lock(ctx.root)
    for row in view["writes"]:
        if row["path"] == "governance/sources.lock.yaml":
            source_lock = ctx.domain.load_yaml(
                base64.b64decode(row["bytes_b64"], validate=True)
            )
            ctx.domain.validate_shape("sources", source_lock, ctx.rules)
    rules = {**ctx.rules, "source_lock": source_lock}
    claims = {}
    for row in view["writes"]:
        if not row["path"].startswith("knowledge/") or pathlib.PurePosixPath(
            row["path"]
        ).name in ("AGENTS.md", "index.md", "README.md"):
            continue
        card = knowledge.parse_card(
            base64.b64decode(row["bytes_b64"], validate=True), row["path"], rules
        )
        if card["metadata"]["review_mode"] != "code_gate":
            if view.get("review_mode") == "mixed":
                continue
            raise Invalid("code view contains a document-review card")
        knowledge.validate_card(card, None, rules)
        for claim in card["claims"]:
            key = (card["metadata"]["id"], claim["id"])
            if key in claims:
                raise Invalid("duplicate Claim in code view")
            claims[key] = {
                **claim,
                "card_path": row["path"],
                "card_lifecycle": card["metadata"]["lifecycle"],
                "replacement": card["metadata"].get("replacement") or [],
                "deprecation_reason": card["metadata"].get("deprecation_reason"),
            }
    if not claims:
        raise Incomplete("code view contains no verifiable Claims")
    return claims, source_lock, resources


def verify_report(ctx, report, view, context, mode):
    trust = ctx.catalog.get("semantic_reviewers", {}).get(report.get("reviewer_id"))
    if not trust:
        raise Incomplete("trusted semantic reviewer is not available")
    if trust.get("synthetic"):
        marker = ctx.root / ".isolated-knowledge-fixture"
        if (
            not trust.get("fixture_root")
            or pathlib.Path(trust["fixture_root"]).resolve() != ctx.root
            or not marker.is_file()
            or marker.read_text(encoding="utf-8").strip()
            != "AIOTBOT_SYNTHETIC_FIXTURE_V2"
        ):
            raise Incomplete("synthetic semantic reviewer requires an isolated fixture")
    payload = report.get("payload")
    if (
        report.get("schema_version") != "2.0"
        or report.get("record_kind") != "semantic_review"
        or not isinstance(payload, dict)
    ):
        raise Failed("invalid signed semantic report")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(trust["public_key_b64"], validate=True)
        )
        public.verify(
            base64.b64decode(report["signature_b64"], validate=True), canonical(payload)
        )
    except Exception as exc:
        raise Failed("semantic reviewer signature invalid") from exc
    if (
        payload.get("view_digest") != view["digest"]
        or payload.get("context_digest") != context["digest"]
        or payload.get("mode") != mode
    ):
        raise Failed("semantic report exact-view/context/mode binding mismatch")
    issued = payload.get("issued_at")
    if (
        not isinstance(issued, (int, float))
        or isinstance(issued, bool)
        or not math.isfinite(issued)
        or issued > time.time() + 60
    ):
        raise Failed("semantic report timestamp invalid")
    return payload, "synthetic_code_reviewer" if trust.get(
        "synthetic"
    ) else "authenticated_code_reviewer"


def frozen_identity(ctx, context, mode):
    """Validate persisted signed context/evidence without reading today's checkout."""
    target, build, repos = (
        context.get("target"),
        context.get("build_evidence"),
        context.get("repos"),
    )
    if (
        not isinstance(target, dict)
        or not isinstance(build, dict)
        or not isinstance(repos, dict)
        or not repos
        or build.get("profile") != target.get("build_profile")
        or build.get("source_revision") != target.get("revision")
        or not re.fullmatch(r"[0-9a-f]{64}", str(build.get("macro_digest", "")))
    ):
        raise Incomplete("historical context/build identity is incomplete")
    result = {
        "repos": {},
        "target": target,
        "build_files": {},
        "macro_digest": build["macro_digest"],
    }
    if not build.get("artifacts"):
        raise Incomplete("historical build evidence is missing")
    for item in build["artifacts"]:
        raw = ctx.path(item.get("path"), ("logs/evidence",)).read_bytes()
        if digest(raw) != item.get("sha256"):
            raise Incomplete("historical build evidence bytes changed")
        result["build_files"][item["path"]] = item["sha256"]
    for repo_id, item in repos.items():
        if (
            not isinstance(item.get("files"), dict)
            or not item["files"]
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(item.get("head", "")))
        ):
            raise Incomplete("historical repository manifest is incomplete")
        for relative, expected in item["files"].items():
            safe_path(ctx.root, relative)
            if not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
                raise Incomplete("historical code byte identity is incomplete")
        result["repos"][repo_id] = {
            "root": str(pathlib.Path(item["root"])),
            "head": item["head"],
            "files": item["files"],
            "checked_files_dirty": bool(item.get("dirty"))
            if mode == "local"
            else False,
        }
    return result


def evaluate(
    ctx,
    request,
    view,
    mode,
    report_override=None,
    record_snapshots=False,
    historical=False,
):
    context_ref = request.get("context_ref") or view.get("context_ref")
    if not context_ref:
        raise Incomplete("fixed real code context is missing")
    ctx.path(
        context_ref,
        (
            f".build/operations/{view['operation_id']}",
            ".build/project-context",
            "logs/contexts",
        ),
    )
    if not ctx.path(context_ref).is_file():
        raise Incomplete("fixed real code context is unavailable")
    context = ctx.read(context_ref)
    if (
        context.get("record_kind") != "project_context"
        or context.get("state") not in ("loaded", "context_loaded")
        or (
            not historical
            and pathlib.Path(context.get("knowledge_root", "")).resolve() != ctx.root
        )
    ):
        raise Incomplete("code context is not a project context")
    if historical:
        before = frozen_identity(ctx, context, mode)
    else:
        config, policy, config_raw = read_configuration(ctx, context)
        before = code_identity(ctx, context, config, policy, mode)
    claims, source_lock, resources = claims_and_sources(ctx, view)
    selected_card = request.get("card_path")
    if selected_card and selected_card not in {
        claim["card_path"] for claim in claims.values()
    }:
        raise Invalid("requested card is not in the signed code view")
    report_ref = request.get("semantic_report_ref")
    if report_override is None and not report_ref:
        raise Incomplete("positive signed semantic evidence is missing")
    report = (
        report_override
        if report_override is not None
        else strict_json(
            ctx.path(
                report_ref,
                ("logs/semantic-reviews", f".build/operations/{view['operation_id']}"),
            ).read_text(encoding="utf-8")
        )
    )
    payload, tier = verify_report(ctx, report, view, context, mode)
    rows = payload.get("claims")
    if not isinstance(rows, list) or len(rows) != len(claims):
        raise Incomplete("semantic evidence does not cover every Claim exactly once")
    seen, verified_claims, checked_snapshots = set(), [], {}
    resource_map = {item["source_id"]: item for item in source_lock["resources"]}
    for row in rows:
        key = (row.get("card_id"), row.get("claim_id"))
        if key not in claims or key in seen:
            raise Failed("duplicate or unexpected semantic Claim")
        seen.add(key)
        knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
        retired = claims[key]["card_lifecycle"] == "deprecated"
        if not retired and not knowledge.match_scope(
            claims[key], context["target"], "implementation"
        ):
            raise Incomplete(
                "Claim applicability is not supported by this fixed Target/build context"
            )
        if retired:
            if (
                row.get("status") != "retired"
                or not isinstance(row.get("reason"), str)
                or not row["reason"].strip()
                or row["reason"] != claims[key]["deprecation_reason"]
                or row.get("replacement") != claims[key]["replacement"]
            ):
                raise Failed(
                    "retired Claim requires signed exact reason and replacement mapping"
                )
        elif row.get("status") != "supported":
            raise Failed("semantic reviewer did not support every Claim")
        if selected_card and claims[key]["card_path"] != selected_card:
            verified_claims.append(row)
            continue
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise Incomplete("zero findings do not constitute positive evidence")
        claim_sources = claims[key]["source_records"]
        code_support = False
        for ref in claim_sources:
            matching = [
                item
                for item in evidence
                if item.get("source_id") == ref["source_id"]
                and item.get("snapshot_id") == ref["snapshot_id"]
                and item.get("locator") == ref["locator"]
            ]
            if not matching:
                raise Incomplete("Claim source locator is not positively covered")
            snapshot = resources.validate_source_ref(ref, source_lock)
            raw = resources.recover_snapshot(ctx.root, snapshot)
            if any(item.get("sha256") != digest(raw) for item in matching):
                raise Failed("signed evidence digest does not match immutable snapshot")
            resource = resource_map[ref["source_id"]]
            if resource["kind"] == "code":
                if retired:
                    code_support = True
                    continue
                for item in matching:
                    checked = item.get("checked_snapshot")
                    if checked is None:
                        repo_id = ref["locator"].get("repo_id") or resource.get(
                            "repo_id"
                        )
                        relative = ref["locator"].get("path") or resource.get("path")
                        actual = (
                            before["repos"]
                            .get(repo_id, {})
                            .get("files", {})
                            .get(relative)
                        )
                        if actual != snapshot["sha256"]:
                            raise Incomplete(
                                "latest code changed; independent signed checked_snapshot evidence is required"
                            )
                        continue
                    repo_id, relative = checked.get("repo_id"), checked.get("path")
                    repo = before["repos"].get(repo_id)
                    if (
                        not repo
                        or repo["files"].get(relative) != checked.get("sha256")
                        or checked.get("commit") != repo["head"]
                        or not isinstance(checked.get("snapshot_id"), str)
                        or not re.fullmatch(
                            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", checked["snapshot_id"]
                        )
                    ):
                        raise Incomplete(
                            "checked snapshot is not bound to the latest authorized context"
                        )
                    recovery_ref = (
                        "logs/evidence/checked-code/" + checked["sha256"] + ".bin"
                    )
                    if historical:
                        current = ctx.path(recovery_ref).read_bytes()
                    else:
                        source_path = safe_path(repo["root"], relative)
                        current = (
                            git_read(
                                repo["root"],
                                ["cat-file", "blob", repo["head"] + ":" + relative],
                            )
                            if mode == "merge"
                            else source_path.read_bytes()
                        )
                    location = checked.get("locator")
                    if (
                        not isinstance(location, dict)
                        or location.get("kind") != "lines"
                        or not isinstance(location.get("start"), int)
                        or not isinstance(location.get("end"), int)
                        or not 1
                        <= location["start"]
                        <= location["end"]
                        <= len(current.splitlines())
                        or checked.get("sha256") != digest(current)
                        or checked.get("bytes") != len(current)
                    ):
                        raise Incomplete("checked code bytes or locator are not valid")
                    recovery_ref = (
                        "logs/evidence/checked-code/" + checked["sha256"] + ".bin"
                    )
                    recovery = ctx.path(recovery_ref)
                    if recovery.exists() and recovery.read_bytes() != current:
                        raise Invalid("checked evidence object was changed")
                    if not recovery.exists():
                        if not record_snapshots:
                            raise Incomplete("checked code recovery object is missing")
                        atomic_bytes(recovery, current)
                    checked_record = {**checked, "recovery": {"path": recovery_ref}}
                    if (
                        checked["snapshot_id"] in checked_snapshots
                        and checked_snapshots[checked["snapshot_id"]] != checked_record
                    ):
                        raise Failed(
                            "checked snapshot ID has conflicting byte identities"
                        )
                    checked_snapshots[checked["snapshot_id"]] = checked_record
                code_support = True
        if not code_support:
            raise Incomplete("code Claims require positive code-snapshot support")
        verified_claims.append(row)
    after = (
        frozen_identity(ctx, context, mode)
        if historical
        else code_identity(ctx, context, config, policy, mode)
    )
    if (
        before != after
        or (
            not historical
            and (ctx.root.parent / "config.yml").read_bytes() != config_raw
        )
        or ctx.read(context_ref)["digest"] != context["digest"]
        or checked_view(ctx, request)["digest"] != view["digest"]
    ):
        raise Incomplete("read-only gate inputs changed while checking")
    return {
        "context_ref": context_ref,
        "context_digest": context["digest"],
        "code_identity": before,
        "claims": verified_claims,
        "checked_snapshots": list(checked_snapshots.values()),
        "semantic_report": report,
        "verification_tier": tier,
    }


def local_check(ctx, request, action="run"):
    op = ctx.operation(request)
    view = checked_view(ctx, request)
    if view.get("review_mode") not in {"code_gate", "mixed"}:
        raise Invalid("pure-document views are exempt and reject code-gate invocation")
    if action not in ("run", "merge", "verify-proof"):
        raise Invalid("unsupported code-gate action")
    if action == "verify-proof":
        ctx.path(request.get("proof_ref"), (f"logs/operations/{op}",))
        proof = ctx.read(request.get("proof_ref"))
        if proof.get("delegated_proof_ref"):
            delegated_ref = proof["delegated_proof_ref"]
            ctx.path(delegated_ref, (f"logs/operations/{op}",))
            delegated = ctx.read(delegated_ref)
            if (
                proof.get("record_kind") != "merge_check"
                or proof.get("mode") != "merge"
                or proof.get("status") != "passed"
                or proof.get("view_digest") != view["digest"]
                or delegated.get("digest") != proof.get("delegated_proof_digest")
                or delegated.get("claims") != proof.get("claims")
            ):
                raise Invalid("merge handoff differs from its exact engine proof")
            proof = delegated
        mode = proof.get("mode")
        purpose = request.get("purpose", "current")
        if purpose not in ("current", "historical"):
            raise Invalid("unknown proof purpose")
        if (
            proof.get("record_kind")
            != ("merge_check" if mode == "merge" else "local_check")
            or proof.get("status") != "passed"
            or mode not in ("local", "merge")
            or proof.get("view_digest") != view["digest"]
        ):
            raise Blocked("proof is not a passing local check for this view")
        verified = evaluate(
            ctx,
            {**request, "context_ref": proof.get("context_ref")},
            view,
            mode,
            proof.get("semantic_report"),
            historical=purpose == "historical",
        )
        if (
            verified["claims"] != proof.get("claims")
            or verified["context_digest"] != proof.get("context_digest")
            or verified["code_identity"] != proof.get("code_identity")
            or any(
                snapshot not in proof.get("checked_snapshots", [])
                for snapshot in verified["checked_snapshots"]
            )
        ):
            raise Invalid("code proof differs from current authenticated evidence")
        return {
            "proof_verified": True,
            "mode": mode,
            "purpose": purpose,
            "card_path": request.get("card_path"),
            "view_digest": view["digest"],
            "verification_tier": verified["verification_tier"],
            "phase": "verified",
        }
    mode = "merge" if action == "merge" else "local"
    details, gaps, status = {}, [], "passed"
    try:
        details = evaluate(ctx, request, view, mode, record_snapshots=True)
    except Incomplete as exc:
        status, gaps = "incomplete", [str(exc)]
    except Failed as exc:
        status, gaps = "failed", [str(exc)]
    record = ctx.record(
        "merge_check" if mode == "merge" else "local_check",
        op,
        status=status,
        mode=mode,
        view_ref=request["view_ref"],
        view_digest=view["digest"],
        claims=details.pop("claims", []),
        gaps=gaps,
        **details,
    )
    attempt = request.get("workflow", {}).get("attempt_id")
    if attempt is not None and (
        not isinstance(attempt, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", attempt)
    ):
        raise Invalid("invalid workflow attempt_id")
    suffix = "-" + attempt if attempt else ""
    ref = f"logs/operations/{op}/{mode}-check{suffix}.json"
    ctx.save(ref, record)
    return {
        "merge_check_ref" if mode == "merge" else "local_check_ref": ref,
        "check_status": status,
        "mode": mode,
        "phase": status,
    }
