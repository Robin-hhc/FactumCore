"""Reference observations and publication bindings around the pure resolver."""

from __future__ import annotations

import re

from . import code_evidence, source_resources
from .code_reference_versions import reference_key, stamp_card
from .validation import ContractError


CHECK = ".build/code-evidence-check.json"


def body_location_reviews(root, catalog, cards, states):
    """Guard finite, adjacent code-location syntax; this is not prose understanding.

    A current reference's content may be unchanged while its repeated body line
    locator is stale. Keep that observation relocated, but require author review.
    Registered snapshot refs do not appear in the current-source observations.
    """
    from . import ingest

    number = r"[1-9]\d*(?:\s*[-–—~～至到]\s*[Ll]?[1-9]\d*)?"
    explicit = (r"第\s*" + number + r"\s*行|(?i:lines?)\b\s*" + number
                + r"|(?:#|:)?[Ll]\s*" + number)
    gap = r"[ \t`*_()\[\]（）]*"
    result, paths, patterns = {}, {}, {}
    for card in cards:
        lines = [(number, line.replace("\\", "/")) for number, line in enumerate(card["body"].splitlines(), 1)]
        for item in states.get(card["id"], []):
            if item["status"] != "relocated":
                continue
            identity = item["source_id"]
            if identity not in paths:
                source = catalog.get_file(identity)
                paths[identity] = {source["path"].replace("\\", "/"),
                                   str(ingest.source_path(root, source)).replace("\\", "/")}
            reference = item["reference"]
            anchors = {identity, *paths[identity]}
            anchors.update(value for value in (reference.get("symbol"),
                           reference.get("selector", {}).get("name")) if value)
            compiled = []
            for anchor in sorted(anchors):
                colon_location = anchor == identity or anchor in paths[identity]
                key = (anchor, colon_location)
                if key not in patterns:
                    token = r"(?<![A-Za-z0-9_/-])" + re.escape(anchor) + r"(?![A-Za-z0-9_/-])"
                    syntax = explicit + (r"|:\s*" + number if colon_location else "")
                    # Keep connectors finite: punctuation/Markdown, or this explicit English phrase.
                    patterns[key] = re.compile(token + gap + r"(?:function\s+is\s+at\s+)?(?P<locator>" + syntax + ")")
                compiled.append((anchor, patterns[key]))
            for line_number, normalized in lines:
                for anchor, pattern in compiled:
                    match = pattern.search(normalized)
                    if match:
                        result.setdefault(card["id"], []).append({
                            "source_id": identity, "body_line": line_number, "anchor": anchor,
                            "locator": match.group("locator"), "reason": "explicit_body_code_location",
                            "old_range": {name: reference[name] for name in ("line_start", "line_end")},
                        })
                        break
    return result


def historical(reference, registry):
    """Only an owned, registered snapshot establishes immutable semantics."""
    return any(item["snapshot_id"] == reference.get("snapshot_id")
               and item["source_id"] == reference["code_id"]
               for item in registry.get("snapshots", []))


def observe(root, catalog, cards, *, data=None, only_source=None):
    """Read each current source once and report every ordinary reference."""
    from . import ingest
    sources = {row["id"]: row for row in catalog.list_files(kind="code")}
    contents = dict(data or {})
    decoded, caches, result = {}, {}, {}
    reference_context = {"formal": True, "loaded": {}, "legacy": {}, "data": {}, "descriptors": {}}
    for card in cards:
        observations = []
        for reference in card["code_ref"]:
            if historical(reference, catalog.registry):
                continue
            identity = reference["code_id"]
            if only_source is not None and identity != only_source:
                continue
            source = sources.get(identity)
            if source is None:
                raise ContractError("UNKNOWN_SOURCE_ID", identity)
            if identity not in contents:
                try:
                    contents[identity] = ingest.source_path(root, source).read_bytes()
                except FileNotFoundError:
                    contents[identity] = None
            content = contents[identity]
            if reference.get("snapshot_id"):
                resolved = {"status": "unresolved", "reason": "The snapshot label is not registered for this source"}
            elif content is None:
                resolved = {"status": "unresolved"}
            else:
                if identity not in decoded:
                    decoded[identity] = source_resources.extract_code_text(content, ingest.code_extractor(source))[0]
                resolved = code_evidence.resolve(
                    decoded[identity], reference["line_start"], reference["line_end"],
                    reference.get("evidence_version"), cache=caches.setdefault(identity, {}))
            proposed = dict(reference)
            if resolved.get("line_start") is not None:
                proposed.update(line_start=resolved["line_start"], line_end=resolved["line_end"])
            # The resolver already proves a plain line range exists and matches.
            # Only selectors need the extra identity check and one shared parser cache.
            if resolved["status"] in {"fresh", "relocated"} and (reference.get("symbol") or reference.get("selector")):
                try:
                    ingest._reference_check(root, source, proposed, content, extractor=ingest.code_extractor(source),
                                            context=reference_context)
                except (ValueError, ContractError) as error:
                    resolved = {"status": "unresolved", "reason": str(error)}
            observations.append({"source_id": identity, "reference": reference,
                                 "proposed_reference": proposed, **resolved})
        result[card["id"]] = observations
    return result, contents


