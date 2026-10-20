"""Card/Claim parsing, complete relationships and conservative scope matching."""

from __future__ import annotations
import re
from .validation import (
    ContractError,
    load_yaml,
    sha256_bytes,
    validate_id,
    validate_shape,
)


def _unfenced(body):
    result, fence = [], None
    for line in body.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            result.append(
                " " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")) :]
            )
        elif fence:
            result.append(
                " " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")) :]
            )
        else:
            result.append(line)
    return "".join(result)


def _unique(items, field):
    values = [item[field] if isinstance(item, dict) else item for item in items]
    if len(values) != len(set(values)):
        raise ContractError("DUPLICATE_ID", field)
    return set(values)


def parse_card(data, path, rules):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractError("INVALID_CARD_ENCODING", exc, path) from exc
    if "\x00" in text:
        raise ContractError("NUL_INPUT", "Invalid card text", path)
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        raise ContractError("FRONTMATTER_REQUIRED", "Expected YAML frontmatter", path)
    meta = load_yaml(match.group(1))
    validate_shape("card", meta, rules)
    body, visible = text[match.end() :], _unfenced(text[match.end() :])
    sections = set(re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", visible, re.M))
    missing = (
        set(rules["profiles"]["profiles"][meta["profile"]]["required_sections"])
        - sections
    )
    if missing:
        raise ContractError("MISSING_SECTIONS", ", ".join(sorted(missing)), path)
    validate_id(meta["id"])
    _unique(meta["claims"], "id")
    _unique(meta["scope"]["contexts"], "context_id")
    contexts = {c["context_id"]: c for c in meta["scope"]["contexts"]}
    if any(not _has_condition(c) for c in contexts.values()):
        raise ContractError(
            "EMPTY_CONTEXT", "A context must constrain a real dimension", path
        )
    if meta["scope"]["applicability"] == "constrained" and not contexts:
        raise ContractError(
            "EMPTY_SCOPE", "Constrained scope requires conditions", path
        )
    _unique(meta["sources"], "evidence_ref")
    sources = {s["evidence_ref"]: s for s in meta["sources"]}
    anchors = list(
        re.finditer(
            r"^[ \t]*<a id=[\"']([^\"']+)[\"']></a>[ \t]*(?:\r?\n|$)", visible, re.M
        )
    )
    if len({a.group(1) for a in anchors}) != len(anchors):
        raise ContractError("DUPLICATE_ANCHOR", "Explicit anchor repeats", path)
    spans = {
        a.group(1): (
            a.end(),
            anchors[i + 1].start() if i + 1 < len(anchors) else len(body),
        )
        for i, a in enumerate(anchors)
    }
    claims = []
    for claim in meta["claims"]:
        validate_id(claim["id"])
        if not claim["source_refs"] or len(claim["source_refs"]) != len(
            set(claim["source_refs"])
        ):
            raise ContractError("INVALID_CLAIM_SOURCES", claim["id"], path)
        if not set(claim["source_refs"]).issubset(sources):
            raise ContractError("UNKNOWN_EVIDENCE_REF", claim["id"], path)
        if not set(claim["context_ids"]).issubset(contexts):
            raise ContractError("UNKNOWN_CONTEXT_REF", claim["id"], path)
        ref = claim["text_ref"]
        if ref.startswith("#") and ref[1:] in spans:
            start, end = spans[ref[1:]]
        elif re.fullmatch(r"lines:\d+-\d+", ref):
            first, last = map(int, ref[6:].split("-"))
            lines = body.splitlines(keepends=True)
            if not 1 <= first <= last <= len(lines):
                raise ContractError("INVALID_CLAIM_SPAN", ref, path)
            start, end = len("".join(lines[: first - 1])), len("".join(lines[:last]))
        else:
            raise ContractError("INVALID_CLAIM_SPAN", ref, path)
        if not body[start:end].strip():
            raise ContractError("EMPTY_CLAIM_TEXT", ref, path)
        compiled = dict(claim)
        compiled.update(
            text=body[start:end],
            span={"start": start, "end": end},
            scope={
                "applicability": meta["scope"]["applicability"],
                "contexts": [contexts[c] for c in claim["context_ids"]],
            },
            source_records=[sources[s] for s in claim["source_refs"]],
        )
        if (
            compiled["scope"]["applicability"] == "constrained"
            and not compiled["scope"]["contexts"]
        ):
            raise ContractError("CLAIM_SCOPE_REQUIRED", claim["id"], path)
        claims.append(compiled)
    for relation in meta["relations"]:
        if not set(relation["context_ids"]).issubset(contexts):
            raise ContractError("UNKNOWN_CONTEXT_REF", "relation", path)
    return {
        "metadata": meta,
        "body": body,
        "raw": data,
        "path": str(path),
        "claims": claims,
        "sha256": sha256_bytes(data),
        "body_digest": sha256_bytes(body.encode("utf-8")),
    }


def validate_card(card, view=None, rules=None):
    if rules:
        validate_shape("card", card.get("metadata", card), rules)
        from .source_resources import read_source_lock, validate_source_ref

        source_lock = rules.get("source_lock")
        if source_lock is None:
            source_lock = read_source_lock(rules["knowledge_root"])
        for source in card.get("metadata", card)["sources"]:
            validate_source_ref(source, source_lock)
    if view is not None:
        validate_relations(view)
    return card


def validate_relations(view):
    values = list(view.values()) if isinstance(view, dict) else list(view)
    metadata = [c.get("metadata", c) for c in values]
    if len({c["id"] for c in metadata}) != len(metadata):
        raise ContractError("DUPLICATE_CARD_ID", "Card IDs must be domain-unique")
    by_id, edges = {c["id"]: c for c in metadata}, {}
    for card in metadata:
        edges[card["id"]] = []
        replacements = card.get("replacement") or []
        if isinstance(replacements, str):
            replacements = [replacements]
        for target_id in replacements:
            if target_id not in by_id:
                raise ContractError("DANGLING_RELATION", target_id)
            edges[card["id"]].append(target_id)
        for relation in card["relations"]:
            target = by_id.get(relation["target_card_id"])
            if target is None:
                raise ContractError("DANGLING_RELATION", relation["target_card_id"])
            if relation.get("target_claim_id") and relation["target_claim_id"] not in {
                c["id"] for c in target["claims"]
            }:
                raise ContractError(
                    "DANGLING_CLAIM_RELATION", relation["target_claim_id"]
                )
            if relation["type"] in ("requires", "replacement"):
                edges[card["id"]].append(target["id"])
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise ContractError("RELATION_CYCLE", node)
        if node in visited:
            return
        visiting.add(node)
        for other in edges[node]:
            visit(other)
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        visit(node)
    return view


def _has_condition(group):
    return any(
        group.get(key)
        for key in (
            "target_id",
            "chip",
            "side",
            "build_profile",
            "pairing_id",
            "revision",
            "features_all",
            "features_none",
            "protocol_versions",
        )
    )


def match_scope(claim, context, purpose="current"):
    if purpose == "current" and claim.get("usage") != "current":
        return False
    if purpose == "implementation" and claim.get("evidence_kind") not in (
        "implementation",
        "measurement",
    ):
        return False
    scope = claim.get("scope", {})
    mode = scope.get("applicability", "unknown")
    if mode == "unknown":
        return purpose in ("guidance", "historical")
    if mode == "universal":
        return True
    for group in scope.get("contexts", []):
        if not _has_condition(group):
            continue
        if any(
            group.get(k) is not None and context.get(k) != group[k]
            for k in ("target_id", "chip", "side", "build_profile", "pairing_id")
        ):
            continue
        features = set(context.get("features", []))
        if (
            not set(group.get("features_all", [])).issubset(features)
            or set(group.get("features_none", [])) & features
        ):
            continue
        if group.get("protocol_versions") and not set(
            group["protocol_versions"]
        ).issubset(context.get("protocol_versions", [])):
            continue
        if group.get("revision_policy") == "pinned" and (
            not group.get("revision") or context.get("revision") != group["revision"]
        ):
            continue
        return True
    return False
