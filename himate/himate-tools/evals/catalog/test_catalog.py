"""Public catalog behavior for the single-file ingest model."""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def test_bidirectional_references_and_processed_file_survive_rebuild(tmp_path):
    catalog_type = module("catalog").Catalog
    parse_card = module("cards_v3").parse_card
    root = tmp_path / "knowledge-root"
    (root / "governance").mkdir(parents=True)
    (root / "knowledge").mkdir()
    catalog = catalog_type(root)
    doc = catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
    other = catalog.register("raw", "docs-raw/other.md", source_id="doc-other")
    code = catalog.register("code", "src/wait.c", repo="wifi", source_id="code-wait")
    data = b"""---
id: wait-rule
doc_ref:
  - doc_id: doc-design
    line_start: 2
    line_end: 8
  - doc_id: doc-other
    section: Conditions
code_ref:
  - code_id: code-wait
    line_start: 10
    line_end: 20
    symbol: wait_reply
---
# Waiting rule

Wait for a reply under the stated conditions.
"""
    card_path = root / "knowledge" / "wait.md"
    card_path.write_bytes(data)
    catalog.refresh_cards([parse_card(data, "knowledge/wait.md")])
    catalog.mark_processed(doc["id"], "a" * 64)
    catalog.mark_processed(other["id"], "b" * 64)

    assert [row["id"] for row in catalog.cards_for(doc["id"])] == ["wait-rule"]
    assert {row["id"] for row in catalog.files_for("wait-rule")} == {
        "doc-design", "doc-other", "code-wait"
    }
    assert [row["id"] for row in catalog.list_files(kind="code", referenced=True)] == [code["id"]]

    catalog.close()
    (root / "artifacts" / "knowledge.sqlite").unlink()
    rebuilt = catalog_type(root)
    rebuilt.rebuild()
    assert rebuilt.get_file("doc-design")["processed_hash"] == "a" * 64
    assert rebuilt.get_file("doc-other")["processed_hash"] == "b" * 64
    assert [row["id"] for row in rebuilt.cards_for("code-wait")] == ["wait-rule"]
    rebuilt.close()


def test_replacing_one_card_refreshes_its_whole_reference_set(tmp_path):
    catalog_type, parse_card = module("catalog").Catalog, module("cards_v3").parse_card
    (tmp_path / "knowledge").mkdir()
    with catalog_type(tmp_path) as catalog:
        for identity in ("first", "second", "third"):
            catalog.register("raw", f"docs-raw/{identity}.md", source_id=identity)
        def card(references):
            import yaml
            data = ("---\n" + yaml.safe_dump({"id": "one", "doc_ref": [
                {"doc_id": identity, "section": "Rule"} for identity in references], "code_ref": []})
                    + "---\n# A rule\nKeep the valid requirements.\n").encode()
            return parse_card(data, "knowledge/one.md")
        catalog.refresh_cards([card(["first", "second"])])
        catalog.refresh_cards([card(["second", "third"])])
        assert catalog.cards_for("first") == []
        assert {row["id"] for row in catalog.files_for("one")} == {"second", "third"}
        catalog.remove_cards(["one"])
        catalog.remove_cards(["one"])
        assert catalog.cards_for("second") == []


