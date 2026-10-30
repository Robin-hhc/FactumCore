"""Read-only raw acquisition with immutable local recovery objects."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
from urllib.parse import unquote, urlsplit

import yaml

from . import staging, source_resources

from .runtime import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
    safe,
    sha,
)

RAW_CLASSES = {"conventions", "chips", "storys", "specs", "protocols", "troubleshooting"}


def extract(context, data, suffix, *, primary=True):
    try:
        return context.modules["source_resources"].extract_document(data, suffix, primary=primary)
    except context.modules["validation"].ContractError as exc:
        raise NodeError(exc.code, exc.message, exc.path, blocked=exc.code == "PARTIAL_DOCUMENT") from exc
    except ImportError as exc:
        raise NodeError("SOURCE_ADAPTER_UNAVAILABLE", "The fixed document adapter is unavailable", blocked=True) from exc
    except Exception as exc:
        # Fixed adapters expose format-specific exceptions for malformed input.
        # Preserve programmer errors; only adapter/encoding failures become
        # source diagnostics which an opt-in patrol may isolate per document.
        if isinstance(exc, (UnicodeError, EOFError)) or type(exc).__module__.split(".")[0] in {"pypdf", "docx", "lxml", "zipfile"}:
            raise NodeError("UNREADABLE_DOCUMENT", "The fixed adapter cannot read this original: " + str(exc)) from exc
        raise


def raw_member(context, ref, expected_binding=None):
    if source_resources.is_dbox_path(ref):
        try:
            observed = source_resources.read_dbox(context.root, ref, expected_binding or getattr(context, "expected_dbox_binding", None))
        except context.modules["validation"].ContractError as exc:
            raise NodeError(exc.code, exc.message, exc.path, blocked=exc.code == "DBOX_BINDING_CHANGED",
                            data={"needs_scan": True, "affected_scope": [ref]} if exc.code == "DBOX_BINDING_CHANGED" else None) from exc
        return {"path": ref, "data": observed["data"], "signature": observed["signature"],
                "dbox_binding": observed["dbox_binding"]}
    parts = PurePosixPath(ref).parts if isinstance(ref, str) else ()
    if len(parts) < 3 or parts[0] != "docs-raw" or parts[1] not in RAW_CLASSES:
        raise NodeError(
            "RAW_SCOPE_REQUIRED", "Expected a file in a supported landed docs-raw class", ref
        )
    path = safe(context.root, ref)
    if not path.is_file():
        raise NodeError("SOURCE_MISSING", "Expected a landed regular raw file", ref)
    before = path.stat()
    data = fixed_bytes(context.root, ref)
    after = path.stat()

    def signature(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns

    if signature(before) != signature(after):
        raise NodeError("SOURCE_CHANGED", "Original changed while reading", ref)
    return {"path": ref, "data": data, "signature": signature(after)}


def _attachment_references(members):
    """Parse local references once for both explicit checks and enumeration."""
    references, gaps = [], []
    for member in members:
        if PurePosixPath(member["path"]).suffix.lower() != ".md":
            continue
        text = member["data"].decode("utf-8-sig")
        text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
        text = re.sub(r"(?s)<!--.*?-->|`[^`\n]*`", "", text)
        targets = re.findall(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)", text)
        targets += re.findall(r"(?im)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", text)
        targets += re.findall(
            r"""(?is)<(?:img|object|iframe|source)\b[^>]*(?:src|data)\s*=\s*["']([^"']+)["']""",
            text,
        )
        targets += re.findall(
            r"""(?is)<(?:img|object|iframe|source)\b[^>]*(?:src|data)\s*=\s*([^\s"'=<>`]+)""",
            text,
        )
        for target in targets:
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                if parsed.scheme or parsed.netloc:
                    gaps.append(
                        "Remote and embedded URI references were not fetched or interpreted"
                    )
                continue  # references remain unvisited; remote bytes never become source evidence.
            path = unquote(parsed.path)
            if path.startswith("/") or "\\" in path or ":" in path:
                raise NodeError(
                    "UNSAFE_ATTACHMENT",
                    "Attachment path must be local raw-relative",
                    path,
                )
            parts = list(PurePosixPath(member["path"]).parent.parts)
            for part in PurePosixPath(path).parts:
                if part == "..":
                    if not parts:
                        raise NodeError(
                            "UNSAFE_ATTACHMENT", "Attachment escapes raw root", target
                        )
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            resolved = "/".join(parts)
            if source_resources.is_dbox_path(member["path"]) and not source_resources.is_dbox_path(resolved):
                raise NodeError("UNSAFE_ATTACHMENT", "Attachment cannot leave the dbox source root", member["path"])
            references.append(resolved)
    return sorted(set(references)), gaps


def check_attachments(members):
    supplied = {member["path"] for member in members}
    references, gaps = _attachment_references(members)
    for resolved in references:
        if resolved not in supplied:
            raise NodeError("ATTACHMENT_REQUIRED", "Referenced local attachment must be explicit", resolved)
    return gaps


def local_attachments(context, primary):
    """Enumerate landed Markdown dependencies; never fetch URIs or follow links.

    This is an explicit prepare option, not source.capture's default behavior.
    Every discovered path goes through the same raw class and safe-file checks
    as explicitly supplied evidence. Cycles are finite and originals stay read
    only. Unsupported media retain opaque bytes and extraction limitations.
    """
    members, pending = {}, [primary]
    while pending:
        ref = pending.pop()
        if ref in members:
            continue
        member = raw_member(context, ref)
        members[ref] = member
        references, _ = _attachment_references([member])
        pending.extend(path for path in references if path not in members)
    return sorted(set(members) - {primary})


def snapshot_text(context, snapshot, resource, data, *, staged_objects=None):
    """Use frozen local extraction or reproduce it from the exact Git original."""
    suffix = snapshot.get("format", PurePosixPath(resource["path"]).suffix.lower())
    retained = snapshot.get("extraction")
    if retained:
        reconstructed = False
        try:
            extracted = _evidence_bytes(context, retained["text_ref"], retained["text_sha256"], "extractions", ".txt", staged_objects)
            locator_bytes = _evidence_bytes(context, retained["locator_ref"], retained["locator_sha256"], "locators", ".json", staged_objects)
            text = extracted.decode("utf-8")
            locators = json.loads(locator_bytes)["locators"]
            gaps = list(retained.get("limitations", []))
        except OSError:
            if resource.get("kind") == "code":
                try:
                    text, locators = context.modules["source_resources"].extract_code_text(data, retained.get("extractor"))
                except context.modules["validation"].ContractError as exc:
                    raise NodeError("SOURCE_EXTRACTION_UNAVAILABLE", "Frozen code extraction cannot be reproduced by its fixed adapter", blocked=True) from exc
                gaps = list(retained.get("limitations", []))
            else:
                text, locators, extractor, gaps = extract(context, data, suffix, primary=False)
                if extractor != retained.get("extractor"):
                    raise NodeError("SOURCE_EXTRACTION_UNAVAILABLE", "The installed document adapter differs from the frozen adapter", blocked=True)
            if text is None:
                raise NodeError("SOURCE_EXTRACTION_UNAVAILABLE", "Exact original could not reproduce its frozen extraction", blocked=True)
            extracted = text.encode("utf-8")
            locator_bytes = canonical({"locators": locators})
            reconstructed = True
        if (sha(extracted) != retained["text_sha256"] or sha(locator_bytes) != retained["locator_sha256"]
                or (snapshot.get("locator", {}).get("sha256") and sha(locator_bytes) != snapshot["locator"]["sha256"])):
            if reconstructed:
                raise NodeError("SOURCE_EXTRACTION_UNAVAILABLE", "Exact original cannot reproduce frozen extraction and locators under current rules", blocked=True)
            raise NodeError("SOURCE_INTEGRITY_ERROR", "Frozen or reconstructed extraction/locators differ")
        return text, locators, gaps
    if resource.get("kind") == "code":
        return None, [], ["Frozen code snapshot has no interpreted text extraction; only exact original bytes are available"]
    text, locators, _, gaps = extract(context, data, suffix, primary=False)
    if text is not None:
        gaps.append("This snapshot has no retained extraction; text was re-extracted by the current pinned resolver")
    return text, locators, gaps


def _evidence_bytes(context, ref, expected, folder, suffix, entries=None):
    safe(context.root, ref, ["logs/evidence"])
    try:
        return staging.read_bytes(context.root, ref, entries, expected_sha=expected)
    except FileNotFoundError:
        return staging.read_bytes(context.root, "logs/evidence/published/" + folder + "/" + expected + suffix,
                                  entries, expected_sha=expected)


def recovered_bytes(context, snapshot, *, staged_objects=None):
    try:
        return context.modules["source_resources"].recover_snapshot(context.root, snapshot, staged_objects=staged_objects)
    except context.modules["validation"].ContractError as exc:
        if exc.code == "EVIDENCE_OBJECT_CHANGED":
            raise NodeError("SOURCE_INTEGRITY_ERROR", "Recovered bytes differ from exact snapshot") from exc
        raise


def symbol_cache(context):
    """Reuse parsed bytes only within this operation, never current observations."""
    cache = getattr(context, "_code_symbol_cache", None)
    if cache is None:
        cache = {}
        context._code_symbol_cache = cache
    return cache


def resolve_source(context, reference, bundle=None):
    lock = bundle
    if lock is None:
        lock = load_yaml(fixed_bytes(context.root, "governance/sources.lock.yaml"))
    matches = [
        s
        for s in lock["snapshots"]
        if s["snapshot_id"] == reference["snapshot_id"]
        and s["source_id"] == reference["source_id"]
    ]
    if len(matches) != 1:
        raise NodeError(
            "SOURCE_UNAVAILABLE",
            "Exact source snapshot is not uniquely registered",
            blocked=True,
        )
    snapshot = matches[0]
    recovery = snapshot.get("recovery", {})
    is_git = isinstance(recovery, dict) and (recovery.get("kind") == "git" or recovery.get("method") == "git")
    if not isinstance(recovery, dict) or not (
        recovery.get("path") or recovery.get("reference")
    ):
        raise NodeError(
            "RECOVERY_UNAVAILABLE",
            "No supported immutable local recovery object",
            blocked=True,
        )
    if (
        recovery.get("path")
        and recovery.get("reference")
        and recovery["path"] != recovery["reference"]
    ):
        raise NodeError("SOURCE_INTEGRITY_ERROR", "Recovery path aliases disagree")
    original_ref = ("git:" + recovery.get("commit", recovery.get("revision", "")) + ":" + recovery["path"]
                    if is_git else recovery.get("path", recovery.get("reference")))
    try:
        data, original_ref = context.modules["source_resources"].recover_snapshot_source(context.root, snapshot,
            staged_objects=staging.entries_from_bundle(bundle))
    except context.modules["validation"].ContractError as exc:
        if exc.code == "EVIDENCE_OBJECT_CHANGED":
            raise NodeError("SOURCE_INTEGRITY_ERROR", "Recovered bytes differ from exact snapshot") from exc
        raise
    if sha(data) != snapshot["sha256"] or len(data) != snapshot["bytes"]:
        raise NodeError(
            "SOURCE_INTEGRITY_ERROR", "Recovered bytes differ from exact snapshot"
        )
    if "code_ref" in reference:
        context.modules["source_resources"].validate_reference(
            reference, lock, lambda fixed_snapshot: data,
            symbol_cache=symbol_cache(context),
        )
    resource = next(
        r for r in lock["resources"] if r["source_id"] == reference["source_id"]
    )
    suffix = snapshot.get("format", PurePosixPath(resource["path"]).suffix.lower())
    text, locators, gaps = snapshot_text(context, snapshot, resource, data,
                                      staged_objects=staging.entries_from_bundle(bundle))
    locator = reference.get("locator", {})
    if resource.get("kind") == "code" and locator.get("kind") == "bytes":
        start, end = locator.get("start"), locator.get("end")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start <= end <= len(data)
        ):
            raise NodeError(
                "INVALID_SOURCE_LOCATOR", "Byte range is outside fixed code bytes"
            )
        text = None
        gaps.append(
            "Byte locator retains exact bytes without asserting semantic text interpretation"
        )
    if text is not None and not locator:
        raise NodeError(
            "INVALID_SOURCE_LOCATOR",
            "Exact source reference requires a readable locator",
        )
    if text is not None and locator:
        kind = locator.get("kind")
        if kind in {"lines", "line"}:
            if resource.get("kind") != "code" and suffix not in {".md", ".txt"}:
                raise NodeError(
                    "INVALID_SOURCE_LOCATOR",
                    "This document format requires its native page/paragraph locator",
                )
            start, end = locator.get("start"), locator.get("end")
            lines = text.splitlines(keepends=True)
            if (
                isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or not 1 <= start <= end <= len(lines)
            ):
                raise NodeError(
                    "INVALID_SOURCE_LOCATOR",
                    "Source line range is outside exact original",
                )
            text = "".join(lines[start - 1 : end])
        elif kind in {"page", "pages", "paragraph", "paragraphs", "table_row"}:
            try:
                selected = context.modules["source_resources"].document_segments(locators, locator, suffix)
            except context.modules["validation"].ContractError as exc:
                raise NodeError(exc.code, exc.message, exc.path) from exc
            text = "\n\n".join(item["text"] for item in selected)
        else:
            raise NodeError(
                "UNSUPPORTED_SOURCE_LOCATOR",
                "Unsupported original locator",
                blocked=True,
            )
    dbox_current = {}
    try:
        if resource.get("kind") == "code":
            current_hash = current_code_hash(context, resource)
        elif source_resources.is_dbox_path(resource.get("path")):
            try:
                current = source_resources.read_dbox(context.root, resource["path"])
                current_hash = current["sha256"]
                dbox_current = {"current_source_binding": current["dbox_binding"],
                                "current_source_path": str(current["actual_path"]),
                                "current_source_observation": {"status": "available"}}
            except (OSError, ValueError) as exc:
                current_hash = None
                dbox_current = {"current_source_binding": None, "current_source_path": None,
                                "current_source_observation": {"status": "unavailable", "code": getattr(exc, "code", "SOURCE_INPUT_UNAVAILABLE")}}
                gaps.append("Current dbox original is unavailable; only exact retained evidence was recovered")
        else:
            current_hash = sha(
                fixed_bytes(context.root, resource["path"], ["docs-raw"])
            )
        current_matches = (
            current_hash == snapshot["sha256"] if current_hash is not None else None
        )
    except OSError:
        current_hash, current_matches = None, None
        gaps.append(
            "Current source location is unavailable; only exact retained evidence was recovered"
        )
    if current_matches is None and resource.get("kind") == "code":
        gaps.append(
            "Current registered code root is unavailable or unauthorized; fixed evidence is historical only"
        )
    if current_matches is False:
        gaps.append("Current source bytes differ from this fixed historical snapshot")
    result = {
        **dbox_current,
        "source_ref": reference,
        "source_kind": resource.get("kind"),
        "resource": resource,
        "snapshot": snapshot,
        "snapshot_digest": digest(snapshot),
        "original_ref": original_ref,
        "sha256": snapshot["sha256"],
        "bytes": len(data),
        "bytes_b64": __import__("base64").b64encode(data).decode(),
        "text": text,
        "locator": locator,
        "limitations": gaps,
        "current_source_matches": current_matches,
        "current_source_sha256": current_hash,
    }
    if "code_ref" in reference:
        navigation = context.modules["source_resources"].resolve_code_navigation(
            context.root, reference, lock, cache=symbol_cache(context),
        )
        result["code_navigation"] = navigation
        if navigation["status"] != "resolved":
            result["limitations"].append(
                "Current code navigation is " + navigation["status"] + ": " + navigation["reason"]
            )
    return result



