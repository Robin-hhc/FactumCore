"""Finite path discovery and actual entry loading; no whole-disk scan or implicit trust."""

from __future__ import annotations
from pathlib import Path
import subprocess
from support import (
    NodeError,
    canonical,
    domain,
    load_yaml,
    read_json,
    safe,
    sha,
    tool_identity,
    write_bytes,
)


def under(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve(request, registry=None):
    target = Path(request["target_path"]).expanduser().resolve(strict=True)
    candidates = []
    explicit = request.get("config_path")
    if explicit:
        candidates = [(Path(explicit).resolve(strict=True), None)]
    else:
        for parent in (target if target.is_dir() else target.parent, *target.parents):
            path = parent / "config.yml"
            if path.is_file():
                candidates.append((path.resolve(), None))
                break
        if not candidates and registry:
            for entry in read_json(registry).get("workspaces", []):
                path = Path(entry["config_path"]).resolve(strict=True)
                config = load_yaml(path.read_bytes())
                for repo in config.get("repos", []):
                    if repo.get("root"):
                        root = Path(repo["root"])
                        root = (
                            root.resolve()
                            if root.is_absolute()
                            else (path.parent / root).resolve()
                        )
                        if under(target, root):
                            candidates.append((path, entry))
                            break
    unique = {str(path): (path, entry) for path, entry in candidates}
    if len(unique) != 1:
        raise NodeError(
            "BINDING_AMBIGUOUS" if unique else "BINDING_NOT_FOUND",
            "A single registered workspace is required",
            blocked=True,
        )
    config_path, entry = next(iter(unique.values()))
    raw = config_path.read_bytes()
    config = load_yaml(raw)
    workspace = config_path.parent
    roots = config.get("knowledge_roots", {})
    if set(roots) != {"wifi"}:
        raise NodeError(
            "DOMAIN_MAPPING_INVALID", "Exactly the configured WiFi root is required"
        )
    knowledge_root = safe(workspace, roots["wifi"])
    matches = []
    for repo in config.get("repos", []):
        if not repo.get("root"):
            continue
        root = Path(repo["root"])
        root = (
            root.resolve(strict=True)
            if root.is_absolute()
            else (workspace / root).resolve(strict=True)
        )
        if under(target, root):
            matches.append((len(root.parts), repo, root))
    if matches:
        depth = max(x[0] for x in matches)
        matches = [x for x in matches if x[0] == depth]
        if len(matches) != 1:
            raise NodeError(
                "REPO_BINDING_AMBIGUOUS", "Equally specific repo mappings", blocked=True
            )
    elif not under(target, workspace):
        raise NodeError(
            "TARGET_NOT_REGISTERED",
            "Target path has no registered repo mapping",
            blocked=True,
        )
    if config_path.read_bytes() != raw:
        raise NodeError(
            "CONFIG_CHANGED", "Config changed while resolving", blocked=True
        )
    return target, workspace, knowledge_root, config_path, config, raw, entry, matches


def execute(request, args, package):
    target, workspace, root, config_path, config, raw, entry, matches = resolve(
        request, args.registry
    )
    pinned = args.rules_digest or (entry or {}).get("rules_digest")
    if not pinned and args.catalog:
        catalog = read_json(args.catalog)
        pinned = (
            catalog.get("workspaces", {})
            .get(config.get("workspace_id"), {})
            .get("rules_digest")
        )
    if not pinned:
        return {
            "state": "resolved",
            "workspace_id": config.get("workspace_id"),
            "knowledge_root": str(root),
            "config_path": str(config_path),
            "gaps": ["trusted_rules_digest_required"],
        }, "resolved"
    modules, rules = domain(root, pinned)
    modules["validation"].validate_shape("workspace", config, rules)
    entries = [workspace / "AGENTS.md", root / "AGENTS.md"]
    if matches:
        repo_root = matches[0][2]
        current = target if target.is_dir() else target.parent
        local = []
        while under(current, repo_root):
            path = current / "AGENTS.md"
            if path.is_file():
                local.append(path)
            if current == repo_root:
                break
            current = current.parent
        entries.extend(reversed(local))
    trace = []
    observed = {}
    for path in dict.fromkeys(entries):
        if not path.is_file():
            raise NodeError(
                "ENTRY_NOT_READABLE", "Required Agent entry missing", path, blocked=True
            )
        data = path.read_bytes()
        trace.append(
            {
                "path": str(path),
                "sha256": sha(data),
                "content": data.decode("utf-8-sig"),
            }
        )
        observed[path] = data
    repos = {}
    gaps = []
    if not matches:
        gaps.append("real_business_repo_unknown")
    else:
        repo = matches[0][1]
        code_root = matches[0][2]
        git = [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=NUL",
            "-C",
            str(code_root),
        ]
        result = subprocess.run(
            git + ["rev-parse", "HEAD"], capture_output=True, check=False, timeout=30
        )
        repos[repo["repo_id"]] = {
            "repo_id": repo["repo_id"],
            "root": str(code_root),
            "commit": result.stdout.decode().strip()
            if result.returncode == 0
            else None,
            "dirty": "unknown",
            "build_profile": None,
            "files": {},
        }
        gaps.append("build_and_dirty_context_not_yet_fixed")
    if (
        any(path.read_bytes() != data for path, data in observed.items())
        or config_path.read_bytes() != raw
    ):
        raise NodeError("ENTRY_CHANGED", "Entry changed while loading", blocked=True)
    selected_target = None
    if request.get("target_id"):
        selected = [
            item
            for item in config["targets"]
            if item["target_id"] == request["target_id"]
        ]
        if len(selected) != 1:
            raise NodeError(
                "TARGET_NOT_REGISTERED", "Explicit Target must be uniquely registered"
            )
        selected_target = {**selected[0], "features": None, "revision": None}
        gaps.append("actual_build_macro_and_revision_evidence_required")
    else:
        gaps.append("target_not_selected")
    record = modules["records"].seal(
        {
            "schema_version": "2.0",
            "record_kind": "project_context",
            "operation_id": request.get("operation_id", "binding"),
            "state": "context_loaded",
            "workspace_id": config["workspace_id"],
            "workspace_root": str(workspace),
            "knowledge_root": str(root),
            "target_path": str(target),
            "config_path": str(config_path),
            "config_digest": sha(raw),
            "rules_digest": pinned,
            "tool_identity": tool_identity(package),
            "entries": trace,
            "repos": repos,
            "target": selected_target,
            "build_evidence": None,
            "context_kind": "discovery",
            "targets": config["targets"],
            "pairs": config["pairs"],
            "gaps": gaps,
        }
    )
    ref = ".build/project-context/" + record["digest"] + ".json"
    write_bytes(root, ref, canonical(record))
    return {
        "state": "context_loaded",
        "context_ref": ref,
        "context_digest": record["digest"],
        "knowledge_root": str(root),
        "gaps": gaps,
    }, "context_loaded"
