"""Tiling masks are visible in verified whole-page PDF previews."""

from io import BytesIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.contracts import module

parser = module("document_parser")


def pattern_pdf(*, pages=1, bitmap=False, unpatterned=()):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

    def dictionary(**entries):
        return DictionaryObject({NameObject("/" + name): value for name, value in entries.items()})

    writer = PdfWriter()
    font = writer._add_object(dictionary(Type=NameObject("/Font"), Subtype=NameObject("/Type1"),
                                         BaseFont=NameObject("/Helvetica")))
    mask = DecodedStreamObject()
    mask.set_data(bytes((0xAA, 0x55)) * 4)
    mask.update(dictionary(Type=NameObject("/XObject"), Subtype=NameObject("/Image"),
                           Width=NumberObject(8), Height=NumberObject(8),
                           BitsPerComponent=NumberObject(1), ImageMask=BooleanObject(True)))
    pattern = DecodedStreamObject()
    pattern.set_data(b"1 1 1 rg 0 0 1 1 re f\n0 0 0 rg\nq 1 0 0 -1 0 1 cm /Tile Do Q")
    pattern.update(dictionary(
        Type=NameObject("/Pattern"), PatternType=NumberObject(1), PaintType=NumberObject(1),
        TilingType=NumberObject(1), BBox=ArrayObject([NumberObject(n) for n in (0, 0, 1, 1)]),
        XStep=NumberObject(1), YStep=NumberObject(1),
        Matrix=ArrayObject([NumberObject(n) for n in (1, 0, 0, -1, 0, 160)]),
        Resources=dictionary(XObject=dictionary(Tile=writer._add_object(mask))),
    ))
    resources = dictionary(Font=dictionary(F1=font), Pattern=dictionary(Fill=writer._add_object(pattern)))
    if bitmap:
        image = DecodedStreamObject()
        image.set_data(bytes((10, 60, 180)) * 64)
        image.update(dictionary(Type=NameObject("/XObject"), Subtype=NameObject("/Image"),
                                Width=NumberObject(8), Height=NumberObject(8),
                                BitsPerComponent=NumberObject(8), ColorSpace=NameObject("/DeviceRGB")))
        resources[NameObject("/XObject")] = dictionary(Bitmap=writer._add_object(image.flate_encode()))
    resources_ref = writer._add_object(resources)

    for number in range(1, pages + 1):
        page = writer.add_blank_page(width=240, height=160)
        page[NameObject("/Resources")] = resources_ref
        content = DecodedStreamObject()
        commands = [f"BT /F1 12 Tf 20 135 Td (Physical page {number}) Tj ET".encode()]
        if number not in unpatterned:
            commands.append(b"q /Pattern cs /Fill scn 30 40 80 55 re f Q")
        if bitmap:
            commands.append(b"q 24 0 0 24 145 50 cm /Bitmap Do Q")
        content.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def parse_pattern(root, data, *, page_range=None, options=None):
    source = {"id": "synthetic-tiling-pattern", "path": "docs-raw/tiling-pattern.pdf"}
    descriptor = parser.parse(root, source, data, ".build/materials/parsed",
                              page_range=page_range, options=options)
    loaded = parser.load(root, descriptor, expected_source_id=source["id"],
                         expected_sha256=parser.sha256_bytes(data))
    return descriptor, loaded


def page_previews(descriptor):
    return [image for image in descriptor["images"] if image["role"] == "page_preview"]


