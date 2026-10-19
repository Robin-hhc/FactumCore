"""Technical card parsing; synthetic declarations never stand for human approval."""

import copy
import shutil
from pathlib import Path

import pytest
import yaml
from _shared import cards, receipts

ROOT = Path(__file__).resolve().parents[5]
KNOWLEDGE = ROOT / "aiot-wifi-knowledge"
SNAPSHOTS = [{"snapshot_id": "raw:snapshot-one", "source_id": "sample-document"}]


@pytest.fixture
def knowledge(tmp_path):
    target = tmp_path / "knowledge"
    shutil.copytree(KNOWLEDGE / "governance", target / "governance")
    return target


def metadata(profile="entity"):
    return {
        "schema_version": "1.0",
        "id": "sample-card",
        "profile": profile,
        "title": "Synthetic title",
        "summary": "Synthetic parser example, not a business conclusion.",
        "lifecycle": "draft",
        "review_mode": "manual_document",
        "owner": "fixture",
        "scope": {"applicability": "unknown", "contexts": []},
        "aliases": [],
        "sources": ["raw:snapshot-one"],
        "claims": [
            {
                "id": "claim-one",
                "text_ref": "#claim-one",
                "evidence_kind": "design",
                "source_ids": ["sample-document"],
                "context_ids": [],
                "usage": "guidance",
                "verification_requirements": [],
            }
        ],
        "relations": [],
    }


def body_for(profile="entity"):
    profiles = yaml.safe_load(
        (KNOWLEDGE / "governance/schemas/profiles.yaml").read_text(encoding="utf-8")
    )["profiles"]
    sections = profiles[profile]["required_sections"]
    return "\n".join(
        ['<a id="claim-one"></a>', "Synthetic claim. 中文。", ""]
        + [f"## {section}\nSynthetic supporting text.\n" for section in sections]
    )


def encode_card(meta=None, body=None, *, newline="\n"):
    meta = metadata() if meta is None else meta
    body = body_for(meta["profile"]) if body is None else body
    text = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + body
    return text.replace("\n", newline).encode("utf-8")


def parse(data, knowledge, **kwargs):
    return cards.parse_card(data, knowledge, source_snapshots=SNAPSHOTS, **kwargs)


def assert_error(code, data, knowledge, **kwargs):
    with pytest.raises(ValueError) as caught:
        parse(data, knowledge, **kwargs)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "profile", ["entity", "flow", "protocol", "rule", "command", "runbook", "glossary"]
)
def test_each_profile_parses_exact_body_and_character_span(knowledge, profile):
    meta = metadata(profile)
    body = body_for(profile)
    before = encode_card(meta, body)
    result = parse(before, knowledge)
    assert result["metadata"] == meta
    assert result["body"] == body
    assert result["body_digest"] == receipts.digest_bytes(body.encode("utf-8"))
    span = result["claim_spans"]["claim-one"]
    assert span["anchor"] == "claim-one"
    assert result["body"][span["start"] : span["end"]].startswith("Synthetic claim. 中文。")
    assert before == encode_card(meta, body)


def test_utf8_bom_crlf_preserve_original_body_characters(knowledge):
    data = b"\xef\xbb\xbf" + encode_card(newline="\r\n")
    result = parse(data, knowledge)
    assert "\r\n" in result["body"]
    span = result["claim_spans"]["claim-one"]
    assert result["body"][span["start"] : span["end"]].startswith("Synthetic claim.")


def test_anchor_span_stops_before_next_explicit_anchor(knowledge):
    body = body_for().replace(
        "Synthetic claim. 中文。\n",
        'Synthetic claim. 中文。\n<a id="unclaimed"></a>\nOther text.\n',
    )
    result = parse(encode_card(body=body), knowledge)
    span = result["claim_spans"]["claim-one"]
    assert result["body"][span["start"] : span["end"]] == "Synthetic claim. 中文。\n"


def test_line_reference_is_one_based_inclusive_and_unicode_offsets(knowledge):
    meta = metadata()
    meta["claims"][0]["text_ref"] = "lines:2-2"
    result = parse(encode_card(meta), knowledge)
    span = result["claim_spans"]["claim-one"]
    assert result["body"][span["start"] : span["end"]] == "Synthetic claim. 中文。\n"
    assert span["anchor"] is None


@pytest.mark.parametrize(
    "reference", ["lines:0-1", "lines:3-2", "lines:1-999", "http://example.invalid", "#missing"]
)
def test_invalid_or_dangling_text_references(knowledge, reference):
    meta = metadata()
    meta["claims"][0]["text_ref"] = reference
    assert_error("INVALID_TEXT_REF", encode_card(meta), knowledge)


def test_duplicate_anchor_and_empty_anchor_span_rejected(knowledge):
    assert_error(
        "DUPLICATE_ANCHOR", encode_card(body=body_for() + '\n<a id="claim-one"></a>\n'), knowledge
    )
    assert_error(
        "EMPTY_CLAIM_SPAN",
        encode_card(body=body_for().replace("Synthetic claim. 中文。\n", '<a id="next"></a>\n')),
        knowledge,
    )


def test_duplicate_claim_source_and_context_ids_rejected(knowledge):
    meta = metadata()
    meta["claims"].append(copy.deepcopy(meta["claims"][0]))
    assert_error("DUPLICATE_CLAIM_ID", encode_card(meta), knowledge)
    meta = metadata()
    meta["sources"].append(meta["sources"][0])
    assert_error("DUPLICATE_SOURCE_REF", encode_card(meta), knowledge)
    meta = metadata()
    context = {
        "context_id": "context-one",
        "target_id": None,
        "chip": None,
        "side": None,
        "build_profile": None,
        "features_all": [],
        "features_none": [],
        "protocol_versions": [],
        "revision_policy": "not_applicable",
    }
    meta["scope"]["contexts"] = [context, copy.deepcopy(context)]
    assert_error("DUPLICATE_CONTEXT_ID", encode_card(meta), knowledge)


