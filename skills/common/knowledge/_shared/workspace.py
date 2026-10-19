"""Resolve explicitly registered code paths without reading knowledge bodies or writing files."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import __version__, contracts, receipts


class ProjectError(ValueError):
    """A stable, machine-readable discovery failure."""

    def __init__(self, code: str, message: str, path: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def _tool_digest() -> str:
    root = Path(__file__).parent
    return receipts.digest_json(
        {
            name: receipts.digest_file(root / name)
            for name in ("__init__.py", "workspace.py", "contracts.py", "receipts.py", "scope.py")
        }
    )


def _path(value: Any, base: Path | None = None, *, strict: bool = False) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not str(value):
        raise ProjectError("INVALID_PATH", "A non-empty filesystem path is required.")
    path = Path(value)
    if not path.is_absolute():
        if base is None:
            raise ProjectError(
                "BASE_REQUIRED", "A relative code path requires an explicit base.", str(value)
            )
        path = base / path
    try:
        return path.resolve(strict=strict)
    except (OSError, RuntimeError) as exc:
        raise ProjectError(
            "PATH_UNAVAILABLE", "The requested path cannot be resolved.", str(path)
        ) from exc


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _load(path: Path, *, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        data = path.read_bytes()
        value = contracts.load_document_bytes(data, path)
    except (OSError, ValueError) as exc:
        raise ProjectError(code, f"Cannot load the registered document: {exc}", str(path)) from exc
    if not isinstance(value, dict):
        raise ProjectError(code, "The registered document must be an object.", str(path))
    return value, data


def _git(root: Path, *arguments: str, optional: bool = False, strip: bool = True) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError(
            "GIT_UNAVAILABLE", "Git identity could not be inspected.", str(root)
        ) from exc
    if result.returncode:
        if optional and result.returncode == 1:
            return None
        raise ProjectError(
            "GIT_IDENTITY_UNAVAILABLE", "Git identity could not be inspected.", str(root)
        )
    return result.stdout.strip() if strip else result.stdout


def _has_attribute_helpers(root: Path) -> bool:
    # Attribute conversion can execute even during status. Detect configured
    # commands without editing repository or user settings.
    names = _git(
        root,
        "config",
        "--null",
        "--name-only",
        "--get-regexp",
        r"^filter\..*\.(clean|process|smudge)$",
        optional=True,
        strip=False,
    )
    if names is None:
        return False
    if not names.endswith("\0"):
        raise ProjectError(
            "GIT_IDENTITY_UNAVAILABLE",
            "Git helper configuration could not be inspected.",
            str(root),
        )
    for name in sorted(set(names[:-1].split("\0"))):
        values = _git(root, "config", "--null", "--get-all", name, optional=True, strip=False)
        if values is not None and any(value for value in values.removesuffix("\0").split("\0")):
            return True
    return False


def _dirty_state(root: Path) -> dict[str, Any]:
    if _has_attribute_helpers(root):
        return {
            "dirty": None,
            "dirty_status": "unavailable_configured_helpers",
            "reason": "Git attribute conversion commands are configured; status was skipped.",
        }
    index = _git(root, "ls-files", "--stage", "-z")
    if any(entry.startswith("160000 ") for entry in index.split("\0")):
        return {
            "dirty": None,
            "dirty_status": "unavailable_submodules",
            "reason": "Gitlinks are present; recursive status was skipped.",
        }
    return {
        "dirty": bool(
            _git(
                root,
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
                "--ignore-submodules=all",
            )
        ),
        "dirty_status": "observed",
    }


def _entry_path(entry: Path, owner: Path) -> Path:
    try:
        canonical = entry.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProjectError(
            "ENTRY_UNAVAILABLE", "A required project entry cannot be resolved.", str(entry)
        ) from exc
    if not _within(canonical, owner):
        raise ProjectError(
            "ENTRY_PATH_ESCAPE", "A required entry escapes its registered root.", str(entry)
        )
    if not canonical.is_file() or not os.access(canonical, os.R_OK):
        raise ProjectError(
            "ENTRY_UNAVAILABLE", "A required project entry is missing or unreadable.", str(entry)
        )
    return canonical


def _identity(candidate: dict[str, Any], requested: Path) -> dict[str, Any]:
    repo, root = candidate["repo"], candidate["repo_root"]
    if repo["kind"] == "export":
        current = requested if requested.is_dir() else requested.parent
        while _within(current, root):
            if (current / ".git").exists():
                code = "REPO_KIND_MISMATCH" if current == root else "GIT_BOUNDARY_MISMATCH"
                raise ProjectError(
                    code, "An export registration crosses Git checkout metadata.", str(current)
                )
            if current == root:
                break
            current = current.parent
        if repo.get("expected_identity") is not None:
            raise ProjectError(
                "IDENTITY_UNVERIFIABLE",
                "The export has no implemented snapshot identity verifier.",
                str(root),
            )
        return {
            "kind": "export",
            "root": str(root),
            "head": None,
            "dirty": None,
            "snapshot_status": "not_captured",
        }
    actual_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != root:
        raise ProjectError(
            "GIT_ROOT_MISMATCH",
            "The registered Git root is not the actual checkout root.",
            str(root),
        )
    location = requested if requested.is_dir() else requested.parent
    requested_root = Path(_git(location, "rev-parse", "--show-toplevel")).resolve()
    if requested_root != root:
        raise ProjectError(
            "GIT_BOUNDARY_MISMATCH",
            "The requested path belongs to a different nested checkout.",
            str(requested),
        )
    origin = _git(root, "config", "--get", "remote.origin.url", optional=True)
    if repo.get("expected_identity") is not None and origin != repo["expected_identity"]:
        raise ProjectError(
            "REPO_IDENTITY_MISMATCH",
            "The actual origin differs from the registered identity.",
            str(root),
        )
    return {
        "kind": "git",
        "root": str(root),
        "head": _git(root, "rev-parse", "HEAD"),
        **_dirty_state(root),
        "origin": origin,
        "git_dir": str(Path(_git(root, "rev-parse", "--absolute-git-dir")).resolve()),
        "common_dir": str((root / _git(root, "rev-parse", "--git-common-dir")).resolve()),
    }


def _choose(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ProjectError(
            "UNREGISTERED_PATH", "No explicitly registered module contains the requested path."
        )
    ordered = sorted(candidates, key=lambda item: len(item["module_root"].parts), reverse=True)
    deepest = ordered[0]
    if deepest["binding"].get("override_nested") is True and all(
        item["module_root"] != deepest["module_root"]
        and _within(deepest["module_root"], item["module_root"])
        for item in ordered[1:]
    ):
        return deepest
    raise ProjectError(
        "AMBIGUOUS_BINDING",
        "Multiple registered modules match without an explicit nested override.",
    )


def resolve_project(
    path: str | os.PathLike[str],
    registry_path: str | os.PathLike[str],
    base_path: str | os.PathLike[str] | None = None,
    load_context: bool = False,
    authorization_epoch: str = "local",
) -> dict[str, Any]:
    """Return a discovery receipt; only ``load_context`` reads entry file bodies.

    The registry locates configuration and never grants access. This first slice
    intentionally does not load config.local.yml or install global Agent rules.
    """
    if not isinstance(authorization_epoch, str) or not authorization_epoch:
        raise ProjectError(
            "INVALID_AUTHORIZATION_EPOCH", "An explicit non-empty authorization epoch is required."
        )
    tool_digest = _tool_digest()
    base = _path(base_path, Path.cwd(), strict=True) if base_path is not None else None
    if base is not None and not base.is_dir():
        raise ProjectError("INVALID_BASE", "The explicit base must be a directory.", str(base))
    requested = _path(path, base, strict=True)
    registry_file = _path(registry_path, Path.cwd(), strict=True)
    registry, registry_bytes = _load(registry_file, code="REGISTRY_INVALID")
    registry_digest = receipts.digest_bytes(registry_bytes)
    if registry.get("schema_version") != "1.0" or not isinstance(registry.get("workspaces"), list):
        raise ProjectError(
            "REGISTRY_INVALID",
            "The registry must use schema_version 1.0 and a workspace list.",
            str(registry_file),
        )
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    unconfigured = False
    for registration in registry["workspaces"]:
        if not isinstance(registration, dict) or not isinstance(
            registration.get("workspace_id"), str
        ):
            raise ProjectError(
                "REGISTRY_INVALID",
                "Each registration requires a workspace identity.",
                str(registry_file),
            )
        workspace_id = registration["workspace_id"]
        if workspace_id in seen:
            raise ProjectError(
                "REGISTRY_INVALID",
                "Duplicate workspace identities are not allowed.",
                str(registry_file),
            )
        seen.add(workspace_id)
        config_file = _path(registration.get("config"), registry_file.parent, strict=True)
        config, config_bytes = _load(config_file, code="CONFIG_INVALID")
        config_digest = receipts.digest_bytes(config_bytes)
        if config_digest != registration.get("config_digest"):
            raise ProjectError(
                "REGISTRY_STALE",
                "The registered config digest differs from its current bytes.",
                str(config_file),
            )
        if config.get("schema_version") != "1.0" or config.get("workspace_id") != workspace_id:
            raise ProjectError(
                "CONFIG_IDENTITY_MISMATCH",
                "The configuration identity differs from its registration.",
                str(config_file),
            )
        workspace_root = config_file.parent
        roots = config.get("knowledge_roots")
        if (
            not isinstance(roots, dict)
            or not isinstance(roots.get("wifi"), str)
            or not roots["wifi"]
        ):
            raise ProjectError(
                "INVALID_CONFIGURATION",
                "The workspace requires a WiFi knowledge-root locator.",
                str(config_file),
            )
        registered_knowledge_root = _path(roots["wifi"], workspace_root, strict=True)
        if not registered_knowledge_root.is_dir():
            raise ProjectError(
                "KNOWLEDGE_ROOT_UNAVAILABLE",
                "The registered knowledge root is not a directory.",
                str(registered_knowledge_root),
            )
        rule_file = registered_knowledge_root / "governance/framework.lock.yaml"
        try:
            rule_digest = receipts.digest_file(rule_file)
            diagnostics = contracts.validate_document(
                "workspace", config, registered_knowledge_root
            )
            if receipts.digest_file(rule_file) != rule_digest:
                raise ProjectError(
                    "BINDING_CHANGED",
                    "The contract lock changed during configuration validation.",
                    str(rule_file),
                )
        except contracts.ContractError as exc:
            raise ProjectError(exc.code, exc.message, exc.path) from exc
        except (OSError, RuntimeError) as exc:
            raise ProjectError(
                "CONTRACT_UNAVAILABLE",
                "The registered contract bundle cannot be read.",
                str(registered_knowledge_root),
            ) from exc
        if diagnostics:
            raise ProjectError(
                "CONFIG_INVALID",
                f"Workspace scope validation failed: {diagnostics}",
                str(config_file),
            )
        repos = {repo["repo_id"]: repo for repo in config["repos"]}
        for binding in config["architecture"]:
            repo = repos[binding["repo_id"]]
            if repo.get("root") is None:
                unconfigured = True
                continue
            repo_root = _path(repo["root"], workspace_root)
            module_root = _path(binding.get("module_root", "."), repo_root)
            if not _within(module_root, repo_root):
                raise ProjectError(
                    "MODULE_OUTSIDE_REPO",
                    "A registered module escapes its repository root.",
                    str(module_root),
                )
            if not _within(requested, module_root):
                continue
            if not repo_root.is_dir() or not module_root.is_dir():
                raise ProjectError(
                    "CODE_ROOT_UNAVAILABLE",
                    "The registered code or module root is unavailable.",
                    str(module_root),
                )
            candidates.append(
                {
                    "config_file": config_file,
                    "config_digest": config_digest,
                    "config_bytes": config_bytes,
                    "config": config,
                    "workspace_root": workspace_root,
                    "repo": repo,
                    "repo_root": repo_root,
                    "module_root": module_root,
                    "binding": binding,
                    "rule_file": rule_file,
                    "rule_digest": rule_digest,
                }
            )
    if not candidates and unconfigured:
        raise ProjectError(
            "CODE_ROOT_UNCONFIGURED", "A registered source root remains unknown.", str(requested)
        )
    selected = _choose(candidates)
    config, binding = selected["config"], selected["binding"]
    knowledge_value = config.get("knowledge_roots", {}).get(binding["knowledge_domain"])
    if not knowledge_value:
        raise ProjectError(
            "KNOWLEDGE_ROOT_UNCONFIGURED",
            "The selected domain has no knowledge root.",
            str(selected["config_file"]),
        )
    knowledge_root = _path(knowledge_value, selected["workspace_root"], strict=True)
    if not knowledge_root.is_dir():
        raise ProjectError(
            "KNOWLEDGE_ROOT_UNAVAILABLE",
            "The configured knowledge root must be a directory.",
            str(knowledge_root),
        )
    entries = [
        (selected["workspace_root"] / "AGENTS.md", selected["workspace_root"]),
        (knowledge_root / "AGENTS.md", knowledge_root),
        (knowledge_root / "knowledge/AGENTS.md", knowledge_root),
    ]
    entry_paths = [_entry_path(entry, owner) for entry, owner in entries]
    identity = _identity(selected, requested)
    entry_reads = []
    if load_context:
        for number, ((entry, owner), expected_path) in enumerate(
            zip(entries, entry_paths), start=1
        ):
            try:
                canonical = _entry_path(entry, owner)
                if canonical != expected_path:
                    raise ProjectError(
                        "ENTRY_CHANGED", "An entry path changed before its read.", str(entry)
                    )
                contents = canonical.read_bytes()
                digest = receipts.digest_bytes(contents)
                if _entry_path(entry, owner) != canonical or digest != receipts.digest_file(
                    canonical
                ):
                    raise ProjectError(
                        "ENTRY_CHANGED", "An entry changed during its read.", str(entry)
                    )
                text = contents.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProjectError(
                    "ENTRY_ENCODING", "A required project entry is not UTF-8 text.", str(entry)
                ) from exc
            except OSError as exc:
                raise ProjectError(
                    "ENTRY_UNAVAILABLE", "A required project entry could not be read.", str(entry)
                ) from exc
            entry_reads.append(
                {
                    "path": str(canonical),
                    "digest": digest,
                    "bytes": len(contents),
                    "content": text,
                    "trace": {
                        "tool": "workspace.resolve_project",
                        "action": "read_bytes",
                        "sequence": number,
                    },
                }
            )
    # Recheck the discovery inputs after tool reads; a concurrent config edit must
    # never result in a receipt that binds an obsolete mapping to newly read text.
    if (
        registry_file.read_bytes() != registry_bytes
        or selected["config_file"].read_bytes() != selected["config_bytes"]
    ):
        raise ProjectError(
            "BINDING_CHANGED",
            "Discovery configuration changed while resolving the project.",
            str(registry_file),
        )
    if receipts.digest_file(selected["rule_file"]) != selected["rule_digest"]:
        raise ProjectError(
            "BINDING_CHANGED",
            "The contract lock changed while resolving the project.",
            str(selected["rule_file"]),
        )
    try:
        diagnostics = contracts.validate_document("workspace", config, knowledge_root)
    except contracts.ContractError as exc:
        raise ProjectError(exc.code, exc.message, exc.path) from exc
    if diagnostics:
        raise ProjectError(
            "BINDING_CHANGED",
            "Workspace validation changed while resolving the project.",
            str(selected["config_file"]),
        )
    for (entry, owner), expected_path in zip(entries, entry_paths):
        if _entry_path(entry, owner) != expected_path:
            raise ProjectError(
                "ENTRY_CHANGED", "An entry path changed after resolution.", str(entry)
            )
    for record in entry_reads:
        if receipts.digest_file(record["path"]) != record["digest"]:
            raise ProjectError(
                "ENTRY_CHANGED", "A required entry changed after its context read.", record["path"]
            )
    if _identity(selected, requested) != identity:
        raise ProjectError(
            "CHECKOUT_CHANGED",
            "The checkout identity changed while resolving the project.",
            str(selected["repo_root"]),
        )
    if _tool_digest() != tool_digest:
        raise ProjectError(
            "BINDING_CHANGED",
            "The discovery tool changed while resolving the project.",
            str(Path(__file__).parent),
        )
    target_candidates = [
        target["target_id"]
        for target in config["targets"]
        if selected["repo"]["repo_id"] in target["source_bindings"]
    ]
    unknown_fields = ["selected_target", "code_verification", "knowledge_coverage"]
    if identity["kind"] == "git" and identity["dirty"] is None:
        unknown_fields.append("checkout.dirty")
    for target in config["targets"]:
        if target["target_id"] in target_candidates:
            for field in (
                "module_roots",
                "build_profile",
                "required_features",
                "protocol_versions",
            ):
                if target.get(field) in (None, [], "unknown"):
                    unknown_fields.append(f"targets.{target['target_id']}.{field}")
    return {
        "schema_version": "1.0",
        "record_kind": "project_context",
        "receipt_id": str(uuid4()),
        "status": "context_loaded" if load_context else "resolved",
        "binding_id": binding["binding_id"],
        "requested_path": str(path),
        "canonical_path": str(requested),
        "workspace_id": config["workspace_id"],
        "workspace_root": str(selected["workspace_root"]),
        "config": {
            "path": str(selected["config_file"]),
            "digest": selected["config_digest"],
            "local_overrides_loaded": False,
        },
        "config_digest": selected["config_digest"],
        "registry": {"path": str(registry_file), "digest": registry_digest},
        "checkout_identity": identity,
        "knowledge_bindings": [
            {
                "domain": binding["knowledge_domain"],
                "root": str(knowledge_root),
                "module_root": str(selected["module_root"]),
            }
        ],
        "required_entry_files": [str(entry) for entry in entry_paths],
        "entry_reads": entry_reads,
        "resolved_context": {
            "repo_id": selected["repo"]["repo_id"],
            "target_candidates": sorted(target_candidates),
            "selected_target": None,
        },
        "unknown_fields": sorted(unknown_fields),
        "authorization_epoch": authorization_epoch,
        "tool": {"name": "workspace.resolve_project", "version": __version__},
        "tool_digest": tool_digest,
        "rule_digest": selected["rule_digest"],
        "skill_digest": None,
        "diagnostics": [],
    }
