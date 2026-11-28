"""Version and relocate explicit source lines without inferring program semantics.

Ported from LangChain OpenWiki's repository evidence resolver at
c6cac5edfcd9193e3525f469d24bd4ac33d74c85, resolver.ts:294-741, 798-810.
https://github.com/langchain-ai/openwiki/blob/c6cac5edfcd9193e3525f469d24bd4ac33d74c85/src/claims/evidence/repository/resolver.ts
Copyright (c) 2026. MIT license: see code_evidence.LICENSE alongside this file.

This profile normalizes CRLF to LF, unlike the upstream exact-line-ending
profile. Other whitespace is significant. A unique text match establishes
content relocation, not the semantic identity of an enclosing code object.
Missing or unknown versions remain unversioned until a caller reviews them.
"""

from __future__ import annotations

import base64
from bisect import bisect_right
import binascii
import hashlib
import json
import re


_PREFIX = "fc-code-lines-v1:sha256:"
_CONTEXT_LINES = 3
_MAX_INTEGER = 2**53 - 1
_CACHE_KEY = "code_evidence:fc-code-lines-v1"
_FIELDS = {"selectedLineCount", "firstSelectedLineHash", "lastSelectedLineHash",
           "precedingContextLineCount", "precedingContextHash",
           "followingContextLineCount", "followingContextHash"}


def capture(text: str, line_start: int, line_end: int, *, cache=None) -> str:
    """Capture a caller-verified inclusive, one-based range for later resolution.

    The returned opaque version is evidence metadata, not an approval receipt.
    Invalid text or a range outside this source raises ValueError. ``cache`` is
    an optional caller-owned dictionary, normally retained for one file/run.
    """
    _validate_hint(line_start, line_end)
    document = _document(text, cache)
    if line_end > len(document["lines"]):
        raise ValueError("Code evidence range is outside the supplied source")
    return _version(document["lines"], (line_start - 1, line_end))


def resolve(text: str, line_start: int, line_end: int, version, *, cache=None) -> dict:
    """Observe the current location/content of an existing evidence version.

    ``fresh`` and ``relocated`` retain the supplied version. ``changed`` offers
    a new version that must not be accepted without the caller's review.
    ``unresolved`` means no unique range can be determined. Missing, malformed
    or unsupported versions return ``unversioned`` rather than capturing an
    unreviewed baseline. An old hint may be beyond the current file's end.
    """
    _validate_hint(line_start, line_end)
    document = _document(text, cache)
    previous = _parse_version(version)
    if previous is None:
        return {"status": "unversioned"}
    lines = document["lines"]
    hint = (line_start - 1, line_end) if line_end <= len(lines) else None
    span = _unchanged_range(document, hint, previous)
    if span is not None:
        status = "fresh" if span == (line_start - 1, line_end) else "relocated"
        return _result(status, lines, span, version)
    span = _changed_range(document, previous["metadata"])
    if span is not None:
        return _result("changed", lines, span, _version(lines, span))
    return {"status": "unresolved"}


def _validate_hint(start, end):
    if (type(start) is not int or type(end) is not int
            or not 1 <= start <= end <= _MAX_INTEGER):
        raise ValueError("Code evidence needs a positive inclusive line range")


def _document(text, cache):
    if not isinstance(text, str):
        raise ValueError("Code evidence source must be decoded text")
    if cache is not None and not isinstance(cache, dict):
        raise ValueError("Code evidence cache must be a caller-owned dictionary")
    previous = cache.get(_CACHE_KEY) if cache is not None else None
    if isinstance(previous, dict) and previous.get("text") == text:
        return previous
    normalized = text.replace("\r\n", "\n")
    pieces = normalized.split("\n")
    lines = [piece + "\n" for piece in pieces[:-1]]
    if pieces[-1]:
        lines.append(pieces[-1])
    document = {"text": text, "lines": lines, "line_hashes": None, "line_starts": {}, "contexts": {}}
    if cache is not None:
        cache[_CACHE_KEY] = document
    return document


def _hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _content(lines, span):
    return "".join(lines[span[0]:span[1]])


def _result(status, lines, span, version):
    return {"status": status, "line_start": span[0] + 1, "line_end": span[1],
            "evidence_version": version, "content": _content(lines, span)}