def test_claim_context_relation_context_and_source_must_resolve(knowledge):
    meta = metadata()
    meta["claims"][0]["context_ids"] = ["missing"]
    assert_error("UNKNOWN_CONTEXT_REF", encode_card(meta), knowledge)
    meta = metadata()
    meta["relations"] = [
        {"type": "related_to", "target_card_id": "other", "context_ids": ["missing"]}
    ]
    assert_error("UNKNOWN_CONTEXT_REF", encode_card(meta), knowledge)
    meta = metadata()
    meta["claims"][0]["source_ids"] = ["raw:snapshot-one"]
    assert_error("UNKNOWN_CLAIM_SOURCE", encode_card(meta), knowledge)
    meta = metadata()
    meta["sources"] = ["raw:missing"]
    assert_error("UNKNOWN_SOURCE_REF", encode_card(meta), knowledge)


def test_only_selected_card_snapshots_authorize_claim_logical_sources(knowledge):
    snapshots = SNAPSHOTS + [{"snapshot_id": "raw:snapshot-two", "source_id": "other-document"}]
    meta = metadata()
    meta["claims"][0]["source_ids"] = ["other-document"]
    with pytest.raises(ValueError) as caught:
        cards.parse_card(encode_card(meta), knowledge, source_snapshots=snapshots)
    assert caught.value.code == "UNKNOWN_CLAIM_SOURCE"


def test_snapshot_allowlist_and_unresolved_bindings(knowledge):
    assert_error("UNKNOWN_SOURCE_REF", encode_card(), knowledge, source_refs={"raw:other"})
    with pytest.raises(ValueError) as caught:
        cards.parse_card(encode_card(), knowledge)
    assert caught.value.code == "SOURCE_BINDING_REQUIRED"
    lock = {"schema_version": "1.0", "resources": [], "snapshots": SNAPSHOTS}
    (knowledge / "governance/sources.lock.yaml").write_text(yaml.safe_dump(lock), encoding="utf-8")
    result = cards.parse_card(encode_card(), knowledge)
    assert result["metadata"]["sources"] == ["raw:snapshot-one"]


def test_ambiguous_snapshot_identity_rejected(knowledge):
    snapshots = SNAPSHOTS + [{"snapshot_id": "raw:snapshot-one", "source_id": "other-document"}]
    with pytest.raises(ValueError) as caught:
        cards.parse_card(encode_card(), knowledge, source_snapshots=snapshots)
    assert caught.value.code == "DUPLICATE_SNAPSHOT_ID"


def test_profiles_are_structure_only_and_fenced_examples_do_not_supply_sections(knowledge):
    body = body_for().replace("## 职责\nSynthetic supporting text.\n", "```md\n## 职责\n```\n")
    assert_error("PROFILE_SECTION_MISSING", encode_card(body=body), knowledge)
    # The parser deliberately does not judge whether text under a section is true.
    result = parse(
        encode_card(body=body_for().replace("Synthetic supporting text.", "unknown")), knowledge
    )
    assert "unknown" in result["body"]


def test_fenced_anchor_example_does_not_resolve_claim(knowledge):
    body = body_for().replace('<a id="claim-one"></a>', '```html\n<a id="claim-one"></a>\n```')
    assert_error("INVALID_TEXT_REF", encode_card(body=body), knowledge)


def test_html_comment_examples_cannot_supply_anchors_or_profile_sections(knowledge):
    body = body_for().replace('<a id="claim-one"></a>', '<!--\n<a id="claim-one"></a>\n-->')
    assert_error("INVALID_TEXT_REF", encode_card(body=body), knowledge)
    body = body_for().replace("## 职责\n", "<!--\n## 职责\n-->\n")
    assert_error("PROFILE_SECTION_MISSING", encode_card(body=body), knowledge)


@pytest.mark.parametrize(
    "data",
    [b"not-frontmatter", b"---\n[not-an-object]\n---\nx", b"\xff", b"---\nid: a\nid: b\n---\nx"],
)
def test_malformed_utf8_yaml_frontmatter_rejected(knowledge, data):
    with pytest.raises(ValueError):
        parse(data, knowledge)


def test_input_must_be_bytes_and_source_ids_are_not_paths(knowledge):
    with pytest.raises(ValueError):
        parse("filename.md", knowledge)
    data = encode_card()
    result = cards.parse_card(data, knowledge, source_snapshots=SNAPSHOTS)
    assert result["metadata"]["sources"] == ["raw:snapshot-one"]


@pytest.mark.parametrize(
    "profile", ["entity", "flow", "protocol", "rule", "command", "runbook", "glossary"]
)
def test_checked_in_templates_render_to_parseable_synthetic_cards(knowledge, profile):
    template = (KNOWLEDGE / "governance/templates" / f"{profile}.md").read_text(encoding="utf-8")
    values = {
        "card_id": "sample-card",
        "title": "Synthetic parser example",
        "owner": "fixture",
        "summary": "Synthetic template rendering",
        "snapshot_id": "raw:snapshot-one",
        "source_id": "sample-document",
        "claim_id": "claim-one",
        "claim_text": "Synthetic text.",
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    result = parse(template.encode("utf-8"), knowledge)
    assert result["metadata"]["profile"] == profile
    assert "{{" not in template