def test_real_tiling_mask_has_a_registered_whole_page_preview(tmp_path):
    from PIL import Image
    import pypdfium2 as pdfium

    data = pattern_pdf()
    descriptor, loaded = parse_pattern(tmp_path, data)

    previews = page_previews(descriptor)
    assert len(previews) == 1, descriptor["gaps"][:2]
    assert previews[0]["locator"] == {"kind": "page", "page": 1}
    assert previews[0]["source_sha256"] == descriptor["source_sha256"]
    assert "Physical page 1" in loaded["text"]
    assert descriptor["parse_status"] == "parsed", descriptor["gaps"][:2]
    assert all(gap["code"] != "IMAGE_UNAVAILABLE" for gap in descriptor["gaps"])
    assert loaded["manifest"]["page_preview"]["requested_pages"] == [1]
    textures = [image for image in descriptor["images"] if image["role"] == "pattern_texture"]
    assert textures and all(image["ref"] is None for image in textures)
    pattern_gaps = [gap for gap in descriptor["gaps"] if gap["code"] == "PDF_PATTERN_PAGE_PREVIEW"]
    assert len(pattern_gaps) == 1
    assert pattern_gaps[0]["severity"] == "warning"
    assert pattern_gaps[0]["pattern_tiles"] == len(textures)
    assert pattern_gaps[0]["preview_ref"] == previews[0]["ref"]
    assert any(row["ref"] == previews[0]["ref"] for row in loaded["manifest"]["files"])
    assert "images/page_preview_000001.png" in loaded["markdown"]
    pdf = pdfium.PdfDocument(data)
    page = pdf[0]
    bitmap = page.render(scale=1.5)
    try:
        with Image.open(tmp_path / previews[0]["ref"]) as image:
            assert image.size == (360, 240)
            assert image.convert("RGB").tobytes() == bitmap.to_pil().convert("RGB").tobytes()
    finally:
        bitmap.close()
        page.close()
        pdf.close()


def test_automatic_preview_uses_sparse_pattern_pages_beyond_explicit_cap(tmp_path):
    descriptor, loaded = parse_pattern(tmp_path, pattern_pdf(pages=10, unpatterned=(2,)))

    expected = [1, *range(3, 11)]
    preview = loaded["manifest"]["page_preview"]
    assert descriptor["parse_status"] == "parsed", descriptor["gaps"][:2]
    assert preview["requested_pages"] == expected
    assert preview["rendered_pages"] == expected
    assert [image["locator"]["page"] for image in page_previews(descriptor)] == expected
    warnings = [gap for gap in descriptor["gaps"] if gap["code"] == "PDF_PATTERN_PAGE_PREVIEW"]
    assert [gap["locator"]["page"] for gap in warnings] == expected


def test_automatic_preview_cap_keeps_later_pattern_page_in_review(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, "_PATTERN_PREVIEW_PAGES", 1)
    descriptor, loaded = parse_pattern(tmp_path, pattern_pdf(pages=2))

    assert descriptor["parse_status"] == "partial"
    preview = loaded["manifest"]["page_preview"]
    assert preview["requested_pages"] == [1, 2]
    assert preview["rendered_pages"] == [1]
    assert [image["locator"]["page"] for image in page_previews(descriptor)] == [1]
    pattern_gaps = {gap["locator"]["page"]: (gap["code"], gap["severity"])
                    for gap in descriptor["gaps"] if gap["code"].startswith("PDF_PATTERN_")}
    assert pattern_gaps == {
        1: ("PDF_PATTERN_PAGE_PREVIEW", "warning"),
        2: ("PDF_PATTERN_PREVIEW_UNAVAILABLE", "review"),
    }


def test_pattern_reuses_explicit_preview_for_original_page(tmp_path):
    descriptor, loaded = parse_pattern(tmp_path, pattern_pdf(pages=3), page_range=(2, 2))

    assert loaded["manifest"]["page_preview"]["requested_range"] == [2, 2]
    assert loaded["manifest"]["pages"] == [2]
    previews = page_previews(descriptor)
    assert [image["locator"]["page"] for image in previews] == [2]
    warnings = [gap for gap in descriptor["gaps"] if gap["code"] == "PDF_PATTERN_PAGE_PREVIEW"]
    assert len(warnings) == 1
    assert warnings[0]["preview_ref"] == previews[0]["ref"]


