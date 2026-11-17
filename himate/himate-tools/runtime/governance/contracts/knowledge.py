"""Read-only checks for explicit legacy card declarations and body spans."""

from __future__ import annotations

import re

from .validation import ContractError, validate_id


def unfenced(body):
    """Hide fenced text without changing offsets used by legacy anchors."""
    result, fence = [], None
    for line in body.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            result.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
        elif fence:
            result.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
        else:
            result.append(line)
    return "".join(result)


def _records(value, field, identity, path):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ContractError("INVALID_LEGACY_DECLARATION", f"{field} must contain objects", path)
    values = [item.get(identity) for item in value]
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ContractError("INVALID_LEGACY_DECLARATION", f"{field} needs {identity}", path)
    if len(set(values)) != len(values):
        raise ContractError("DUPLICATE_ID", identity, path)
    return {item[identity]: item for item in value}


def _references(value, field, available, path):
    if (not isinstance(value, list) or any(not isinstance(item, str) for item in value)
            or len(set(value)) != len(value)):
        raise ContractError("INVALID_LEGACY_DECLARATION", f"{field} must contain unique references", path)
    if available is not None and not set(value).issubset(available):
        code = "UNKNOWN_EVIDENCE_REF" if field == "source_refs" else "UNKNOWN_CONTEXT_REF"
        raise ContractError(code, field, path)


def validate_legacy(metadata, body, path):
    """Check only declarations the author supplied; never add Claim semantics."""
    sources = _records(metadata.get("sources", []), "sources", "evidence_ref", path)
    for source in sources.values():
        validate_id(source.get("source_id"))
        if not isinstance(source.get("locator"), dict) or not source["locator"]:
            raise ContractError("INVALID_LEGACY_DECLARATION", "sources needs a locator", path)
        if "code_ref" in source:
            from .code_symbols import validate_code_ref

            validate_code_ref(source["code_ref"])
    # Mixed headers sometimes named old evidence implicitly. Keep those author
    # declarations readable without inventing names for their concise references.
    evidence = set(sources) if "sources" in metadata else None
    scope = metadata.get("scope", {})
    if not isinstance(scope, dict):
        raise ContractError("INVALID_LEGACY_DECLARATION", "scope must be an object", path)
    contexts = _records(scope.get("contexts", []), "contexts", "context_id", path)
    claims = _records(metadata.get("claims", []), "claims", "id", path)
    visible = unfenced(body)
    anchors = list(re.finditer(
        r"^[ \t]*<a id=[\"']([^\"']+)[\"']></a>[ \t]*(?:\r?\n|$)", visible, re.M))
    if len({anchor.group(1) for anchor in anchors}) != len(anchors):
        raise ContractError("DUPLICATE_ANCHOR", "Explicit anchor repeats", path)
    spans = {anchor.group(1): (
        anchor.end(), anchors[index + 1].start() if index + 1 < len(anchors) else len(body))
        for index, anchor in enumerate(anchors)}
    lines = body.splitlines(keepends=True)
    for claim in claims.values():
        validate_id(claim["id"])
        if "source_refs" in claim:
            if not claim["source_refs"]:
                raise ContractError("INVALID_CLAIM_SOURCES", claim["id"], path)
            _references(claim["source_refs"], "source_refs", evidence, path)
        if "context_ids" in claim:
            _references(claim["context_ids"], "context_ids", contexts, path)
        reference = claim.get("text_ref")
        if isinstance(reference, str) and reference.startswith("#") and reference[1:] in spans:
            start, end = spans[reference[1:]]
        elif isinstance(reference, str) and re.fullmatch(r"lines:\d+-\d+", reference):
            first, last = map(int, reference[6:].split("-"))
            if not 1 <= first <= last <= len(lines):
                raise ContractError("INVALID_CLAIM_SPAN", reference, path)
            start, end = len("".join(lines[:first - 1])), len("".join(lines[:last]))
        else:
            raise ContractError("INVALID_CLAIM_SPAN", reference, path)
        if not body[start:end].strip():
            raise ContractError("EMPTY_CLAIM_TEXT", reference, path)
    relations = metadata.get("relations", [])
    if not isinstance(relations, list) or any(not isinstance(item, dict) for item in relations):
        raise ContractError("INVALID_LEGACY_DECLARATION", "relations must contain objects", path)
    for relation in relations:
        if "context_ids" in relation:
            _references(relation["context_ids"], "context_ids", contexts, path)
