"""Assemble the canonical visual reading material at the P1 boundary."""

from collections import defaultdict
import hashlib
from html import escape
from io import BytesIO
import math
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from .markdown_images import markdown_image_tokens
from .runtime import native_path
from .validation import ContractError


FORMATS = frozenset({".pdf", ".docx", ".xlsx"})
PAGE_MARKER = re.compile(rb"(?m)^<!-- physical-page:(\d+) -->\n")


def image_reader(root, options):
    """Use the packaged Docling OCR engine on original images of any format."""
    import numpy
    from PIL import Image
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import RapidOcrOptions
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel

    from .document_parser import _model_directory, safe_path

    directory = _model_directory(root, options)
    if not directory.is_dir() or not safe_path(directory, "RapidOcr").is_dir():
        raise ContractError("PARSER_MODELS_REQUIRED", "Install the local knowledge OCR models before preparing images")
    engine = RapidOcrModel(
        enabled=True, artifacts_path=directory,
        options=RapidOcrOptions(backend="onnxruntime", lang=options["ocr_languages"]),
        accelerator_options=AcceleratorOptions(device="cpu", num_threads=options["threads"]),
    )

    def read(path):
        with Image.open(native_path(path)) as source:
            rgba = source.convert("RGBA")
            image = Image.new("RGB", rgba.size, "white")
            image.paste(rgba, mask=rgba.getchannel("A"))
            result = engine.reader(numpy.asarray(image))
        return "\n".join(result.txts or ()) if result is not None else ""

    return read


def pdf_markdown(document, rendered):
    """Use Docling's serialized items once, grouping by their original page."""
    from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownParams
    from docling_core.types.doc import ImageRefMode

    serializer = MarkdownDocSerializer(
        doc=document, params=MarkdownParams(image_mode=ImageRefMode.REFERENCED,
                                            traverse_pictures=True, caption_placement="layout",
                                            mark_meta=True, compact_tables=True),
    )
    groups = defaultdict(list)
    page_views = set()
    number = min(document.pages, default=1)
    for part in serializer.get_parts(traverse_pictures=True):
        number = next((prov.page_no for span in part.spans for prov in span.item.prov), number)
        if len(part.spans) == 1 and part.spans[0].item.self_ref in rendered:
            if (number, part.text) in page_views:
                continue
            page_views.add((number, part.text))
        groups[number].append(part.text)
    return "\n\n".join(
        "\n\n".join([f"<!-- physical-page:{page} -->\n## Physical page {page}", *groups[page]])
        for page in sorted(document.pages)
    ) + "\n"


def _contains_vector_graphic(page, pdfium, size):
    """Identify visible paths with area, including filled drawing regions."""
    width, height = size
    horizontal = vertical = 0
    for item in page.get_objects(filter=(pdfium.raw.FPDF_PAGEOBJ_PATH, pdfium.raw.FPDF_PAGEOBJ_SHADING)):
        left, bottom, right, top = item.get_bounds()
        if (right - left >= width * 0.08 and top - bottom >= height * 0.04
                and (right - left) * (top - bottom) >= width * height * 0.02):
            return True
        horizontal += right - left >= width * 0.15 and top - bottom < 2
        vertical += top - bottom >= height * 0.05 and right - left < 2
        if horizontal >= 2 and vertical >= 2:
            return True
    return False


def _save_page_view(page, output, width, height, budget):
    from docling_core.types.doc import ImageRef, Size

    scale = min(1.5, math.sqrt(1_100_000 / (width * height)))
    bitmap = page.render(scale=scale)
    try:
        with bitmap.to_pil() as image, BytesIO() as stream:
            image.save(stream, "PNG")
            data = stream.getvalue()
            size = Size(width=image.width, height=image.height)
    finally:
        bitmap.close()
    reference = "images/" + hashlib.sha256(data).hexdigest() + ".png"
    target = Path(native_path(output / reference))
    written = 0
    if not target.is_file():
        if len(data) > budget:
            raise ContractError("PARSE_OUTPUT_LIMIT", "Original page views exceed the remaining material quota")
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
        written = len(data)
    return ImageRef(mimetype="image/png", dpi=max(1, round(scale * 72)), size=size, uri=Path(reference)), written