def _unchanged_range(document, hint, previous):
    lines = document["lines"]
    metadata = previous["metadata"]
    count = metadata["selectedLineCount"]
    if (hint is not None and hint[1] - hint[0] == count
            and _hash(_content(lines, hint)) == previous["contentHash"]):
        return hint
    if document["line_hashes"] is None:
        document["line_hashes"] = [_hash(line) for line in lines]
        for start, digest in enumerate(document["line_hashes"]):
            document["line_starts"].setdefault(digest, []).append(start)
    hashes = document["line_hashes"]
    matches = []
    for start in document["line_starts"].get(metadata["firstSelectedLineHash"], ()):
        end = start + count
        if (end <= len(lines) and hashes[end - 1] == metadata["lastSelectedLineHash"]
                and _hash(_content(lines, (start, end))) == previous["contentHash"]):
            matches.append((start, end))
    if len(matches) == 1:
        return matches[0]
    matches = [span for span in matches if _matches_context(lines, span, metadata)]
    return matches[0] if len(matches) == 1 else None


def _matches_context(lines, span, metadata):
    start, end = span
    before = metadata["precedingContextLineCount"]
    after = metadata["followingContextLineCount"]
    before_matches = (start == 0 if before == 0 else start >= before
                      and _hash("".join(lines[start - before:start])) == metadata["precedingContextHash"])
    after_matches = (end == len(lines) if after == 0 else end + after <= len(lines)
                     and _hash("".join(lines[end:end + after])) == metadata["followingContextHash"])
    return before_matches and after_matches


def _context_boundaries(document, count, digest, side):
    lines = document["lines"]
    if count == 0:
        return [0 if side == "before" else len(lines)]
    contexts = document["contexts"]
    if count not in contexts:
        starts = {}
        for start in range(len(lines) - count + 1):
            key = _hash("".join(lines[start:start + count]))
            starts.setdefault(key, []).append(start)
        contexts[count] = starts
    matches = contexts[count].get(digest, ())
    return [start + count if side == "before" else start for start in matches]


def _changed_range(document, metadata):
    starts = _context_boundaries(document, metadata["precedingContextLineCount"],
                                 metadata["precedingContextHash"], "before")
    ends = _context_boundaries(document, metadata["followingContextLineCount"],
                               metadata["followingContextHash"], "after")
    candidate = None
    for start in starts:
        first_end = bisect_right(ends, start)
        remaining = len(ends) - first_end
        if remaining > 1 or remaining == 1 and candidate is not None:
            return None
        if remaining == 1:
            candidate = (start, ends[first_end])
    return candidate


def _version(lines, span):
    start, end = span
    before_start = max(0, start - _CONTEXT_LINES)
    after_end = min(len(lines), end + _CONTEXT_LINES)
    metadata = {
        "selectedLineCount": end - start,
        "firstSelectedLineHash": _hash(lines[start]),
        "lastSelectedLineHash": _hash(lines[end - 1]),
        "precedingContextLineCount": start - before_start,
        "precedingContextHash": _hash("".join(lines[before_start:start])),
        "followingContextLineCount": after_end - end,
        "followingContextHash": _hash("".join(lines[end:after_end])),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(metadata, separators=(",", ":")).encode("utf-8"))
    return _PREFIX + _hash(_content(lines, span)) + ":" + encoded.decode("ascii").rstrip("=")


def _is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _parse_version(value):
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return None
    digest, separator, encoded = value[len(_PREFIX):].partition(":")
    if (not separator or not _is_hash(digest)
            or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None):
        return None
    try:
        decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        metadata = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeError, binascii.Error):
        return None
    if not isinstance(metadata, dict) or set(metadata) != _FIELDS:
        return None
    for field, minimum, maximum in (("selectedLineCount", 1, _MAX_INTEGER),
                                    ("precedingContextLineCount", 0, _CONTEXT_LINES),
                                    ("followingContextLineCount", 0, _CONTEXT_LINES)):
        if type(metadata[field]) is not int or not minimum <= metadata[field] <= maximum:
            return None
    if not all(_is_hash(metadata[field]) for field in
               ("firstSelectedLineHash", "lastSelectedLineHash", "precedingContextHash", "followingContextHash")):
        return None
    return {"contentHash": digest, "metadata": metadata}
