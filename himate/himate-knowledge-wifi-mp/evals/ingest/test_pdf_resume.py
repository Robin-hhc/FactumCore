"""PDF batches keep durable evaluated-page facts without marking the whole file early."""

from io import BytesIO
import json
from pathlib import Path
import shutil
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def pdf_bytes(pages):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=400)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts", ".build"):
        (root / name).mkdir(parents=True)
    (root / ".build/README.md").write_bytes(b"Local staging only.\r\n")
    (root / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(5))

    def convert(_root, _source, data, output, _options, _range, _source_hash, _profile_hash):
        from pypdf import PdfReader

        pages = list(range(1, len(PdfReader(BytesIO(data)).pages) + 1))
        text = "\n\n".join(f"Physical page {page}: a synthetic requirement." for page in pages)
        (output / "document.md").write_text(text, encoding="utf-8")
        (output / "document.json").write_text(json.dumps({"pictures": []}), encoding="utf-8")
        return text, [{"locator": {"kind": "page", "page": page},
                       "text": f"Physical page {page}: a synthetic requirement."} for page in pages], [], [], pages

    monkeypatch.setattr(module("document_parser"), "_docling", convert)
    return root


def prepare(root, **extra):
    task, phase = module("ingest").scan(root, {"source": "docs-raw/protocol.pdf",
                                               "review_page_budget": 2, **extra})
    assert phase == "prepared", task
    return task


def text_pages(root, monkeypatch, contents, *, illustrated=False):
    """Keep the native PDF page universe while controlling converted test material."""
    (root / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(len(contents)))

    def convert(_root, _source, _data, output, _options, _range, _source_hash, _profile_hash):
        pages = list(range(1, len(contents) + 1))
        text = "\n\n".join(contents)
        (output / "document.md").write_text(text, encoding="utf-8")
        document = {"pictures": [], "tables": []}
        images = []
        if illustrated:
            asset = output / "image.png"
            asset.write_bytes(b"Synthetic image asset; image decoding is outside this test.")
            images.append({"ref": asset.relative_to(root).as_posix(), "provenance": [{"page_no": 1}]})
            document["tables"].append({"self_ref": "#/tables/0", "prov": [{"page_no": 1}]})
            document["pictures"].append({"self_ref": "#/pictures/0", "prov": [{"page_no": 1}]})
        (output / "document.json").write_text(json.dumps(document), encoding="utf-8")
        return text, [{"locator": {"kind": "page", "page": page}, "text": body}
                      for page, body in zip(pages, contents)], images, [], pages

    monkeypatch.setattr(module("document_parser"), "_docling", convert)


def plan(root, pages, *, card=None):
    value = {"cards": [{"id": card, "path": f"knowledge/{card}.md"}] if card else []}
    if pages is not None:
        value["source_pages"] = pages
    (root / ".build/plan.md").write_text(
        "---\n" + yaml.safe_dump(value) + "---\nAll material within this batch was evaluated.\n",
        encoding="utf-8")


def draft(root, identity, source_id, page):
    header = {"id": identity, "doc_ref": [{"doc_id": source_id, "page_start": page, "page_end": page}],
              "code_ref": []}
    target = root / ".build/cards" / f"{identity}.md"
    target.write_text("---\n" + yaml.safe_dump(header) + "---\n# Requirement\n\nA synthetic requirement.\n",
                      encoding="utf-8")