def test_patrol_refreshes_a_replaced_card_identity_without_advancing_sources(tmp_path):
    catalog_type, library = module("catalog").Catalog, module("library")
    for directory in ("docs-raw", "knowledge", "governance"):
        (tmp_path / directory).mkdir()
    for name in ("a", "b"):
        (tmp_path / "docs-raw" / f"{name}.md").write_text(
            f"# {name}\n\nA documented requirement.\n", encoding="utf-8")
    hashes = {}
    with catalog_type(tmp_path) as catalog:
        for name in ("a", "b"):
            identity = f"doc-{name}"
            catalog.register("raw", f"docs-raw/{name}.md", source_id=identity)
            hashes[identity] = module("ingest").sha((tmp_path / "docs-raw" / f"{name}.md").read_bytes())
            catalog.mark_processed(identity, hashes[identity])

    def replace(identity, doc_id):
        (tmp_path / "knowledge/rule.md").write_text(
            f"---\nid: {identity}\ndoc_ref:\n- doc_id: {doc_id}\n"
            "  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Rule\nA requirement.\n",
            encoding="utf-8",
        )

    replace("former-rule", "doc-a")
    indexed, phase = library.patrol(tmp_path, "reindex", {})
    assert phase == "reindexed" and indexed["cards"] == 1
    registry_before = (tmp_path / "governance/sources.lock.yaml").read_bytes()

    # Another producer may publish a replacement identity at this same path;
    # after a pull, the local SQLite cache still contains the former card.
    replace("new-rule", "doc-b")
    planned, phase = library.patrol(tmp_path, "plan", {})
    assert phase == "needs_reindex", planned
    with catalog_type(tmp_path) as catalog:
        assert catalog.get_card("former-rule") is None
        assert catalog.cards_for("doc-a") == []
        assert [card["id"] for card in catalog.cards_for("doc-b")] == ["new-rule"]
        assert [source["id"] for source in catalog.files_for("new-rule")] == ["doc-b"]

    indexed, phase = library.patrol(tmp_path, "reindex", {})
    assert phase == "reindexed" and indexed["cards"] == 1
    completed, phase = library.patrol(tmp_path, "complete", {})
    assert phase == "completed" and completed["remaining"] == 0
    assert (tmp_path / "governance/sources.lock.yaml").read_bytes() == registry_before
    with catalog_type(tmp_path) as catalog:
        assert {identity: catalog.get_file(identity)["processed_hash"] for identity in hashes} == hashes
        assert [card["id"] for card in catalog.all_cards()] == ["new-rule"]
    assert not (tmp_path / ".build").exists()


