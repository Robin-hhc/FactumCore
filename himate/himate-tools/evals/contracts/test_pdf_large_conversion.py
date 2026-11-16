"""Bounded native conversion preserves original PDF identities across batches."""

from io import BytesIO
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.contracts import module

parser = module("document_parser")
ContractError = module("validation").ContractError


def six_page_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for number in range(1, 7):
        page = writer.add_blank_page(width=300, height=200)
        image = DecodedStreamObject()
        image.set_data(bytes((number * 20, 60, 180)) * 80)
        image.update({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(8),
            NameObject("/Height"): NumberObject(10),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
            NameObject("/XObject"): DictionaryObject({
                NameObject("/Tiny"): writer._add_object(image.flate_encode()),
            }),
        })
        content = DecodedStreamObject()
        content.set_data(
            f"BT /F1 12 Tf 20 175 Td (Requirement for original page {number}.) Tj ET\n"
            "q 8 0 0 10 20 145 cm /Tiny Do Q".encode()
        )
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def conversions(monkeypatch):
    """Observe real conversions while making their otherwise-large batch boundary small."""
    monkeypatch.setattr(parser, "_PDF_CONVERSION_PAGES", 2)
    original = parser._converter
    calls = []

    def converter(root, suffix, options):
        instance = original(root, suffix, options)
        convert = instance.convert

        def observed(source, **arguments):
            calls.append(arguments["page_range"])
            return convert(source, **arguments)

        monkeypatch.setattr(instance, "convert", observed)
        return instance

    monkeypatch.setattr(parser, "_converter", converter)
    return calls


def parse_pdf(root, *, page_range=None, options=None):
    source = {"id": "synthetic-large-pdf", "path": "docs-raw/large.pdf"}
    data = six_page_pdf()
    descriptor = parser.parse(root, source, data, ".build/materials/parsed",
                              page_range=page_range, options=options)
    loaded = parser.load(root, descriptor, expected_source_id=source["id"],
                         expected_sha256=parser.sha256_bytes(data))
    return descriptor, loaded


@pytest.mark.parametrize("page_range,expected_calls,expected_pages", [
    (None, [(1, 2), (3, 4), (5, 6)], list(range(1, 7))),
    ((3, 6), [(3, 4), (5, 6)], list(range(3, 7))),
])
def test_batched_real_pdf_keeps_page_text_elements_and_pixels(
        tmp_path, conversions, page_range, expected_calls, expected_pages):
    from docling_core.types.doc import DoclingDocument
    from PIL import Image

    descriptor, loaded = parse_pdf(tmp_path, page_range=page_range)

    assert conversions == expected_calls
    assert descriptor["parse_status"] == "parsed", descriptor["gaps"]
    assert loaded["manifest"]["pages"] == expected_pages
    document = DoclingDocument.model_validate(loaded["document"])
    assert sorted(document.pages) == expected_pages
    assert [document.pages[number].page_no for number in expected_pages] == expected_pages
    for number in expected_pages:
        page = parser.select(loaded, {"kind": "page", "page": number})
        assert f"Requirement for original page {number}." in page[0]["text"]
    for item, _ in document.iterate_items():
        assert all(prov.page_no in expected_pages for prov in getattr(item, "prov", []))
    elements = [row for row in loaded["locators"]["segments"]
                if row["locator"]["kind"] == "element"]
    assert elements
    assert len({row["locator"]["ref"] for row in elements}) == len(elements)
    for row in elements:
        assert parser.select(loaded, row["locator"]) == [row]

    pictures = [item for item in descriptor["images"] if item["role"] == "document_picture"]
    assert len(pictures) == len(expected_pages)
    assert sorted(item["provenance"][0]["page_no"] for item in pictures) == expected_pages
    for item in pictures:
        number = item["provenance"][0]["page_no"]
        with Image.open(tmp_path / item["ref"]) as image:
            assert image.size == (8, 10)
            assert image.convert("RGB").getpixel((4, 5)) == (number * 20, 60, 180)


def test_missing_batch_page_does_not_shift_later_physical_pages(
        tmp_path, conversions, monkeypatch):
    from docling_core.types.doc import DoclingDocument

    # Alter the real converter result, after conversion and before concatenation.
    factory = parser._converter

    def converter(root, suffix, options):
        instance = factory(root, suffix, options)
        convert = instance.convert

        def drop_page(source, **arguments):
            result = convert(source, **arguments)
            if 4 in result.document.pages:
                value = result.document.export_to_dict()
                value["pages"].pop("4")
                for kind in ("texts", "pictures", "tables", "key_value_items"):
                    for item in value.get(kind, []):
                        item["prov"] = [prov for prov in item.get("prov", []) if prov["page_no"] != 4]
                result.document = DoclingDocument.model_validate(value)
            return result

        monkeypatch.setattr(instance, "convert", drop_page)
        return instance

    monkeypatch.setattr(parser, "_converter", converter)
    descriptor, loaded = parse_pdf(tmp_path)

    assert descriptor["parse_status"] == "partial"
    assert any(gap["code"] == "DOCUMENT_PARTIAL"
               and gap.get("locator") == {"kind": "pages", "start": 3, "end": 4}
               for gap in descriptor["gaps"])
    assert loaded["manifest"]["pages"] == [1, 2, 3, 5, 6]
    for number in (3, 5, 6):
        selected = parser.select(loaded, {"kind": "page", "page": number})
        assert f"Requirement for original page {number}." in selected[0]["text"]
    with pytest.raises(ContractError, match="INVALID_SOURCE_LOCATOR"):
        parser.select(loaded, {"kind": "page", "page": 4})


@pytest.mark.parametrize("page_range", [None, (1, 1)])
def test_explicit_original_page_cap_is_honored_before_batch_conversion(
        tmp_path, conversions, page_range):
    descriptor, loaded = parse_pdf(tmp_path, page_range=page_range, options={"max_pages": 3})

    assert conversions == []
    assert descriptor["parse_status"] == "partial"
    assert any(gap["code"] == "PARSE_PAGE_LIMIT" for gap in descriptor["gaps"])
    assert loaded["manifest"]["pages"] == []
    assert not loaded["text"]
