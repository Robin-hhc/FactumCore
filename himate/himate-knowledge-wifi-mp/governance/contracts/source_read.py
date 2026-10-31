"""Short-lived, isolated source-reading jobs; ingestion owns its own materials."""

from contextlib import ExitStack, contextmanager
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
from uuid import uuid4

from .validation import ContractError, _workspace_no_links, safe_path, validate_id


READ_ROOT = "artifacts/source-read"
TTL_SECONDS = 1800
MAX_TTL_SECONDS = 86400
MAX_JOBS = 8
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
_READ_ID = re.compile(r"[0-9a-f]{32}\Z")


def _now():
    return time.time()


def _identity(read_id):
    if not isinstance(read_id, str) or not _READ_ID.fullmatch(read_id):
        raise ContractError("INVALID_SOURCE_READ_ID", "Expected 32 lowercase hexadecimal characters")
    return read_id


def _safe(root, reference):
    path = safe_path(root, reference, [READ_ROOT])
    _workspace_no_links(path)
    return path


def _job(root, read_id):
    return _safe(root, READ_ROOT + "/" + _identity(read_id))


def _busy_path(root, read_id):
    return _safe(root, READ_ROOT + "/.locks/" + _identity(read_id) + ".lock")


@contextmanager
def _file_lock(path, *, blocking=True):
    """OS locks coordinate separate CLI processes and vanish when one exits."""
    _workspace_no_links(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    with os.fdopen(descriptor, "r+b") as stream:
        if not os.fstat(stream.fileno()).st_size:
            stream.write(b"\0")
            stream.flush()
        try:
            if os.name == "nt":
                import msvcrt

                deadline = time.monotonic() + 30
                while True:
                    stream.seek(0)
                    try:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        acquired = True
                        break
                    except OSError:
                        if not blocking:
                            break
                        if time.monotonic() >= deadline:
                            raise ContractError("SOURCE_READ_BUSY", "Source reading metadata is busy")
                        time.sleep(0.025)
            else:
                import fcntl

                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
                    acquired = True
                except BlockingIOError:
                    pass
            yield acquired
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _guard(root):
    base = _safe(root, READ_ROOT)
    base.mkdir(parents=True, exist_ok=True)
    _safe(root, READ_ROOT + "/.locks").mkdir(exist_ok=True)
    with _file_lock(_safe(root, READ_ROOT + "/.lock")):
        yield


def _lease(root, read_id):
    path = _safe(root, READ_ROOT + "/" + _identity(read_id) + "/lease.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        expires = value["expires_at"]
        valid = (value["read_id"] == read_id and value["state"] in {"converting", "ready"}
                 and not isinstance(expires, bool) and isinstance(expires, (float, int))
                 and math.isfinite(expires))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ContractError("SOURCE_READ_INVALID", "Source reading lease is missing or malformed", read_id) from error
    if not valid:
        raise ContractError("SOURCE_READ_INVALID", "Source reading lease has invalid identity or state", read_id)
    return value


def _write_lease(root, read_id, value):
    reference = READ_ROOT + "/" + _identity(read_id)
    target = _safe(root, reference + "/lease.json")
    temporary = _safe(root, reference + "/.lease-" + uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_tree(root, directory):
    """Never recursively delete a directory containing a link or junction."""
    _workspace_no_links(directory)
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            _workspace_no_links(Path(parent) / name)


def _remove_job(root, read_id):
    directory = _job(root, read_id)
    _validate_tree(root, directory)
    # Resolve the final target once more immediately before the recursive delete.
    shutil.rmtree(_job(root, read_id))


def _ids(root):
    base = _safe(root, READ_ROOT)
    result = []
    for path in base.iterdir():
        if _READ_ID.fullmatch(path.name):
            checked = _job(root, path.name)
            if checked.is_dir():
                result.append(path.name)
    return sorted(result)


def _cleanup_locked(root, now):
    removed = []
    for read_id in _ids(root):
        try:
            lease = _lease(root, read_id)
        except ContractError:
            continue  # Unknown material is not permission to recursively delete it.
        if lease["expires_at"] > now:
            continue
        busy = _busy_path(root, read_id)
        with _file_lock(busy, blocking=False) as available:
            if not available:
                continue
            if _lease(root, read_id)["expires_at"] > now:
                continue
            _remove_job(root, read_id)
            removed.append(read_id)
        busy.unlink(missing_ok=True)
    return removed


def cleanup(root):
    """Reclaim only expired, unused jobs, including crashed conversions."""
    root = Path(root).resolve(strict=True)
    with _guard(root):
        return {"removed": _cleanup_locked(root, _now())}


def renew(root, read_id, *, ttl_seconds=TTL_SECONDS):
    """A ready handle expires explicitly; renewal never revives an expired one."""
    _identity(read_id)
    if (isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int)
            or not 1 <= ttl_seconds <= MAX_TTL_SECONDS):
        raise ContractError("INVALID_SOURCE_READ_TTL", "TTL must be an integer from 1 to 86400 seconds")
    root = Path(root).resolve(strict=True)
    with _guard(root):
        if not _job(root, read_id).is_dir():
            raise ContractError("SOURCE_READ_NOT_FOUND", "Source reading handle does not exist", read_id)
        lease = _lease(root, read_id)
        if lease["state"] != "ready":
            raise ContractError("SOURCE_READ_BUSY", "Source conversion is still running", read_id)
        now = _now()
        if lease["expires_at"] <= now:
            raise ContractError("SOURCE_READ_EXPIRED", "Extract the source again after its lease expires", read_id)
        lease["expires_at"] = now + ttl_seconds
        _write_lease(root, read_id, lease)
        return {"read_id": read_id, "expires_at": lease["expires_at"]}


def release(root, read_id):
    """Release exactly one job; unknown valid handles are already released."""
    _identity(read_id)
    root = Path(root).resolve(strict=True)
    with _guard(root):
        if not _job(root, read_id).exists():
            return {"released": False, "read_id": read_id}
        if _lease(root, read_id)["state"] == "converting":
            raise ContractError("SOURCE_READ_BUSY", "Source conversion is still running", read_id)
        busy = _busy_path(root, read_id)
        with _file_lock(busy, blocking=False) as available:
            if not available:
                raise ContractError("SOURCE_READ_BUSY", "Source conversion is still running", read_id)
            _remove_job(root, read_id)
        busy.unlink(missing_ok=True)
        return {"released": True, "read_id": read_id}


def create(root, source, data, *, options=None, page_range=None):
    """Convert fixed bytes once; never register sources or touch ingest state."""
    from . import document_parser

    root = Path(root).resolve(strict=True)
    source_id = validate_id(source.get("source_id", source.get("id")))
    suffix = Path(source.get("path", "")).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        raise ContractError("UNSUPPORTED_DOCUMENT_FORMAT", "A document needs its actual format suffix")
    if not isinstance(data, bytes) or len(data) > MAX_SOURCE_BYTES:
        raise ContractError("SOURCE_READ_TOO_LARGE", "Source bytes must not exceed 256 MiB")
    if options is not None and not isinstance(options, dict):
        raise ContractError("INVALID_PARSER_OPTIONS", "Parser options must be an object")
    options = dict(options or {})
    timeout = options.get("timeout_seconds", 300)
    limit = options.get("max_output_bytes", MAX_OUTPUT_BYTES)
    input_limit = options.get("max_input_bytes", MAX_SOURCE_BYTES)
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or timeout <= 0):
        raise ContractError("INVALID_PARSER_OPTIONS", "Timeout must be positive and finite")
    for field, value, maximum in (("max_input_bytes", input_limit, MAX_SOURCE_BYTES),
                                  ("max_output_bytes", limit, MAX_OUTPUT_BYTES)):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ContractError("INVALID_PARSER_OPTIONS", field + " must be an integer from 1 to 268435456")
    read_id = uuid4().hex
    reference = READ_ROOT + "/" + read_id
    busy_path = None
    owned = False
    with ExitStack() as busy:
        try:
            with _guard(root):
                now = _now()
                _cleanup_locked(root, now)
                if len(_ids(root)) >= MAX_JOBS:
                    raise ContractError("SOURCE_READ_CAPACITY", "Release an active read handle before extracting another source")
                _job(root, read_id).mkdir()
                owned = True
                busy_path = _busy_path(root, read_id)
                if not busy.enter_context(_file_lock(busy_path, blocking=False)):
                    raise ContractError("SOURCE_READ_BUSY", "Source reading handle is already in use", read_id)
                _write_lease(root, read_id, {"read_id": read_id, "state": "converting",
                                          "expires_at": now + max(timeout, TTL_SECONDS)})
            original_ref = reference + "/source" + suffix
            _safe(root, original_ref).write_bytes(data)
            parsed = document_parser.parse(root, source, data, reference + "/parsed",
                                           options=options, page_range=page_range)
            directory = _safe(root, reference + "/parsed")
            _validate_tree(root, directory)
            total = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
            if total > limit:
                raise ContractError("SOURCE_READ_TOO_LARGE", "Parsed output exceeds the source reading size limit")
            with _guard(root):
                expires_at = _now() + TTL_SECONDS
                _write_lease(root, read_id, {"read_id": read_id, "state": "ready",
                                          "source_id": source_id, "expires_at": expires_at})
            return {"read_id": read_id, "expires_at": expires_at,
                    "original_ref": original_ref, "parsed": parsed}
        except BaseException:
            if owned:
                with _guard(root):
                    if _job(root, read_id).exists():
                        _remove_job(root, read_id)
                # Close our own busy handle before removing its sidecar on Windows.
                busy.close()
                if busy_path is not None:
                    with _guard(root):
                        busy_path.unlink(missing_ok=True)
            raise