@pytest.mark.parametrize("replace_known", [False, True], ids=["retained-card", "replaced-card"])
def test_patrol_refresh_still_rejects_duplicate_formal_identities(tmp_path, replace_known):
    catalog_type = module("catalog").Catalog
    (tmp_path / "knowledge").mkdir()
    with catalog_type(tmp_path) as catalog:
        catalog.register("raw", "docs-raw/spec.md", source_id="doc-spec")

    def content(identity):
        return (f"---\nid: {identity}\ndoc_ref:\n- doc_id: doc-spec\n"
                "  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Rule\nA requirement.\n")

    original = tmp_path / "knowledge/rule.md"
    original.write_text(content("old-rule"), encoding="utf-8")
    with catalog_type(tmp_path) as catalog:
        assert catalog.get_card("old-rule") is not None
    identity = "new-rule" if replace_known else "old-rule"
    if replace_known:
        original.write_text(content(identity), encoding="utf-8")
    (tmp_path / "knowledge/duplicate.md").write_text(content(identity), encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE_CARD_ID"):
        module("library").patrol(tmp_path, "plan", {})


def test_no_card_success_and_handled_deletion_are_distinct_from_unprocessed(tmp_path):
    catalog_type = module("catalog").Catalog
    with catalog_type(tmp_path) as catalog:
        plain = catalog.register("raw", "docs-raw/plain.md", source_id="plain")
        catalog.register("raw", "docs-raw/gone.md", source_id="gone")
        assert plain["processed"] is False
        catalog.mark_processed("plain", "a" * 64)
        catalog.mark_processed("gone", None, exists=False)
    with catalog_type(tmp_path) as catalog:
        assert catalog.get_file("plain")["processed"] is True
        assert catalog.get_file("gone")["processed_exists"] is False
        assert catalog.get_file("gone")["processed"] is True
        assert catalog.list_files(referenced=True) == []


def test_source_identity_is_stable_and_conflicts_are_reported(tmp_path):
    catalog_type = module("catalog").Catalog
    with catalog_type(tmp_path) as catalog:
        first = catalog.register("raw", "docs-raw/spec.md")
        assert catalog.register("doc", "docs-raw/spec.md")["id"] == first["id"]
        with pytest.raises(ValueError, match="SOURCE_ID_CONFLICT"):
            catalog.register("raw", "docs-raw/different.md", source_id=first["id"])
        with pytest.raises(ValueError, match="INVALID_SOURCE_PATH"):
            catalog.register("raw", "../outside.md")


def test_uncommitted_new_content_clears_older_source_commit(tmp_path):
    with module("catalog").Catalog(tmp_path) as catalog:
        source = catalog.register("raw", "docs-raw/design.md")
        catalog.mark_processed(source["id"], "a" * 64, source_commit="c" * 40)
        catalog.mark_processed(source["id"], "b" * 64)
        assert catalog.get_file(source["id"])["source_commit"] is None


def test_registry_restore_removes_files_absent_from_restored_registry(tmp_path):
    import yaml
    catalog_type = module("catalog").Catalog
    with catalog_type(tmp_path) as catalog:
        catalog.register("raw", "docs-raw/new.md", source_id="new")
    registry = tmp_path / "governance/sources.lock.yaml"
    registry.write_text(yaml.safe_dump({"schema_version": "2.0", "resources": [], "snapshots": []}))
    with catalog_type(tmp_path) as catalog:
        assert catalog.list_files() == []


def test_reference_kind_must_match_registered_file(tmp_path):
    with module("catalog").Catalog(tmp_path) as catalog:
        catalog.register("code", "src/wait.c", source_id="code-wait")
        card = module("cards_v3").parse_card(b"---\nid: rule\ndoc_ref:\n- doc_id: code-wait\n  section: Rule\ncode_ref: []\n---\n# Rule\nWait for a reply.\n", "knowledge/rule.md")
        with pytest.raises(ValueError, match="SOURCE_KIND_MISMATCH"):
            catalog.refresh_cards([card])


def test_batch_registration_keeps_order_identity_and_rebuild_facts(tmp_path):
    catalog_type = module("catalog").Catalog
    with catalog_type(tmp_path) as catalog:
        first = catalog.register("raw", "docs-raw/first.md", source_id="doc-first")
        rows = catalog.register_many([
            {"kind": "raw", "path": "docs-raw/first.md"},
            {"kind": "doc", "path": "docs-raw/second.md"},
            {"kind": "code", "path": "src/wait.c", "repo": "wifi", "source_id": "code-wait"},
            {"kind": "raw", "path": "docs-raw/second.md"},
        ])
        assert rows[0]["id"] == first["id"]
        assert rows[1]["id"] == rows[3]["id"]
        assert rows[2]["id"] == "code-wait"
        assert catalog.register("raw", "docs-raw/second.md")["id"] == rows[1]["id"]
        assert len(catalog.list_files()) == 3
        catalog.mark_processed(rows[1]["id"], "e" * 64)
    (tmp_path / "artifacts/knowledge.sqlite").unlink()
    with catalog_type(tmp_path) as catalog:
        assert len(catalog.list_files()) == 3
        assert catalog.get_file(rows[1]["id"])["processed_hash"] == "e" * 64


def test_invalid_batch_does_not_partially_register_sources(tmp_path):
    catalog_type = module("catalog").Catalog
    with catalog_type(tmp_path) as catalog:
        catalog.register("raw", "docs-raw/original.md", source_id="original")
        with pytest.raises(ValueError, match="SOURCE_ID_CONFLICT"):
            catalog.register_many([
                {"kind": "raw", "path": "docs-raw/new.md", "source_id": "new"},
                {"kind": "raw", "path": "docs-raw/wrong.md", "source_id": "original"},
            ])
        assert [row["id"] for row in catalog.list_files()] == ["original"]
    with catalog_type(tmp_path) as catalog:
        assert [row["id"] for row in catalog.list_files()] == ["original"]


def test_failed_catalog_initialization_releases_database_connection(tmp_path):
    import sqlite3
    catalog_type = module("catalog").Catalog
    connections = []
    class FailingCatalog(catalog_type):
        def refresh(self):
            connections.append(self.connection)
            self.connection.execute("UPDATE files SET path=path")
            raise OSError("Synthetic refresh error")
    try:
        with pytest.raises(OSError, match="refresh error"):
            FailingCatalog(tmp_path)
        with sqlite3.connect(tmp_path / "artifacts/knowledge.sqlite", timeout=0) as connection:
            connection.execute("BEGIN IMMEDIATE")
    finally:
        for connection in connections:
            connection.close()


@pytest.mark.parametrize("header,code", [
    ({"id": "c", "doc_ref": [], "code_ref": []}, "INVALID_CARD_REFERENCES"),
    ({"id": "c", "doc_ref": [{"doc_id": "d"}], "code_ref": []}, "DOC_LOCATOR_REQUIRED"),
    ({"id": "c", "doc_ref": [{"doc_id": "d", "line_start": 5, "line_end": 2}], "code_ref": []}, "INVALID_REFERENCE_RANGE"),
    ({"id": "c", "doc_ref": [{"doc_id": "d", "section": "Rule"}], "code_ref": [{"code_id": "code"}]}, "CODE_RANGE_REQUIRED"),
    ({"id": "c", "doc_ref": [{"doc_id": "d", "line_start": True, "line_end": 2}], "code_ref": []}, "INVALID_REFERENCE_RANGE"),
])
def test_invalid_reference_structure_is_rejected(header, code):
    import yaml
    raw = ("---\n" + yaml.safe_dump(header) + "---\n# Card\nSome knowledge.\n").encode()
    with pytest.raises(ValueError, match=code):
        module("cards_v3").parse_card(raw, "knowledge/card.md")


def test_legacy_rich_claims_and_original_bytes_are_preserved():
    import yaml
    metadata = {
        "schema_version": "2.0", "id": "legacy", "profile": "rule", "title": "Legacy",
        "summary": "A prior result", "lifecycle": "stable", "owner": "owner",
        "review_mode": "code_gate", "scope": {"applicability": "constrained", "contexts": [
            {"context_id": "host", "chip": "chip12", "side": "host", "features_all": ["timeout"]}]},
        "aliases": [], "sources": [
            {"evidence_ref": "design", "source_id": "doc", "snapshot_id": "old-doc", "locator": {"kind": "lines", "start": 2, "end": 7}},
            {"evidence_ref": "impl", "source_id": "code", "snapshot_id": "old-code", "locator": {"kind": "lines", "start": 11, "end": 22}, "code_ref": {"kind": "function", "name": "wait_reply"}},
        ], "claims": [{"id": "wait", "text_ref": "#wait", "evidence_kind": "implementation",
                        "source_refs": ["design", "impl"], "context_ids": ["host"], "usage": "current",
                        "verification_requirements": []}], "relations": [],
    }
    raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n# Legacy\n\n<a id=\"wait\"></a>\nWait under the given conditions.\n").encode()
    card = module("cards_v3").parse_card(raw, "knowledge/legacy.md")
    assert card["raw"] == raw
    assert card["metadata"] == metadata
    assert card["doc_ref"][0]["snapshot_id"] == "old-doc"
    assert card["code_ref"][0]["symbol"] == "wait_reply"
    assert card["metadata"]["scope"]["contexts"][0]["features_all"] == ["timeout"]
    assert card["metadata"]["claims"][0]["usage"] == "current"
    assert "claims" not in card


def test_schema_accepts_concise_header_and_keeps_legacy_symbol_shape():
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).resolve().parents[2] / "governance/schemas/frontmatter.schema.json").read_text())
    Draft202012Validator(schema).validate({"id": "c", "doc_ref": [{"doc_id": "d", "page_start": 2, "page_end": 4}], "code_ref": []})
    source_schema = {"$defs": schema["$defs"], **schema["properties"]["sources"]["items"]}
    Draft202012Validator(source_schema).validate({"evidence_ref": "e", "source_id": "c", "snapshot_id": "s",
                                                "locator": {"kind": "lines", "start": 1, "end": 4},
                                                "code_ref": {"kind": "function", "name": "wait_reply"}})