def git_read(root, arguments, *, optional=False, authorized_root=None):
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_") or key == "GIT_TEST_ASSUME_DIFFERENT_OWNER"
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_OPTIONAL_LOCKS="0",
        GIT_TERMINAL_PROMPT="0",
        GIT_NO_LAZY_FETCH="1",
    )
    argv = [
        "git",
        "--no-pager",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "diff.external=",
        "-c",
        "core.attributesFile=" + os.devnull,
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "safe.directory=" + (authorized_root or root).resolve().as_posix(),
        "-C",
        str(root),
        *arguments,
    ]
    try:
        result = subprocess.run(
            argv, env=environment, capture_output=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NodeError(
            "GIT_UNAVAILABLE", "Cannot inspect registered Git metadata", blocked=True
        ) from exc
    if result.returncode:
        if optional:
            return None
        raise NodeError(
            "GIT_IDENTITY_UNAVAILABLE",
            "Cannot inspect registered Git identity",
            blocked=True,
        )
    return result.stdout


def authorized_repo(context, repo_id, receipt=None, *, module_path=None):
    try:
        config_path = context.modules["validation"].workspace_config_path(
            context.root
        )
    except (ValueError, OSError) as exc:
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Exact workspace config is unavailable",
            blocked=True,
        ) from exc
    workspace = config_path.parent
    config_bytes = config_path.read_bytes()
    config = load_yaml(config_bytes)
    context.modules["validation"].validate_shape("workspace", config, context.rules)
    config = context.modules["validation"].normalize_workspace(config, workspace)
    policy = config.get("code_policy")
    if safe(
        workspace, config["knowledge_roots"]["wifi"]
    ).resolve() != context.root or any(
        row["knowledge_domain"] != "wifi" for row in config["architecture"]
    ):
        raise NodeError(
            "CODE_DOMAIN_MISMATCH",
            "Code registration must bind the selected WiFi knowledge root and domain",
            blocked=True,
        )
    if not policy or config.get("code_policy") != policy:
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Protected and declared code policies differ",
            blocked=True,
        )
    if module_path is not None:
        if not isinstance(module_path, str) or not module_path:
            raise NodeError("CODE_MODULE_UNKNOWN", "module_path must name an actual configured module", blocked=True)
        modules = [row for row in config.get("modules", []) if row["path"] == module_path]
        selected = [row for row in config["repos"] if len(modules) == 1
                    and row.get("workspace_path") == modules[0]["workspace_path"]]
        if config.get("mapping_kind") != "modules" or len(selected) != 1:
            raise NodeError("CODE_MODULE_UNKNOWN", "module_path must uniquely match config.modules[].path", module_path, blocked=True)
        selected_id = selected[0]["repo_id"]
        if repo_id is not None and repo_id != selected_id:
            raise NodeError("CODE_MODULE_MISMATCH", "repo_id and module_path select different modules", module_path, blocked=True)
        repo_id = selected_id
    rows = [row for row in config["repos"] if row["repo_id"] == repo_id]
    root_value = policy.get("repo_roots", {}).get(repo_id)
    if (
        len(rows) != 1
        or not rows[0].get("root")
        or not root_value
        or not Path(root_value).is_absolute()
    ):
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Repository root is not explicitly authorized",
            blocked=True,
        )
    registered = Path(rows[0]["root"])
    if not registered.is_absolute():
        registered = workspace / registered
    root = registered.resolve(strict=True)
    if root != Path(root_value).resolve(strict=True) or not root.is_dir():
        raise NodeError(
            "CODE_ROOT_MISMATCH",
            "Registered repository differs from protected root",
            blocked=True,
        )
    item = None
    if receipt is not None:
        if (
            receipt.get("state") != "context_loaded"
            or receipt.get("workspace_id") != config["workspace_id"]
            or receipt.get("config_digest") != sha(config_bytes)
            or Path(receipt.get("knowledge_root", "")).resolve() != context.root
            or Path(receipt.get("workspace_root", "")).resolve() != workspace
        ):
            raise NodeError(
                "CODE_CONTEXT_STALE",
                "Loaded context does not bind this workspace/config",
                blocked=True,
            )
        repos = receipt.get("repos", {})
        if isinstance(repos, list):
            if len({row["repo_id"] for row in repos}) != len(repos):
                raise NodeError(
                    "CODE_CONTEXT_STALE",
                    "Context repository identities are ambiguous",
                    blocked=True,
                )
            repos = {row["repo_id"]: row for row in repos}
        item = repos.get(repo_id)
        if not item or Path(item.get("root", "")).resolve() != root:
            raise NodeError(
                "CODE_ROOT_MISMATCH",
                "Context cannot authorize a different repository root",
                blocked=True,
            )
    if config_path.read_bytes() != config_bytes:
        raise NodeError(
            "CODE_CONTEXT_STALE",
            "Workspace config changed while resolving authorization",
            blocked=True,
        )
    return root, rows[0], config, item, sha(config_bytes)


