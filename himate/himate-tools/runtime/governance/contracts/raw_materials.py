"""Browse and save physical raw materials for a trusted local host."""

import errno
import hashlib
import heapq
import os
from pathlib import Path
import re
import stat
import tempfile

from .document_parser import SUPPORTED_FORMATS
from .source_read import _file_lock
from .validation import ContractError, safe_path
from .workspace_config import WorkspaceConfigError, no_links, relative_path


PRIVATE_NAMES = {"dbox.local.yml"}
RESERVED_NAMES = {"agents.md", "index.md", "readme.md", "dbox.example.yml", "dbox.local.yml.example"}
PACKAGE_MARKER = ".intake-package.json"
MAX_PATH = 1024


def _visible(name):
    if name.startswith(".") or name.casefold() in PRIVATE_NAMES or any(ord(char) < 32 for char in name):
        return False
    try:
        relative_path(name)
    except WorkspaceConfigError:
        return False
    return True


def _linked(info):
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def _raw_path(root, path, *, directory=False):
    if not isinstance(path, str) or (not path and not directory):
        raise ContractError("RAW_UNSAFE_PATH", "Expected a path relative to docs-raw")
    if path and not all(_visible(part) for part in path.split("/")):
        raise ContractError("RAW_UNSAFE_PATH", "Invalid raw path", path)
    try:
        candidate = safe_path(root, "docs-raw/" + path if path else "docs-raw", ["docs-raw"])
        no_links(candidate)
        return candidate
    except (ContractError, WorkspaceConfigError) as error:
        raise ContractError("RAW_UNSAFE_PATH", "Invalid or linked raw path", path) from error


def _info(target, path, *, directory=False):
    try:
        info = target.lstat()
    except (FileNotFoundError, NotADirectoryError) as error:
        raise ContractError("RAW_NOT_FOUND", "Raw path does not exist", path) from error
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if _linked(info) or not valid:
        raise ContractError("RAW_UNSAFE_PATH", "Expected a regular raw file or directory", path)
    return info


def _has_package_marker(directory):
    return os.path.lexists(directory / PACKAGE_MARKER)


def _category_allowed(path, directory):
    if not path or len(path) > MAX_PATH:
        return False
    parts = path.split("/")
    if parts[0].casefold() == "sources" or not all(_visible(part) for part in parts):
        return False
    for _ in parts:
        if _has_package_marker(directory):
            return False
        directory = directory.parent
    return True


def category_directory(root, path, *, error="RAW_UNSAFE_PATH"):
    """Resolve one existing ordinary directory, using the same rules as discovery."""
    directory = _raw_path(root, path, directory=True)
    if not _category_allowed(path, directory):
        raise ContractError(error, "Expected an ordinary category directory", path)
    return directory, _info(directory, path, directory=True)


def categories(root):
    raw = _raw_path(root, "", directory=True)
    _info(raw, "", directory=True)
    result = []
    for directory, children, _ in os.walk(raw, followlinks=False):
        parent = Path(directory)
        allowed = []
        for name in children:
            child = parent / name
            relative = child.relative_to(raw).as_posix()
            if (len(relative) > MAX_PATH or not _visible(name)
                    or (parent == raw and name.casefold() == "sources")):
                continue
            try:
                if _linked(child.lstat()) or _has_package_marker(child):
                    continue
            except FileNotFoundError:
                continue
            allowed.append(name)
            result.append({"id": relative, "label": relative, "description": ""})
        children[:] = allowed
    return sorted(result, key=lambda row: row["id"])