@pytest.mark.parametrize("code_refs", [[], [{"code_id": "code", "line_start": 1, "line_end": 4, "symbol": "handle"}]])
def test_concise_parser_preserves_raw_header_without_synthetic_semantics(code_refs):
    import yaml
    metadata = {"id": "concise", "doc_ref": [{"doc_id": "doc", "section": "Design"}], "code_ref": code_refs}
    raw = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n# Concise title\n\nA design requirement.\n").encode()
    card = module("cards_v3").parse_card(raw, "knowledge/concise.md", concise_only=True)
    assert card["raw"] == raw
    assert card["metadata"] == metadata
    assert card["title"] == "Concise title"
    assert card["metadata"].get("tags", []) == []
    assert card["metadata"].get("lifecycle", "stable") == "stable"
    assert not {"claims", "scope", "usage", "profile", "summary"} & set(card)


def test_legacy_concise_draft_is_readable_without_added_scope_or_claims():
    import json
    import yaml

    metadata = {"id": "draft", "doc_ref": [{"doc_id": "doc", "section": "Design"}],
                "code_ref": [], "lifecycle": "draft"}
    raw = ("---\n" + yaml.safe_dump(metadata) + "---\n# Draft\nA retained draft.\n").encode()
    schema = json.loads((Path(__file__).resolve().parents[2] / "governance/schemas/frontmatter.schema.json").read_text())
    card = module("cards_v3").parse_card(raw, "knowledge/draft.md", {"schemas": {"card": schema}})
    assert card["legacy"] is True
    assert card["raw"] == raw
    assert card["metadata"] == metadata
    assert not {"scope", "claims", "usage"} & set(card)


