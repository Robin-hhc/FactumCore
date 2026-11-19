"""A complete conversion and the P2 reading range have separate lifetimes."""

from pathlib import Path
import sys
from io import BytesIO
import json

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
    assert not (knowledge / ".build/task.json").exists()
    assert not list((knowledge / "artifacts/ingest/parsed").glob("*.json"))
    monkeypatch.setattr(material, "image_reader", lambda *args: lambda path: "SCAN RECOVERED")
    prepared, phase = run_scan(knowledge, "scan.pdf")
    assert phase == "prepared", prepared
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