def read_code(root, relative):
    if ".git" in {part.casefold() for part in PurePosixPath(relative).parts}:
        raise NodeError(
            "UNSAFE_PATH", "Git internals are not selected source files", relative
        )
    path = safe(root, relative)
    if not path.is_file():
        raise NodeError(
            "CODE_FILE_MISSING",
            "Selected registered code file is unavailable",
            relative,
            blocked=True,
        )
    before = path.stat()
    raw = fixed_bytes(root, relative)
    after = path.stat()

    def signature(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
        )

    if signature(before) != signature(after):
        raise NodeError(
            "CODE_CHANGED", "Selected code changed during read", blocked=True
        )
    return raw, signature(after)


def metadata(root, registered, relative, receipt=None):
    kind = registered["kind"]
    if registered.get("evidence_basis") == "filesystem":
        return {"kind": "export", "revision": None, "checked_file_dirty": None,
                "evidence_basis": "filesystem"}, None
    if kind == "export":
        current = root
        for part in [None, *PurePosixPath(relative).parent.parts]:
            if part not in (None, "."):
                current = current / part
            if (current / ".git").exists():
                raise NodeError(
                    "REPO_KIND_MISMATCH",
                    "Export selection crosses Git metadata",
                    blocked=True,
                )
        return {"kind": "export", "revision": None, "checked_file_dirty": None}, None
    if kind != "git":
        raise NodeError(
            "UNSUPPORTED_CODE_KIND",
            "Repository kind must be git or export",
            blocked=True,
        )
    actual_root = Path(
        git_read(root, ["rev-parse", "--show-toplevel"]).decode().strip()
    ).resolve()
    selected_root = Path(
        git_read((root / relative).parent, ["rev-parse", "--show-toplevel"], authorized_root=root)
        .decode()
        .strip()
    ).resolve()
    if actual_root != root or selected_root != root:
        raise NodeError(
            "GIT_BOUNDARY_MISMATCH",
            "Selection crosses the authorized Git checkout",
            blocked=True,
        )
    origin = git_read(
        root, ["config", "--local", "--get", "remote.origin.url"], optional=True
    )
    origin = origin.decode().strip() if origin is not None else None
    if (
        registered.get("expected_identity")
        and registered["expected_identity"] != origin
    ):
        raise NodeError(
            "GIT_IDENTITY_MISMATCH",
            "Actual origin differs from registered identity",
            blocked=True,
        )
    head = git_read(root, ["rev-parse", "--verify", "HEAD^{commit}"], optional=True)
    head = head.decode("ascii").strip() if head is not None else None
    if receipt and any(
        receipt.get(field) not in (None, "", "unknown") and receipt[field] != head
        for field in ("head", "commit")
    ):
        raise NodeError(
            "CODE_CONTEXT_STALE", "Git HEAD changed after context loading", blocked=True
        )
    committed = (
        git_read(root, ["cat-file", "blob", head + ":" + relative], optional=True)
        if head
        else None
    )
    return {"kind": "git", "revision": head, "checked_file_dirty": None}, committed


