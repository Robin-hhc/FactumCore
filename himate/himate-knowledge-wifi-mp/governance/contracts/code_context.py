"""Fix P1's selected code inputs without discovering a repository-wide graph."""

from pathlib import PurePosixPath

from .runtime import NodeError, safe, sha


def _changed(message, path):
    return NodeError("SOURCE_CHANGED", message, str(path), blocked=True,
                     data={"needs_scan": True, "affected_scope": [str(path)]})


def _entries(context, workspace, selected, config):
    paths = [safe(workspace, "AGENTS.md"), safe(context.root, "AGENTS.md")]
    for repo_id, root, relative in selected:
        parents = [PurePosixPath("."), *reversed(PurePosixPath(relative).parent.parents), PurePosixPath(relative).parent]
        paths.extend(safe(root, (parent / "AGENTS.md").as_posix()) for parent in parents
                     if context.modules["validation"].workspace_file_allowed(config, repo_id, (parent / "AGENTS.md").as_posix()))
    result, bindings = [], []
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.read_bytes() != raw:
            raise _changed("Agent entry changed during code preparation", path)
        result.append({"path": str(path), "sha256": sha(raw)})
        bindings.append({"path": str(path), "sha256": sha(raw), "bytes": len(raw)})
    return result, bindings


def _selected(resources, snapshots):
    code = {row["source_id"]: row for row in resources if row.get("kind") == "code"}
    selected = {}
    for snapshot in snapshots:
        resource = code.get(snapshot["source_id"])
        if resource is None:
            continue
        key = resource["repo_id"], resource["path"]
        if key in selected and selected[key] != snapshot["sha256"]:
            raise NodeError("MATERIAL_IDENTITY_CONFLICT", "Current code has multiple adopted byte versions", resource["path"])
        selected[key] = snapshot["sha256"]
    return selected


def _check_fixed(context, loaded, selected):
    """Explicit complete inputs stay fixed; legacy capture-only contexts remain compatible."""
    operations = context.modules["source_operations"]
    for (repo_id, relative), expected in selected.items():
        operations.authorized_repo(context, repo_id, loaded)
        files = loaded.get("repos", {}).get(repo_id, {}).get("files")
        if files and files.get(relative) != expected:
            raise NodeError("CODE_CONTEXT_STALE", "Fixed context does not cover the adopted code bytes", relative, blocked=True)


def prepare(context, resources, snapshots, reference=None, *, explicit=False):
    """Return one immutable context binding, derived only when its file manifest is absent."""
    selected = _selected(resources, snapshots)
    loaded = context.record(reference, "project_context") if reference else None
    if not selected:
        return ({"context_ref": reference, "context_digest": loaded["digest"]}
                if loaded else {"context_ref": None})
    if loaded:
        _check_fixed(context, loaded, selected if explicit else {
            key: value for key, value in selected.items()
            if key[1] in loaded.get("repos", {}).get(key[0], {}).get("files", {})
        })
        if loaded.get("context_kind") not in {"discovery", "source_materials"} or (
                explicit and loaded.get("context_kind") != "discovery"):
            return {"context_ref": reference, "context_digest": loaded["digest"]}
    operations, validation = context.modules["source_operations"], context.modules["validation"]
    config_path = validation.workspace_config_path(context.root)
    workspace, config_raw = config_path.parent, config_path.read_bytes()
    config_digest = sha(config_raw)
    repos, paths = {}, []
    config = None
    for (repo_id, relative), expected in sorted(selected.items()):
        root, registered, config, _, actual_config = operations.authorized_repo(context, repo_id)
        if actual_config != config_digest:
            raise _changed("Workspace configuration changed during code preparation", config_path)
        if not validation.workspace_file_allowed(config, repo_id, relative):
            raise NodeError("CODE_MODULE_UNKNOWN", "Adopted code is outside configured modules", relative, blocked=True)
        before, committed = operations.metadata(root, registered, relative)
        raw, _ = operations.read_code(root, relative)
        if sha(raw) != expected or operations.metadata(root, registered, relative)[0] != before:
            raise _changed("Code changed after its captured snapshot", root / relative)
        if repo_id not in repos:
            identity = None
            if registered["kind"] == "git":
                origin = operations.git_read(root, ["config", "--local", "--get", "remote.origin.url"], optional=True)
                identity = origin.decode().strip() if origin is not None else None
            repos[repo_id] = {
                "repo_id": repo_id, "root": str(root), "kind": registered["kind"],
                "head": before["revision"], "identity": identity,
                "dirty": False if before["revision"] else "unknown", "files": {},
                **{key: registered[key] for key in ("evidence_basis", "workspace_path") if key in registered},
            }
        repo = repos[repo_id]
        if repo["head"] != before["revision"]:
            raise _changed("Repository revision changed during code preparation", root)
        repo["files"][relative] = expected
        if before["revision"]:
            repo["dirty"] = repo["dirty"] or raw != committed
        paths.append((repo_id, root, relative))
    entries, guarded_entries = _entries(context, workspace, paths, config)
    if loaded and loaded.get("context_kind") == "source_materials":
        observed = {row["path"]: row["sha256"] for row in entries}
        for entry in loaded.get("entries", []):
            if observed.get(entry["path"]) != entry["sha256"]:
                raise _changed("Previously adopted Agent entry changed", entry["path"])
    if config_path.read_bytes() != config_raw:
        raise _changed("Workspace configuration changed during code preparation", config_path)
    record = context.seal({
        "state": "context_loaded", "context_kind": "source_materials",
        "workspace_id": config["workspace_id"], "workspace_root": str(workspace),
        "knowledge_root": str(context.root), "config_path": str(config_path),
        "config_digest": config_digest, "entries": entries, "repos": repos,
        "target": loaded.get("target") if loaded else None, "build_evidence": None,
        "current_files": guarded_entries,
        "gaps": ["actual_build_macro_and_runtime_evidence_not_provided"],
        **({"mapping_kind": "modules", "modules": config["modules"],
            "architecture": config["architecture"], "code_root": config["code_root"]}
           if config.get("mapping_kind") == "modules" else {}),
    }, "project_context")
    reference = context.base + "/contexts/" + record["digest"] + ".json"
    context.save(reference, record)
    return {"context_ref": reference, "context_digest": record["digest"]}