def record(context, source, reference, data):
    """Capture bytes actually checked; version tokens supplied by authors are ignored."""
    from . import ingest
    if reference.get("snapshot_id"):
        raise ContractError("CODE_EVIDENCE_REQUIRES_CARD_UPDATE",
                            "Replace an unregistered snapshot label with a current reference or a valid historical snapshot")
    identity = source["source_id"]
    captures = context.setdefault("code_capture", {})
    if identity not in captures:
        captures[identity] = (data, source_resources.extract_code_text(data, ingest.code_extractor(source))[0], {})
    previous, text, cache = captures[identity]
    if previous != data:
        raise ContractError("CODE_EVIDENCE_CHANGED", "One check cannot confirm multiple current versions of the same code source")
    version = code_evidence.capture(text, reference["line_start"], reference["line_end"], cache=cache)
    context.setdefault("code_versions", {})[reference_key(reference)] = version
    if identity not in context.setdefault("code_inputs", {}):
        context["code_inputs"][identity] = {"sha256": ingest.sha(data)}


def receipt(task_bytes, drafts, context):
    from . import ingest
    return {"task_sha256": ingest.sha(task_bytes or b""),
            "drafts": sorted((card["id"], ingest.sha(card["raw"])) for card in drafts),
            "versions": context.get("code_versions", {}), "sources": context.get("code_inputs", {})}


def verify(root, catalog, checked, task_bytes, drafts, *, reviewed_cards=None):
    """Do not stamp a different source version between independent check and publish."""
    from . import ingest
    signature = sorted([card["id"], ingest.sha(card["raw"])] for card in drafts)
    if (checked.get("task_sha256") != ingest.sha(task_bytes or b"")
            or checked.get("drafts") != signature):
        raise ContractError("CODE_EVIDENCE_NOT_CHECKED", "Check the current task and candidates again")
    references = [reference for card in (reviewed_cards if reviewed_cards is not None else drafts)
                  for reference in card["code_ref"] if not historical(reference, catalog.registry)]
    expected_keys = {reference_key(reference) for reference in references}
    if (set(checked.get("versions", {})) != expected_keys
            or set(checked.get("sources", {})) != {reference["code_id"] for reference in references}):
        raise ContractError("CODE_EVIDENCE_COVERAGE", "The check must cover every current code reference being confirmed")
    contents = {}
    for identity, expected in checked.get("sources", {}).items():
        source = catalog.get_file(identity)
        if source is None:
            raise ContractError("CODE_EVIDENCE_CHANGED", identity)
        try:
            current = ingest.source_path(root, source).read_bytes()
        except FileNotFoundError as error:
            raise ContractError("CODE_EVIDENCE_CHANGED", identity) from error
        if ingest.sha(current) != expected.get("sha256"):
            raise ContractError("CODE_EVIDENCE_CHANGED", "Code changed after its actual reference check", source["path"])
        contents[identity] = current
    context = {}
    for reference in references:
        record(context, catalog.get_file(reference["code_id"]), reference, contents[reference["code_id"]])
    if context.get("code_versions", {}) != checked.get("versions", {}):
        raise ContractError("CODE_EVIDENCE_COVERAGE", "A supplied evidence version differs from the actual checked fragment")
    return checked.get("versions", {})


def stamp(cards, versions):
    return [stamp_card(card, versions) for card in cards]
