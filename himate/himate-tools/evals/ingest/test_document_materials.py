"""A complete conversion and the P2 reading range have separate lifetimes."""

from pathlib import Path
import sys
from io import BytesIO
import json
from zipfile import ZipFile

import pytest
import yaml

evals = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(evals), str(evals / "support")]
from build_document_corpus import figure, long_pdf, scanned_pdf, word, workbook
from contracts import module


@pytest.fixture
def knowledge(tmp_path):
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (tmp_path / name).mkdir()
    return tmp_path


def run_scan(root, name, **request):
    return module("ingest").scan(root, {"source": "docs-raw/" + name, **request})


def write_plan(root, start, end):
    metadata = {"cards": [], "source_units": [[start, end]]}
    (root / ".build/plan.md").write_text("---\n" + yaml.safe_dump(metadata) + "---\nNo new cards.\n", encoding="utf-8")


def test_long_pdf_converts_all_pages_while_review_is_bounded(knowledge):
    long_pdf(knowledge / "docs-raw/long.pdf", 2001)
    task, phase = run_scan(knowledge, "long.pdf")
    assert phase == "prepared", task
    parsed = task["source"]["parsed"]
    assert parsed["statistics"]["page_count"] == 2001
    markdown = (knowledge / parsed["markdown_ref"]).read_text(encoding="utf-8")
    assert "PDF PAGE 00001 CHECK" in markdown and "PDF PAGE 02001 CHECK" in markdown
    review = task["document_review"]
    packet = (knowledge / review["packet_ref"]).read_bytes()
    assert len(packet) <= 76_000
    assert review["end_unit"] < review["total_units"]


def test_corrupt_pdf_is_blocked_before_a_review_task_exists(knowledge):
    (knowledge / "docs-raw/broken.pdf").write_bytes(b"%PDF-1.7\nbroken body")
    data, phase = run_scan(knowledge, "broken.pdf")
    assert phase == "blocked", data
    assert any("PDF_PAGE_COUNT_UNAVAILABLE" in gap for gap in data["gaps"])
    assert not (knowledge / ".build/task.json").exists()


@pytest.mark.parametrize("name,tail", [("report.docx", "WORD TABLE ROW 100"),
                                      ("measures.xlsx", "XLSX ROW 3000 CHECK")])
def test_office_full_markdown_inline_ocr_and_resume(knowledge, monkeypatch, name, tail):
    material = module("document_material")
    monkeypatch.setattr(material, "image_reader", lambda *args: lambda path: "OCR FIGURE VALUE 42")
    builder = word if name.endswith(".docx") else workbook
    builder(knowledge / "docs-raw" / name, figure())
    task, phase = run_scan(knowledge, name, review_text_budget=4000)
    assert phase == "prepared", task
    parsed = task["source"]["parsed"]
    markdown = (knowledge / parsed["markdown_ref"]).read_text(encoding="utf-8")
    image = next(line for line in markdown.splitlines() if "![" in line and "images/" in line)
    assert "OCR FIGURE VALUE 42" in markdown.split(image, 1)[1]
    assert tail in markdown
    if name.endswith(".xlsx"):
        loaded = module("document_parser").load(knowledge, parsed, expected_source_id=task["source"]["source_id"],
                                                 expected_sha256=task["source"]["hash"])
        assert any(row["text"] == "XLSX MERGED CHECK" for row in module("document_parser").select(
            loaded, {"kind": "cell_range", "sheet": "Offset", "range": "B12:D12"}))
    review = task["document_review"]
    assert (knowledge / review["packet_ref"]).stat().st_size <= 4000
    write_plan(knowledge, review["start_unit"], review["start_unit"])
    assert module("ingest").check(knowledge, {})[1] == "passed"
    receipt, phase = module("ingest").commit(knowledge, {"reason": "Selected material has no knowledge changes."})
    assert phase == "completed" and not receipt["source_complete"]
    next_task, phase = run_scan(knowledge, name, review_text_budget=4000)
    assert phase == "prepared"
    assert next_task["document_review"]["start_unit"] == review["start_unit"] + 1
    assert next_task["source"]["parsed"]["manifest_sha256"] == parsed["manifest_sha256"]


