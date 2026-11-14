"""Persistent PDF review coverage through the public source catalog."""

from pathlib import Path
import json
import sys

import pytest
from jsonschema import Draft202012Validator
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


@pytest.fixture
def library(tmp_path):
    for directory in ("docs-raw", "knowledge", "governance"):
        (tmp_path / directory).mkdir()
    return tmp_path


def test_partial_pdf_review_preserves_last_complete_version_and_merges_pages(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.mark_processed("doc-pdf", "a" * 64)

        source = catalog.record_pdf_review("doc-pdf", "b" * 64, [[5, 8], [1, 3], [3, 4]], 20)

        assert source["processed_hash"] == "a" * 64
        assert source["processing"] == {"source_sha256": "b" * 64, "reviewed_pages": [[1, 8]]}
        assert catalog.get_file("doc-pdf")["processing"] == source["processing"]
        assert catalog.list_files()[0]["processing"] == source["processing"]

    with module("catalog").Catalog(library) as reopened:
        assert reopened.get_file("doc-pdf")["processed_hash"] == "a" * 64
        assert reopened.get_file("doc-pdf")["processing"]["reviewed_pages"] == [[1, 8]]


def test_source_schema_limits_pdf_processing_to_its_explicit_fields():
    schema = json.loads((Path(__file__).resolve().parents[2]
                         / "governance/schemas/sources.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    source = {"source_id": "doc-pdf", "kind": "raw", "path": "docs-raw/protocol.PDF"}

    def errors(processing, **extra):
        return list(validator.iter_errors({"schema_version": "2.0", "snapshots": [],
                                           "resources": [{**source, **extra, "processing": processing}]}))

    valid = {"source_sha256": "a" * 64, "reviewed_pages": []}
    assert not errors(valid)
    assert errors({**valid, "stage": "reading"})
    assert errors({**valid, "source_sha256": "bad-hash"})
    assert errors({**valid, "reviewed_pages": [[True, 2]]})
    assert errors({**valid, "reviewed_pages": [[0, 2]]})
    assert errors(valid, kind="code")
    assert errors(valid, path="docs-raw/protocol.md")
    assert errors(valid, path="docs-raw/protocol.md", source_path="docs-raw/protocol.pdf")


def test_page_ranges_are_normalized_without_mutating_the_callers_input():
    ranges = [[7, 9], [2, 4], [4, 7], [12, 12]]
    assert module("catalog").normalize_page_ranges(ranges, 15) == [[2, 9], [12, 12]]
    assert ranges == [[7, 9], [2, 4], [4, 7], [12, 12]]
    assert module("catalog").remaining_page_ranges(15, ranges) == [[1, 1], [10, 11], [13, 15]]
    assert module("catalog").normalize_page_ranges([]) == []
    assert module("catalog").remaining_page_ranges(2, []) == [[1, 2]]
    assert module("catalog").remaining_page_ranges(2, [[1, 2]]) == []


@pytest.mark.parametrize("ranges", [
    None, "1-2", [1], [[1]], [[1, 2, 3]], [[True, 2]], [[1, False]],
    [[0, 1]], [[-1, 1]], [[2, 1]], [[1, 11]], [[1.5, 2]], [[1, "2"]],
])
def test_page_ranges_reject_invalid_types_and_bounds(ranges):
    with pytest.raises(ValueError, match="INVALID_REVIEWED_PAGES"):
        module("catalog").normalize_page_ranges(ranges, 10)


@pytest.mark.parametrize("count", [False, 0, -1, 2.5, "2"])
def test_total_page_counts_must_be_positive_integers(count):
    with pytest.raises(ValueError, match="INVALID_REVIEWED_PAGES"):
        module("catalog").normalize_page_ranges([], count)
    with pytest.raises(ValueError, match="INVALID_REVIEWED_PAGES"):
        module("catalog").remaining_page_ranges(count, [])


def test_pdf_completion_and_last_batch_retry_do_not_reopen_partial_coverage(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.record_pdf_review("doc-pdf", "b" * 64, [[1, 3]], 5)

        complete = catalog.record_pdf_review("doc-pdf", "b" * 64, [[3, 5]], 5, source_commit="c" * 40)

        assert "processing" not in complete
        assert complete["processed_hash"] == "b" * 64
        assert complete["processed_exists"] is True
        assert complete["source_commit"] == "c" * 40
        repeated = catalog.record_pdf_review("doc-pdf", "b" * 64, [[3, 5]], 5)
        assert repeated == complete
        with pytest.raises(ValueError, match="INVALID_REVIEWED_PAGES"):
            catalog.record_pdf_review("doc-pdf", "b" * 64, [[1, 6]], 5)


def test_pdf_restarts_and_changed_versions_do_not_inherit_prior_coverage(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.mark_processed("doc-pdf", "a" * 64)
        first = catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 2]], 5, restart=True)
        assert first["processing"] == {"source_sha256": "a" * 64, "reviewed_pages": [[1, 2]]}
        assert first["processed_hash"] == "a" * 64
        assert catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 2]], 5, restart=True) == first
        advanced = catalog.record_pdf_review("doc-pdf", "a" * 64, [[3, 3]], 5)
        assert advanced["processing"]["reviewed_pages"] == [[1, 3]]
        restarted = catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 1]], 5, restart=True)
        assert restarted["processing"]["reviewed_pages"] == [[1, 1]]
        changed = catalog.record_pdf_review("doc-pdf", "b" * 64, [[2, 3]], 5)
        assert changed["processing"] == {"source_sha256": "b" * 64, "reviewed_pages": [[2, 3]]}
        assert changed["processed_hash"] == "a" * 64