def current_code_hash(context, resource):
    try:
        root, registered, config, _, config_digest = authorized_repo(
            context, resource["repo_id"]
        )
        if not context.modules["validation"].workspace_file_allowed(config, resource["repo_id"], resource["path"]):
            return None
        before = metadata(root, registered, resource["path"])
        raw, _ = read_code(root, resource["path"])
        after = metadata(root, registered, resource["path"])
        _, _, _, _, after_config = authorized_repo(context, resource["repo_id"])
        if before != after or config_digest != after_config:
            return None
        return sha(raw)
    except (OSError, NodeError, ValueError, yaml.YAMLError):
        return None


def _formal_lock(context):
    try:
        raw = fixed_bytes(context.root, "governance/sources.lock.yaml")
    except FileNotFoundError:
        return {"resources": [], "snapshots": []}, None
    return load_yaml(raw), sha(raw)


def _registered_snapshot(snapshot, lock):
    registered = [item for item in lock.get("snapshots", []) if item["snapshot_id"] == snapshot["snapshot_id"]]
    if registered:
        if len(registered) != 1 or any(registered[0].get(key) != snapshot.get(key)
                                      for key in ("source_id", "sha256", "bytes")):
            raise NodeError("SOURCE_INTEGRITY_ERROR", "Registered snapshot conflicts with captured identity")
        return dict(registered[0])
    return snapshot


def _stage_payloads(context, payloads):
    kinds = {"objects": "original", "locators": "locator", "extractions": "extraction"}
    return staging.merge_entries([staging.stage_bytes(context, ref, data, kind=kinds[PurePosixPath(ref).parent.name])
                                   for ref, data in sorted(payloads.items())])


def _event_proposals(lock, lock_digest, snapshots):
    changes = []
    for snapshot in snapshots:
        prior = [item["snapshot_id"] for item in lock.get("snapshots", [])
                 if item["source_id"] == snapshot["source_id"]]
        if prior and snapshot["snapshot_id"] not in prior:
            changes.append({"source_id": snapshot["source_id"], "old_snapshot_ids": sorted(prior),
                            "new_snapshot_id": snapshot["snapshot_id"], "source_lock_digest": lock_digest})
    return changes


def capture_code(context):
    request = context.request
    encoding = request.get("text_encoding", "utf-8")
    extractors = {"utf-8": "code-utf8:1", "gb18030": "code-gb18030:1"}
    if not isinstance(encoding, str) or encoding not in extractors:
        raise NodeError("INVALID_CODE_ENCODING", "text_encoding must be utf-8 or gb18030; encoding is never guessed")
    extractor = extractors[encoding]
    repo_id, relative, source_id = (
        request.get("repo_id"),
        request.get("relative_path"),
        request.get("source_id"),
    )
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or any(ord(c) < 32 for c in source_id)
    ):
        raise NodeError("INVALID_SOURCE_ID", "Explicit logical source ID required")
    receipt = context.record(request["context_ref"], "project_context") if request.get("context_ref") else None
    root, registered, config, item, config_digest = authorized_repo(
        context, repo_id, receipt, module_path=request.get("module_path")
    )
    repo_id = registered["repo_id"]
    safe(root, relative)
    if not context.modules["validation"].workspace_file_allowed(config, repo_id, relative):
        raise NodeError(
            "CODE_MODULE_UNKNOWN",
            "Selected code is outside registered architecture modules",
            blocked=True,
        )
    before, committed = metadata(root, registered, relative, item)
    raw, signature = read_code(root, relative)
    code_identity = {
        **before,
        "repo_id": repo_id,
        **({"workspace_path": registered["workspace_path"]} if registered.get("workspace_path") else {}),
        "dirty_scope": "selected_file",
        "checked_file_dirty": (raw != committed) if before["revision"] else None,
    }
    limitations = [
        "not_semantically_verified: actual code bytes are frozen; Target/build/macros require separate positive gate evidence"
    ]
    if before.get("evidence_basis") == "filesystem":
        limitations.append("Version is unknown unless explicitly provided; current source checks use exact file bytes")
    elif before["kind"] == "export":
        limitations.append(
            "No Git revision exists for this export; version remains explicitly unknown"
        )
    try:
        text, locators = context.modules["source_resources"].extract_code_text(raw, extractor)
    except context.modules["validation"].ContractError as exc:
        if "text_encoding" in request:
            raise NodeError("UNREADABLE_CODE_TEXT", "Selected code cannot be strictly decoded by the explicit encoding, or contains NUL") from exc
        text, locators = None, []
        limitations.append(
            "Code encoding is unsupported; original bytes retained without interpreted text"
        )
    raw_hash = sha(raw)
    snapshot_id = "code:" + digest(
        {
            "source_id": source_id,
            "repo_id": repo_id,
            "path": relative,
            "sha256": raw_hash,
            "identity": code_identity,
            "version": request.get("version", "unknown"),
            "text_digest": sha(text.encode()) if text is not None else None,
            "locators": digest(locators),
            **({"extractor": extractor} if encoding != "utf-8" else {}),
        }
    )
    object_ref, locator_ref = (
        "logs/evidence/published/objects/" + raw_hash + ".bin",
        "logs/evidence/published/locators/" + sha(canonical({"locators": locators})) + ".json",
    )
    payloads = {object_ref: raw, locator_ref: canonical({"locators": locators})}
    snapshot = {
        "source_id": source_id,
        "snapshot_id": snapshot_id,
        "sha256": raw_hash,
        "bytes": len(raw),
        "format": PurePosixPath(relative).suffix.lower(),
        "version": request.get("version", "unknown"),
        "code_identity": code_identity,
        "locator": {
            "kind": "locator_map",
            "reference": locator_ref,
            "sha256": sha(payloads[locator_ref]),
        },
        "recovery": {
            "method": "evidence_object",
            "path": object_ref,
            "reference": object_ref,
            "status": "available",
        },
    }
    if before["kind"] == "git" and before["revision"] and committed is not None and raw == committed:
        snapshot["local_recovery"] = dict(snapshot["recovery"])
        snapshot["recovery"] = {"kind": "git", "method": "git", "repo_id": repo_id,
                                "commit": before["revision"], "path": relative, "status": "available"}
        recovered = context.modules["source_resources"].recover_snapshot(context.root, snapshot, allow_local_fallback=False)
        if recovered != raw:
            raise NodeError("SOURCE_INTEGRITY_ERROR", "Exact configured Git code differs from captured bytes")
    extractions = []
    if text is not None:
        text_ref = "logs/evidence/published/extractions/" + sha(text.encode()) + ".txt"
        payloads[text_ref] = text.encode()
        extraction = {
            "snapshot_id": snapshot_id,
            "extractor": extractor,
            "text_ref": text_ref,
            "text_sha256": sha(text.encode()),
            "locator_ref": locator_ref,
            "locator_sha256": sha(payloads[locator_ref]),
            "limitations": limitations,
        }
        snapshot["extraction"] = extraction
        extractions.append(extraction)
    lock, lock_digest = _formal_lock(context)
    snapshot = _registered_snapshot(snapshot, lock)
    extractions = [snapshot["extraction"]] if snapshot.get("extraction") else []
    staged_objects = _stage_payloads(context, payloads)
    bundle = context.seal(
        {
            "resources": [
                {
                    "source_id": source_id,
                    "kind": "code",
                    "repo_id": repo_id,
                    "path": relative,
                }
            ],
            "snapshots": [snapshot],
            "extractions": extractions,
            "context_ref": request.get("context_ref"),
            "config_digest": config_digest,
            "limitations": limitations,
            "staged_objects": staged_objects,
            "event_proposals": _event_proposals(lock, lock_digest, [snapshot]),
        },
        "source_bundle",
    )
    after, after_signature = read_code(root, relative)
    after_identity, after_committed = metadata(root, registered, relative, item)
    _, _, _, _, after_config = authorized_repo(context, repo_id, receipt)
    if (
        after != raw
        or after_signature != signature
        or after_identity != before
        or after_committed != committed
        or after_config != config_digest
    ):
        raise NodeError(
            "CODE_CHANGED",
            "Code or registration changed during evidence capture",
            blocked=True,
        )
    ref = context.save(context.base + "/capture.json", bundle)
    return {
        "bundle_ref": ref,
        "bundle_digest": bundle["digest"],
        "event_refs": [],
        "event_proposals": bundle["event_proposals"],
        "code_identity": code_identity,
        "limitations": limitations,
    }, "captured"


