"""Canonical digests and command envelopes; this module never confirms a human action."""

import hashlib
import json
import uuid
from pathlib import Path

from . import SCHEMA_VERSION


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: str | Path) -> str:
    return digest_bytes(Path(path).read_bytes())


def digest_json(value) -> str:
    return digest_bytes(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


def envelope(status, *, result=None, diagnostics=None, input_digests=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "operation_id": str(uuid.uuid4()),
        "input_digests": input_digests or {},
        "output_refs": [],
        "diagnostics": diagnostics or [],
        "retryability": "not_needed" if status == "ok" else "after_correction",
        "result": result,
    }