def test_processing_views_rebuild_from_registry_and_do_not_mutate_its_bytes(library):
    registry = library / "governance/sources.lock.yaml"
    registry.write_text(yaml.safe_dump({"schema_version": "2.0", "snapshots": [], "resources": [{
        "source_id": "doc-pdf", "kind": "raw", "path": "docs-raw/protocol.pdf", "extra": "keep",
        "processing": {"source_sha256": "a" * 64, "reviewed_pages": [[4, 6], [1, 3]]},
    }]}), encoding="utf-8")
    original = registry.read_bytes()
    card = library / "knowledge/pdf-note.md"
    card.write_text("---\nid: pdf-note\ndoc_ref:\n- doc_id: doc-pdf\n  page_start: 1\n"
                    "  page_end: 3\ncode_ref: []\n---\n# PDF note\nA synthetic requirement.\n",
                    encoding="utf-8")
    with module("catalog").Catalog(library) as catalog:
        expected = {"source_sha256": "a" * 64, "reviewed_pages": [[1, 6]]}
        assert catalog.get_file("doc-pdf")["processing"] == expected
        assert catalog.list_files()[0]["processing"] == expected
        assert catalog.files_for("pdf-note")[0]["processing"] == expected
        source_view = catalog.get_file("doc-pdf")
        source_view["processing"]["reviewed_pages"][0][1] = 99
        assert catalog.get_file("doc-pdf")["processing"] == expected
        assert registry.read_bytes() == original
        columns = {row["name"] for row in catalog.connection.execute("PRAGMA table_info(files)")}
        assert "processing" not in columns and "reviewed_pages" not in columns

    (library / "artifacts/knowledge.sqlite").unlink()
    with module("catalog").Catalog(library) as rebuilt:
        rebuilt.rebuild()
        assert rebuilt.get_file("doc-pdf")["processing"] == expected
        rebuilt.register_many([{"kind": "raw", "path": "docs-raw/other.pdf"}])
        assert rebuilt.get_file("doc-pdf")["processing"] == expected
    saved = yaml.safe_load(registry.read_bytes())
    assert saved["resources"][0]["extra"] == "keep"
    assert saved["resources"][0]["processing"]["reviewed_pages"] == [[4, 6], [1, 3]]


def test_source_list_exposes_processing_in_all_existing_query_forms(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 2]], 5)
    (library / "knowledge/pdf-note.md").write_text(
        "---\nid: pdf-note\ndoc_ref:\n- doc_id: doc-pdf\n  page_start: 1\n"
        "  page_end: 2\ncode_ref: []\n---\n# PDF note\nA synthetic requirement.\n", encoding="utf-8")
    sources = module("library").sources
    expected = {"source_sha256": "a" * 64, "reviewed_pages": [[1, 2]]}
    listing, phase = sources(library, "list", {})
    assert phase == "listed" and listing["files"][0]["processing"] == expected
    selected, phase = sources(library, "list", {"source_id": "doc-pdf"})
    assert phase == "listed" and selected["source"]["processing"] == expected
    related, phase = sources(library, "list", {"card_id": "pdf-note"})
    assert phase == "listed" and related["files"][0]["processing"] == expected


