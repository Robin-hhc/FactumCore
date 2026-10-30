"""Explicit root synchronization and scoped, read-only native Git observations.

Internal MM adaptation belongs at ``request.sync``.  No MM subcommand, project
enumerator or output format is inferred here.  A successful adapter exit only
describes that command; the next CLI process reloads rules/configuration and
observes each authorized repository independently.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess

from .runtime import NodeError, digest, safe


GIT_TIMEOUT_SECONDS = 30
MAX_SYNC_OUTPUT = 65536
_OID = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


def _issue(code, reason, **fields):
    return {"code": code, "reason": str(reason), **fields}


def _unlinked_directory(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise NodeError("PATROL_PATH_UNAUTHORIZED", "An explicit absolute directory is required", value)
    for member in [path, *path.parents]:
        if member.is_symlink() or (os.path.lexists(member) and getattr(member.lstat(), "st_file_attributes", 0)
                                   & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise NodeError("PATROL_PATH_UNAUTHORIZED", "Linked repository directories are not allowed", member)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise NodeError("PATROL_PATH_UNAVAILABLE", "Repository location is not a directory", value)
    return resolved


def _environment():
    # A caller's GIT_DIR, index, config injection or work-tree must never select
    # another repository. The synchronization command may still use explicitly
    # installed credential helpers/configuration, unlike the read-only observer.
    return {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}


def _stop_process(process):
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def sync(context):
    """Run only the operator's explicit argv/cwd adapter, with no shell."""
    supplied = context.request.get("sync")
    if supplied is None:
        return {"sync_status": "skipped", "complete": True,
                "scope": "no_sync_adapter_requested"}, "skipped"
    if not isinstance(supplied, dict) or set(supplied) - {"argv", "cwd", "timeout_seconds"}:
        raise NodeError("PATROL_SYNC_INVALID", "sync must contain argv, absolute cwd and timeout_seconds")
    argv = supplied.get("argv")
    timeout = supplied.get("timeout_seconds")
    if (not isinstance(argv, list) or not argv or not argv[0]
            or any(not isinstance(item, str) or "\0" in item for item in argv)
            or isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 86400 or not isinstance(supplied.get("cwd"), str)):
        raise NodeError("PATROL_SYNC_INVALID", "Invalid synchronization argv/cwd/timeout")
    cwd = _unlinked_directory(supplied["cwd"])
    identity = digest({"argv": argv, "cwd": str(cwd), "timeout_seconds": timeout})
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=_environment(), shell=False,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, **options)
    except OSError as exc:
        raise NodeError("PATROL_SYNC_UNAVAILABLE", "Synchronization adapter could not start", cwd,
                        blocked=True, data={"adapter_digest": identity, "reason": str(exc)}) from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _stop_process(process)
        stdout, stderr = process.communicate()
        raise NodeError("PATROL_SYNC_TIMEOUT", "Synchronization adapter exceeded its explicit timeout", cwd,
                        blocked=True, data={"adapter_digest": identity, "timeout_seconds": timeout,
                                            "stdout": stdout[:MAX_SYNC_OUTPUT].decode("utf-8", errors="replace"),
                                            "stderr": stderr[:MAX_SYNC_OUTPUT].decode("utf-8", errors="replace")}) from exc
    observed = {"adapter_digest": identity, "cwd": str(cwd), "exit_code": process.returncode,
                "stdout": stdout[:MAX_SYNC_OUTPUT].decode("utf-8", errors="replace"),
                "stderr": stderr[:MAX_SYNC_OUTPUT].decode("utf-8", errors="replace"),
                "output_truncated": len(stdout) > MAX_SYNC_OUTPUT or len(stderr) > MAX_SYNC_OUTPUT,
                "scope": "adapter_command_only"}
    if process.returncode:
        raise NodeError("PATROL_SYNC_FAILED", "Synchronization adapter returned a nonzero exit code", cwd,
                        blocked=True, data=observed)
    return {**observed, "sync_status": "succeeded", "complete": True}, "synced"


def _git(root, arguments):
    env = _environment()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_PAGER="cat", GIT_NO_LAZY_FETCH="1", LC_ALL="C")
    return subprocess.run([
        "git", "--no-optional-locks", "--literal-pathspecs", "-c", "core.fsmonitor=false",
        "-c", "core.hooksPath=" + os.devnull, "-c", "core.pager=cat",
        "-c", "diff.external=", "-c", "protocol.allow=never",
        "-c", "protocol.file.allow=never", "-c", "safe.directory=" + root.as_posix(),
        "-C", str(root), *arguments,
    ], env=env, capture_output=True, timeout=GIT_TIMEOUT_SECONDS, check=False)


def _text(raw):
    return raw.decode("utf-8", errors="replace").strip()


def _missing_object(raw):
    return any(marker in raw.lower() for marker in (
        b"not a valid object", b"invalid object name", b"bad object",
        b"could not get object info", b"needed a single revision", b"unknown revision",
    ))


def _path(raw):
    value = raw.decode("utf-8", errors="strict")
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or "\\" in value or ":" in value or "\0" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("Git returned an unsafe relative path")
    return value


