"""Own-run temporary storage; reports and pre-existing directories are never removed."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import uuid


MARKER = ".factum-acceptance-owner.json"
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
DIRECTORY = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0x10)


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & REPARSE_POINT)


def _absolute(path):
    return Path(os.path.abspath(path))


def _overlap(first, second):
    return first == second or first in second.parents or second in first.parents


def _check_ancestors(path):
    for parent in (path, *path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if _linked(info):
            raise ValueError(f"Linked output or temporary paths are not accepted: {parent}")


def _check_new(path):
    _check_ancestors(path)
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise ValueError(f"Use a new directory; previous evidence is never removed: {path}")


def _check_knowledge_ancestors(path):
    for parent in path.parents:
        if ((parent / "config.yml").is_file() and (parent / "docs-raw").is_dir()
                and (parent / "knowledge").is_dir()):
            raise ValueError(f"Temporary files must be outside a knowledge root: {parent}")


def _remove_owned_tree(path, boundary):
    """Unlink directory links themselves, without traversing external targets."""
    if path != boundary and boundary not in path.parents:
        raise ValueError("Temporary cleanup escaped its owned root")
    info = path.lstat()
    if _linked(info):
        if stat.S_ISLNK(info.st_mode):
            path.unlink()
        elif getattr(info, "st_file_attributes", 0) & DIRECTORY:
            # Windows directory junction: rmdir removes this entry, not target data.
            os.rmdir(path)
        else:
            path.unlink()
        return
    if stat.S_ISDIR(info.st_mode):
        for child in path.iterdir():
            _remove_owned_tree(child, boundary)
        path.rmdir()
    else:
        path.unlink()


class RunStorage:
    def __init__(self, output, temporary, policy, source_roots):
        self.output = _absolute(output)
        self.separate = temporary is not None
        self.temporary = _absolute(temporary) if self.separate else self.output
        self.policy = policy
        if policy != "never" and not self.separate:
            raise ValueError("--cleanup-temp requires a separate --temp-dir; reports are never removed")
        _check_new(self.output)
        if self.separate:
            _check_new(self.temporary)
            if _overlap(self.output, self.temporary):
                raise ValueError("Report and temporary directories must not overlap")
            for source in source_roots:
                if _overlap(self.temporary, _absolute(source)):
                    raise ValueError(f"Temporary files must be outside source directories: {source}")
            _check_knowledge_ancestors(self.temporary)
        self.output.mkdir(parents=True)
        if self.separate:
            self.temporary.mkdir(parents=True)
            self.marker = {
                "schema_version": "1.0", "run_id": uuid.uuid4().hex,
                "report_dir": str(self.output), "temp_dir": str(self.temporary),
                "owner_pid": os.getpid(),
            }
            (self.temporary / MARKER).write_text(json.dumps(self.marker), encoding="utf-8")
            self.identity = self.temporary.stat()
        (self.temporary / "t").mkdir()

    def describe(self):
        return {"report_dir": str(self.output), "temp_dir": str(self.temporary),
                "cleanup_policy": self.policy, "cleanup_status": "retained"}

    def finish(self, passed):
        report = self.describe()
        if not passed or self.policy == "never":
            return report
        try:
            _check_ancestors(self.temporary)
            current = self.temporary.stat()
            if (current.st_dev, current.st_ino) != (self.identity.st_dev, self.identity.st_ino):
                raise ValueError("Temporary root identity changed")
            if json.loads((self.temporary / MARKER).read_text(encoding="utf-8")) != self.marker:
                raise ValueError("Temporary ownership marker changed")
            _remove_owned_tree(self.temporary, self.temporary)
            report["cleanup_status"] = "removed"
        except (OSError, ValueError) as error:
            report.update(cleanup_status="failed", cleanup_error=str(error))
        return report
