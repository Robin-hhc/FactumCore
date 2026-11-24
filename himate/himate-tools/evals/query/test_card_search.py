"""Whole-card candidate search, with no implicit purpose or applicability gate."""

from pathlib import Path
import sqlite3
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def library_at(root):
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "docs-raw/design.md").write_text("# Design\n\nRX requirements.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
    return root


def write_card(root, identity, body, **extra):
    metadata = {"id": identity, "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
                "code_ref": [], **extra}
    path = root / "knowledge" / (identity + ".md")
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n" + body, encoding="utf-8")
    return path, metadata


def search(root, text, **extra):
    result, phase = module("library").query(root, {"query": text, **extra})
    assert phase == "searched", result
    return result


def test_three_field_card_is_searchable_and_read_returns_only_declared_metadata(tmp_path):
    root = library_at(tmp_path)
    path, metadata = write_card(root, "rx", "# RX flow\n\nrx_validate_frame checks the length.\n\n"
                                "The design budget is 8 ms; timing has not been measured.\n")
    result = search(root, "rx_validate_frame")
    assert [hit["card_id"] for hit in result["matches"]] == ["rx"]
    assert set(result["matches"][0]) == {"card_id", "path", "title", "tags", "lifecycle", "score"}
    assert result["matches"][0]["tags"] == []
    assert result["matches"][0]["lifecycle"] == "stable"
    assert set(result) == {"matches", "truncated", "report_ref"}
    read, phase = module("library").query(root, {"card_id": "rx"}, read=True)
    assert phase == "read"
    assert read["metadata"] == metadata
    assert read["doc_ref"] == metadata["doc_ref"]
    assert read["code_ref"] == []
    raw = path.read_bytes().decode("utf-8")
    assert read["body"] == raw.split("---", 2)[2].lstrip("\r\n")
    assert "8 ms" in read["body"] and "not been measured" in read["body"]
    assert not {"purpose", "eligible_claim_ids", "claims", "scope", "usage"} & set(read)


def test_query_terms_can_match_different_paragraphs_and_tags_are_exact_and(tmp_path):
    root = library_at(tmp_path)
    write_card(root, "both", "# RX\n\nrx_validate_frame validates length.\n\nDelivery follows.\n", tags=["RX", "Device"])
    write_card(root, "one", "# RX\n\nrx_validate_frame delivers.\n", tags=["RX"])
    result = search(root, "rx_validate_frame Delivery", tags=["RX", "Device"])
    assert [hit["card_id"] for hit in result["matches"]] == ["both"]
    assert {hit["card_id"] for hit in search(root, "rx_validate_frame", tags=["rx"])["matches"]} == {"both", "one"}
    assert search(root, "rx_validate_frame", tags=["RX", "Missing"])["matches"] == []
    assert search(root, "rx_validate_frames")["matches"] == []


@pytest.mark.parametrize("tags", [
    ["80211BE", "Device", "STRASSE"],
    [" 80211be ", "\tdevice\n", "straße"],
    ["８０２１１ｂｅ", "ＤＥＶＩＣＥ", "Strasse", "80211BE"],
])
def test_tags_normalize_both_sides_without_rewriting_display_or_card_bytes(tmp_path, tags):
    root = library_at(tmp_path)
    stored = [" ８０２１１ＢＥ ", "Ｄｅｖｉｃｅ", "Straße", "80211be"]
    path, metadata = write_card(root, "tagged", "# Needle\n\nA useful rule.\n", tags=stored)
    before = path.read_bytes()
    result = search(root, "needle", tags=tags)
    assert [(hit["card_id"], hit["tags"]) for hit in result["matches"]] == [("tagged", stored)]
    read, _ = module("library").query(root, {"card_id": "tagged"}, read=True)
    assert read["metadata"] == metadata
    assert path.read_bytes() == before


def test_normalized_tags_still_require_complete_values_and_keep_internal_spaces(tmp_path):
    root = library_at(tmp_path)
    write_card(root, "tagged", "# Needle\n", tags=["rx  path", "802.11BE"])
    assert [hit["card_id"] for hit in search(root, "needle", tags=["RX  PATH", "802.11be"])["matches"]] == ["tagged"]
    for tags in (["rx path"], ["rx"], ["80211be"], ["802.11be", "missing"]):
        assert search(root, "needle", tags=tags)["matches"] == []


@pytest.mark.parametrize("top_k", [1, 100])
def test_case_and_whitespace_variants_keep_scores_order_and_top_k(tmp_path, top_k):
    root = library_at(tmp_path)
    write_card(root, "a-upper", "# 80211BE\n\nShared rule.\n")
    write_card(root, "z-lower", "# 80211be\n\nShared rule.\n")
    expected = [{"card_id": identity, "path": f"knowledge/{identity}.md", "title": title,
                 "tags": [], "lifecycle": "stable", "score": 9}
                for identity, title in (("a-upper", "80211BE"), ("z-lower", "80211be"))][:top_k]
    for text in ("80211be", "80211BE", "80211Be", "  ８０２１１ｂｅ\t\n", "80211BE  80211be"):
        result = search(root, text, top_k=top_k)
        assert result["matches"] == expected
        assert result["truncated"] is (top_k == 1)


def test_lifecycle_filters_whole_cards_and_read_preserves_deprecated_and_legacy_draft(tmp_path):
    root = library_at(tmp_path)
    write_card(root, "normal", "# Normal\n\nrx_timeout design advice.\n")
    write_card(root, "old", "# Old\n\nrx_timeout prior rule.\n", lifecycle="deprecated")
    write_card(root, "draft", "# Draft\n\nrx_timeout draft.\n", lifecycle="draft")
    assert [hit["card_id"] for hit in search(root, "rx_timeout")["matches"]] == ["normal"]
    assert {hit["card_id"] for hit in search(root, "rx_timeout", include_deprecated=True)["matches"]} == {"normal", "old"}
    for identity, lifecycle in (("old", "deprecated"), ("draft", "draft")):
        read, phase = module("library").query(root, {"card_id": identity}, read=True)
        assert phase == "read" and read["lifecycle"] == lifecycle
        assert read["metadata"]["lifecycle"] == lifecycle


@pytest.mark.parametrize("extra", [{"purpose": "current"}, {"purpose": None}, {"purpose": ""}, {"context": {}}, {"context": None}])
@pytest.mark.parametrize("read", [False, True])
def test_removed_parameters_fail_before_catalog_or_normal_report(tmp_path, extra, read):
    request = {"card_id": "absent"} if read else {"query": "RX"}
    with pytest.raises(ValueError, match="QUERY_PARAMETERS_REMOVED"):
        module("library").query(tmp_path, {**request, **extra}, read=read)
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize("top_k", [0, 101, True, 1.0, None])
def test_top_k_contract_is_still_one_to_one_hundred(tmp_path, top_k):
    root = library_at(tmp_path)
    with pytest.raises(ValueError, match="INVALID_TOP_K"):
        search(root, "RX", top_k=top_k)


@pytest.mark.parametrize("query", ["needle", "NEEDLE", "Ｎｅｅｄｌｅ", "  needle\t\n", "needle NEEDLE"])
def test_field_weights_deduplicate_terms_and_ties_use_card_id(tmp_path, query):
    root = library_at(tmp_path)
    write_card(root, "title", "# needle\n\nNo extra match.\n")
    write_card(root, "tag", "# Tagged\n\nNo extra match.\n", tags=["needle"])
    write_card(root, "body-b", "# B\n\nneedle needle\n\nneedle\n")
    write_card(root, "body-a", "# A\n\nneedle\n")
    result = search(root, query, top_k=3)
    assert [(hit["card_id"], hit["score"]) for hit in result["matches"]] == [("title", 9), ("tag", 5), ("body-a", 1)]
    assert result["truncated"] is True


def test_legacy_claim_count_does_not_multiply_whole_card_title_score(tmp_path):
    root = library_at(tmp_path)
    body = '# needle\n\n<a id="first"></a>\nFirst condition.\n\n<a id="second"></a>\nSecond condition.\n'
    claims = [{"id": name, "text_ref": "#" + name, "usage": "guidance", "evidence_kind": "design",
               "source_refs": ["doc-1"], "context_ids": [], "verification_requirements": []}
              for name in ("first", "second")]
    write_card(root, "one", body, claims=claims[:1])
    write_card(root, "two", body, claims=claims)
    result = search(root, "NEEDLE")
    assert [(hit["card_id"], hit["score"]) for hit in result["matches"]] == [("one", 9), ("two", 9)]


def test_legacy_aliases_and_separate_claim_sections_are_auxiliary_search_text(tmp_path):
    root = library_at(tmp_path)
    claims = [{"id": name, "text_ref": "#" + name, "usage": usage, "evidence_kind": "design",
               "source_refs": ["doc-1"], "context_ids": [], "verification_requirements": []}
              for name, usage in (("first", "guidance"), ("second", "historical"))]
    path, metadata = write_card(root, "mixed", '# Mixed\n\n<a id="first"></a>\nalpha condition.\n\n<a id="second"></a>\nbeta history.\n',
                                aliases=["legacy_alias"], search_terms=["legacy_search"], claims=claims,
                                scope={"applicability": "unknown", "contexts": []})
    before = path.read_bytes()
    assert [hit["card_id"] for hit in search(root, "alpha beta")["matches"]] == ["mixed"]
    assert [hit["card_id"] for hit in search(root, "legacy_alias legacy_search")["matches"]] == ["mixed"]
    read, _ = module("library").query(root, {"card_id": "mixed"}, read=True)
    assert read["metadata"] == metadata
    assert path.read_bytes() == before


def legacy_search_cache(root, format_version=None):
    """Install a prior search schema while preserving the current cards signature."""
    library = module("library")
    with module("catalog").Catalog(root) as catalog:
        signature = library._signature(catalog)
        catalog.connection.execute("DROP TABLE IF EXISTS search_terms")
        catalog.connection.execute("CREATE TABLE search_terms(token TEXT,card_id TEXT,claim_id TEXT,field TEXT, PRIMARY KEY(token,card_id,claim_id,field))")
        catalog.connection.execute("INSERT INTO search_terms VALUES('sentinel','old','claim','body')")
        catalog.connection.execute("CREATE TABLE IF NOT EXISTS search_state(key TEXT PRIMARY KEY,value TEXT)")
        catalog.connection.execute("INSERT OR REPLACE INTO search_state VALUES('cards',?)", (signature,))
        catalog.connection.execute("DELETE FROM search_state WHERE key='format'")
        if format_version is not None:
            catalog.connection.execute("INSERT INTO search_state VALUES('format',?)", (format_version,))


@pytest.mark.parametrize("format_version", [None, "claim-v0", "card-v1"], ids=["unversioned", "old-version", "wrong-structure"])
def test_search_format_upgrade_without_card_changes_preserves_source_versions_and_bytes(tmp_path, format_version):
    root = library_at(tmp_path)
    path, _ = write_card(root, "rx", '# RX\n\n<a id="answer"></a>\nrx_timeout condition remains unknown.\n',
                         scope={"applicability": "unknown", "contexts": []},
                         claims=[{"id": "answer", "text_ref": "#answer", "usage": "historical",
                                  "evidence_kind": "design", "source_refs": ["doc-1"], "context_ids": [],
                                  "verification_requirements": ["Recheck applicability before reuse"]}])
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed("doc-design", "a" * 64, source_commit="c" * 40)
        source_before = catalog.get_file("doc-design")
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    card_before = path.read_bytes()
    legacy_search_cache(root, format_version)
    assert [hit["card_id"] for hit in search(root, "rx_timeout")["matches"]] == ["rx"]
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("doc-design") == source_before
        assert catalog.connection.execute("SELECT value FROM search_state WHERE key='format'").fetchone()[0] == module("library").SEARCH_VERSION
        assert [row[1] for row in catalog.connection.execute("PRAGMA table_info(search_terms)")] == ["token", "card_id", "field"]
    assert path.read_bytes() == card_before
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry


def test_old_card_cache_with_compatible_structure_rebuilds_without_card_changes(tmp_path):
    root = library_at(tmp_path)
    path, _ = write_card(root, "rule", "# Needle\n\nA useful rule.\n", tags=["  RX "])
    search(root, "needle")
    before = path.read_bytes()
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    with module("catalog").Catalog(root) as catalog:
        catalog.connection.execute("UPDATE search_state SET value='card-v1' WHERE key='format'")
        catalog.connection.execute("DELETE FROM search_terms")
        catalog.connection.execute("INSERT INTO search_terms VALUES('sentinel','rule','body')")
    result = search(root, "NEEDLE", tags=["rx"])
    assert [(hit["card_id"], hit["score"], hit["tags"]) for hit in result["matches"]] == [("rule", 9, ["  RX "])]
    with module("catalog").Catalog(root) as catalog:
        assert catalog.connection.execute("SELECT value FROM search_state WHERE key='format'").fetchone()[0] == module("library").SEARCH_VERSION
    assert search(root, "sentinel")["matches"] == []
    assert path.read_bytes() == before
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry


def test_failed_search_upgrade_rolls_back_old_cache_and_source_state(tmp_path, monkeypatch):
    root = library_at(tmp_path)
    path, _ = write_card(root, "rx", "# RX\n\nrx_timeout condition.\n")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed("doc-design", "b" * 64)
        source_before = catalog.get_file("doc-design")
    legacy_search_cache(root)
    before = path.read_bytes()
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    lexical = module("library").indexing.lexical
    def fail_on_body(text):
        if "rx_timeout" in text:
            raise OSError("Synthetic search upgrade failure")
        return lexical(text)
    monkeypatch.setattr(module("library").indexing, "lexical", fail_on_body)
    with pytest.raises(OSError, match="Synthetic search upgrade failure"):
        search(root, "rx_timeout")
    with sqlite3.connect(root / "artifacts/knowledge.sqlite") as connection:
        assert connection.execute("SELECT * FROM search_terms").fetchall() == [("sentinel", "old", "claim", "body")]
        assert connection.execute("SELECT value FROM search_state WHERE key='format'").fetchone() is None
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("doc-design") == source_before
    assert path.read_bytes() == before
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry
