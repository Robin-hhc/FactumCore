"""Parse complete cards and references without inventing author declarations."""

from __future__ import annotations

import copy
import re

from .knowledge import unfenced, validate_legacy
from .validation import ContractError, canonical_bytes, load_yaml, sha256_bytes, validate_id, validate_shape


CARD_FIELDS = frozenset({"id", "doc_ref", "code_ref", "tags", "lifecycle"})
LEGACY_FIELDS = frozenset({
    "schema_version", "profile", "title", "summary", "review_mode", "owner", "scope",
    "aliases", "sources", "claims", "relations", "replacement", "deprecation_reason", "search_terms",
})


def _range(item, first, last, path):
    present = first in item or last in item
    if present and (type(item.get(first)) is not int or type(item.get(last)) is not int
                    or not 1 <= item[first] <= item[last]):
        raise ContractError("INVALID_REFERENCE_RANGE", f"Use positive {first}/{last}", path)
    return present


def _document_locator(locator, path):
    if not isinstance(locator, dict):
        raise ContractError("INVALID_SOURCE_LOCATOR", "Expected a native document locator", path)
    kind = locator.get("kind")
    if kind == "table_row":
        if (set(locator) - {"kind", "table", "row"}
                or any(type(locator.get(field)) is not int or locator[field] < 1 for field in ("table", "row"))):
            raise ContractError("INVALID_SOURCE_LOCATOR", "Use positive native table/row addresses", path)
        return
    if kind not in ("page", "pages", "paragraph", "paragraphs"):
        raise ContractError("INVALID_SOURCE_LOCATOR", "Use native pages, paragraphs or a table row", path)
    field = "page" if kind in ("page", "pages") else "paragraph"
    if set(locator) - {"kind", field, "start", "end", "number", "id"}:
        raise ContractError("INVALID_SOURCE_LOCATOR", "Unknown native document address fields", path)
    first = locator.get(field, locator.get("start", locator.get("number", locator.get("id"))))
    last = locator.get("end", first)
    if type(first) is not int or type(last) is not int or not 1 <= first <= last:
        raise ContractError("INVALID_SOURCE_LOCATOR", "Use a positive native document address range", path)


def _references(items, kind, path):
    if not isinstance(items, list) or (kind == "doc" and not items):
        raise ContractError("INVALID_CARD_REFERENCES", f"{kind}_ref must be a list", path)
    fields = {kind + "_id", "line_start", "line_end", "snapshot_id", "evidence_ref"}
    fields.update({"page_start", "page_end", "section", "locator"} if kind == "doc" else {"symbol", "selector"})
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("INVALID_CARD_REFERENCE", "Expected a reference object", path)
        if set(item) - fields:
            raise ContractError("INVALID_CARD_REFERENCE", "Unknown reference fields", path)
        validate_id(item.get(kind + "_id"))
        lines = _range(item, "line_start", "line_end", path)
        pages = _range(item, "page_start", "page_end", path)
        section = item.get("section")
        if section is not None and (not isinstance(section, str) or not section.strip()):
            raise ContractError("INVALID_REFERENCE_SECTION", "Section must be nonempty text", path)
        if "locator" in item:
            _document_locator(item["locator"], path)
        if kind == "code" and not lines:
            raise ContractError("CODE_RANGE_REQUIRED", "Code references need line_start/line_end", path)
        if kind == "doc" and not (lines or pages or section or "locator" in item):
            raise ContractError("DOC_LOCATOR_REQUIRED", "Use lines, pages, a section or a native document locator", path)
        for field in ("symbol", "snapshot_id", "evidence_ref"):
            if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                code = "INVALID_CODE_SYMBOL" if field == "symbol" else "INVALID_CARD_REFERENCE"
                raise ContractError(code, f"{field} must be nonempty text", path)
        if "selector" in item:
            from .code_symbols import validate_code_ref

            validate_code_ref(item["selector"])
        key = canonical_bytes(item)
        if key in seen:
            raise ContractError("DUPLICATE_CARD_REFERENCE", item[kind + "_id"], path)
        seen.add(key)
        result.append(copy.deepcopy(item))
    return result


