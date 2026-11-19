"""Build local PDF, DOCX and XLSX samples with known source locations."""

from argparse import ArgumentParser
from io import BytesIO
import json
from pathlib import Path


def long_pdf(path, page_count, *, vector=False):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    resources = writer._add_object(DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    }))
    for number in range(1, page_count + 1):
        page = writer.add_blank_page(width=300, height=200)
        page[NameObject("/Resources")] = resources
        content = DecodedStreamObject()
        body = f"BT /F1 11 Tf 18 175 Td (PDF PAGE {number:05d} CHECK) Tj ET\n"
        if vector:
            body += "0.3 0.5 0.7 rg 20 70 80 50 re f"
        content.set_data(body.encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(path)


def figure():
    from PIL import Image, ImageDraw, ImageFont

    with Image.new("RGB", (480, 210), "white") as image:
        draw = ImageDraw.Draw(image)
        draw.text((36, 20), "LIMIT 42 VOLTS", font=ImageFont.load_default(size=36), fill="black")
        draw.line([(18, 175), (122, 141), (222, 151), (320, 112), (440, 87)], fill="blue", width=5)
        out = BytesIO()
        image.save(out, "PNG")
    return out.getvalue()


def scanned_pdf(path):
    from PIL import Image, ImageDraw, ImageFont
    from pypdf import PdfWriter

    long_pdf(path, 1, vector=True)
    writer = PdfWriter()
    writer.append(path)
    with Image.new("RGB", (960, 440), "white") as image:
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=46)
        draw.text((65, 48), "SCAN PAGE TWO CHECK", font=font, fill="black")
        draw.text((65, 155), "Threshold 42 volts", font=font, fill="black")
        draw.rectangle((60, 252, 850, 360), outline="black", width=4)
        draw.text((78, 270), "Reading 17.5 amps", font=font, fill="black")
        bitmap = BytesIO()
        image.save(bitmap, "PDF", resolution=120)
        bitmap.seek(0)
        writer.append(bitmap)
    writer.write(path)


def word(path, picture):
    from docx import Document
    from docx.shared import Inches

    document = Document()
    document.add_heading("Document conversion acceptance", 0)
    for number in range(1, 1801):
        if number % 100 == 1:
            document.add_heading(f"Section {number}", 1)
        document.add_paragraph(f"DOCX PARAGRAPH {number:04d} CHECK. 中文正文。")
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, title in zip(table.rows[0].cells, ("Index", "Description", "Value")):
        cell.text = title
    for number in range(1, 101):
        for cell, value in zip(table.add_row().cells, (str(number), f"WORD TABLE ROW {number}", str(number * 10))):
            cell.text = value
    document.add_picture(BytesIO(picture), width=Inches(3))
    document.add_paragraph("DOCX FIGURE CAPTION CHECK", style="Caption")
    document.save(path)


def workbook(path, picture):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image

    book = Workbook()
    dense = book.active
    dense.title = "Measures"
    dense.append(["ID", "中文名称", "Minimum", "Nominal", "Maximum", "Note"])
    for row in range(2, 3001):
        dense.append([row, f"设备 {row}", row * 2, row * 3, row * 4, f"XLSX ROW {row} CHECK"])
    offset = book.create_sheet("Offset")
    offset.merge_cells("B12:D12")
    offset["B12"] = "XLSX MERGED CHECK"
    offset["B13"] = "Code"
    offset["C13"] = "Value"
    offset["B14"] = "XLSX OFFSET CHECK"
    offset["C14"] = 418
    offset.add_image(Image(BytesIO(picture)), "F18")
    book.save(path)


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    cli.add_argument("--pdf-pages", type=int, default=2101)
    args = cli.parse_args()
    if args.pdf_pages < 12:
        cli.error("--pdf-pages must be at least 12")
    output = args.output
    output.mkdir(parents=True)
    picture = figure()
    long_pdf(output / "long.pdf", args.pdf_pages)
    scanned_pdf(output / "scan-and-text.pdf")
    word(output / "report.docx", picture)
    workbook(output / "measures.xlsx", picture)
    sample_pages = [1, 200, 201, args.pdf_pages] if args.pdf_pages > 201 else [1, args.pdf_pages]
    expected = {
        "long.pdf": {"pages": args.pdf_pages,
                     "sample_pages": sample_pages},
        "scan-and-text.pdf": {"pages": 2, "scan_page": 2, "ocr_text": "Threshold 42 volts"},
        "report.docx": {"text": ["DOCX PARAGRAPH 1800 CHECK", "WORD TABLE ROW 100", "DOCX FIGURE CAPTION CHECK", "LIMIT 42 VOLTS"],
                        "images": 1},
        "measures.xlsx": {"cells": {"Measures!F3000": "XLSX ROW 3000 CHECK", "Offset!B12:D12": "XLSX MERGED CHECK",
                                    "Offset!B14": "XLSX OFFSET CHECK"}, "images": 1, "ocr_text": "LIMIT 42 VOLTS"},
    }
    (output / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