def resolve_bundle(context, reference):
    bundle = context.record(reference, "source_bundle")
    if any(source_resources.is_dbox_path(row.get("path")) for row in bundle["resources"]):
        source_resources.validate_dbox_binding(bundle.get("dbox_binding"))
    entries = staging.validate_entries(context.root, staging.entries_from_bundle(bundle))
    portable_ids = set()
    for snapshot in bundle["snapshots"]:
        recovery = snapshot["recovery"]
        if (
            recovery.get("path")
            and recovery.get("reference")
            and recovery["path"] != recovery["reference"]
        ):
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "Recovery path aliases disagree"
            )
        data = recovered_bytes(context, snapshot, staged_objects=entries)
        if sha(data) != snapshot["sha256"] or len(data) != snapshot["bytes"]:
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "Retained object differs from snapshot"
            )
        if recovery.get("kind") == "git" or recovery.get("method") == "git":
            resource = next(r for r in bundle["resources"] if r["source_id"] == snapshot["source_id"])
            snapshot_text(context, snapshot, resource, data, staged_objects=entries)
            portable_ids.add(snapshot["snapshot_id"])
            continue
        locator = snapshot.get("locator", {})
        if locator.get("reference") and sha(
            _evidence_bytes(context, locator["reference"], locator["sha256"], "locators", ".json", entries)
        ) != locator.get("sha256"):
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR",
                "Retained locator map differs from snapshot",
            )
    for extraction in bundle.get("extractions", []):
        if extraction["snapshot_id"] in portable_ids:
            continue
        if (
            sha(
                _evidence_bytes(context, extraction["text_ref"], extraction["text_sha256"], "extractions", ".txt", entries)
            )
            != extraction["text_sha256"]
        ):
            raise NodeError(
                "SOURCE_INTEGRITY_ERROR", "Retained extraction differs from bundle"
            )
    return {"bundle_ref": reference, "bundle": bundle}