def test_pdf_scan_ocr_belongs_below_the_original_image(knowledge, monkeypatch):
    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "OCR SCAN PAGE TWO")
    scanned_pdf(knowledge / "docs-raw/scan.pdf")
    task, phase = run_scan(knowledge, "scan.pdf")
    assert phase == "prepared", task
    assert task["source"]["parsed"]["parse_status"] == "parsed"
    markdown = (knowledge / task["source"]["parsed"]["markdown_ref"]).read_text(encoding="utf-8")
    second = markdown.split("## Physical page 2", 1)[1]
    assert second.index("![") < second.index("OCR SCAN PAGE TWO")
    review = task["document_review"]
    for variant in ("packet_ref", "index_ref"):
        assert (knowledge / review[variant]).is_file()
    packet = knowledge / review["packet_ref"]
    packet.write_bytes(packet.read_bytes() + b"\nWrong material\n")
    write_plan(knowledge, review["start_unit"], review["end_unit"])
    failure, phase = module("ingest").check(knowledge, {})
    assert phase == "failed" and failure["findings"][0]["code"] == "DOCUMENT_REVIEW_MATERIAL_CHANGED"


def test_one_large_pdf_page_is_reviewed_in_parts_before_completion(knowledge, monkeypatch):
    from pypdf import PdfWriter

    source = knowledge / "docs-raw/dense.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    writer.write(source)
    body = "BEGIN " + "测" * 58_000 + " END"

    def convert(_root, _source, _data, output, _options, _range, _source_hash, _profile_hash):
        (output / "document.md").write_bytes(("<!-- physical-page:1 -->\n## Physical page 1\n\n" + body).encode("utf-8"))
        (output / "document.json").write_bytes(b'{"pictures":[]}')
        return body, [{"locator": {"kind": "page", "page": 1}, "text": body}], [], [], [1]

    monkeypatch.setattr(module("document_parser"), "_docling", convert)
    packets = BytesIO()
    for batch_number in range(1, 4):
        task, phase = run_scan(knowledge, "dense.pdf", review_text_budget=4_000_000)
        assert phase == "prepared", task
        scope = task["document_review"]
        assert scope["start_unit"] == batch_number
        assert scope["end_unit"] == batch_number
        packet = (knowledge / scope["packet_ref"]).read_bytes()
        assert len(packet) <= 76_000
        packet.decode("utf-8")
        packets.write(packet)
        write_plan(knowledge, batch_number, batch_number)
        assert module("ingest").check(knowledge, {})[1] == "passed"
        receipt, phase = module("ingest").commit(knowledge, {"reason": "This part has no knowledge changes."})
        assert phase == "completed" and receipt["source_complete"] == (batch_number == 3)
    assert packets.getvalue() == (knowledge / scope["markdown_ref"]).read_bytes()
    assert run_scan(knowledge, "dense.pdf")[1] == "unchanged"


def test_unavailable_ocr_can_retry_same_source_without_publishing_a_partial_cache(knowledge, monkeypatch):
    material = module("document_material")
    source = knowledge / "docs-raw/scan.pdf"
    scanned_pdf(source)

    def unavailable(*args):
        raise module("validation").ContractError("PARSER_MODELS_REQUIRED", "OCR unavailable")

    monkeypatch.setattr(material, "image_reader", unavailable)
    failed, phase = run_scan(knowledge, "scan.pdf")
    assert phase == "blocked" and failed["source"]["parsed"]["parse_status"] == "partial"
    assert [item["code"] for item in failed["diagnostics"]] == ["PARSER_MODELS_REQUIRED"]
    assert not (knowledge / ".build/task.json").exists()
    assert not list((knowledge / "artifacts/ingest/parsed").glob("*.json"))
    monkeypatch.setattr(material, "image_reader", lambda *args: lambda path: "SCAN RECOVERED")
    prepared, phase = run_scan(knowledge, "scan.pdf")
    assert phase == "prepared", prepared
    assert prepared["source"]["source_id"] == failed["source"]["source_id"]
    assert prepared["source"]["parsed"]["parse_status"] == "parsed"
    assert prepared["source"]["parsed"]["manifest_sha256"] != failed["source"]["parsed"]["manifest_sha256"]


def test_word_table_retains_image_ocr_inside_its_cell_and_keeps_header(knowledge, monkeypatch):
    from docx import Document

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "IMAGE LIMIT | 42")
    document = Document()
    document.sections[0].header.paragraphs[0].text = "HEADER CHECK"
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Figure"
    table.cell(0, 1).text = "Measurement"
    table.cell(1, 0).paragraphs[0].add_run().add_picture(BytesIO(figure()))
    table.cell(1, 1).text = "RIGHT CELL CHECK"
    document.save(knowledge / "docs-raw/table.docx")
    task, phase = run_scan(knowledge, "table.docx")
    assert phase == "prepared", task
    text = (knowledge / task["document_review"]["markdown_ref"]).read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "RIGHT CELL CHECK" in line)
    assert row.startswith("|") and "![Image](images/" in row and "<br>OCR<br>IMAGE LIMIT" in row
    assert "HEADER CHECK" in text


