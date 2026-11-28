"""System evidence versions preserve authored card content and reference identity."""

import copy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml


_spec = importlib.util.spec_from_file_location(
    "code_reference_version_support", Path(__file__).parents[1] / "support/contracts.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
cards = _helper.module("cards_v3")
validation = _helper.module("validation")


def reference(**extra):
    return {"code_id": "code-example", "line_start": 2, "line_end": 3, **extra}


def card_bytes(refs=None, *, doc_extra=None, body=None):
    metadata = {
        "id": "card-example",
        "doc_ref": [{"doc_id": "doc-example", "line_start": 1, "line_end": 3, **(doc_extra or {})}],
        "code_ref": [reference()] if refs is None else refs,
        "tags": ["sample"],
        "lifecycle": "stable",
    }
    return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + "---\n" + (body or "# Example\n\nAn authored fact.\n")).encode("utf-8")


def parsed(refs=None, **kwargs):
    return cards.parse_card(card_bytes(refs, **kwargs), "knowledge/example.md")


def schema_errors(kind, ref):
    schema = json.loads((Path(__file__).parents[2]
                         / "runtime/governance/schemas/frontmatter.schema.json").read_bytes())
    return list(Draft202012Validator({"$ref": "#/$defs/" + kind + "_reference", "$defs": schema["$defs"]})
                .iter_errors(ref))


@pytest.mark.parametrize("version", [None, "range-v1:example", "future-range-v9:opaque"])
def test_code_ref_keeps_optional_system_version_without_claiming_its_protocol(version):
    ref = reference(**({"evidence_version": version} if version is not None else {}))
    result = parsed([ref])
    assert result["code_ref"] == [ref]
    assert not schema_errors("code", ref)


@pytest.mark.parametrize("version", ["", "   ", None, 1, True, [], {}])
def test_nontext_or_empty_code_evidence_version_is_invalid(version):
    ref = reference(evidence_version=version)
    with pytest.raises(validation.ContractError):
        parsed([ref])
    assert schema_errors("code", ref)


def test_document_ref_cannot_receive_a_code_evidence_version():
    with pytest.raises(validation.ContractError, match="INVALID_CARD_REFERENCE"):
        parsed(doc_extra={"evidence_version": "range-v1:example"})
    assert schema_errors("doc", {"doc_id": "doc-example", "line_start": 1, "line_end": 3,
                                 "evidence_version": "range-v1:example"})


def test_system_version_does_not_make_duplicate_reference_positions_distinct():
    with pytest.raises(validation.ContractError, match="DUPLICATE_CARD_REFERENCE"):
        parsed([reference(evidence_version="range-v1:old"), reference(evidence_version="range-v1:new")])


def test_reference_key_ignores_version_and_mapping_key_order_only():
    versions = _helper.module("code_reference_versions")
    ref = reference(selector={"kind": "macro", "name": "LIMIT"}, evidence_version="old")
    reordered = {key: copy.deepcopy(ref[key]) for key in reversed(ref)}
    reordered["evidence_version"] = "new"
    assert versions.reference_key(ref) == versions.reference_key(reordered)
    assert versions.reference_key(ref) != versions.reference_key({**ref, "line_end": 4})
    assert versions.reference_key(ref) != versions.reference_key({**ref, "code_id": "other-code"})


def test_stamp_card_changes_only_selected_versions_and_preserves_exact_body():
    versions = _helper.module("code_reference_versions")
    refs = [reference(), reference(line_start=5, line_end=6, evidence_version="keep-this-version")]
    original = parsed(refs, body="# 原文\r\n\r\nKeep  two spaces.\r\n```c\r\nreturn 3;\r\n```\r\n")
    before = copy.deepcopy(original)
    result = versions.stamp_card(original, {versions.reference_key(refs[0]): "range-v1:captured"})

    assert original == before
    assert result["body"] == original["body"]
    assert result["body_digest"] == original["body_digest"]
    assert result["code_ref"] == [{**refs[0], "evidence_version": "range-v1:captured"}, refs[1]]
    assert result["metadata"] == {**original["metadata"], "code_ref": result["code_ref"]}
    assert result["sha256"] != original["sha256"]
    assert result["id"] == original["id"] and result["path"] == original["path"]


def test_stamp_card_skips_fixed_history_and_unknown_reference_keys():
    versions = _helper.module("code_reference_versions")
    historical = reference(snapshot_id="snapshot-old", evidence_ref="historical-proof")
    original = parsed([historical])
    result = versions.stamp_card(original, {
        versions.reference_key(historical): "must-not-retarget-history",
        versions.reference_key(reference(line_start=9, line_end=9)): "unrelated",
    })
    assert result["raw"] == original["raw"]
    assert result["code_ref"] == [historical]


def test_stamp_card_is_byte_preserving_when_version_already_matches():
    versions = _helper.module("code_reference_versions")
    ref = reference(evidence_version="range-v1:same")
    original = parsed([ref])
    result = versions.stamp_card(original, {versions.reference_key(ref): ref["evidence_version"]})
    assert result["raw"] == original["raw"]


def test_stamp_card_validates_generated_version_values():
    versions = _helper.module("code_reference_versions")
    original = parsed()
    with pytest.raises(validation.ContractError, match="INVALID_CODE_EVIDENCE_VERSION"):
        versions.stamp_card(original, {versions.reference_key(original["code_ref"][0]): " "})


def test_legacy_source_only_card_requires_authored_update_before_stamping():
    versions = _helper.module("code_reference_versions")
    metadata = {"id": "legacy-card", "sources": [{
        "source_id": "code-example", "evidence_ref": "legacy-code",
        "locator": {"kind": "lines", "start": 2, "end": 3},
        "code_ref": {"kind": "function", "name": "example"},
    }]}
    raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n# Legacy\n\nKeep this fact.\n").encode()
    original = cards.parse_card(raw, "knowledge/legacy.md")
    with pytest.raises(validation.ContractError, match="CODE_EVIDENCE_REQUIRES_CARD_UPDATE"):
        versions.stamp_card(original, {versions.reference_key(original["code_ref"][0]): "range-v1:new"})
    assert original["raw"] == raw