def retain_pdf_views(document, data, output, max_bytes):
    """Supply a visual source for pages with missing bitmaps or drawn figures."""
    import pypdfium2 as pdfium
    from docling_core.types.doc import BoundingBox, ProvenanceItem

    existing = defaultdict(list)
    for picture in document.pictures:
        if picture.prov:
            existing[picture.prov[0].page_no].append(picture)
    textual = {prov.page_no for item in document.texts if item.text.strip() for prov in item.prov}
    rendered = set()
    budget = max_bytes - sum(path.stat().st_size for path in Path(native_path(output / "images")).glob("*.png"))
    pdf = pdfium.PdfDocument(data)
    try:
        for number in sorted(document.pages):
            page = pdf[number - 1]
            try:
                width, height = page.get_size()
                missing = [picture for picture in existing[number] if picture.image is None]
                image_objects = (not existing[number] and next(page.get_objects(filter=(pdfium.raw.FPDF_PAGEOBJ_IMAGE,)), None) is not None)
                undetected_content = (number not in textual and not existing[number] and next(page.get_objects(), None) is not None)
                if not (missing or image_objects or undetected_content or _contains_vector_graphic(page, pdfium, (width, height))):
                    continue
                if not math.isfinite(width * height) or min(width, height) <= 0:
                    raise ContractError("PDF_VISUAL_UNAVAILABLE", f"Cannot render physical page {number}")
                image, written = _save_page_view(page, output, width, height, budget)
                budget -= written
                if missing:
                    for picture in missing:
                        picture.image = image
                        rendered.add(picture.self_ref)
                else:
                    picture = document.add_picture(image=image, prov=ProvenanceItem(
                        page_no=number, bbox=BoundingBox(l=0, t=height, r=width, b=0, coord_origin="BOTTOMLEFT"),
                        charspan=(0, 0),
                    ))
                    rendered.add(picture.self_ref)
            finally:
                page.close()
    finally:
        pdf.close()
    return rendered


def _drawing_nodes(node):
    if node.tag == "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent":
        branch = next(iter(node), None)
        if branch is not None:
            yield from _drawing_nodes(branch)
        return
    yield node
    for child in node:
        yield from _drawing_nodes(child)


def _office_image_count(data, suffix):
    # Only local drawing relationships in the main document/workbook count.
    drawing = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    embedded = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    try:
        with ZipFile(BytesIO(data)) as archive:
            parts = (["word/document.xml"] if suffix == ".docx" else
                     [name for name in archive.namelist() if re.fullmatch(r"xl/drawings/drawing\d+\.xml", name)])
            return sum(node.tag == drawing and bool(node.get(embedded)) for name in parts
                       for node in _drawing_nodes(ElementTree.fromstring(archive.read(name))))
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ContractError("DOCUMENT_IMAGE_INVENTORY", "Unable to read the Office drawing inventory") from error


def retain_workbook_formulas(document, data):
    """Carry original formulas beside Docling's cached cell values."""
    from docling_core.types.doc import BoundingBox, DocItemLabel, ProvenanceItem
    from openpyxl.utils.cell import coordinate_to_tuple

    spreadsheet = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    relationship = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    groups = {group.name: group for group in document.groups if group.label == "sheet"}
    with ZipFile(BytesIO(data)) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        sheets = {item.get("Id"): item.get("Target") for item in rels if item.get("Type", "").endswith("/worksheet")}
        for number, sheet in enumerate(workbook.iter(f"{spreadsheet}sheet"), 1):
            name, target = sheet.get("name"), sheets.get(sheet.get(relationship))
            if not target:
                continue
            path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if not path.startswith("xl/"):
                raise ContractError("DOCUMENT_SHEET_UNAVAILABLE", "Worksheet path leaves the workbook", name)
            with archive.open(path) as stream:
                for _, node in ElementTree.iterparse(stream, events=("end",)):
                    if node.tag == spreadsheet + "c":
                        formula = node.find(spreadsheet + "f")
                        if formula is not None and formula.text:
                            if name not in groups:
                                raise ContractError("DOCUMENT_SHEET_UNAVAILABLE", "Worksheet with formulas has no reading group", name)
                            address = node.get("r")
                            row, column = coordinate_to_tuple(address)
                            page = document.pages[number]
                            page.size.width = max(page.size.width, column)
                            page.size.height = max(page.size.height, row)
                            document.add_text(label=DocItemLabel.PARAGRAPH, text=f"Formula {address} = {formula.text}",
                                              parent=groups[name], content_layer=groups[name].content_layer,
                                              prov=ProvenanceItem(page_no=number, charspan=(0, 0), bbox=BoundingBox(
                                                  l=column - 1, r=column, t=row - 1, b=row, coord_origin="TOPLEFT")))
                        node.clear()
                    elif node.tag == spreadsheet + "row":
                        node.clear()


