"""Read-only raw capture and durable evidence recovery; no remote acquisition.

The first slice extracts UTF-8 .md/.txt only. Binary attachments are preserved
as opaque original objects, never presented as extracted or OCR text.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from . import contracts, receipts

RAW_CLASSES = frozenset({"conventions", "chips", "storys", "specs", "protocols"})
TEXT_FORMATS = {".md": "text/markdown", ".txt": "text/plain"}
TOOL = "hs-common-raw-utf8"
TOOL_VERSION = "1"


class SourceError(ValueError):
    def __init__(self, code, message, path=""):
        super().__init__(message)
        self.code, self.message, self.path = code, message, str(path)


def _fail(code, message, path=""):
    raise SourceError(code, message, path)


def _root(knowledge_root):
    try:
        return _native(Path(knowledge_root).resolve(strict=True))
    except OSError as exc:
        raise SourceError("SOURCE_UNAVAILABLE", "Knowledge root is unavailable") from exc


def _native(path):
    """Use Windows extended paths for evidence trees with digest filenames."""
    value = str(path)
    if os.name == "nt" and path.is_absolute() and not value.startswith("\\\\?\\"):
        return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)
    return path


def _raw_path(root, supplied):
    raw = os.fspath(supplied)
    if not isinstance(raw, str) or not raw:
        _fail("DOCUMENT_SOURCE_DEFERRED", "Expected a local raw file")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) and not re.match(r"^[A-Za-z]:[\\/]", raw):
        _fail("DOCUMENT_SOURCE_DEFERRED", "Remote and linked document sources are deferred")
    candidate = Path(raw)
    if ".." in candidate.parts:
        _fail("SOURCE_PATH_ESCAPE", "Parent traversal is not a raw source reference")
    lexical = _native(candidate) if candidate.is_absolute() else root / candidate
    try:
        relative = lexical.relative_to(root)
    except ValueError:
        _fail("SOURCE_PATH_ESCAPE", "Document must be under the knowledge raw root")
    if (
        len(relative.parts) < 3
        or relative.parts[0] != "docs-raw"
        or relative.parts[1] not in RAW_CLASSES
        or lexical.name.casefold() in {"agents.md", "index.md"}
    ):
        _fail(
            "DOCUMENT_SOURCE_DEFERRED",
            "Only raw originals in the five enabled classes are supported",
            relative,
        )
    try:
        resolved = lexical.resolve(strict=True)
        if not resolved.is_relative_to(root / "docs-raw" / relative.parts[1]):
            _fail("SOURCE_PATH_ESCAPE", "Raw link resolves outside its registered class", relative)
        if not resolved.is_file():
            _fail("SOURCE_UNAVAILABLE", "Raw original is not a regular file", relative)
        return lexical, resolved, relative.as_posix()
    except OSError as exc:
        raise SourceError("SOURCE_UNAVAILABLE", "Raw original is unavailable", relative) from exc


def _signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read_member(root, supplied):
    lexical, resolved, relative = _raw_path(root, supplied)
    try:
        signature = _signature(resolved)
        data = resolved.read_bytes()
        if lexical.resolve(strict=True) != resolved or _signature(resolved) != signature:
            _fail("SOURCE_CHANGED", "Raw original changed while being read", relative)
    except OSError as exc:
        raise SourceError(
            "SOURCE_CHANGED", "Raw original disappeared while being read", relative
        ) from exc
    return {
        "path": lexical,
        "resolved": resolved,
        "raw_path": relative,
        "data": data,
        "signature": signature,
    }


def _recheck(root, captured):
    for member in captured:
        try:
            _, resolved, _ = _raw_path(root, member["path"])
            if (
                resolved != member["resolved"]
                or _signature(resolved) != member["signature"]
                or resolved.read_bytes() != member["data"]
            ):
                _fail("SOURCE_CHANGED", "Raw original changed during capture", member["raw_path"])
        except OSError as exc:
            raise SourceError(
                "SOURCE_CHANGED", "Raw original became unavailable", member["raw_path"]
            ) from exc


def _extract(data, suffix, *, primary):
    if suffix not in TEXT_FORMATS:
        if primary:
            _fail("UNSUPPORTED_DOCUMENT_FORMAT", "This slice extracts UTF-8 .md/.txt only")
        return None, None, None
    encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        text = data.decode(encoding)
        if "\x00" in text:
            raise UnicodeError("NUL in text")
    except UnicodeError as exc:
        raise SourceError(
            "UNSUPPORTED_ENCODING", "Text must be valid UTF-8 without NUL characters"
        ) from exc
    byte_position = 3 if encoding == "utf-8-sig" else 0
    position, spans, section = 0, [], []
    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        heading = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t]*\r?\n?$", line)
        if heading:
            depth = len(heading[1])
            section = section[: depth - 1] + [heading[2]]
        byte_end = byte_position + len(line.encode("utf-8"))
        spans.append(
            {
                "line": line_number,
                "text_start": position,
                "text_end": position + len(line),
                "byte_start": byte_position,
                "byte_end": byte_end,
                "section": list(section),
            }
        )
        position += len(line)
        byte_position = byte_end
    locators = {
        "schema_version": "1.0",
        "original_digest": receipts.digest_bytes(data),
        "text_digest": receipts.digest_bytes(text.encode("utf-8")),
        "unit": "line",
        "spans": spans,
    }
    return text, encoding, locators


def _markdown_destinations(text):
    """Recognize inline, reference-definition and HTML href/src destinations.

    Inline destinations are balanced instead of truncating at the first ')'.
    No destination is fetched or executed. Fragment-only links are navigation.
    """
    visible, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        visible.append(line)
    text = re.sub(r"<!--.*?(?:-->|$)", "", "".join(visible), flags=re.DOTALL)
    text = re.sub(r"(`+).*?\1", "", text, flags=re.DOTALL)
    destinations = []
    for opening in re.finditer(r"\]\(\s*", text):
        offset = opening.end()
        if offset < len(text) and text[offset] == "<":
            end = text.find(">", offset + 1)
            if end < 0:
                _fail("UNSUPPORTED_MARKDOWN_LINK", "Unclosed angle link destination")
            destinations.append(text[offset + 1 : end])
            continue
        value, depth = [], 0
        while offset < len(text):
            char = text[offset]
            if char == "\\" and offset + 1 < len(text):
                offset += 1
                value.append(text[offset])
            elif char == "(":
                depth += 1
                value.append(char)
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
                value.append(char)
            elif char.isspace() and depth == 0:
                break
            else:
                value.append(char)
            offset += 1
        destinations.append("".join(value))
    for match in re.finditer(
        r"(?m)^ {0,3}\[[^\]]+\]:[ \t]*(?:\r?\n[ \t]*)?(<[^>\r\n]*>|\S+)", text
    ):
        destinations.append(match[1].strip("<>"))

    class _HTMLDestinations(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if not value:
                    continue
                if key in {"srcset", "imagesrcset"}:
                    _fail(
                        "UNSUPPORTED_MARKDOWN_LINK",
                        "HTML responsive assets require an explicit simplified raw export",
                    )
                if key in {"src", "href", "poster"} or (tag == "object" and key == "data"):
                    destinations.append(value)

    parser = _HTMLDestinations()
    parser.feed(text)
    parser.close()
    return destinations


def _check_references(root, captured):
    declared = {member["resolved"] for member in captured}
    for member in captured:
        if member["path"].suffix.lower() != ".md":
            continue
        for destination in _markdown_destinations(member["text"]):
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = member["path"].parent / unquote(parsed.path)
            # Local relative links may use '..', but normalization must still
            # resolve to an explicitly captured allowed raw original.
            path = Path(os.path.abspath(path))
            try:
                _, resolved, _ = _raw_path(root, path)
            except SourceError as exc:
                if exc.code == "SOURCE_UNAVAILABLE":
                    raise SourceError(
                        "ATTACHMENT_MISSING",
                        "Markdown local attachment is missing",
                        member["raw_path"],
                    ) from exc
                raise
            if resolved not in declared:
                _fail(
                    "ATTACHMENT_NOT_DECLARED",
                    "Markdown local attachment must be explicitly captured",
                    member["raw_path"],
                )


def _safe_relative(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence references must be safe relative paths")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence references must be normalized relative paths")
    return path


def _contained(root, relative, *, exists=True):
    path = root.joinpath(*_safe_relative(relative).parts)
    try:
        resolved = path.resolve(strict=exists)
        if not resolved.is_relative_to(root):
            _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence reference escapes its root", relative)
        return path
    except OSError as exc:
        raise SourceError(
            "EVIDENCE_INTEGRITY_ERROR", "Evidence payload is unavailable", relative
        ) from exc


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _identity(source_id, version, members):
    return {
        "schema_version": "1.0",
        "source_id": source_id,
        "declared_version": version,
        "extractor": {
            "tool": TOOL,
            "version": TOOL_VERSION,
            "parameters": {"newline": "preserve", "bom": "strip_from_text_only"},
        },
        "members": [
            {
                key: member[key]
                for key in (
                    "raw_path",
                    "source_id",
                    "object_digest",
                    "bytes",
                    "mime",
                    "encoding",
                    "extraction",
                )
            }
            for member in members
        ],
    }


def _source_objects(member, identity, bundle_ref, acquired_at):
    resource = {
        "source_id": member["source_id"],
        "kind": "raw_document",
        "authority_domain": "wifi",
        "resolver": "knowledge_raw",
        "resource_id": member["raw_path"],
    }
    extract = member["extraction"]
    snapshot = {
        "source_id": member["source_id"],
        "snapshot_id": member["snapshot_id"],
        "declared_version": identity["declared_version"],
        "object_digest": member["object_digest"],
        "bytes": member["bytes"],
        "mime": member["mime"],
        "encoding": member["encoding"],
        "digest_kind": "original_bytes",
        "retrieval": {"method": "raw_file", "location": member["raw_path"]},
        "recovery": {
            "status": "available",
            "method": "evidence_bundle",
            "reference": f"{bundle_ref}/{member['object_ref']}",
            "retention_policy": "Retain this bundle while referenced by any card or audit record",
        },
        "acquired_at": acquired_at,
        "acquisition_tool": TOOL + ":" + TOOL_VERSION,
        "locator_policy": "UTF-8 original byte offsets and extracted Unicode character/line offsets"
        if extract
        else "Opaque original attachment; no text locator claimed",
        "extraction": {
            "status": "complete" if extract else "not_required",
            "tool": TOOL if extract else None,
            "tool_version": TOOL_VERSION if extract else None,
            "parameters": identity["extractor"]["parameters"] if extract else {},
            "text_digest": extract["text_digest"] if extract else None,
            "locator_ref": f"{bundle_ref}/{extract['locator_ref']}" if extract else None,
        },
    }
    return resource, snapshot


def _output_location(root):
    # Refuse linked output ancestors before creating anything, even when the
    # target stays inside K: persistent evidence must not redirect to raw.
    current = root
    for part in ("logs", "evidence"):
        current = current / part
        if current.exists() and (current.is_symlink() or current.is_junction()):
            _fail("EVIDENCE_PATH_ESCAPE", "Evidence output must not use linked ancestors")
        if current.exists() and not current.is_dir():
            _fail("EVIDENCE_PATH_ESCAPE", "Evidence output ancestor is not a directory")
    return current


def capture_document(
    knowledge_root, path, *, source_id, declared_version="unknown", attachments=None
):
    """Capture one primary document and an explicit, complete attachment set.

    Returns a verified capture with a source-lock delta. Only logs/evidence is
    written. It never registers sources, edits raw, creates cards or indexes.
    """
    root = _root(knowledge_root)
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or any(ord(c) < 32 for c in source_id)
    ):
        _fail("INVALID_SOURCE_ID", "source_id must be a nonempty logical identifier")
    if not isinstance(declared_version, str) or not declared_version:
        _fail("INVALID_SOURCE_VERSION", "Use a declared version or the literal unknown")
    if attachments is None:
        attachments = []
    if not isinstance(attachments, (list, tuple)):
        _fail("INVALID_ATTACHMENTS", "Attachments must be an explicit list of local paths")
    captured = [_read_member(root, entry) for entry in [path, *attachments]]
    if len({member["resolved"] for member in captured}) != len(captured):
        _fail("DUPLICATE_SOURCE_MEMBER", "Each original must be listed once")
    captured[1:] = sorted(captured[1:], key=lambda item: item["raw_path"])
    members = []
    for position, captured_member in enumerate(captured):
        suffix = captured_member["path"].suffix.lower()
        text, encoding, locators = _extract(captured_member["data"], suffix, primary=position == 0)
        captured_member.update(text=text, locators=locators)
        digest = receipts.digest_bytes(captured_member["data"])
        member_source_id = (
            source_id
            if position == 0
            else source_id
            + ":attachment:"
            + receipts.digest_bytes(captured_member["raw_path"].encode())[:24]
        )
        extraction = None
        if text is not None:
            extraction_id = receipts.digest_json(
                {"object_digest": digest, "tool": TOOL, "version": TOOL_VERSION}
            )
            extraction = {
                "text_ref": f"extractions/{extraction_id}/text.txt",
                "text_digest": receipts.digest_bytes(text.encode("utf-8")),
                "locator_ref": f"extractions/{extraction_id}/locators.json",
                "locator_digest": receipts.digest_json(locators),
            }
        members.append(
            {
                "raw_path": captured_member["raw_path"],
                "source_id": member_source_id,
                "snapshot_id": "raw:"
                + receipts.digest_json(
                    {
                        "source_id": member_source_id,
                        "digest": digest,
                        "version": declared_version,
                        "extraction": extraction,
                    }
                ),
                "object_digest": digest,
                "bytes": len(captured_member["data"]),
                "mime": TEXT_FORMATS.get(suffix, "application/octet-stream"),
                "encoding": encoding,
                "object_ref": f"objects/{digest}.bin",
                "extraction": extraction,
            }
        )
    _check_references(root, captured)
    identity = _identity(source_id, declared_version, members)
    bundle_id = receipts.digest_json(identity)
    bundle_ref = f"logs/evidence/{bundle_id}"
    acquired_at = datetime.now(timezone.utc).isoformat()
    resources, snapshots = [], []
    for member in members:
        resource, snapshot = _source_objects(member, identity, bundle_ref, acquired_at)
        resources.append(resource)
        snapshots.append(snapshot)
    delta = {"schema_version": "1.0", "resources": resources, "snapshots": snapshots}
    errors = contracts.validate_document("sources", delta, root)
    if errors:
        _fail(
            "SOURCE_CONTRACT_INVALID",
            "Captured source objects do not satisfy the locked source contract",
        )
    _recheck(root, captured)
    evidence = _output_location(root)
    final = evidence / bundle_id
    if final.exists():
        existing = load_capture(root, bundle_ref)
        if existing["identity"] != identity:
            _fail(
                "EVIDENCE_INTEGRITY_ERROR",
                "Existing content-addressed bundle has a different identity",
            )
        return existing
    evidence.mkdir(parents=True, exist_ok=True)
    lock, staging = (
        evidence / ("." + bundle_id + ".lock"),
        evidence / ("." + bundle_id + "." + uuid.uuid4().hex + ".tmp"),
    )
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SourceError(
            "CAPTURE_BUSY", "Another capture of this identity is in progress"
        ) from exc
    try:
        os.close(lock_fd)
        if final.exists():
            return load_capture(root, bundle_ref)
        staging.mkdir()
        manifest = {**delta, "bundle_id": bundle_id, "identity": identity, "members": members}
        for member, original in zip(members, captured, strict=True):
            obj = staging / member["object_ref"]
            obj.parent.mkdir(parents=True, exist_ok=True)
            if not obj.exists():
                obj.write_bytes(original["data"])
            if member["extraction"]:
                extract = member["extraction"]
                text_file = staging / extract["text_ref"]
                text_file.parent.mkdir(parents=True, exist_ok=True)
                text_file.write_bytes(original["text"].encode("utf-8"))
                (staging / extract["locator_ref"]).write_bytes(_canonical(original["locators"]))
        (staging / "manifest.json").write_bytes(_canonical(manifest))
        _recheck(root, captured)
        # os.rename under the exclusive identity lock publishes a complete
        # directory. Readers never receive a partially built final bundle.
        staging.rename(final)
        return load_capture(root, bundle_ref, receipts.digest_json(manifest))
    except OSError as exc:
        raise SourceError(
            "EVIDENCE_WRITE_FAILED", "Evidence capture could not be published"
        ) from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def load_capture(knowledge_root, bundle_ref, manifest_digest=None):
    """Verify a retained bundle without consulting the original raw tree.

    Downstream records should pin manifest_digest. Without that external pin,
    content identity and every payload are checked, but acquisition timestamps
    are merely self-described metadata, not authenticated historical facts.
    """
    root = _root(knowledge_root)
    parts = _safe_relative(bundle_ref).parts
    if (
        len(parts) != 3
        or parts[:2] != ("logs", "evidence")
        or not re.fullmatch(r"[0-9a-f]{64}", parts[2])
    ):
        _fail("EVIDENCE_INTEGRITY_ERROR", "Expected one retained evidence bundle reference")
    bundle = _contained(root, bundle_ref)
    try:
        manifest_file = _contained(bundle, "manifest.json")
        data = manifest_file.read_bytes()
        if manifest_digest is not None and receipts.digest_bytes(data) != manifest_digest:
            _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence manifest digest mismatch")
        manifest = contracts.load_document_bytes(data, "manifest.json")
        if set(manifest) != {
            "schema_version",
            "bundle_id",
            "identity",
            "members",
            "resources",
            "snapshots",
        }:
            _fail("EVIDENCE_INTEGRITY_ERROR", "Unexpected evidence manifest fields")
        identity, members = manifest["identity"], manifest["members"]
        if manifest["bundle_id"] != parts[2] or receipts.digest_json(identity) != parts[2]:
            _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence identity does not match its address")
        if (
            not isinstance(members, list)
            or not members
            or len(members) != len(manifest["snapshots"])
            or len(members) != len(manifest["resources"])
        ):
            _fail("EVIDENCE_INTEGRITY_ERROR", "Incomplete evidence member set")
        if _identity(identity["source_id"], identity["declared_version"], members) != identity:
            _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence metadata identity mismatch")
        delta = {key: manifest[key] for key in ("schema_version", "resources", "snapshots")}
        if contracts.validate_document("sources", delta, root):
            _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence source objects violate the locked contract")
        loaded, payloads = [], [(manifest_file, data)]
        for position, member in enumerate(members):
            if set(member) != {
                "raw_path",
                "source_id",
                "snapshot_id",
                "object_digest",
                "bytes",
                "mime",
                "encoding",
                "object_ref",
                "extraction",
            }:
                _fail("EVIDENCE_INTEGRITY_ERROR", "Invalid evidence member fields")
            raw_path = _safe_relative(member["raw_path"])
            if (
                len(raw_path.parts) < 3
                or raw_path.parts[0] != "docs-raw"
                or raw_path.parts[1] not in RAW_CLASSES
                or raw_path.name.casefold() in {"agents.md", "index.md"}
            ):
                _fail(
                    "EVIDENCE_INTEGRITY_ERROR", "Manifest does not describe an allowed raw original"
                )
            obj = _contained(bundle, member["object_ref"])
            if member["object_ref"] != f"objects/{member['object_digest']}.bin":
                _fail(
                    "EVIDENCE_INTEGRITY_ERROR",
                    "Original object reference does not match its digest",
                )
            original = obj.read_bytes()
            payloads.append((obj, original))
            if (
                receipts.digest_bytes(original) != member["object_digest"]
                or len(original) != member["bytes"]
            ):
                _fail("EVIDENCE_INTEGRITY_ERROR", "Original object digest or size mismatch")
            text, encoding, locators = _extract(
                original, raw_path.suffix.lower(), primary=position == 0
            )
            if encoding != member["encoding"]:
                _fail("EVIDENCE_INTEGRITY_ERROR", "Stored encoding disagrees with original bytes")
            extract = member["extraction"]
            if (text is None) != (extract is None):
                _fail(
                    "EVIDENCE_INTEGRITY_ERROR",
                    "Stored extraction mode disagrees with original format",
                )
            if extract:
                if set(extract) != {"text_ref", "text_digest", "locator_ref", "locator_digest"}:
                    _fail("EVIDENCE_INTEGRITY_ERROR", "Invalid extraction fields")
                text_path, locator_path = (
                    _contained(bundle, extract["text_ref"]),
                    _contained(bundle, extract["locator_ref"]),
                )
                text_data, locator_data = text_path.read_bytes(), locator_path.read_bytes()
                payloads.extend([(text_path, text_data), (locator_path, locator_data)])
                if (
                    receipts.digest_bytes(text_data) != extract["text_digest"]
                    or text_data != text.encode("utf-8")
                    or receipts.digest_bytes(locator_data) != extract["locator_digest"]
                    or contracts.load_document_bytes(locator_data) != locators
                ):
                    _fail(
                        "EVIDENCE_INTEGRITY_ERROR",
                        "Extracted text or original locator mapping mismatch",
                    )
            resource, snapshot = manifest["resources"][position], manifest["snapshots"][position]
            acquired_at = datetime.fromisoformat(snapshot["acquired_at"])
            if acquired_at.tzinfo is None:
                _fail("EVIDENCE_INTEGRITY_ERROR", "Acquisition time must include a timezone")
            expected_source_id = (
                identity["source_id"]
                if position == 0
                else identity["source_id"]
                + ":attachment:"
                + receipts.digest_bytes(member["raw_path"].encode())[:24]
            )
            expected_snapshot_id = "raw:" + receipts.digest_json(
                {
                    "source_id": expected_source_id,
                    "digest": member["object_digest"],
                    "version": identity["declared_version"],
                    "extraction": extract,
                }
            )
            if (
                member["source_id"] != expected_source_id
                or member["snapshot_id"] != expected_snapshot_id
                or member["mime"]
                != TEXT_FORMATS.get(raw_path.suffix.lower(), "application/octet-stream")
            ):
                _fail(
                    "EVIDENCE_INTEGRITY_ERROR",
                    "Captured source identity or format disagrees with its bytes",
                )
            expected_resource, expected_snapshot = _source_objects(
                member, identity, bundle_ref, snapshot["acquired_at"]
            )
            if resource != expected_resource or snapshot != expected_snapshot:
                _fail("EVIDENCE_INTEGRITY_ERROR", "Source delta disagrees with captured member")
            loaded.append({**member, "text": text, "locators": locators})
        for path, original in payloads:
            if path.read_bytes() != original or not path.resolve(strict=True).is_relative_to(
                bundle
            ):
                _fail("EVIDENCE_INTEGRITY_ERROR", "Evidence changed during recovery")
        return {
            **manifest,
            "bundle_ref": bundle_ref,
            "manifest_digest": receipts.digest_bytes(data),
            "source_id": identity["source_id"],
            "members": loaded,
        }
    except SourceError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise SourceError(
            "EVIDENCE_INTEGRITY_ERROR", "Evidence bundle is incomplete or invalid"
        ) from exc