def test_partial_pdf_resumes_after_cache_and_database_rebuild_then_completes(library):
    root = library
    task = prepare(root)
    source_id = task["source"]["source_id"]
    assert task["pdf_review"]["start_page"] == 1
    assert task["pdf_review"]["end_page"] == 2
    packet = (root / task["pdf_review"]["packet_ref"]).read_text(encoding="utf-8")
    assert "Physical page 1" in packet and "Physical page 2" in packet
    assert "Physical page 3" not in packet
    plan(root, [[1, 2]], card="mlo")
    draft(root, "mlo", source_id, 1)
    assert module("ingest").check(root, {})[1] == "passed"
    result, phase = module("ingest").commit(root, {})
    assert phase == "completed" and result["source_complete"] is False, result
    assert result.get("processed_hash") is None
    listed, _ = module("library").sources(root, "list", {"source_id": source_id})
    assert listed["source"]["processing"]["reviewed_pages"] == [[1, 2]]
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    (root / "artifacts/knowledge.sqlite").unlink()
    cache = root / task["source"]["parsed"]["manifest_ref"]
    shutil.rmtree(cache.parent)
    pending, phase = module("library").patrol(root, "plan", {})
    assert phase == "needs_ingest" and pending["next_file"]["source_id"] == source_id
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry

    task = prepare(root)
    assert task["pdf_review"]["reviewed_pages"] == [[1, 2]]
    assert task["pdf_review"]["start_page"] == 3
    plan(root, [[3, 3]])
    assert module("ingest").check(root, {})[1] == "passed"
    result, _ = module("ingest").commit(root, {"reason": "This assessed reference page adds no new card."})
    assert result["source_complete"] is False
    assert result["processing"]["reviewed_pages"] == [[1, 3]]

    task = prepare(root)
    assert task["pdf_review"]["start_page"] == 4
    assert task["pdf_review"]["end_page"] == 5
    plan(root, [[4, 5]], card="phy")
    # Earlier pages may support a new card without changing the assessed batch.
    draft(root, "phy", source_id, 1)
    assert module("ingest").check(root, {})[1] == "passed"
    result, _ = module("ingest").commit(root, {})
    assert result["source_complete"] is True
    assert result["processed_hash"] == task["source"]["hash"]
    listed, _ = module("library").sources(root, "list", {"source_id": source_id})
    assert "processing" not in listed["source"]
    assert module("ingest").scan(root, {})[1] == "unchanged"
    assert (root / ".build/README.md").read_bytes() == b"Local staging only.\r\n"


@pytest.mark.parametrize("pages", [None, [], [[2, 2]], [[1, 3]], [[1, True]], [[1, 1], [2, 2]]])
def test_pdf_plan_must_explicitly_cover_the_bounded_batch_before_check_or_apply(library, pages):
    prepare(library)
    plan(library, pages)
    result, phase = module("ingest").check(library, {})
    assert phase == "failed", result
    assert any(item["code"].startswith("PDF_REVIEW_") for item in result["findings"])
    with pytest.raises(ValueError, match="PDF_REVIEW_"):
        module("ingest").commit(library, {"reason": "No card is needed."})
    with module("catalog").Catalog(library) as catalog:
        assert catalog.list_files()[0].get("processing") is None