def _raw_write_lock(root):
    lock = safe_path(root, "artifacts/raw-save.lock", ["artifacts"])
    no_links(lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    return _file_lock(lock)


def mkdir(root, path):
    if not isinstance(path, str) or not path or len(path) > MAX_PATH:
        raise ContractError("RAW_UNSAFE_PATH", "Expected a new directory path relative to docs-raw", path)
    parent_path, _, name = path.rpartition("/")
    if (not _visible(name) or (not parent_path and name.casefold() == "sources")
            or path.startswith("/")):
        raise ContractError("RAW_UNSAFE_PATH", "Invalid new raw directory", path)
    with _raw_write_lock(root):
        if parent_path:
            parent, _ = category_directory(root, parent_path)
        else:
            parent = _raw_path(root, "", directory=True)
            _info(parent, "", directory=True)
        try:
            if any(child.name.casefold() == name.casefold() for child in parent.iterdir()):
                raise FileExistsError(name)
            (parent / name).mkdir()
        except FileExistsError as error:
            raise ContractError("RAW_TARGET_EXISTS", "A file or folder with that name already exists", path) from error
        except OSError as error:
            raise ContractError("RAW_MKDIR_FAILED", "Cannot create the raw directory", path) from error
    return {"path": path}


def rmdir(root, path):
    with _raw_write_lock(root):
        directory, _ = category_directory(root, path)
        try:
            directory.rmdir()
        except FileNotFoundError as error:
            raise ContractError("RAW_NOT_FOUND", "Raw path does not exist", path) from error
        except OSError as error:
            if error.errno in {errno.ENOTEMPTY, errno.EEXIST} or getattr(error, "winerror", None) == 145:
                raise ContractError("RAW_DIRECTORY_NOT_EMPTY", "Raw directory is not empty", path) from error
            raise ContractError("RAW_RMDIR_FAILED", "Cannot remove the raw directory", path) from error
    return {"path": path}


def list_entries(root, path, after, count):
    directory = _raw_path(root, path, directory=True)
    _info(directory, path, directory=True)
    prefix = path + "/" if path else ""
    ordinary_parent = not path or _category_allowed(path, directory)

    def directory_details(item):
        child = directory / item["name"]
        category = (ordinary_parent and len(item["path"]) <= MAX_PATH
                    and (bool(path) or item["name"].casefold() != "sources")
                    and not _has_package_marker(child))
        empty = False
        if category:
            try:
                with os.scandir(child) as contents:
                    empty = next(contents, None) is None
            except OSError:
                pass
        return {**item, "category": category, "empty": empty}

    with os.scandir(directory) as entries:
        def visible_entries():
            for entry in entries:
                if entry.name <= after or not _visible(entry.name):
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if _linked(info):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    yield {"name": entry.name, "path": prefix + entry.name, "kind": "directory", "size": None}
                elif stat.S_ISREG(info.st_mode):
                    yield {"name": entry.name, "path": prefix + entry.name, "kind": "file", "size": info.st_size}

        rows = heapq.nsmallest(count, visible_entries(), key=lambda item: item["name"])
    return [directory_details(item) if item["kind"] == "directory" else item for item in rows]


def file_path(root, path):
    target = _raw_path(root, path)
    info = _info(target, path)
    return {"name": target.name, "path": path, "kind": "file", "size": info.st_size,
            "absolute_path": str(target)}


def _open_stage(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ContractError("RAW_INVALID_STAGE", "Provide a trusted absolute staging file")
    path = Path(value)
    try:
        no_links(path)
        info = path.lstat()
        if _linked(info) or not stat.S_ISREG(info.st_mode):
            raise ContractError("RAW_INVALID_STAGE", "Staging must be a regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        stream = os.fdopen(os.open(path, flags), "rb")
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(info, opened):
            stream.close()
            raise ContractError("RAW_INVALID_STAGE", "Staging file changed while opening")
        return stream
    except (OSError, ValueError, WorkspaceConfigError) as error:
        raise ContractError("RAW_INVALID_STAGE", "Cannot open a trusted regular staging file") from error


def save(root, request, *, category_only=False):
    path = request.get("path")
    if not isinstance(path, str) or not all(_visible(part) for part in path.split("/")):
        raise ContractError("RAW_UNSAFE_PATH", "Invalid raw path")
    parts = path.split("/")
    parent_path = "/".join(parts[:-1])
    if category_only:
        directory, parent = category_directory(root, parent_path, error="INTAKE_CATEGORY_INVALID")
    else:
        directory = _raw_path(root, parent_path, directory=True)
        parent = _info(directory, parent_path, directory=True)
    target = directory / parts[-1]
    if (tuple(part.casefold() for part in parts[:2]) == ("sources", "dbox")
            or target.name.casefold() in RESERVED_NAMES
            or target.suffix.lower() not in SUPPORTED_FORMATS):
        raise ContractError("RAW_UNSUPPORTED_TARGET", "Choose a supported raw document filename", path)
    if any(child.name.casefold() == target.name.casefold() for child in directory.iterdir()):
        raise ContractError("RAW_TARGET_EXISTS", "A file with that name already exists", path)
    size_expected = request.get("expected_size")
    hash_expected = request.get("expected_sha256")
    if size_expected is not None and (type(size_expected) is not int or size_expected < 0):
        raise ContractError("RAW_INVALID_STAGE", "Expected size must be a nonnegative integer")
    if hash_expected is not None and (not isinstance(hash_expected, str) or not re.fullmatch(r"[0-9a-f]{64}", hash_expected)):
        raise ContractError("RAW_INVALID_STAGE", "Expected hash must be a lowercase SHA-256")
    temporary = None
    digest = hashlib.sha256()
    size = 0
    try:
        with _open_stage(request.get("staged_path")) as source:
            before = os.fstat(source.fileno())
            # Only complete files acquire a supported extension under docs-raw.
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".upload-", suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size_expected is not None and size > size_expected:
                        raise ContractError("RAW_STAGE_MISMATCH", "Staging length differs from the request")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            after = os.fstat(source.fileno())
        observed = digest.hexdigest()
        if (before.st_size != size or after.st_size != size or before.st_mtime_ns != after.st_mtime_ns
                or (size_expected is not None and size != size_expected)
                or (hash_expected is not None and observed != hash_expected)):
            raise ContractError("RAW_STAGE_MISMATCH", "Staging size or hash changed")
        try:
            # Serialize the casefold check across cooperating CLI processes.
            # The link also prevents replacement by a non-cooperating writer.
            with _raw_write_lock(root):
                if category_only:
                    current, observed_parent = category_directory(root, parent_path, error="INTAKE_CATEGORY_INVALID")
                else:
                    current = _raw_path(root, parent_path, directory=True)
                    observed_parent = _info(current, parent_path, directory=True)
                if not os.path.samestat(parent, observed_parent):
                    raise ContractError("RAW_UNSAFE_PATH", "Raw target directory changed", path)
                if any(child.name.casefold() == target.name.casefold() for child in current.iterdir()):
                    raise ContractError("RAW_TARGET_EXISTS", "A file with that name already exists", path)
                os.link(temporary, target, follow_symlinks=False)
        except FileExistsError as error:
            raise ContractError("RAW_TARGET_EXISTS", "A file with that name already exists", path) from error
        except OSError as error:
            raise ContractError("RAW_SAVE_FAILED", "Cannot atomically save the raw file", path) from error
        return {"name": target.name, "path": path, "kind": "file", "size": size, "sha256": observed}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