@pytest.mark.parametrize("processing", [
    None, {}, {"source_sha256": "a" * 64}, {"source_sha256": "bad", "reviewed_pages": []},
    {"source_sha256": "a" * 64, "reviewed_pages": [[True, 2]]},
    {"source_sha256": "a" * 64, "reviewed_pages": [[2, 1]]},
    {"source_sha256": "a" * 64, "reviewed_pages": [], "stage": "reading"},
])
def test_registry_rejects_malformed_processing_at_read_and_write(library, processing):
    registry = library / "governance/sources.lock.yaml"
    source = {"source_id": "doc-pdf", "kind": "raw", "path": "docs-raw/protocol.pdf"}
    registry.write_text(yaml.safe_dump({"schema_version": "2.0", "snapshots": [],
                                       "resources": [{**source, "processing": processing}]}), encoding="utf-8")
    original = registry.read_bytes()
    with pytest.raises(ValueError, match="INVALID_PDF_PROCESSING"):
        module("catalog").Catalog(library)
    assert registry.read_bytes() == original
    registry.write_text(yaml.safe_dump({"schema_version": "2.0", "snapshots": [],
                                       "resources": [source]}), encoding="utf-8")
    with module("catalog").Catalog(library) as catalog:
        catalog.registry["resources"][0]["processing"] = processing
        before = registry.read_bytes()
        with pytest.raises(ValueError, match="INVALID_PDF_PROCESSING"):
            catalog.register("raw", "docs-raw/other.pdf", source_id="doc-other")
        assert registry.read_bytes() == before


@pytest.mark.parametrize(("kind", "path"), [("raw", "docs-raw/note.md"), ("code", "main/note.pdf")])
def test_review_coverage_is_limited_to_raw_pdf_sources(library, kind, path):
    with module("catalog").Catalog(library) as catalog:
        catalog.register(kind, path, source_id="source")
        before = (library / "governance/sources.lock.yaml").read_bytes()
        with pytest.raises(ValueError, match="PDF_SOURCE_REQUIRED"):
            catalog.record_pdf_review("source", "a" * 64, [[1, 2]], 5)
        assert (library / "governance/sources.lock.yaml").read_bytes() == before


def test_handled_pdf_deletion_clears_obsolete_partial_coverage(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 2]], 5)
        missing = catalog.mark_processed("doc-pdf", None, exists=False)
        assert "processing" not in missing
        assert missing["processed_hash"] is None
        assert missing["processed_exists"] is False


def test_completed_pdf_retry_still_requires_a_real_total_page_count(library):
    with module("catalog").Catalog(library) as catalog:
        catalog.register("raw", "docs-raw/protocol.pdf", source_id="doc-pdf")
        catalog.mark_processed("doc-pdf", "a" * 64)
        with pytest.raises(ValueError, match="INVALID_REVIEWED_PAGES"):
            catalog.record_pdf_review("doc-pdf", "a" * 64, [[1, 2]], None)


def test_pdf_review_result_projects_receipts_without_mutating_the_source():
    source = {"source_id": "doc-pdf", "kind": "raw", "path": "docs-raw/protocol.pdf",
              "processed_hash": "a" * 64, "processed_exists": True,
              "processing": {"source_sha256": "b" * 64, "reviewed_pages": [[1, 2]]}}
    before = yaml.safe_dump(source)
    project = module("catalog").pdf_review_result
    assert project(source, "b" * 64, [[3, 4]], 5) == {
        "source_sha256": "b" * 64, "reviewed_pages": [[1, 4]]}
    assert project(source, "b" * 64, [[3, 5]], 5) is None
    assert project(source, "b" * 64, [[3, 4]], 5, restart=True) == {
        "source_sha256": "b" * 64, "reviewed_pages": [[3, 4]]}
    assert project(source, "c" * 64, [[3, 4]], 5) == {
        "source_sha256": "c" * 64, "reviewed_pages": [[3, 4]]}
    assert yaml.safe_dump(source) == before
    complete = {key: value for key, value in source.items() if key != "processing"}
    assert project(complete, "a" * 64, [[3, 4]], 5) is None