def test_defer_and_failed_pdf_publish_do_not_advance_evaluated_pages(library, monkeypatch):
    prepare(library)
    result, phase = module("ingest").commit(library, {"defer": True, "reason": "Missing evidence."})
    assert phase == "deferred", result
    plan(library, [[1, 2]])
    catalog_type = module("catalog").Catalog

    def fail(_self):
        raise OSError("synthetic index failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(catalog_type, "rebuild", fail)
        with pytest.raises(OSError, match="synthetic index failure"):
            module("ingest").commit(library, {"reason": "Assessed; no card needed."})
    assert (library / ".build/task.json").exists()
    with catalog_type(library) as catalog:
        source = catalog.list_files()[0]
        assert source.get("processing") is None and source["processed_hash"] is None
    result, _ = module("ingest").commit(library, {"reason": "Assessed; no card needed."})
    assert result["processing"]["reviewed_pages"] == [[1, 2]]


def test_pdf_changed_version_never_inherits_old_page_coverage(library):
    task = prepare(library)
    plan(library, [[1, 2]])
    module("ingest").commit(library, {"reason": "Assessed; no increment."})
    (library / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(6))
    task = prepare(library)
    assert task["pdf_review"]["total_pages"] == 6
    assert task["pdf_review"]["reviewed_pages"] == []
    assert task["pdf_review"]["start_page"] == 1


@pytest.mark.parametrize("budget", [0, 1001, True, "2", None])
def test_invalid_pdf_budget_keeps_existing_staging(library, budget):
    marker = library / ".build/task.json"
    marker.write_bytes(b'{"unfinished":true}')
    with pytest.raises(ValueError, match="PDF_REVIEW_BUDGET"):
        prepare(library, review_page_budget=budget)
    assert marker.read_bytes() == b'{"unfinished":true}'


def test_same_hash_reprocess_partial_stays_pending_for_scan_and_patrol(library):
    task = prepare(library, review_page_budget=20)
    plan(library, [[1, 5]])
    module("ingest").commit(library, {"reason": "All pages assessed, no increment."})
    full_hash = task["source"]["hash"]
    repeated = prepare(library, reprocess=True)
    assert repeated["pdf_review"]["start_page"] == 1
    plan(library, [[1, 2]])
    result, _ = module("ingest").commit(library, {"reason": "First batch of explicit reassessment."})
    assert result["processed_hash"] == full_hash and result["source_complete"] is False
    pending, phase = module("library").patrol(library, "plan", {})
    assert phase == "needs_ingest", pending
    continued = prepare(library)
    assert continued["source"]["change"] == "resume"
    assert continued["pdf_review"]["start_page"] == 3


@pytest.mark.parametrize("complete", [False, True], ids=["partial", "full"])
def test_receipt_write_failure_does_not_advance_formal_coverage(library, monkeypatch, complete):
    prepare(library, review_page_budget=20 if complete else 2)
    plan(library, [[1, 5 if complete else 2]])
    registry_path = library / "governance/sources.lock.yaml"
    before = registry_path.read_bytes()
    ingest = module("ingest")
    original = ingest.write_json

    def fail_receipt(path, value):
        if path == library / "artifacts/ingest/latest.json":
            raise OSError("synthetic receipt failure")
        return original(path, value)

    monkeypatch.setattr(ingest, "write_json", fail_receipt)
    with pytest.raises(OSError, match="synthetic receipt failure"):
        ingest.commit(library, {"reason": "Assessed; no increment."})
    assert registry_path.read_bytes() == before
    assert (library / ".build/task.json").exists()


@pytest.mark.parametrize("material", ["packet_ref", "page_index_ref"])
def test_modified_review_packet_cannot_be_applied(library, material):
    task = prepare(library)
    plan(library, [[1, 2]])
    (library / task["pdf_review"][material]).write_bytes(b"Unreviewed replacement material")
    result, phase = module("ingest").check(library, {})
    assert phase == "failed" and result["findings"][0]["code"] == "PDF_REVIEW_MATERIAL_CHANGED"
    with pytest.raises(ValueError, match="PDF_REVIEW_MATERIAL_CHANGED"):
        module("ingest").commit(library, {"reason": "Assessed; no increment."})


def test_missing_conversion_pages_never_shrink_the_original_pdf_universe(library, monkeypatch):
    parser = module("document_parser")
    convert = parser._docling

    def partial(*args):
        text, segments, images, gaps, pages = convert(*args)
        return text, [item for item in segments if item["locator"]["page"] <= 2], images, gaps, pages[:2]

    monkeypatch.setattr(parser, "_docling", partial)
    task = prepare(library)
    assert task["pdf_review"]["total_pages"] == 5
    assert task["source"]["parsed"]["statistics"]["page_count"] == 2
    plan(library, [[1, 2]])
    result, _ = module("ingest").commit(library, {"reason": "Only first batch assessed."})
    assert result["source_complete"] is False and result["remaining_pages"] == [[3, 5]]
    prepare(library)
    plan(library, [[3, 4]])
    checked, phase = module("ingest").check(library, {})
    assert phase == "failed" and checked["findings"][0]["code"] == "PDF_REVIEW_MATERIAL_UNAVAILABLE"
    with pytest.raises(ValueError, match="PDF_REVIEW_MATERIAL_UNAVAILABLE"):
        module("ingest").commit(library, {"reason": "Cannot treat missing pages as blank."})


def test_thousand_page_pdf_only_hands_off_one_bounded_packet(library):
    (library / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(1001))
    task = prepare(library, review_page_budget=20)
    batch = task["pdf_review"]
    assert batch["total_pages"] == 1001
    assert (batch["start_page"], batch["end_page"]) == (1, 20)
    packet = (library / batch["packet_ref"]).read_text(encoding="utf-8")
    assert "Physical page 20:" in packet and "Physical page 21:" not in packet
    plan(library, [[1, 20]])
    result, _ = module("ingest").commit(library, {"reason": "First twenty pages assessed."})
    assert result["remaining_pages"] == [[21, 1001]] and result["source_complete"] is False
    following = prepare(library)
    assert following["pdf_review"]["start_page"] == 21


def test_default_text_budget_has_no_implicit_page_cap(library):
    (library / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(1001))
    task, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared", task
    batch = task["pdf_review"]
    assert batch["page_budget"] is None
    assert batch["text_budget"] == 400000
    assert (batch["start_page"], batch["end_page"]) == (1, 1001)
    packet = (library / batch["packet_ref"]).read_text(encoding="utf-8")
    assert "Physical page 1001:" in packet
    assert 0 < batch["text_units"] < batch["text_budget"]


@pytest.mark.parametrize("budget", [0, 4000001, True, "1000", 1.5, None])
def test_invalid_pdf_text_budget_keeps_existing_staging(library, budget):
    marker = library / ".build/task.json"
    marker.write_bytes(b'{"unfinished":true}')
    with pytest.raises(ValueError, match="PDF_REVIEW_BUDGET"):
        prepare(library, review_text_budget=budget)
    assert marker.read_bytes() == b'{"unfinished":true}'


def test_text_threshold_includes_the_whole_page_that_crosses_it(library, monkeypatch):
    first, second = "FIRST_PAGE_" + "a" * 100, "SECOND_PAGE_" + "b" * 1000
    text_pages(library, monkeypatch, [first, second, "THIRD_PAGE_MUST_WAIT"])
    task, phase = module("ingest").scan(library, {
        "source": "docs-raw/protocol.pdf", "review_text_budget": 300,
    })
    assert phase == "prepared", task
    batch = task["pdf_review"]
    assert (batch["start_page"], batch["end_page"]) == (1, 2)
    packet = (library / batch["packet_ref"]).read_text(encoding="utf-8")
    assert first in packet and second in packet
    assert "THIRD_PAGE_MUST_WAIT" not in packet
    assert batch["text_units"] == len(packet) > 300


def test_exact_text_threshold_stops_after_that_whole_page(library, monkeypatch):
    text_pages(library, monkeypatch, ["a" * 100] * 3)
    one_page = prepare(library, review_page_budget=1)
    packet = (library / one_page["pdf_review"]["packet_ref"]).read_text(encoding="utf-8")
    task, phase = module("ingest").scan(library, {
        "source": "docs-raw/protocol.pdf", "review_text_budget": len(packet),
    })
    assert phase == "prepared", task
    assert task["pdf_review"]["end_page"] == 1
    assert task["pdf_review"]["text_units"] == len(packet)


@pytest.mark.parametrize(("budget", "expected_end"), [(1, 1), (4000000, 5)])
def test_text_budget_inclusive_limits_are_valid(library, budget, expected_end):
    task, phase = module("ingest").scan(library, {
        "source": "docs-raw/protocol.pdf", "review_text_budget": budget,
    })
    assert phase == "prepared", task
    assert task["pdf_review"]["end_page"] == expected_end


def test_one_oversized_page_is_neither_rejected_nor_truncated(library, monkeypatch):
    huge = "GIANT_BEGIN_" + "a" * 450000 + "_GIANT_END"
    text_pages(library, monkeypatch, [huge, "NEXT_PAGE_MUST_WAIT"])
    task, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared", task
    batch = task["pdf_review"]
    assert (batch["start_page"], batch["end_page"]) == (1, 1)
    packet = (library / batch["packet_ref"]).read_text(encoding="utf-8")
    assert huge in packet and "NEXT_PAGE_MUST_WAIT" not in packet
    assert batch["text_units"] == len(packet) > 400000
    plan(library, [[1, 1]])
    assert module("ingest").check(library, {})[1] == "passed"
    result, _ = module("ingest").commit(library, {"reason": "The complete oversized page was evaluated."})
    assert result["processing"]["reviewed_pages"] == [[1, 1]]


def test_text_units_weight_all_non_ascii_characters_and_include_structure_entries(library, monkeypatch):
    text_pages(library, monkeypatch, ["A中é😀\n\n| Cell |\n| --- |\n| TABLE |"], illustrated=True)
    task, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared", task
    batch = task["pdf_review"]
    packet = (library / batch["packet_ref"]).read_text(encoding="utf-8")
    # Exactly three non-ASCII characters each add three units over their Python character length.
    assert batch["text_units"] == len(packet) + 9
    assert "| TABLE |" in packet and "Image: " in packet
    index = json.loads((library / batch["page_index_ref"]).read_text(encoding="utf-8"))
    assert index["text_units"] == batch["text_units"]
    page = index["pages"][0]
    assert type(page["text_units"]) is int and page["text_units"] > 13
    assert page["image_count"] == 1 and page["table_count"] == 1


def test_pdf_handoff_summarizes_repeated_whole_book_diagnostics(library, monkeypatch):
    parser = module("document_parser")
    convert = parser._docling

    def noisy(*args):
        text, segments, images, gaps, pages = convert(*args)
        for number in range(3000):
            reference = f"#/pictures/{number}"
            images.append({"ref": None, "element_ref": reference, "provenance": []})
            gaps.append({"code": "IMAGE_UNAVAILABLE", "severity": "review",
                         "message": "An extracted picture has no saved local image",
                         "locator": {"kind": "element", "ref": reference}})
        return text, segments, images, gaps, pages

    monkeypatch.setattr(parser, "_docling", noisy)
    task = prepare(library)
    assert (library / ".build/task.json").stat().st_size < 12000
    assert task["source"]["parsed"]["parse_status"] == "partial"
    assert len(task["gaps"]) == 1 and "3000" in task["gaps"][0]
    index_path = library / task["pdf_review"]["page_index_ref"]
    assert index_path.stat().st_size < 12000
    index = json.loads(index_path.read_bytes())
    assert len(index["gaps"]) == 1 and index["gaps"][0]["count"] == 3000
    assert index["gap_details_ref"] == task["source"]["parsed"]["manifest_ref"]
    manifest = json.loads((library / index["gap_details_ref"]).read_bytes())
    assert len(manifest["gaps"]) == len(manifest["images"]) == 3000
    assert index["gaps"][0]["details_ref"] == index["gap_details_ref"]


def test_page_index_keeps_shared_image_provenance_local_without_changing_manifest(library, monkeypatch):
    text_pages(library, monkeypatch, ["First physical page", "Second physical page"], illustrated=True)
    parser = module("document_parser")
    convert = parser._docling

    def shared(*args):
        result = convert(*args)
        result[2][0]["provenance"].append({"page_no": 2})
        return result

    monkeypatch.setattr(parser, "_docling", shared)
    task = prepare(library)
    index = json.loads((library / task["pdf_review"]["page_index_ref"]).read_bytes())
    for page in index["pages"]:
        assert page["image_count"] == 1
        assert page["images"][0]["provenance"] == [{"page_no": page["page"]}]
    manifest_path = library / task["source"]["parsed"]["manifest_ref"]
    original = manifest_path.read_bytes()
    assert json.loads(original)["images"][0]["provenance"] == [{"page_no": 1}, {"page_no": 2}]
    plan(library, [[1, 2]])
    assert module("ingest").check(library, {})[1] == "passed"
    assert manifest_path.read_bytes() == original


def test_repeated_bitmap_draws_do_not_fill_the_reading_packet_with_identical_paths(library, monkeypatch):
    parser = module("document_parser")
    text_pages(library, monkeypatch, ["A physical page requirement."] * 5, illustrated=True)
    convert = parser._docling

    def repeated_draws(*args):
        text, segments, images, gaps, pages = convert(*args)
        repeated = [{**images[0], "element_ref": f"#/pictures/{number}"} for number in range(2000)]
        return text, segments, repeated, gaps, pages

    monkeypatch.setattr(parser, "_docling", repeated_draws)
    task = prepare(library, review_text_budget=5000)
    packet = (library / task["pdf_review"]["packet_ref"]).read_text(encoding="utf-8")
    index = json.loads((library / task["pdf_review"]["page_index_ref"]).read_bytes())
    manifest = json.loads((library / task["source"]["parsed"]["manifest_ref"]).read_bytes())
    reference = manifest["images"][0]["ref"]

    assert task["pdf_review"]["end_page"] == 2
    assert task["pdf_review"]["text_units"] < 5000
    assert packet.count("Image: " + reference) == 1
    assert "2000 drawing occurrences" in packet
    assert index["pages"][0]["image_count"] == len(index["pages"][0]["images"]) == 2000
    assert len({row["element_ref"] for row in index["pages"][0]["images"]}) == 2000
    assert len(manifest["images"]) == 2000


@pytest.mark.parametrize(("body", "expected_end"), [("sparse", 5), ("d" * 2000, 1)])
def test_same_text_budget_adapts_to_page_density(library, monkeypatch, body, expected_end):
    text_pages(library, monkeypatch, [body] * 5)
    task, phase = module("ingest").scan(library, {
        "source": "docs-raw/protocol.pdf", "review_text_budget": 1000,
    })
    assert phase == "prepared", task
    assert task["pdf_review"]["end_page"] == expected_end


@pytest.mark.parametrize(("body", "expected_end"), [("a" * 100, 3), ("中" * 100, 1)])
def test_text_budget_uses_unicode_weights_to_choose_pages(library, monkeypatch, body, expected_end):
    text_pages(library, monkeypatch, [body] * 5)
    task, phase = module("ingest").scan(library, {
        "source": "docs-raw/protocol.pdf", "review_text_budget": 400,
    })
    assert phase == "prepared", task
    assert task["pdf_review"]["end_page"] == expected_end


def test_explicit_thousand_page_limit_is_valid(library):
    (library / "docs-raw/protocol.pdf").write_bytes(pdf_bytes(1001))
    task = prepare(library, review_page_budget=1000)
    assert task["pdf_review"]["page_budget"] == 1000
    assert task["pdf_review"]["end_page"] == 1000


def test_agent_can_assess_less_than_the_candidate_and_resume_at_the_next_page(library):
    task, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared" and task["pdf_review"]["end_page"] == 5
    plan(library, [[1, 1]])
    assert module("ingest").check(library, {})[1] == "passed"
    result, _ = module("ingest").commit(library, {"reason": "Only the first physical page was assessed."})
    assert result["processing"]["reviewed_pages"] == [[1, 1]]
    assert result["remaining_pages"] == [[2, 5]]
    next_task, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared"
    assert (next_task["pdf_review"]["start_page"], next_task["pdf_review"]["end_page"]) == (2, 5)


def test_candidate_stops_at_the_end_of_the_first_unreviewed_interval(library):
    task = prepare(library)
    with module("catalog").Catalog(library) as catalog:
        catalog.record_pdf_review(task["source"]["source_id"], task["source"]["hash"], [[3, 4]], 5)
    resumed, phase = module("ingest").scan(library, {"source": "docs-raw/protocol.pdf"})
    assert phase == "prepared"
    assert resumed["pdf_review"]["remaining_pages"] == [[1, 2], [5, 5]]
    assert (resumed["pdf_review"]["start_page"], resumed["pdf_review"]["end_page"]) == (1, 2)


@pytest.mark.parametrize(("field", "value"), [
    ("text_budget", True), ("text_budget", 1), ("text_units", True), ("text_units", 0),
])
def test_modified_text_budget_metadata_cannot_be_applied(library, field, value):
    task = prepare(library)
    plan(library, [[1, 2]])
    task["pdf_review"][field] = value
    (library / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    registry = (library / "governance/sources.lock.yaml").read_bytes()
    result, phase = module("ingest").check(library, {})
    assert phase == "failed", result
    assert result["findings"][0]["code"].startswith("PDF_REVIEW_")
    with pytest.raises(ValueError, match="PDF_REVIEW_"):
        module("ingest").commit(library, {"reason": "Cannot publish modified budget metadata."})
    assert (library / "governance/sources.lock.yaml").read_bytes() == registry


@pytest.mark.parametrize(("field", "value"), [("kind", "code"), ("path", "docs-raw/pretend.md"),
                                               ("exists", False)])
def test_task_identity_cannot_turn_a_pdf_into_an_unscoped_apply(library, field, value):
    task = prepare(library)
    plan(library, None)
    task["source"][field] = value
    (library / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    checked, phase = module("ingest").check(library, {})
    assert phase == "failed", checked
    assert checked["findings"][0]["code"] == "SOURCE_IDENTITY_CHANGED"
    with pytest.raises(ValueError, match="SOURCE_IDENTITY_CHANGED"):
        module("ingest").commit(library, {"reason": "Cannot downgrade PDF scope."})
