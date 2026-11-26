"""Run the fixed Git operations for an independent knowledge repository."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import time

from .protocol import NodeError, safe


STATUS_TIMEOUT = 30
COMMIT_TIMEOUT = 110
DTS_RECORD = ".scratch/hs-knowledge-commit/dts.json"
CR_LINK_RE = re.compile(r"(https?://\S+?)\s+\[CR (?:CREATED|UPDATED)\]")
CR_FALLBACK_RE = re.compile(r"https?://\S*change_requests/\d+")
REPOSITORY_ENVIRONMENT = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                          "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}


class RepositoryError(NodeError):
    def __init__(self, code, message, data):
        super().__init__(code, message)
        self.data, self.phase = data, "failed"


class Git:
    def __init__(self, root, timeout):
        self.root = root
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
        self.data = {"knowledge_root": str(root), "commands": [], "completed_phase": "ready"}
        # The selected knowledge root, rather than inherited Git overrides,
        # determines the repository and index used by every command.
        self.environment = {key: value for key, value in os.environ.items()
                            if key.upper() not in REPOSITORY_ENVIRONMENT}
        self.environment["GIT_OPTIONAL_LOCKS"] = "0"

    def fail(self, code, message):
        raise RepositoryError(code, message, self.data)

    def run(self, *arguments, input=None, allowed=(0,)):
        argv = ["git", *arguments]
        record = {"argv": argv, "stdout": "", "stderr": "", "returncode": None}
        self.data["commands"].append(record)
        remaining = self.deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, self.timeout)
            result = subprocess.run(argv, cwd=str(self.root), env=self.environment,
                                    input=input.encode("utf-8") if input is not None else None,
                                    capture_output=True, timeout=remaining, shell=False)
        except subprocess.TimeoutExpired as error:
            record.update(stdout=_decode(error.stdout), stderr=_decode(error.stderr))
            self.fail("REPO_COMMAND_TIMEOUT",
                      f"Repository operation exceeded its {self.timeout}-second budget")
        except OSError as error:
            record["stderr"] = str(error)
            self.fail("REPO_COMMAND_UNAVAILABLE", str(error))
        record.update(stdout=_decode(result.stdout), stderr=_decode(result.stderr),
                      returncode=result.returncode)
        if result.returncode not in allowed:
            self.fail("REPO_COMMAND_FAILED", f"{' '.join(argv)} failed with exit code {result.returncode}")
        return record


def _decode(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def _request(action, request):
    if not isinstance(request, dict):
        raise NodeError("INVALID_INPUT", "The repository request must be a JSON object")
    fields = {"message", "dts", "upload", "approved"} if action == "commit" else set()
    unknown = set(request) - fields
    if unknown:
        raise NodeError("INVALID_INPUT", "Unknown repository fields: " + ", ".join(sorted(unknown)))
    if action == "commit":
        if request.get("approved") is not True:
            raise NodeError("REPO_APPROVAL_REQUIRED", "Repository commit requires approved=true")
        for field in ("message", "dts"):
            if field in request and (not isinstance(request[field], str) or not request[field].strip()):
                raise NodeError("INVALID_INPUT", f"{field} must be a nonempty string when provided")
        if "upload" in request and not isinstance(request["upload"], bool):
            raise NodeError("INVALID_INPUT", "upload must be a boolean")


def _latest(git):
    output = git.run("log", "-1", "--format=format:%H%x00%s%x00%B")["stdout"]
    sha, subject, message = output.split("\0", 2)
    match = re.search(r"^Change-Id:[ \t]*(\S+)[ \t]*$", message, re.MULTILINE | re.IGNORECASE)
    return {"sha": sha, "subject": subject, "message": message,
            "change_id": match.group(1) if match else None}


def _pending(git):
    return int(git.run("rev-list", "--count", "origin/master..HEAD")["stdout"].strip())


def _load_dts(root):
    path = safe(root, DTS_RECORD)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("dts")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value.strip() else None


def _prepare_local_state(git):
    ignore = safe(git.root, ".gitignore")
    record = safe(git.root, DTS_RECORD)
    if git.run("ls-files", "--", ".scratch")["stdout"]:
        git.fail("REPO_SCRATCH_TRACKED", "Remove tracked .scratch files from version control before committing")
    if git.run("check-ignore", "--no-index", "--quiet", "--", ".scratch/", allowed=(0, 1))["returncode"]:
        content = ignore.read_bytes() if ignore.exists() else b""
        if content and not content.endswith(b"\n"):
            content += b"\n"
        ignore.write_bytes(content + b"/.scratch/\n")
    return record


def run(root, action, request):
    """Return (data, phase); failures retain commands and completed Git stages."""
    if action not in {"status", "commit"}:
        raise NodeError("INVALID_ACTION", "Use repo status or repo commit")
    _request(action, request)
    root = Path(root).resolve(strict=True)
    git = Git(root, STATUS_TIMEOUT if action == "status" else COMMIT_TIMEOUT)
    try:
        if not (root / ".git").exists():
            git.fail("REPO_ROOT_REQUIRED", "Knowledge root must be an independent Git repository root")
        top = Path(git.run("rev-parse", "--show-toplevel")["stdout"].strip()).resolve(strict=True)
        if not top.samefile(root):
            git.fail("REPO_ROOT_REQUIRED", "Knowledge root must be the actual Git repository root")
        pending = _pending(git)
        latest = _latest(git)
        git.data.update(branch=git.run("rev-parse", "--abbrev-ref", "HEAD")["stdout"].strip(),
                        pending_commits=pending, latest_commit=latest, dts=_load_dts(root))
        if action == "status":
            git.data["changes"] = git.run("status", "--short")["stdout"]
            return git.data, "ready"

        mode = "amend" if pending else "create"
        git.data.update(mode=mode, uploaded=False)
        if mode == "create" and "message" not in request:
            git.fail("REPO_MESSAGE_REQUIRED", "A full message is required to create a repository commit")
        git.data["failed_phase"] = "prepare"
        record = _prepare_local_state(git)
        git.data["failed_phase"] = "stage"
        git.run("add", ".")
        git.data.update(completed_phase="staged", failed_phase="commit")
        if mode == "amend":
            git.run("commit", "--amend", "--no-edit")
        else:
            git.run("commit", "--cleanup=verbatim", "--file", "-", input=request["message"])
        git.data.update(completed_phase="committed", failed_phase="inspect")
        latest = _latest(git)
        git.data.update(commit_sha=latest["sha"], change_id=latest["change_id"], latest_commit=latest)
        git.data["pending_commits"] = _pending(git)
        if "dts" in request:
            git.data["failed_phase"] = "record"
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({"dts": request["dts"]}, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
            git.data["dts"] = request["dts"]
        phase = "committed"
        if request.get("upload", False):
            git.data["failed_phase"] = "upload"
            result = git.run("mm", "upload", ".", "-y")
            output = result["stdout"] + result["stderr"]
            match = CR_LINK_RE.search(output) or CR_FALLBACK_RE.search(output)
            if not match:
                git.fail("REPO_CR_URL_MISSING", "Upload output contains no [CR CREATED]/[CR UPDATED] link")
            git.data.update(uploaded=True, cr_url=match.group(1) if match.re is CR_LINK_RE else match.group(0),
                            completed_phase="uploaded")
            phase = "uploaded"
        git.data.pop("failed_phase", None)
        return git.data, phase
    except RepositoryError:
        raise
    except (OSError, ValueError) as error:
        git.fail("REPO_OPERATION_FAILED", str(error))