def parse_diff(raw):
    """Parse --name-status -z, retaining both rename/copy path fields."""
    fields = raw.split(b"\0")
    if fields[-1] != b"":
        raise ValueError("Truncated NUL-delimited Git diff")
    rows, position = [], 0
    while position < len(fields) - 1:
        status = fields[position].decode("ascii", errors="strict")
        position += 1
        if not re.fullmatch(r"(?:[ADMTUXB]|[RC][0-9]{1,3})", status):
            raise ValueError("Unsupported Git diff status")
        count = 2 if status.startswith(("R", "C")) else 1
        if position + count > len(fields) - 1:
            raise ValueError("Incomplete Git diff path fields")
        paths = [_path(value) for value in fields[position:position + count]]
        position += count
        rows.append({"status": status, "old_path": paths[0], "new_path": paths[-1]})
    return rows


def parse_status(raw):
    """Parse porcelain v1 -z: rename destination precedes original path."""
    fields = raw.split(b"\0")
    if fields[-1] != b"":
        raise ValueError("Truncated NUL-delimited Git status")
    rows, position = [], 0
    while position < len(fields) - 1:
        entry = fields[position]
        position += 1
        if len(entry) < 4 or entry[2:3] != b" ":
            raise ValueError("Malformed porcelain status entry")
        status = entry[:2].decode("ascii", errors="strict")
        if any(value not in " MADRCU?!T" for value in status):
            raise ValueError("Unsupported porcelain status")
        destination = _path(entry[3:])
        original = destination
        if "R" in status or "C" in status:
            if position >= len(fields) - 1:
                raise ValueError("Incomplete porcelain rename")
            original = _path(fields[position])
            position += 1
        rows.append({"status": status, "old_path": original, "new_path": destination})
    return rows


def _scope_path(context, config, repo_id, root, git_root, relative):
    # lexical containment is required even for deleted files; existing parents
    # are subsequently checked by the same workspace policy as normal capture.
    absolute = git_root.joinpath(*PurePosixPath(relative).parts)
    if not absolute.is_relative_to(root):
        return None
    selected = absolute.relative_to(root).as_posix()
    bindings = [item for item in config.get("architecture", []) if item.get("repo_id") == repo_id]
    if not any((item["module_root"] == "." or selected.startswith(item["module_root"].rstrip("/") + "/"))
               and (config.get("mapping_kind") != "modules" or not any(
                   selected == excluded or selected.startswith(excluded.rstrip("/") + "/")
                   for excluded in item.get("excluded_roots", []))) for item in bindings):
        return None
    safe(root, selected)
    if not context.modules["validation"].workspace_file_allowed(config, repo_id, selected):
        raise NodeError("PATROL_PATH_UNAUTHORIZED", "Changed path could not be authorized in its configured scope", selected)
    return selected