def _legacy_reference(source, kind):
    value = {kind + "_id": source["source_id"]}
    locator = source["locator"]
    value["locator"] = copy.deepcopy(locator)
    if locator.get("kind") in {"lines", "pages"}:
        stem = "line" if locator["kind"] == "lines" else "page"
        value.update({stem + "_start": locator.get("start"), stem + "_end": locator.get("end")})
    elif locator.get("section"):
        value["section"] = locator["section"]
    if source.get("code_ref"):
        value["symbol"] = source["code_ref"]["name"]
        value["selector"] = copy.deepcopy(source["code_ref"])
    for key in ("evidence_ref", "snapshot_id"):
        if key in source:
            value[key] = source[key]
    return value


def parse_card(data, path, rules=None, source_lookup=None, *, concise_only=False):
    """Return exact declarations plus objective card data and normalized references.

    P4 passes concise_only for new candidates. Formal reads may retain known
    legacy fields; that compatibility does not create missing Claim semantics.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        text = data.decode("utf-8-sig")
    except (UnicodeError, AttributeError) as error:
        raise ContractError("INVALID_CARD_ENCODING", str(error), path) from error
    if "\x00" in text:
        raise ContractError("NUL_INPUT", "NUL is invalid in a card", path)
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if match is None:
        raise ContractError("FRONTMATTER_REQUIRED", "Expected YAML frontmatter", path)
    metadata = load_yaml(match.group(1))
    if not isinstance(metadata, dict):
        raise ContractError("INVALID_FRONTMATTER", "Expected a mapping", path)
    validate_id(metadata.get("id"))
    unknown = set(metadata) - CARD_FIELDS - LEGACY_FIELDS
    if unknown:
        raise ContractError("INVALID_CARD_FIELDS", "Unknown card fields: " + ", ".join(sorted(unknown)), path)
    legacy = (bool(set(metadata) - CARD_FIELDS)
              or (not concise_only and metadata.get("lifecycle") == "draft"))
    if concise_only and legacy:
        raise ContractError("INVALID_CARD_FIELDS", "New cards support only id/doc_ref/code_ref/tags/lifecycle", path)
    if "tags" in metadata:
        tags = metadata["tags"]
        if (not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags)
                or (not legacy and (any(not tag.strip() for tag in tags) or len(set(tags)) != len(tags)))):
            raise ContractError("INVALID_CARD_TAGS", "Use distinct nonempty string tags", path)
    if "lifecycle" in metadata and metadata["lifecycle"] not in (
            ("draft", "stable", "deprecated") if legacy else ("stable", "deprecated")):
        raise ContractError("INVALID_CARD_LIFECYCLE", "Use stable or deprecated for new cards", path)
    body = text[match.end():]
    headings = re.findall(r"^ {0,3}#[ \t]+(.+?)[ \t]*$", unfenced(body), re.M)
    title = re.sub(r"[ \t]+#+[ \t]*$", "", headings[0]).strip() if headings else ""
    if not title:
        title = metadata.get("title", "") if legacy else ""
    if not isinstance(title, str) or not title.strip():
        raise ContractError("CARD_TITLE_REQUIRED", "Card body needs an H1 title", path)
    if legacy:
        validate_legacy(metadata, body, path)
    if "doc_ref" in metadata or "code_ref" in metadata:
        if "doc_ref" not in metadata or "code_ref" not in metadata:
            raise ContractError("CARD_REFERENCES_REQUIRED", "Use doc_ref and code_ref arrays", path)
        docs = _references(metadata["doc_ref"], "doc", path)
        codes = _references(metadata["code_ref"], "code", path)
        if "sources" in metadata:
            declared = {item["source_id"] for item in metadata["sources"]}
            referenced = {item["doc_id"] for item in docs} | {item["code_id"] for item in codes}
            if declared != referenced:
                raise ContractError("SOURCE_REFERENCE_MISMATCH", "sources must agree with doc_ref/code_ref", path)
    elif legacy and metadata.get("sources"):
        docs, codes = [], []
        source_lookup = source_lookup or {}
        for source in metadata["sources"]:
            source_info = source_lookup.get(source["source_id"], {})
            kind = "code" if source.get("code_ref") or source_info.get("kind") == "code" else "doc"
            (codes if kind == "code" else docs).append(_legacy_reference(source, kind))
    else:
        raise ContractError("CARD_REFERENCES_REQUIRED", "Use doc_ref and code_ref arrays", path)
    if rules:
        validate_shape("card", metadata, rules)
    return {
        "id": metadata["id"], "title": title, "path": str(path), "metadata": metadata,
        "body": body, "raw": data, "sha256": sha256_bytes(data),
        "body_digest": sha256_bytes(body.encode("utf-8")),
        "doc_ref": docs, "code_ref": codes, "legacy": legacy,
    }