def docx_png(mode, size, color):
    from PIL import Image

    stream = BytesIO()
    Image.new(mode, size, color).save(stream, format="PNG")
    stream.seek(0)
    return stream


@pytest.mark.parametrize("extension,hidden,renderer,needs_libreoffice", [
    ("emf", False, None, True),
    ("wmf", True, None, False),
    ("png", False, None, False),
    ("emf", False, "configured-renderer", False),
])
def test_word_renderer_required_only_for_visible_unrendered_vector_picture(
        knowledge, monkeypatch, extension, hidden, renderer, needs_libreoffice):
    from docling.backend import msword_backend
    from docling.backend.docx.drawingml import utils as drawingml
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.document_converter import DocumentConverter, WordFormatOption
    from docx import Document

    monkeypatch.setattr(msword_backend, "get_docx_to_pdf_converter", lambda: None)
    monkeypatch.setattr(drawingml, "get_libreoffice_cmd", lambda: renderer)
    word_document = Document()
    picture = word_document.add_picture(docx_png("RGB", (40, 25), "blue"))
    if hidden:
        picture._inline.docPr.set("hidden", "1")
    packaged = BytesIO()
    word_document.save(packaged)
    stream = BytesIO()
    with ZipFile(packaged) as original, ZipFile(stream, "w") as sample:
        for member in original.namelist():
            data = original.read(member)
            if member == "word/media/image1.png":
                member = "word/media/image1." + extension
                data = b"Opaque picture bytes requiring the fallback renderer"
            elif member in {"[Content_Types].xml", "word/_rels/document.xml.rels"} and extension != "png":
                data = data.replace(b".png", ("." + extension).encode("ascii"))
                data = data.replace(b'Extension="png" ContentType="image/png"',
                                    f'Extension="{extension}" ContentType="image/x-{extension}"'.encode("ascii"))
            sample.writestr(member, data)
    stream.seek(0)
    source_bytes = stream.getvalue()

    pictures = module("docx_pictures")
    converter = DocumentConverter(allowed_formats=[InputFormat.DOCX], format_options={
        InputFormat.DOCX: WordFormatOption(backend=pictures.docx_picture_backend()),
    })
    result = converter.convert(DocumentStream(name="drawing.docx", stream=stream))
    _, _, omitted, missing, renderer_required = pictures.export_docx(
        result.document, result.input._backend, knowledge / "artifacts", None, max_bytes=10000, max_images=10,
    )

    assert missing == (0 if hidden else 1)
    assert bool(omitted) == hidden
    assert renderer_required is needs_libreoffice
    if needs_libreoffice:
        (knowledge / "docs-raw/drawing.docx").write_bytes(source_bytes)
        task, phase = run_scan(knowledge, "drawing.docx")
        assert phase == "blocked", task
        assert [item["code"] for item in task["diagnostics"]] == ["LIBREOFFICE_MISSING"]
        assert not (knowledge / ".build/task.json").exists()


def test_word_skips_blank_and_header_images_but_keeps_header_text(knowledge, monkeypatch):
    from docx import Document
    from PIL import Image

    ocr_inputs = []

    def read_image(path):
        with Image.open(module("document_parser").native_path(path)) as image:
            ocr_inputs.append((image.size, image.convert("RGB").getpixel((0, 0))))
        return "BODY FIGURE OCR"

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: read_image)
    document = Document()
    document.add_picture(docx_png("RGBA", (40, 20), (255, 255, 255, 0)))
    document.add_picture(docx_png("RGB", (45, 25), "white"))
    document.add_paragraph("BODY CHECK")
    document.add_picture(docx_png("RGB", (60, 40), "blue"))
    header = document.sections[0].header.paragraphs[0]
    header.text = "HEADER CHECK"
    header.add_run().add_picture(docx_png("RGB", (24, 24), "red"))
    original = knowledge / "docs-raw/figures.docx"
    document.save(original)
    original_bytes = original.read_bytes()

    task, phase = run_scan(knowledge, "figures.docx")

    assert phase == "prepared", task
    assert original.read_bytes() == original_bytes
    parsed = task["source"]["parsed"]
    assert parsed["parse_status"] == "parsed"
    loaded = module("document_parser").load(knowledge, parsed, expected_source_id=task["source"]["source_id"],
                                             expected_sha256=task["source"]["hash"])
    assert "BODY CHECK" in loaded["markdown"] and "HEADER CHECK" in loaded["markdown"]
    assert loaded["markdown"].count("![Image](images/") == 1 and "<!-- image -->" not in loaded["markdown"]
    assert "BODY FIGURE OCR" in loaded["markdown"]
    assert "data:image" not in json.dumps(loaded["document"])
    assert [item["element_ref"] for item in loaded["manifest"]["images"] if item["ref"]] == ["#/pictures/2"]
    assert ocr_inputs == [((60, 40), (0, 0, 255))]