def capture(context):
    request = context.request
    if request.get("kind") == "code":
        return capture_code(context)
    if request.get("kind", "raw") != "raw":
        raise NodeError(
            "CODE_CONTEXT_REQUIRED",
            "This node captures landed raw; code needs registered evidence",
            blocked=True,
        )
    source_id = request.get("source_id")
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or any(ord(c) < 32 for c in source_id)
    ):
        raise NodeError("INVALID_SOURCE_ID", "Explicit logical source ID required")
    refs = [request["source_path"], *request.get("attachments", [])]
    if len(set(refs)) != len(refs):
        raise NodeError("DUPLICATE_ATTACHMENT", "Each original is enumerated once")
    uses_dbox = any(source_resources.is_dbox_path(ref) for ref in refs)
    if uses_dbox:
        if not all(source_resources.is_dbox_path(ref) for ref in refs):
            raise NodeError("UNSAFE_ATTACHMENT", "dbox attachments must share the same source root", source_resources.DBOX_PREFIX)
        current_binding = source_resources.dbox_root(context.root, getattr(context, "expected_dbox_binding", None))["binding"]
        context.expected_dbox_binding = current_binding
    members = [raw_member(context, ref) for ref in refs]
    reference_gaps = check_attachments(members)
    resources, snapshots, extractions, payloads, limitations = [], [], [], {}, []
    limitations += reference_gaps
    lock, lock_digest = _formal_lock(context)
    for i, member in enumerate(members):
        ref, data = member["path"], member["data"]
        text, locators, extractor, gaps = extract(
            context, data, PurePosixPath(ref).suffix.lower(), primary=i == 0
        )
        limitations += gaps
        logical = (
            source_id if i == 0 else source_id + ":attachment:" + sha(ref.encode())[:20]
        )
        object_hash = sha(data)
        snapshot_id = "raw:" + digest(
            {
                "source_id": logical,
                "sha256": object_hash,
                "version": request.get("version"),
                "extractor": extractor,
                "text_digest": sha(text.encode()) if text is not None else None,
                "locator_digest": digest(locators),
            }
        )
        object_ref = "logs/evidence/published/objects/" + object_hash + ".bin"
        locator_ref = "logs/evidence/published/locators/" + sha(canonical({"locators": locators})) + ".json"
        payloads[object_ref], payloads[locator_ref] = (
            data,
            canonical({"locators": locators}),
        )
        resources.append(
            {
                "source_id": logical,
                "kind": "raw" if i == 0 else "attachment",
                "path": ref,
            }
        )
        snapshots.append(
            {
                "source_id": logical,
                "snapshot_id": snapshot_id,
                "sha256": object_hash,
                "bytes": len(data),
                "version": request.get("version"),
                "format": PurePosixPath(ref).suffix.lower(),
                "locator": {
                    "kind": "locator_map",
                    "reference": locator_ref,
                    "sha256": sha(payloads[locator_ref]),
                },
                "recovery": {
                    "method": "evidence_object",
                    "path": object_ref,
                    "reference": object_ref,
                    "status": "available",
                },
            }
        )
        portable = context.modules["source_resources"].git_recovery_for_current(context.root, ref, data)
        if portable:
            snapshots[-1]["local_recovery"] = dict(snapshots[-1]["recovery"])
            snapshots[-1]["recovery"] = portable
        if text is not None:
            text_ref = "logs/evidence/published/extractions/" + sha(text.encode()) + ".txt"
            payloads[text_ref] = text.encode()
            extractions.append(
                {
                    "snapshot_id": snapshot_id,
                    "extractor": extractor,
                    "text_ref": text_ref,
                    "text_sha256": sha(text.encode()),
                    "locator_ref": locator_ref,
                    "locator_sha256": sha(payloads[locator_ref]),
                    "limitations": gaps,
                }
            )
            snapshots[-1]["extraction"] = dict(extractions[-1])
        snapshots[-1] = _registered_snapshot(snapshots[-1], lock)
    extractions = [item["extraction"] for item in snapshots if item.get("extraction")]
    for member in members:
        now = raw_member(context, member["path"])
        if now["data"] != member["data"] or now["signature"] != member["signature"]:
            raise NodeError(
                "SOURCE_CHANGED",
                "Original changed before evidence publication",
                member["path"],
            )
    staged_objects = _stage_payloads(context, payloads)
    bundle = context.seal(
        {
            "resources": resources,
            "snapshots": snapshots,
            "extractions": extractions,
            **({"dbox_binding": current_binding} if uses_dbox else {}),
            "context_ref": request.get("context_ref"),
            "limitations": sorted(set(limitations)),
            "staged_objects": staged_objects,
            "event_proposals": _event_proposals(lock, lock_digest, snapshots),
        },
        "source_bundle",
    )
    ref = context.base + "/capture.json"
    existing = safe(context.root, ref)
    if existing.exists() and existing.read_bytes() != canonical(bundle):
        raise NodeError(
            "OPERATION_CONFLICT", "Operation already captures different originals", ref
        )
    for member in members:
        now = raw_member(context, member["path"])
        if now["data"] != member["data"] or now["signature"] != member["signature"]:
            raise NodeError(
                "SOURCE_CHANGED",
                "Original changed during evidence publication",
                member["path"],
            )
    context.save(ref, bundle)
    return {
        "bundle_ref": ref,
        "bundle_digest": bundle["digest"],
        "event_refs": [],
        "event_proposals": bundle["event_proposals"],
        "limitations": bundle["limitations"],
    }, "captured"


