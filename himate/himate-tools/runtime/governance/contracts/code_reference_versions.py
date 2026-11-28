"""Stamp checked code evidence versions without altering authored card content."""

from __future__ import annotations

import copy

import yaml

from .cards_v3 import parse_card
from .validation import ContractError, canonical_bytes


def reference_key(reference):
    """Identify one declared reference independently of its system version."""
    return canonical_bytes({key: value for key, value in reference.items()
                            if key != "evidence_version"}).decode("utf-8")


def stamp_card(card, versions):
    """Return a parsed card with only selected current-reference versions changed.

    Keys come from the exact references that a check actually read. Missing keys
    leave other evidence untouched; fixed historical snapshots are never rebound.
    No-op updates retain the original bytes, and updates retain the exact body.
    """
    metadata = copy.deepcopy(card["metadata"])
    if "code_ref" not in metadata:
        if any(not reference.get("snapshot_id") and reference_key(reference) in versions
               for reference in card["code_ref"]):
            raise ContractError("CODE_EVIDENCE_REQUIRES_CARD_UPDATE",
                                "Rewrite legacy source declarations before storing current evidence versions",
                                card["path"])
        return card
    changed = False
    for reference in metadata["code_ref"]:
        key = reference_key(reference)
        if reference.get("snapshot_id") or key not in versions:
            continue
        version = versions[key]
        if not isinstance(version, str) or not version.strip():
            raise ContractError("INVALID_CODE_EVIDENCE_VERSION", "evidence_version must be nonempty text", card["path"])
        if reference.get("evidence_version") != version:
            reference["evidence_version"] = version
            changed = True
    if not changed:
        return card
    header = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
    raw = ("---\n" + header + "---\n" + card["body"]).encode("utf-8")
    return parse_card(raw, card["path"])