def test_word_missing_body_picture_still_blocks_with_decorations(knowledge, monkeypatch):
    from docx import Document

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "")
    document = Document()
    document.add_picture(docx_png("RGB", (45, 25), "white"))
    document.add_picture(docx_png("RGB", (60, 40), "blue"))
    document.add_picture(docx_png("RGB", (70, 50), "green"))
    header = document.sections[0].header.paragraphs[0]
    header.add_run().add_picture(docx_png("RGB", (24, 24), "red"))
    packaged = BytesIO()
    document.save(packaged)
    packaged.seek(0)
    with ZipFile(packaged) as original, ZipFile(knowledge / "docs-raw/broken.docx", "w") as broken:
        for member in original.namelist():
            data = original.read(member)
            if member == "word/document.xml":
                # rId for the final body image points to a relation absent from this document.
                before, marker, after = data.rpartition(b'r:embed="')
                assert marker and after.startswith(b"rId")
                data = before + marker + b"rId999999" + after[after.index(b'"'):]
            broken.writestr(member, data)

    task, phase = run_scan(knowledge, "broken.docx")

    assert phase == "blocked", task
    source = task["source"]
    materials = module("document_parser").load(knowledge, source["parsed"], expected_source_id=source["source_id"],
                                                expected_sha256=source["hash"])
    [gap] = materials["manifest"]["gaps"]
    assert gap["code"] == "IMAGE_UNAVAILABLE" and gap["locator"]["ref"] == "#/pictures/2"
    assert not (knowledge / ".build/task.json").exists()


def test_word_keeps_tiny_colored_body_image(knowledge, monkeypatch):
    from docx import Document
    from PIL import Image

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "TINY FIGURE OCR")
    document = Document()
    document.add_paragraph("TINY FIGURE CHECK")
    document.add_picture(docx_png("RGB", (5, 5), "red"))
    document.save(knowledge / "docs-raw/tiny.docx")

    task, phase = run_scan(knowledge, "tiny.docx")

    assert phase == "prepared", task
    parser = module("document_parser")
    source = task["source"]
    materials = parser.load(knowledge, source["parsed"], expected_source_id=source["source_id"],
                            expected_sha256=source["hash"])
    assert "TINY FIGURE OCR" in materials["markdown"]
    [image] = [item for item in materials["manifest"]["images"] if item["ref"]]
    with Image.open(parser.native_path(knowledge / image["ref"])) as bitmap:
        assert bitmap.size == (5, 5)
        assert bitmap.convert("RGB").getpixel((0, 0)) == (255, 0, 0)


def test_word_omits_only_the_hidden_occurrence_of_a_shared_picture(knowledge, monkeypatch):
    from docx import Document

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "SHARED OCR")
    document = Document()
    shared_picture = docx_png("RGB", (60, 40), "blue").getvalue()
    hidden = document.add_paragraph().add_run()
    hidden.font.hidden = True
    hidden.add_picture(BytesIO(shared_picture))
    hidden_drawing = document.add_picture(BytesIO(shared_picture))
    hidden_drawing._inline.docPr.set("hidden", "1")
    hidden_picture = document.add_picture(BytesIO(shared_picture))
    hidden_picture._inline.graphic.graphicData.pic.nvPicPr.cNvPr.set("hidden", "1")
    document.add_picture(BytesIO(shared_picture))
    document.add_picture(BytesIO(shared_picture))
    document.save(knowledge / "docs-raw/shared.docx")

    task, phase = run_scan(knowledge, "shared.docx")

    assert phase == "prepared", task
    source = task["source"]
    parser = module("document_parser")

    def assert_visible_occurrences(parsed):
        materials = parser.load(knowledge, parsed, expected_source_id=source["source_id"],
                                expected_sha256=source["hash"])
        figures = [item for item in materials["manifest"]["images"] if item["ref"]]
        assert [item["element_ref"] for item in figures] == ["#/pictures/3", "#/pictures/4"]
        assert figures[0]["ref"] == figures[1]["ref"]
        assert materials["markdown"].count("![Image](images/") == 2

    assert_visible_occurrences(source["parsed"])
    library = module("library")
    reading, phase = library.sources(knowledge, "extract", {"source_id": source["source_id"]})
    assert phase == "extracted", reading
    assert_visible_occurrences(reading["parsed"])
    assert library.sources(knowledge, "release", {"read_id": reading["read_id"]})[1] == "released"


