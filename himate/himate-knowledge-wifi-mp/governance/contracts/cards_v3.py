"""Decode the concise card references, retaining existing knowledge semantics.

Only card data is read here. Legacy cards are decoded without rewriting their
frontmatter, identifiers, adopted snapshots or claim text.
"""

from __future__ import annotations

import copy
import hashlib
import re

from .knowledge import decode_card
from .validation import ContractError, load_yaml, validate_id, validate_shape


def _range(item, first, last, path):
    present = first in item or last in item
    if present and (type(item.get(first)) is not int or type(item.get(last)) is not int
                    or not 1 <= item[first] <= item[last]):
        raise ContractError("INVALID_REFERENCE_RANGE", f"Use positive {first}/{last}", path)
    return present


def _references(items, kind, path):
    if not isinstance(items, list) or (kind == "doc" and not items):
        raise ContractError("INVALID_CARD_REFERENCES", f"{kind}_ref must be a list", path)
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("INVALID_CARD_REFERENCE", "Expected a reference object", path)
        validate_id(item.get(kind + "_id"))
        lines = _range(item, "line_start", "line_end", path)
        pages = _range(item, "page_start", "page_end", path)
        section = item.get("section")
        if section is not None and (not isinstance(section, str) or not section.strip()):
            raise ContractError("INVALID_REFERENCE_SECTION", "Section must be nonempty text", path)
        if kind == "code" and not lines:
            raise ContractError("CODE_RANGE_REQUIRED", "Code references need line_start/line_end", path)
        if kind == "doc" and not (lines or pages or section):
            raise ContractError("DOC_LOCATOR_REQUIRED", "Use lines, pages or a section", path)
        if "symbol" in item and (not isinstance(item["symbol"], str) or not item["symbol"].strip()):
            raise ContractError("INVALID_CODE_SYMBOL", "Symbol must be nonempty text", path)
        key = repr(sorted(item.items()))
        if key in seen:
            raise ContractError("DUPLICATE_CARD_REFERENCE", item[kind + "_id"], path)
        seen.add(key)
        result.append(copy.deepcopy(item))
    return result


def _locator(reference):
    if "line_start" in reference:
        return {"kind": "lines", "start": reference["line_start"], "end": reference["line_end"]}
    if "page_start" in reference:
        return {"kind": "pages", "start": reference["page_start"], "end": reference["page_end"]}
    return {"kind": "section", "section": reference["section"]}


def _legacy_reference(source, kind):
    value = {kind + "_id": source["source_id"]}
    locator = source.get("locator", {})
    if locator.get("kind") in {"lines", "pages"}:
        stem = "line" if locator["kind"] == "lines" else "page"
        value.update({stem + "_start": locator.get("start"), stem + "_end": locator.get("end")})
    elif locator.get("section"):
        value["section"] = locator["section"]
    else:
        value["locator"] = copy.deepcopy(locator)
    if source.get("code_ref", {}).get("name"):
        value["symbol"] = source["code_ref"]["name"]
        value["selector"] = copy.deepcopy(source["code_ref"])
    for key in ("evidence_ref", "snapshot_id"):
        if key in source:
            value[key] = source[key]
    return value


def parse_card(data, path, rules=None, source_lookup=None):
    """Return one normalized card; rules, when supplied, also check its schema."""
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
    if rules:
        validate_shape("card", metadata, rules)
    source_lookup = source_lookup or {}
    legacy = "doc_ref" not in metadata and "code_ref" not in metadata and "sources" in metadata
    if legacy:
        card = decode_card(data, path, rules or {})
        docs, codes = [], []
        for source in metadata["sources"]:
            source_info = source_lookup.get(source["source_id"], {})
            kind = "code" if source.get("code_ref") or source_info.get("kind") == "code" else "doc"
            (codes if kind == "code" else docs).append(_legacy_reference(source, kind))
    else:
        if "doc_ref" not in metadata or "code_ref" not in metadata:
            raise ContractError("CARD_REFERENCES_REQUIRED", "Use doc_ref and code_ref arrays", path)
        docs = _references(metadata["doc_ref"], "doc", path)
        codes = _references(metadata["code_ref"], "code", path)
        body = text[match.end():]
        title = next(iter(re.findall(r"^#\s+(.+?)\s*$", body, re.M)), metadata["id"])
        normalized = copy.deepcopy(metadata)
        normalized.setdefault("title", title)
        normalized.setdefault("summary", next((line.strip() for line in body.splitlines()
                                                if line.strip() and not line.startswith("#")), title))
        for key, default in {
            "schema_version": "3.0", "profile": "rule", "lifecycle": "stable",
            "review_mode": "code_gate" if codes else "manual_document", "owner": "unknown",
            "scope": {"applicability": "unknown", "contexts": []}, "aliases": [], "relations": [],
        }.items():
            normalized.setdefault(key, default)
        sources = []
        for kind, references in (("doc", docs), ("code", codes)):
            for index, reference in enumerate(references):
                source = {"evidence_ref": reference.get("evidence_ref", f"{kind}-{index + 1}"),
                          "source_id": reference[kind + "_id"], "locator": _locator(reference)}
                if "snapshot_id" in reference:
                    source["snapshot_id"] = reference["snapshot_id"]
                if kind == "code" and reference.get("symbol"):
                    source["code_ref"] = {"kind": "function", "name": reference["symbol"]}
                sources.append(source)
        if "sources" in metadata:
            declared = {item.get("source_id") for item in metadata["sources"]}
            indexed = {item["source_id"] for item in sources}
            if declared != indexed:
                raise ContractError("SOURCE_REFERENCE_MISMATCH",
                                    "Structured Claim sources must agree with doc_ref/code_ref", path)
        # Existing structured claims keep their evidence names when the author
        # retained them; concise cards receive a conservative guidance claim.
        normalized.setdefault("sources", sources)
        normalized.setdefault("claims", [{"id": "knowledge", "text_ref": f"lines:1-{max(1, len(body.splitlines()))}",
                                           "evidence_kind": "design", "usage": "guidance",
                                           "source_refs": [source["evidence_ref"] for source in normalized["sources"]],
                                           "context_ids": [], "verification_requirements": []}])
        import yaml

        decoded = ("---\n" + yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False)
                   + "---\n" + body).encode("utf-8")
        card = decode_card(decoded, path, rules or {})
        # The adapter only normalizes its in-memory view. Published bytes and
        # content hashes always describe the author's original complete card.
        card.update(raw=data, sha256=hashlib.sha256(data).hexdigest())
    card.update(id=metadata["id"], title=card["metadata"]["title"], path=str(path),
                doc_ref=docs, code_ref=codes, legacy=legacy)
    return card