def current_source_bindings(context, resource, snapshot, *, expected_binding=None):
    """Return authorized current paths only when they still match fixed bytes."""
    if resource.get("kind") == "code":
        root, _, config, _, config_digest = authorized_repo(context, resource["repo_id"])
        if not context.modules["validation"].workspace_file_allowed(config, resource["repo_id"], resource["path"]):
            raise NodeError("CODE_MODULE_UNKNOWN", "Selected code is outside configured modules", blocked=True)
        raw, _ = read_code(root, resource["path"])
        config_path = context.modules["validation"].workspace_config_path(context.root)
        config_bytes = config_path.read_bytes()
        if sha(config_bytes) != config_digest:
            raise NodeError("SOURCE_CHANGED", "Workspace configuration changed during material binding", str(config_path), blocked=True,
                            data={"needs_scan": True, "affected_scope": [str(config_path)]})
        result = [{"path": safe(root, resource["path"]).as_posix(), "sha256": sha(raw), "bytes": len(raw), "kind": "code"},
                  {"path": config_path.as_posix(), "sha256": config_digest, "bytes": len(config_bytes), "kind": "config"}]
    else:
        member = raw_member(context, resource["path"], expected_binding)
        raw = member["data"]
        result = [{"path": resource["path"], "sha256": sha(raw), "bytes": len(raw),
                   "kind": "external_raw" if "dbox_binding" in member else "raw",
                   **({"dbox_binding": member["dbox_binding"]} if "dbox_binding" in member else {})}]
    if sha(raw) != snapshot["sha256"] or len(raw) != snapshot["bytes"]:
        raise NodeError("SOURCE_CHANGED", "Current source differs from adopted material", resource["path"], blocked=True,
                        data={"needs_scan": True, "affected_scope": [resource["path"]]})
    return result


def execute(context):
    """Public source operations; no ResultEnvelope or sibling process ownership."""
    action = context.args.action or "capture"
    if action in {"run", "capture"}:
        return capture(context)
    if action == "resolve":
        return resolve_bundle(context, context.request["bundle_ref"]), "resolved"
    if action == "resolve-source":
        bundle = (context.record(context.request["bundle_ref"], "source_bundle")
                  if context.request.get("bundle_ref") else None)
        return resolve_source(context, context.request["source_ref"], bundle), "resolved"
    raise NodeError("UNKNOWN_ACTION", "Expected capture, resolve or resolve-source", action)
