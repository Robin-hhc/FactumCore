"""Parse explicit Card Markdown and technical references, never semantic truth.

Source snapshots must come from a separately verified capture or source lock.
Their identity mapping here does not authenticate source bytes or human actions.
"""

from __future__ import annotations

import re
from pathlib import Path

from jsonschema import Draft202012Validator

from . import contracts, receipts

_DELIMITER = re.compile(r"^---[ \t]*(?:\r?\n|$)")
_ANCHOR = re.compile(r"^ {0,3}<a[ \t]+id=([\"'])([^\"'<>\s]+)\1[ \t]*>[ \t]*</a>[ \t]*(?:\r?\n)?$")
_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*(?:\r?\n)?$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*?)(?:\r?\n)?$")


class CardError(ValueError):
    def __init__(self, code, message, path=""):
        super().__init__(message)
        self.code, self.message, self.path = code, message, str(path)


def _fail(code, message, path=""):
    raise CardError(code, message, path)


def _split(data):
    if not isinstance(data, bytes):
        _fail("INVALID_CARD_INPUT", "Card input must be explicit Markdown bytes")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise CardError("INVALID_CARD_ENCODING", "Card Markdown must be UTF-8") from exc
    if "\x00" in text:
        _fail("INVALID_CARD_ENCODING", "Card Markdown cannot contain NUL characters")
    lines = text.splitlines(keepends=True)
    if not lines or not _DELIMITER.fullmatch(lines[0]):
        _fail("INVALID_CARD_FRONTMATTER", "Card must start with a YAML frontmatter delimiter")
    offset = len(lines[0])
    for line in lines[1:]:
        if _DELIMITER.fullmatch(line):
            try:
                metadata = contracts.load_document_bytes(
                    text[len(lines[0]) : offset].encode("utf-8")
                )
            except contracts.ContractError as exc:
                raise CardError("INVALID_CARD_FRONTMATTER", str(exc)) from exc
            return metadata, text[offset + len(line) :]
        offset += len(line)
    _fail("INVALID_CARD_FRONTMATTER", "Card frontmatter has no closing delimiter")


def _unique(values, code, path):
    if len(values) != len(set(values)):
        _fail(code, "Identifiers or references must not be duplicated", path)


def _visible_line(line, in_comment):
    """Mask HTML comments without changing original character positions."""
    position, parts = 0, []
    while position < len(line):
        if in_comment:
            closing = line.find("-->", position)
            end = len(line) if closing < 0 else closing + 3
            parts.append(re.sub(r"[^\r\n]", " ", line[position:end]))
            position = end
            in_comment = closing < 0
        else:
            opening = line.find("<!--", position)
            if opening < 0:
                parts.append(line[position:])
                break
            parts.append(line[position:opening])
            position, in_comment = opening, True
    return "".join(parts), in_comment


def _body_structure(body):
    anchors, sections = [], set()
    fence, offset, in_comment = None, 0, False
    for line in body.splitlines(keepends=True):
        opening = _FENCE.fullmatch(line)
        if fence:
            if (
                opening
                and opening[1][0] == fence[0]
                and len(opening[1]) >= fence[1]
                and not opening[2].strip()
            ):
                fence = None
        elif opening and not in_comment:
            fence = (opening[1][0], len(opening[1]))
        else:
            visible, in_comment = _visible_line(line, in_comment)
            anchor = _ANCHOR.fullmatch(visible)
            if anchor:
                if any(item["anchor"] == anchor[2] for item in anchors):
                    _fail("DUPLICATE_ANCHOR", "Explicit anchors must be unique", anchor[2])
                anchors.append(
                    {"anchor": anchor[2], "marker_start": offset, "start": offset + len(line)}
                )
            elif re.search(r"<a\b[^>]*\bid\s*=", visible, re.IGNORECASE):
                _fail("INVALID_ANCHOR", 'Use a standalone explicit <a id="..."></a> anchor')
            heading = _HEADING.fullmatch(visible)
            if heading:
                sections.add(re.sub(r"[ \t]+#+[ \t]*$", "", heading[1]).strip())
        offset += len(line)
    result = {}
    for position, item in enumerate(anchors):
        end = anchors[position + 1]["marker_start"] if position + 1 < len(anchors) else len(body)
        result[item["anchor"]] = {"start": item["start"], "end": end, "anchor": item["anchor"]}
    return result, sections