def _repository(context, config_state, mapping, previous):
    config, repo_id = config_state["config"], mapping["repo_id"]
    row = {"repo_id": repo_id, "root": str(mapping.get("root", "")), "git_root": None,
           "head": None, "full_scan": True, "changed_paths": [], "rename_rows": [],
           "dirty_paths": [], "gaps": [], "fallback_reason": "first_observation"}
    try:
        declared = Path(mapping["root"])
        if not declared.is_absolute():
            declared = Path(config_state["path"]).parent / declared
        protected = config.get("code_policy", {}).get("repo_roots", {}).get(repo_id)
        if (not protected or not Path(protected).is_absolute()
                or declared.resolve() != Path(protected).resolve()):
            raise NodeError("PATROL_REPOSITORY_UNAUTHORIZED", "Repository root differs from its configured authorization", declared)
        root = _unlinked_directory(declared)
        row["root"] = str(root)
        if shutil.which("git") is None:
            row["fallback_reason"] = "git_unavailable"
            return row
        located = _git(root, ["rev-parse", "--show-toplevel"])
        if located.returncode:
            if b"not a git repository" in located.stderr.lower():
                row["fallback_reason"] = "not_git"
                return row
            raise NodeError("PATROL_GIT_UNAVAILABLE", _text(located.stderr) or "Git repository could not be inspected", root)
        git_root = _unlinked_directory(_text(located.stdout))
        if not root.is_relative_to(git_root):
            raise NodeError("PATROL_REPOSITORY_UNAUTHORIZED", "Git root does not enclose the configured scope", root)
        if config.get("mapping_kind") == "modules" and not git_root.is_relative_to(Path(config["workspace_root"]).resolve()):
            # A Git-free exported workspace may itself sit in another checkout
            # (notably an isolated fixture). That outer repository is not one
            # of this configuration's managed source repositories.
            row["fallback_reason"] = "not_git"
            row["git_diagnostic"] = "Enclosing Git root is outside the configured workspace"
            return row
        row["git_root"] = str(git_root)
        prefix = root.relative_to(git_root).as_posix()
        head = _git(git_root, ["rev-parse", "--verify", "HEAD^{commit}"])
        if head.returncode:
            if not _missing_object(head.stderr):
                raise NodeError("PATROL_GIT_UNAVAILABLE", _text(head.stderr), root)
            row["fallback_reason"] = "head_unavailable"
            row["git_diagnostic"] = _text(head.stderr)
            return row
        row["head"] = _text(head.stdout)
        if not _OID.fullmatch(row["head"]):
            raise ValueError("Git HEAD is not a full object identity")
        old = previous.get(repo_id)
        if isinstance(old, str) and _OID.fullmatch(old):
            exists = _git(git_root, ["cat-file", "-e", old + "^{commit}"])
            if exists.returncode:
                if not _missing_object(exists.stderr):
                    raise NodeError("PATROL_GIT_UNAVAILABLE", _text(exists.stderr), root)
                row["fallback_reason"] = "baseline_unavailable"
                row["git_diagnostic"] = _text(exists.stderr)
            else:
                ancestor = _git(git_root, ["merge-base", "--is-ancestor", old, row["head"]])
                if ancestor.returncode == 1:
                    row["fallback_reason"] = "history_rewritten"
                elif ancestor.returncode:
                    raise NodeError("PATROL_GIT_UNAVAILABLE", _text(ancestor.stderr), root)
                else:
                    observed = _git(git_root, ["diff", "--no-ext-diff", "--no-textconv", "--name-status",
                                               "--find-renames", "-z", old, row["head"], "--", prefix])
                    if observed.returncode:
                        raise NodeError("PATROL_GIT_UNAVAILABLE", _text(observed.stderr), root)
                    changed = set()
                    for item in parse_diff(observed.stdout):
                        old_path = _scope_path(context, config, repo_id, root, git_root, item["old_path"])
                        new_path = _scope_path(context, config, repo_id, root, git_root, item["new_path"])
                        changed.update(path for path in (old_path, new_path) if path is not None)
                        if item["status"].startswith(("R", "C")) and (old_path is not None or new_path is not None):
                            row["rename_rows"].append({"status": item["status"], "old_path": old_path,
                                                       "new_path": new_path, "kind": "committed"})
                    row.update(full_scan=False, fallback_reason=None, changed_paths=sorted(changed))
        elif old is not None:
            row["fallback_reason"] = "invalid_baseline"
        current = _git(git_root, ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", prefix])
        if current.returncode:
            raise NodeError("PATROL_GIT_UNAVAILABLE", _text(current.stderr), root)
        dirty = set()
        for item in parse_status(current.stdout):
            old_path = _scope_path(context, config, repo_id, root, git_root, item["old_path"])
            new_path = _scope_path(context, config, repo_id, root, git_root, item["new_path"])
            dirty.update(path for path in (old_path, new_path) if path is not None)
            if item["old_path"] != item["new_path"] and (old_path is not None or new_path is not None):
                row["rename_rows"].append({"status": item["status"], "old_path": old_path,
                                           "new_path": new_path, "kind": "working_tree"})
            if ((old_path is not None or new_path is not None)
                    and ("U" in item["status"] or item["status"] in {"AA", "DD"})):
                row["gaps"].append(_issue("PATROL_GIT_UNMERGED", "An authorized path has unresolved merge state",
                                           repo_id=repo_id, path=new_path or old_path))
        row["dirty_paths"] = sorted(dirty)
        check = _git(git_root, ["rev-parse", "--verify", "HEAD^{commit}"])
        if check.returncode or _text(check.stdout) != row["head"]:
            raise NodeError("PATROL_REPOSITORY_CHANGED", "HEAD changed while observing the repository", root)
    except FileNotFoundError as exc:
        # Missing Git executable is an explicit all-file hash fallback, while a
        # missing configured root is an input gap, never an empty observation.
        if exc.filename == "git":
            row["fallback_reason"] = "git_unavailable"
        else:
            row["gaps"].append(_issue("PATROL_REPOSITORY_UNAVAILABLE", exc, repo_id=repo_id))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        row["full_scan"] = True
        row["gaps"].append(_issue(getattr(exc, "code", "PATROL_GIT_UNAVAILABLE"), exc, repo_id=repo_id))
    return row


def observe_repositories(context, config_state, previous_heads):
    """Observe authorized configuration scopes; never advance a baseline."""
    if not isinstance(previous_heads, dict):
        raise NodeError("PATROL_BASELINE_INVALID", "previous_heads must be a repo_id to commit mapping")
    config = config_state["config"]
    repositories, gaps, seen = [], [], set()
    for mapping in config.get("repos", []):
        identity = mapping.get("repo_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            gaps.append(_issue("PATROL_REPOSITORY_AMBIGUOUS", "Repository identity is absent or duplicated", repo_id=identity))
            continue
        seen.add(identity)
        row = _repository(context, config_state, mapping, previous_heads)
        repositories.append(row)
        gaps.extend(row["gaps"])
    for item in config.get("layout_gaps", []):
        gaps.append(_issue("PATROL_WORKSPACE_GAP", "Configured workspace has an unresolved mapping gap", observation=item))
    return {"repositories": repositories,
            "heads": {row["repo_id"]: row["head"] for row in repositories},
            "gaps": gaps, "complete": not gaps}