def test_oversized_explicit_request_keeps_existing_preview_bound(tmp_path):
    data = pattern_pdf(pages=9, unpatterned=range(2, 10))
    descriptor, loaded = parse_pattern(tmp_path, data, page_range=(1, 9))

    assert descriptor["parse_status"] == "partial"
    assert loaded["manifest"]["page_preview"]["requested_range"] == [1, 9]
    assert not page_previews(descriptor)
    codes = {gap["code"] for gap in descriptor["gaps"]}
    assert {"PAGE_PREVIEW_PAGE_LIMIT", "PDF_PATTERN_PREVIEW_UNAVAILABLE"}.issubset(codes)


def test_unrendered_pattern_preview_keeps_review_gap(tmp_path, monkeypatch):
    import pypdfium2 as pdfium

    def fail_render(*args, **kwargs):
        raise RuntimeError("Synthetic preview renderer failure")

    monkeypatch.setattr(pdfium.PdfPage, "render", fail_render)
    descriptor, loaded = parse_pattern(tmp_path, pattern_pdf())

    assert descriptor["parse_status"] == "partial"
    assert not page_previews(descriptor)
    assert "Physical page 1" in loaded["text"]
    assert any(gap["code"] == "PDF_PATTERN_PREVIEW_UNAVAILABLE" and gap["severity"] == "review"
               for gap in descriptor["gaps"])
    assert all(gap["code"] != "PDF_PATTERN_PAGE_PREVIEW" for gap in descriptor["gaps"])


def test_preview_metadata_over_quota_keeps_original_page_material(tmp_path):
    data = pattern_pdf()
    roomy, tight = tmp_path / "roomy", tmp_path / "tight"
    roomy.mkdir()
    tight.mkdir()
    full, original = parse_pattern(roomy, data)
    assert len(page_previews(full)) == 1
    # The PNG and pre-preview files fit because the measured full bundle also
    # includes the preview's Markdown link and JSON metadata.
    quota = full["statistics"]["output_bytes"] - 1

    descriptor, loaded = parse_pattern(tight, data, options={"max_output_bytes": quota})

    assert descriptor["parse_status"] == "partial"
    assert descriptor["statistics"]["output_bytes"] <= quota
    assert loaded["manifest"]["pages"] == [1]
    assert loaded["text"] == original["text"]
    assert not page_previews(descriptor)
    assert not list(tight.rglob("page_preview_*.png"))
    assert "page_preview_000001.png" not in loaded["markdown"]
    codes = {gap["code"] for gap in descriptor["gaps"]}
    assert {"PAGE_PREVIEW_BYTE_LIMIT", "PDF_PATTERN_PREVIEW_UNAVAILABLE"}.issubset(codes)


def test_preview_over_file_limit_keeps_loadable_original_page_material(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, "_MAX_PARSE_FILES", 4)
    descriptor, loaded = parse_pattern(tmp_path, pattern_pdf())

    assert descriptor["parse_status"] == "partial"
    assert len(loaded["manifest"]["files"]) == 4
    assert "Physical page 1" in loaded["text"]
    assert not page_previews(descriptor)
    assert not list(tmp_path.rglob("page_preview_*.png"))
    codes = {gap["code"] for gap in descriptor["gaps"]}
    assert {"PAGE_PREVIEW_FILE_LIMIT", "PDF_PATTERN_PREVIEW_UNAVAILABLE"}.issubset(codes)


def test_direct_bitmap_failure_stays_review_on_patterned_page(tmp_path, monkeypatch):
    pdf_pictures = module("pdf_pictures")
    monkeypatch.setattr(pdf_pictures, "_decode", lambda *args: None)

    descriptor, _ = parse_pattern(tmp_path, pattern_pdf(bitmap=True))

    assert descriptor["parse_status"] == "partial"
    direct = [image for image in descriptor["images"] if image["role"] == "document_picture"
              and image["provenance"][0]["bbox"]["l"] == 145]
    assert len(direct) == 1
    assert direct[0]["ref"] is None
    assert any(gap["code"] == "IMAGE_UNAVAILABLE" and gap["severity"] == "review"
               and gap["locator"] == direct[0]["locator"] for gap in descriptor["gaps"])