def test_legacy_concise_draft_cannot_pass_new_candidate_format_check():
    raw = b"---\nid: draft\ndoc_ref:\n- doc_id: doc\n  section: Design\ncode_ref: []\nlifecycle: draft\n---\n# Draft\nA retained draft.\n"
    with pytest.raises(ValueError, match="INVALID_CARD_LIFECYCLE"):
        module("cards_v3").parse_card(raw, "knowledge/draft.md", concise_only=True)


@pytest.mark.parametrize("extra", [
    {"title": "Old title"}, {"summary": "Old summary"}, {"profile": "rule"},
    {"aliases": ["old_name"]}, {"claims": []}, {"scope": {"applicability": "unknown", "contexts": []}},
    {"usage": "guidance"}, {"owner": "someone"}, {"unknown_field": "value"},
])
def test_new_candidate_parser_enforces_five_fields_even_without_loaded_rules(extra):
    import yaml
    metadata = {"id": "c", "doc_ref": [{"doc_id": "doc", "section": "Design"}], "code_ref": [], **extra}
    raw = ("---\n" + yaml.safe_dump(metadata) + "---\n# Card\nA requirement.\n").encode()
    with pytest.raises(ValueError):
        module("cards_v3").parse_card(raw, "knowledge/c.md", concise_only=True)


@pytest.mark.parametrize("extra", [
    {"tags": "RX"}, {"tags": [""]}, {"tags": ["  "]}, {"tags": ["RX", "RX"]}, {"tags": [7]},
    {"lifecycle": "draft"}, {"lifecycle": None},
])
def test_concise_optional_fields_have_mechanical_types(extra):
    import yaml
    metadata = {"id": "c", "doc_ref": [{"doc_id": "doc", "section": "Design"}], "code_ref": [], **extra}
    raw = ("---\n" + yaml.safe_dump(metadata) + "---\n# Card\nA requirement.\n").encode()
    with pytest.raises(ValueError):
        module("cards_v3").parse_card(raw, "knowledge/c.md", concise_only=True)


def test_mixed_header_retains_explicit_claim_context_and_historical_usage():
    import yaml
    metadata = {"id": "mixed", "doc_ref": [{"doc_id": "doc", "section": "Design"}], "code_ref": [],
                "scope": {"applicability": "constrained", "contexts": [{"context_id": "old", "version": "v1"}]},
                "claims": [{"id": "a", "text_ref": "#a", "usage": "historical", "context_ids": ["old"],
                            "evidence_kind": "measurement", "source_refs": ["doc-1"],
                            "verification_requirements": ["Repeat measurement before applying to v2"]}]}
    raw = ("---\n" + yaml.safe_dump(metadata) + '---\n# Mixed\n\n<a id="a"></a>\nPrior measured result.\n').encode()
    card = module("cards_v3").parse_card(raw, "knowledge/mixed.md")
    assert card["metadata"] == metadata
    assert card["raw"] == raw
    assert "claims" not in card


def test_formal_compatibility_does_not_accept_arbitrary_unknown_header_fields():
    raw = b"---\nid: c\ndoc_ref:\n- doc_id: doc\n  section: Design\ncode_ref: []\nunknown_field: value\n---\n# Card\nA requirement.\n"
    with pytest.raises(ValueError, match="INVALID_CARD_FIELDS"):
        module("cards_v3").parse_card(raw, "knowledge/c.md")


def test_new_card_title_must_be_declared_in_body_h1():
    raw = b"---\nid: c\ndoc_ref:\n- doc_id: doc\n  section: Design\ncode_ref: []\n---\nA requirement without a title.\n"
    with pytest.raises(ValueError, match="CARD_TITLE_REQUIRED"):
        module("cards_v3").parse_card(raw, "knowledge/c.md", concise_only=True)