def _source_mapping(knowledge_root, source_snapshots, needed):
    if source_snapshots is None:
        root = Path(knowledge_root).resolve(strict=True)
        lock = root / "governance/sources.lock.yaml"
        if lock.exists():
            if not lock.resolve(strict=True).is_relative_to(root):
                _fail("SOURCE_PATH_ESCAPE", "Source lock escapes its knowledge root")
            source_snapshots = contracts.load_document(lock).get("snapshots")
        elif needed:
            _fail(
                "SOURCE_BINDING_REQUIRED",
                "Pass verified source_snapshots or an existing source lock",
            )
        else:
            source_snapshots = []
    if not isinstance(source_snapshots, (list, tuple)):
        _fail("INVALID_SOURCE_BINDINGS", "source_snapshots must be an explicit snapshot sequence")
    result = {}
    for snapshot in source_snapshots:
        if not isinstance(snapshot, dict) or any(
            not isinstance(snapshot.get(key), str) or not snapshot[key].strip()
            for key in ("snapshot_id", "source_id")
        ):
            _fail("INVALID_SOURCE_BINDINGS", "Each snapshot must name snapshot_id and source_id")
        identity = snapshot["snapshot_id"]
        if identity in result:
            _fail(
                "DUPLICATE_SNAPSHOT_ID", "Snapshot identity mapping must be unambiguous", identity
            )
        result[identity] = snapshot["source_id"]
    return result


def _references(metadata, knowledge_root, source_snapshots, source_refs):
    refs = metadata["sources"]
    _unique(refs, "DUPLICATE_SOURCE_REF", "/sources")
    mapping = _source_mapping(knowledge_root, source_snapshots, bool(refs))
    if source_refs is not None:
        if not isinstance(source_refs, (list, tuple, set, frozenset)) or any(
            not isinstance(item, str) for item in source_refs
        ):
            _fail(
                "INVALID_SOURCE_BINDINGS", "source_refs must be a collection of fixed snapshot IDs"
            )
        allowed = set(source_refs)
    else:
        allowed = set(mapping)
    for ref in refs:
        if ref not in mapping or ref not in allowed:
            _fail(
                "UNKNOWN_SOURCE_REF", "Card source must resolve to an allowed fixed snapshot", ref
            )
    logical_sources = {mapping[ref] for ref in refs}
    contexts = [item["context_id"] for item in metadata["scope"]["contexts"]]
    _unique(contexts, "DUPLICATE_CONTEXT_ID", "/scope/contexts")
    _unique([claim["id"] for claim in metadata["claims"]], "DUPLICATE_CLAIM_ID", "/claims")
    for claim in metadata["claims"]:
        _unique(claim["source_ids"], "DUPLICATE_SOURCE_REF", claim["id"])
        for ref in claim["source_ids"]:
            if ref not in logical_sources:
                _fail(
                    "UNKNOWN_CLAIM_SOURCE",
                    "Claim logical source must belong to a selected Card snapshot",
                    ref,
                )
    for item in [*metadata["claims"], *metadata["relations"]]:
        _unique(item["context_ids"], "DUPLICATE_CONTEXT_REF", item.get("id", "/relations"))
        for ref in item["context_ids"]:
            if ref not in contexts:
                _fail(
                    "UNKNOWN_CONTEXT_REF",
                    "Context reference does not exist in this Card scope",
                    ref,
                )


def _claim_spans(metadata, body, anchors):
    lines = body.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    result = {}
    for claim in metadata["claims"]:
        ref = claim["text_ref"]
        if ref.startswith("#") and ref[1:] in anchors:
            span = dict(anchors[ref[1:]])
        else:
            match = re.fullmatch(r"lines:([1-9][0-9]*)-([1-9][0-9]*)", ref)
            if not match or not 1 <= int(match[1]) <= int(match[2]) <= len(lines):
                _fail(
                    "INVALID_TEXT_REF",
                    "Claim must reference an existing explicit anchor or body line range",
                    claim["id"],
                )
            span = {
                "start": offsets[int(match[1]) - 1],
                "end": offsets[int(match[2])],
                "anchor": None,
            }
        if not body[span["start"] : span["end"]].strip():
            _fail("EMPTY_CLAIM_SPAN", "A Claim must select nonempty body text", claim["id"])
        result[claim["id"]] = span
    return result


def parse_card(data: bytes, knowledge_root, *, source_snapshots=None, source_refs=None):
    """Parse exact bytes, preserving body text and half-open Unicode offsets.

    Card.sources selects fixed snapshot IDs. Claim.source_ids selects logical
    source IDs resolved only through those snapshots. The mapping is technical;
    verified capture bytes and genuine human confirmation remain caller duties.
    """
    metadata, body = _split(data)
    bundle = contracts.load_bundle(knowledge_root)
    errors = sorted(
        Draft202012Validator(bundle["card"]).iter_errors(metadata),
        key=lambda item: str(item.absolute_path),
    )
    if errors:
        first = errors[0]
        _fail(
            "CARD_SCHEMA_INVALID",
            first.message,
            "/" + "/".join(str(item) for item in first.absolute_path),
        )
    _references(metadata, knowledge_root, source_snapshots, source_refs)
    anchors, sections = _body_structure(body)
    required = bundle["profiles"]["profiles"][metadata["profile"]]["required_sections"]
    missing = [section for section in required if section not in sections]
    if missing:
        _fail(
            "PROFILE_SECTION_MISSING",
            "Missing Profile sections: " + ", ".join(missing),
            metadata["profile"],
        )
    spans = _claim_spans(metadata, body, anchors)
    return {
        "metadata": metadata,
        "body": body,
        "body_digest": receipts.digest_bytes(body.encode("utf-8")),
        "claim_spans": spans,
    }