def test_workbook_retains_hidden_sheet_and_formula_without_cached_value(knowledge):
    from openpyxl import Workbook

    book = Workbook()
    book.active["A1"] = "Visible"
    book.active["B2"] = "=4+19"
    hidden = book.create_sheet("Hidden Values")
    hidden.sheet_state = "hidden"
    hidden["D4"] = "HIDDEN SHEET CHECK"
    book.save(knowledge / "docs-raw/formula.xlsx")
    task, phase = run_scan(knowledge, "formula.xlsx")
    assert phase == "prepared", task
    text = (knowledge / task["document_review"]["markdown_ref"]).read_text(encoding="utf-8")
    assert "Formula B2" in text and "4+19" in text and "HIDDEN SHEET CHECK" in text


def test_p5_rejects_expanding_the_checked_plan(knowledge):
    long_pdf(knowledge / "docs-raw/review.pdf", 12)
    task, phase = run_scan(knowledge, "review.pdf")
    assert phase == "prepared", task
    write_plan(knowledge, 1, 1)
    assert module("ingest").check(knowledge, {})[1] == "passed"
    write_plan(knowledge, 1, 12)
    with pytest.raises(ValueError, match="DOCUMENT_REVIEW_NOT_CHECKED"):
        module("ingest").commit(knowledge, {"reason": "The first page was reviewed."})
    with module("catalog").Catalog(knowledge) as catalog:
        current = catalog.get_file(task["source"]["source_id"])
        assert current.get("processing") is None and current["processed_hash"] is None


def test_staged_office_material_from_an_older_cli_requires_a_new_p1(knowledge):
    from docx import Document

    original = knowledge / "docs-raw/old.docx"
    document = Document()
    document.add_paragraph("A previously parsed source awaiting review.")
    document.save(original)
    task, phase = run_scan(knowledge, "old.docx")
    assert phase == "prepared", task
    task.pop("document_review")
    source = task["source"]
    source["parsed"] = module("document_parser").parse(
        knowledge, source, original.read_bytes(), ".build/materials/parsed",
    )
    (knowledge / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    (knowledge / ".build/plan.md").write_text("---\ncards: []\n---\nNo cards to write.\n", encoding="utf-8")

    failure, phase = module("ingest").check(knowledge, {})
    assert phase == "failed" and failure["findings"][0]["code"] == "DOCUMENT_REVIEW_REQUIRED"
    with pytest.raises(ValueError, match="DOCUMENT_REVIEW_REQUIRED"):
        module("ingest").commit(knowledge, {"reason": "No change is needed."})
    assert run_scan(knowledge, "old.docx")[1] == "prepared"


def test_pdf_layout_change_does_not_merge_review_coverage(knowledge, monkeypatch):
    long_pdf(knowledge / "docs-raw/review.pdf", 12)
    task, phase = run_scan(knowledge, "review.pdf")
    assert phase == "prepared", task
    write_plan(knowledge, 1, 1)
    assert module("ingest").check(knowledge, {})[1] == "passed"
    module("ingest").commit(knowledge, {"reason": "First page reviewed."})

    adapter = module("document_parser")
    convert = adapter._docling

    def changed(*args):
        result = convert(*args)
        with (args[3] / "document.md").open("ab") as markdown:
            markdown.write(b"\nAdditional text from the new parser settings.\n")
        return result

    monkeypatch.setattr(adapter, "_docling", changed)
    next_task, phase = run_scan(knowledge, "review.pdf", parser={"threads": 2})
    assert phase == "prepared", next_task
    assert next_task["source"]["hash"] == task["source"]["hash"]
    assert next_task["document_review"]["start_unit"] == 1
    assert next_task["document_review"]["review_sha256"] != task["document_review"]["review_sha256"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows long paths")
def test_office_cache_can_be_written_and_reread_at_a_long_windows_path(knowledge, monkeypatch):
    from docx import Document

    monkeypatch.setattr(module("document_material"), "image_reader", lambda *args: lambda path: "FIGURE 42")
    root = knowledge / ("long-root-" + "x" * 115)
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / directory).mkdir(parents=True)
    document = Document()
    document.add_paragraph("A test with a long cache path.")
    document.add_picture(BytesIO(figure()))
    document.save(root / "docs-raw/report.docx")
    task, phase = run_scan(root, "report.docx")
    assert phase == "prepared", task
    again, phase = run_scan(root, "report.docx")
    assert phase == "prepared", again
    assert again["source"]["parsed"]["manifest_sha256"] == task["source"]["parsed"]["manifest_sha256"]