def finish(root, output, suffix, data, images, gaps, pages, options):
    """Check the displayed pictures and place their OCR next to each link."""
    from .document_parser import _gap, pdf_page_count, safe_path

    if suffix == ".pdf" and (not pages or pages != list(range(1, pdf_page_count(data) + 1))):
        return [*gaps, _gap("DOCUMENT_PAGE_COVERAGE", "Conversion did not cover the original physical pages", severity="review")]
    if any(gap["severity"] == "review" and gap["code"] != "OCR_REQUIRED" for gap in gaps):
        return gaps

    markdown_path = Path(native_path(output / "document.md"))
    markdown = markdown_path.read_text(encoding="utf-8")
    if suffix == ".pdf" and [int(match.group(1)) for match in PAGE_MARKER.finditer(markdown.encode("utf-8"))] != pages:
        return [*gaps, _gap("DOCUMENT_REVIEW_PAGE_MAP", "Markdown is missing physical page markers", severity="review")]
    tokens = list(markdown_image_tokens(markdown))
    shown = {unquote(uri) for _, _, uri in tokens if uri}
    local = {PurePosixPath(row["ref"]).relative_to(output.relative_to(root).as_posix()).as_posix()
             for row in images if row.get("ref")}
    if ("<!-- image -->" in markdown or not local.issubset(shown)
            or suffix != ".pdf" and _office_image_count(data, suffix) > len(tokens)):
        return [*gaps, _gap("DOCUMENT_IMAGE_COVERAGE", "At least one original image has no local Markdown link", severity="review")]
    if not tokens:
        markdown_path.write_bytes(markdown.encode("utf-8"))
        return gaps

    # A rendered copy of a page with a text layer already has text in the Markdown.
    # Original bitmaps and rendered pages lacking source text need image OCR.
    view_refs = {PurePosixPath(row["ref"]).relative_to(output.relative_to(root).as_posix()).as_posix()
                 for row in images if row.get("role") == "source_page_view" and row.get("ref")}
    ocr_pages = {gap.get("locator", {}).get("page") for gap in gaps if gap["code"] == "OCR_REQUIRED"}
    ocr_views = {PurePosixPath(row["ref"]).relative_to(output.relative_to(root).as_posix()).as_posix()
                 for row in images if row.get("role") == "source_page_view" and row.get("ref")
                 and any(item.get("page_no") in ocr_pages for item in row["provenance"])}
    source_text_views = view_refs - ocr_views
    read = image_reader(root, options) if shown - source_text_views else None
    readings = {}
    pieces, cursor = [], 0
    for start, end, uri in tokens:
        ref = unquote(uri or "")
        path = safe_path(output, ref, ["images"])
        if ref not in readings:
            readings[ref] = "" if ref in source_text_views else read(path)
        pieces.append(markdown[cursor:end])
        if text := readings[ref].strip():
            plain = [re.sub(r"([\\`*{}_\[\]()#+!|])", r"\\\1", escape(line)) for line in text.splitlines()]
            if markdown[markdown.rfind("\n", 0, start) + 1:start].lstrip().startswith("|"):
                pieces.extend(("<br>OCR<br>", "<br>".join(plain)))
            else:
                pieces.extend(("\n\n> OCR\n", "\n".join("> " + line for line in plain), "\n\n"))
        cursor = end
    markdown_path.write_bytes("".join((*pieces, markdown[cursor:])).encode("utf-8"))
    for row in images:
        if row.get("ref"):
            relative = PurePosixPath(row["ref"]).relative_to(output.relative_to(root).as_posix()).as_posix()
            row["ocr_status"] = "source_text" if relative in source_text_views else "completed"
    return [gap for gap in gaps if gap["code"] != "OCR_REQUIRED"]
