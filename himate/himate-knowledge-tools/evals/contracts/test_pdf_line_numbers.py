"""Printed PDF line numbers leave reading views without losing source locations."""

from io import BytesIO
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.contracts import module

parser = module("document_parser")


def draft_pdf():
    """Two margin-number pages plus legitimate numbered-list/table controls."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for name, number_x, body_x in (
        ("left_margin", 30, 86), ("right_margin", 580, 80),
        ("numbered_list", 75, 95), ("numeric_column", 240, 80),
    ):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        commands = []

        def text(x, y, value, size=9):
            escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET".encode())

        text(80, 763, "Synthetic draft: " + name, 12)
        for number in range(1, 66):
            y = 740 - number * 10
            if name == "numeric_column":
                text(body_x, y, "Row identifier")
                text(320, y, f"Value {100 + number}")
            else:
                text(body_x, y, f"Clause {number}. Requirement stays measurable; value 65 is preserved.")
        for number in range(1, 66):
            text(number_x, 740 - number * 10, str(number), 8)
        text(80, 50, "6.5.7.3.3 When generated: 1 2 3 and 65 are meaningful.", 10)
        content = DecodedStreamObject()
        content.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture(scope="module")
def parsed_draft(tmp_path_factory):
    root = tmp_path_factory.mktemp("printed-lines")
    data = draft_pdf()
    source = {"id": "synthetic-printed-lines", "path": "docs-raw/specs/draft.pdf"}
    descriptor = parser.parse(root, source, data, ".build/materials/parsed")
    loaded = parser.load(root, descriptor, expected_source_id=source["id"],
                         expected_sha256=parser.sha256_bytes(data))
    return root, data, descriptor, loaded


def numeric_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip().isdigit()]


def test_native_margin_numbers_are_omitted_from_all_reading_views(parsed_draft):
    _root, _data, descriptor, loaded = parsed_draft
    pages = {row["locator"]["page"]: row["text"] for row in loaded["locators"]["segments"]
             if row["locator"]["kind"] == "page"}
    for page in (1, 2):
        assert numeric_lines(pages[page]) == [], f"Printed line numbers leaked on physical page {page}"
    for page in (3, 4):
        assert numeric_lines(pages[page]) == [str(number) for number in range(1, 66)]
    assert len(numeric_lines(loaded["text"])) == 130
    assert len(numeric_lines(loaded["markdown"])) == 130
    for page in (1, 2, 3):
        for number in range(1, 66):
            assert f"Clause {number}. Requirement stays measurable; value 65 is preserved." in pages[page]
    for number in range(101, 166):
        assert f"Value {number}" in pages[4]
    assert all("6.5.7.3.3 When generated: 1 2 3 and 65 are meaningful." in text
               for text in pages.values())
    assert descriptor["source_sha256"] == parser.sha256_bytes(_data)


def test_hidden_margin_numbers_remain_available_by_public_element_locator(parsed_draft):
    _root, data, descriptor, loaded = parsed_draft
    numeric = [row for row in loaded["document"]["texts"] if row["text"].isdigit()]
    assert len(numeric) == 260
    hidden = [row for row in numeric if row["content_layer"] == "furniture"]
    assert len(hidden) == 130
    for row in hidden:
        assert row["prov"][0]["page_no"] in (1, 2)
        assert row["prov"][0]["bbox"]["l"] in (30, 580)
        locator = {"kind": "element", "ref": row["self_ref"],
                   "source_sha256": descriptor["source_sha256"],
                   "profile_sha256": descriptor["profile_sha256"]}
        assert parser.select(loaded, locator) == [{"locator": locator, "text": row["text"]}]
    assert descriptor["source_sha256"] == parser.sha256_bytes(data)


def test_ingest_packet_uses_cleaned_page_text_with_numeric_controls_intact(parsed_draft):
    _root, _data, _descriptor, loaded = parsed_draft
    packet, index = module("ingest")._pdf_packet(loaded, 1, 4)
    text = packet.decode("utf-8")
    assert len(numeric_lines(text)) == 130
    assert [row["page"] for row in index["pages"]] == [1, 2, 3, 4]
    assert "6.5.7.3.3 When generated" in text
    assert "Clause 65. Requirement stays measurable; value 65 is preserved." in text


def structured_draft(*, side="left", origin="TOPLEFT", scale=1, align="left",
                     ancestor=None, header=False, close_body=False, values=None):
    """Explicit structure exercises guards that native text-only PDFs cannot label."""
    from docling_core.types.doc import (
        BoundingBox, CoordOrigin, DoclingDocument, DocItemLabel, GroupLabel,
        ProvenanceItem, Size, TableData,
    )

    document = DoclingDocument(name="synthetic-margin-layout")
    document.add_page(page_no=1, size=Size(width=612 * scale, height=792 * scale))

    def prov(left, top, right, bottom, length):
        box = BoundingBox(l=left * scale, t=top * scale, r=right * scale,
                          b=bottom * scale, coord_origin=CoordOrigin.TOPLEFT)
        if origin == "BOTTOMLEFT":
            box = box.to_bottom_left_origin(page_height=792 * scale)
        return ProvenanceItem(page_no=1, bbox=box, charspan=(0, length))

    parent = None
    if ancestor == "list":
        parent = document.add_group(label=GroupLabel.ORDERED_LIST)
    elif ancestor == "table":
        parent = document.add_table(data=TableData(num_rows=65, num_cols=1, table_cells=[]),
                                    prov=prov(20, 60, 600, 730, 0))
    elif ancestor == "picture":
        parent = document.add_picture(prov=prov(20, 60, 600, 730, 0))
    elif ancestor == "code":
        parent = document.add_code(text="counter = 65", prov=prov(20, 60, 600, 730, 12))
    if header:
        document.add_text(label=DocItemLabel.TEXT, text="Row", prov=prov(30, 45, 45, 53, 3))
    items = []
    for index, value in enumerate(values if values is not None else range(1, 66)):
        text = str(value)
        width = 4 * len(text)
        left = (30 if side == "left" else 580)
        if align == "right":
            left += 8 - width
        top = 70 + index * 10
        item = document.add_text(label=DocItemLabel.TEXT, text=text, parent=parent,
                                 prov=prov(left, top, left + width, top + 8, len(text)))
        items.append(item)
        body_left = 44 if close_body else 86
        document.add_text(label=DocItemLabel.TEXT, text=f"Requirement {index + 1} retains 65.",
                          prov=prov(body_left, top, 440, top + 8, 27))
    return document, items


@pytest.mark.parametrize("side,origin,scale,align", [
    ("left", "TOPLEFT", 1, "left"),
    ("right", "TOPLEFT", 1, "right"),
    ("left", "BOTTOMLEFT", 1, "right"),
    ("right", "BOTTOMLEFT", 1.5, "left"),
])
def test_layout_rule_handles_both_margins_origins_sizes_and_numeric_alignment(side, origin, scale, align):
    document, items = structured_draft(side=side, origin=origin, scale=scale, align=align)
    before = {item.self_ref: (item.text, item.orig, [prov.model_dump() for prov in item.prov])
              for item in document.texts}
    selected = module("pdf_text").mark_margin_line_numbers(document)
    assert selected == {item.self_ref for item in items}
    assert all(item.content_layer.value == "furniture" for item in items)
    assert before == {item.self_ref: (item.text, item.orig, [prov.model_dump() for prov in item.prov])
                      for item in document.texts}
    assert module("pdf_text").mark_margin_line_numbers(document) == set()


@pytest.mark.parametrize("ancestor", ["list", "table", "picture", "code"])
def test_margin_shaped_numbers_inside_semantic_structures_are_preserved(ancestor):
    document, items = structured_draft(ancestor=ancestor)
    assert module("pdf_text").mark_margin_line_numbers(document) == set()
    assert all(item.content_layer.value == "body" for item in items)


@pytest.mark.parametrize("extra", [
    {"header": True},
    {"close_body": True},
    {"values": range(1, 12)},
    {"values": [*range(1, 32), *range(33, 67)]},
    {"values": range(5, 70)},
    {"values": [f"{number:02}" for number in range(1, 66)]},
    {"values": [f"{number}\n{number + 1}" for number in range(1, 66)]},
    {"values": [str(number).translate(str.maketrans("0123456789", "０１２３４５６７８９"))
                for number in range(1, 66)]},
])
def test_ambiguous_or_incomplete_numeric_columns_are_not_hidden(extra):
    document, items = structured_draft(**extra)
    assert module("pdf_text").mark_margin_line_numbers(document) == set()
    assert all(item.content_layer.value == "body" for item in items)


def test_text_profile_upgrade_builds_new_cache_and_keeps_old_bundle_readable(tmp_path, monkeypatch):
    source = {"id": "synthetic-line-cache", "path": "docs-raw/specs/draft.pdf"}
    data = draft_pdf()
    current_profile = parser._profile
    with monkeypatch.context() as old:
        def previous_profile(*args):
            profile = current_profile(*args)
            profile.pop("text_export", None)
            return profile

        old.setattr(parser, "_profile", previous_profile)
        old.setattr(module("pdf_text"), "mark_margin_line_numbers", lambda document: set())
        first = parser.prepare_pdf(tmp_path, source, data)
    old_bundle = (tmp_path / first["manifest_ref"]).parent
    fixed = {path.relative_to(old_bundle): path.read_bytes()
             for path in old_bundle.rglob("*") if path.is_file()}
    current = parser.prepare_pdf(tmp_path, source, data)
    assert current["profile_sha256"] != first["profile_sha256"]
    assert current["manifest_ref"] != first["manifest_ref"]
    assert parser.prepare_pdf(tmp_path, source, data) == current
    assert {path.relative_to(old_bundle): path.read_bytes()
            for path in old_bundle.rglob("*") if path.is_file()} == fixed
    old_loaded = parser.load(tmp_path, first, expected_source_id=source["id"],
                             expected_sha256=parser.sha256_bytes(data))
    new_loaded = parser.load(tmp_path, current, expected_source_id=source["id"],
                             expected_sha256=parser.sha256_bytes(data))
    assert "text_export" not in old_loaded["manifest"]["profile"]
    assert new_loaded["manifest"]["profile"]["text_export"] == "margin-line-numbers:1"
    assert len(numeric_lines(old_loaded["text"])) == 260
    assert len(numeric_lines(old_loaded["markdown"])) == 260
    assert len(numeric_lines(new_loaded["text"])) == 130
    assert len(numeric_lines(new_loaded["markdown"])) == 130
    old_numeric = [row for row in old_loaded["document"]["texts"] if row["text"].isdigit()]
    assert len(old_numeric) == 260
    for row in old_numeric:
        locator = {"kind": "element", "ref": row["self_ref"],
                   "source_sha256": first["source_sha256"],
                   "profile_sha256": first["profile_sha256"]}
        assert parser.select(old_loaded, locator) == [{"locator": locator, "text": row["text"]}]


def test_existing_furniture_is_retained_in_structure_but_not_added_to_reading_or_segments(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from docling_core.types.doc import (
        BoundingBox, ContentLayer, DocItemLabel, ProvenanceItem,
    )
    from pypdf import PdfWriter

    document, _items = structured_draft()
    furniture_text = "Existing page furniture remains outside body text."
    furniture = document.add_text(label=DocItemLabel.TEXT, text=furniture_text,
                                  content_layer=ContentLayer.FURNITURE,
                                  prov=ProvenanceItem(page_no=1, charspan=(0, len(furniture_text)),
                                      bbox=BoundingBox(l=80, t=20, r=400, b=28)))
    result = SimpleNamespace(document=document, status="success", errors=[])
    converter = SimpleNamespace(convert=lambda *args, **kwargs: result)
    monkeypatch.setattr(parser, "_converter", lambda *args: converter)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    stream = BytesIO()
    writer.write(stream)
    data = stream.getvalue()
    descriptor = parser.parse(tmp_path, {"id": "synthetic-existing-furniture",
                              "path": "docs-raw/furniture.pdf"}, data, ".build/materials/parsed")
    loaded = parser.load(tmp_path, descriptor, expected_source_id="synthetic-existing-furniture",
                         expected_sha256=parser.sha256_bytes(data))
    assert furniture_text not in loaded["text"]
    assert furniture_text not in loaded["markdown"]
    assert all(furniture_text not in row["text"] for row in loaded["locators"]["segments"])
    assert not any(row["locator"].get("ref") == furniture.self_ref
                   for row in loaded["locators"]["segments"])
    kept = [row for row in loaded["document"]["texts"] if row["self_ref"] == furniture.self_ref]
    assert len(kept) == 1 and kept[0]["text"] == furniture_text
    assert kept[0]["content_layer"] == "furniture"
    assert numeric_lines(loaded["text"]) == []


def test_independent_page_extract_uses_same_rule_without_touching_ingest_staging(tmp_path):
    source_read = module("source_read")
    staging = tmp_path / ".build/keep.txt"
    staging.parent.mkdir()
    staging.write_bytes(b"Existing ingest batch remains untouched.")
    data = draft_pdf()
    source = {"id": "synthetic-line-extract", "path": "docs-raw/specs/draft.pdf"}
    reading = source_read.create(tmp_path, source, data, page_range=[2, 2])
    try:
        loaded = parser.load(tmp_path, reading["parsed"], expected_source_id=source["id"],
                             expected_sha256=parser.sha256_bytes(data))
        assert numeric_lines(loaded["text"]) == []
        assert numeric_lines(loaded["markdown"]) == []
        rows = parser.select(loaded, {"kind": "page", "page": 2})
        assert len(rows) == 1 and numeric_lines(rows[0]["text"]) == []
        assert "Clause 65. Requirement stays measurable" in rows[0]["text"]
        hidden = [row for row in loaded["document"]["texts"] if row["content_layer"] == "furniture"]
        assert len(hidden) == 65
        assert all(row["prov"][0]["page_no"] == 2 for row in hidden)
    finally:
        source_read.release(tmp_path, reading["read_id"])
    assert staging.read_bytes() == b"Existing ingest batch remains untouched."


def test_real_ingest_commits_reviewed_range_then_resumes_cleaned_cached_pages(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts", ".build"):
        (root / name).mkdir(parents=True)
    (root / ".build/README.md").write_bytes(b"Local staging only.\r\n")
    data = draft_pdf()
    (root / "docs-raw/draft.pdf").write_bytes(data)
    ingest = module("ingest")
    task, phase = ingest.scan(root, {"source": "docs-raw/draft.pdf", "review_page_budget": 1})
    assert phase == "prepared", task
    assert task["pdf_review"]["start_page"] == task["pdf_review"]["end_page"] == 1
    packet = (root / task["pdf_review"]["packet_ref"]).read_text(encoding="utf-8")
    assert numeric_lines(packet) == []
    assert "Clause 65. Requirement stays measurable" in packet
    assert (root / task["source"]["original_ref"]).read_bytes() == data
    bundle = (root / task["source"]["parsed"]["manifest_ref"]).parent
    fixed = {path.relative_to(bundle): path.read_bytes()
             for path in bundle.rglob("*") if path.is_file()}
    (root / ".build/plan.md").write_text(
        "---\ncards: []\nsource_pages: [[1, 1]]\n---\n"
        "All content on physical page one was evaluated; it adds no knowledge card.\n",
        encoding="utf-8")
    checked, phase = ingest.check(root, {})
    assert phase == "passed", checked
    result, phase = ingest.commit(root, {"reason": "The assessed reference page adds no new card."})
    assert phase == "completed", result
    assert result["source_complete"] is False
    assert result["processing"]["reviewed_pages"] == [[1, 1]]
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    resumed, phase = ingest.scan(root, {"source": "docs-raw/draft.pdf", "review_page_budget": 1})
    assert phase == "prepared", resumed
    assert resumed["pdf_review"]["start_page"] == resumed["pdf_review"]["end_page"] == 2
    assert resumed["pdf_review"]["reviewed_pages"] == [[1, 1]]
    assert resumed["source"]["parsed"]["manifest_ref"] == task["source"]["parsed"]["manifest_ref"]
    resumed_packet = (root / resumed["pdf_review"]["packet_ref"]).read_text(encoding="utf-8")
    assert numeric_lines(resumed_packet) == []
    assert "Clause 65. Requirement stays measurable" in resumed_packet
    assert (root / "governance/sources.lock.yaml").read_bytes() == registry
    assert {path.relative_to(bundle): path.read_bytes()
            for path in bundle.rglob("*") if path.is_file()} == fixed
