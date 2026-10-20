"""Freeze registered selected code bytes without executing repository programs."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import subprocess

from support import (
    NodeError,
    canonical,
    digest,
    fixed_bytes,
    load_yaml,
    read_json,
    safe,
    sha,
    write_bytes,
)


def git_read(root, arguments, *, optional=False):
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
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


def authorized_repo(context, repo_id, receipt=None):
    if not context.args.catalog:
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Installed code policy is required",
            blocked=True,
        )
    catalog = read_json(context.args.catalog)
    policy = catalog.get("code_policy")
    config_path = context.root.parent / "config.yml"
    if config_path.is_symlink() or not config_path.is_file():
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Workspace config is unavailable",
            blocked=True,
        )
    config_bytes = config_path.read_bytes()
    config = load_yaml(config_bytes)
    context.modules["validation"].validate_shape("workspace", config, context.rules)
    if not policy or config.get("code_policy") != policy:
        raise NodeError(
            "CODE_AUTHORIZATION_REQUIRED",
            "Protected and declared code policies differ",
            blocked=True,
        )
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
        registered = context.root.parent / registered
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
            or receipt.get("config_digest") != sha(config_bytes)
            or Path(receipt.get("knowledge_root", "")).resolve() != context.root
            or Path(receipt.get("workspace_root", "")).resolve() != context.root.parent
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
        git_read((root / relative).parent, ["rev-parse", "--show-toplevel"])
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
    if receipt and receipt.get("head") and receipt["head"] != head:
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
        root, _, _, _, _ = authorized_repo(context, resource["repo_id"])
        raw, _ = read_code(root, resource["path"])
        return sha(raw)
    except (OSError, NodeError):
        return None


def capture_code(context):
    request = context.request
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
    if not request.get("context_ref"):
        raise NodeError(
            "CODE_CONTEXT_REQUIRED",
            "Registered loaded project context is required",
            blocked=True,
        )
    receipt = context.record(request["context_ref"], "project_context")
    root, registered, config, item, config_digest = authorized_repo(
        context, repo_id, receipt
    )
    safe(root, relative)
    if not any(
        binding["repo_id"] == repo_id
        and (
            binding["module_root"] == "."
            or relative.startswith(binding["module_root"].rstrip("/") + "/")
        )
        for binding in config["architecture"]
    ):
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
        "dirty_scope": "selected_file",
        "checked_file_dirty": (raw != committed) if before["revision"] else None,
    }
    limitations = [
        "not_semantically_verified: actual code bytes are frozen; Target/build/macros require separate positive gate evidence"
    ]
    if before["kind"] == "export":
        limitations.append(
            "No Git revision exists for this export; version remains explicitly unknown"
        )
    try:
        text = raw.decode("utf-8-sig")
        if "\0" in text:
            raise UnicodeError("NUL in source text")
        locators = [
            {"kind": "lines", "start": i + 1, "end": i + 1, "text": line}
            for i, line in enumerate(text.splitlines())
        ]
    except UnicodeError:
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
        }
    )
    object_ref, locator_ref = (
        "logs/evidence/objects/" + raw_hash + ".bin",
        "logs/evidence/locators/" + digest(locators) + ".json",
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
    extractions = []
    if text is not None:
        text_ref = "logs/evidence/extractions/" + sha(text.encode()) + ".txt"
        payloads[text_ref] = text.encode()
        extraction = {
            "snapshot_id": snapshot_id,
            "extractor": "code-utf8:1",
            "text_ref": text_ref,
            "text_sha256": sha(text.encode()),
            "locator_ref": locator_ref,
            "locator_sha256": sha(payloads[locator_ref]),
            "limitations": limitations,
        }
        snapshot["extraction"] = extraction
        extractions.append(extraction)
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
            "context_ref": request["context_ref"],
            "config_digest": config_digest,
            "limitations": limitations,
        },
        "source_bundle",
    )
    for ref, data in payloads.items():
        write_bytes(context.root, ref, data)
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
        "code_identity": code_identity,
        "limitations": limitations,
    }, "captured"
