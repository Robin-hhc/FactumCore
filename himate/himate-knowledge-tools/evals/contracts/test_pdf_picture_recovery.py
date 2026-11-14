"""Real PDF picture bytes survive native decoder gaps without losing draw locations."""

from io import BytesIO
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.contracts import module

parser = module("document_parser")
ContractError = module("validation").ContractError


def picture_pdf(*, color_space="icc", repeat=1, jpeg=False, rotated=False, mask=False,
                color=(0, 100, 220), pixel_size=(8, 10)):
    """Same RGB bytes; an ICCBased space reproduces the native decoder failure."""
    from PIL import Image, ImageCms
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    image = DecodedStreamObject()
    if jpeg:
        buffer = BytesIO()
        Image.new("RGB", pixel_size, color).save(buffer, format="JPEG", quality=100)
        image.set_data(buffer.getvalue())
        image[NameObject("/Filter")] = NameObject("/DCTDecode")
    else:
        image.set_data(bytes(color) * (pixel_size[0] * pixel_size[1]))
    space = NameObject("/DeviceRGB")
    if color_space == "icc":
        profile = DecodedStreamObject()
        profile.set_data(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
        profile[NameObject("/N")] = NumberObject(3)
        space = ArrayObject([NameObject("/ICCBased"), writer._add_object(profile)])
    image.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Image"),
        NameObject("/Width"): NumberObject(pixel_size[0]),
        NameObject("/Height"): NumberObject(pixel_size[1]),
        NameObject("/BitsPerComponent"): NumberObject(8),
        NameObject("/ColorSpace"): space,
    })
    if mask:
        alpha = DecodedStreamObject()
        alpha.set_data(bytes(0 if x < pixel_size[0] // 2 else 255
                             for _ in range(pixel_size[1]) for x in range(pixel_size[0])))
        alpha.update({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(pixel_size[0]),
            NameObject("/Height"): NumberObject(pixel_size[1]),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/ColorSpace"): NameObject("/DeviceGray"),
        })
        image[NameObject("/SMask")] = writer._add_object(alpha.flate_encode())
    image_ref = writer._add_object(image if jpeg else image.flate_encode())
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        NameObject("/XObject"): DictionaryObject({NameObject("/Tiny"): image_ref}),
    })
    content = DecodedStreamObject()
    commands = [b"BT /F1 12 Tf 20 175 Td (Actual image requirement.) Tj ET"]
    # Keep a native vector path beside the bitmap; recovering a bitmap must not
    # replace the original page or imply that this curve was extracted as text.
    commands.append(b"0 0 1 RG 3 w 20 20 m 70 130 180 30 260 140 c S")
    for number in range(repeat):
        x, y = 20 + (number % 20) * 12, 145 - ((number // 20) % 12) * 10
        matrix = f"0 10 -8 0 {x + 8} {y}" if rotated else f"8 0 0 10 {x} {y}"
        commands.append(f"q {matrix} cm /Tiny Do Q".encode())
    content.set_data(b"\n".join(commands))
    page[NameObject("/Contents")] = writer._add_object(content)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def parse_picture(root, data):
    source = {"id": "synthetic-pdf-pictures", "path": "docs-raw/specs/pictures.pdf"}
    descriptor = parser.parse(root, source, data, ".build/materials/parsed")
    loaded = parser.load(root, descriptor, expected_source_id=source["id"],
                         expected_sha256=parser.sha256_bytes(data))
    return descriptor, loaded


def picture_rows(descriptor):
    return [image for image in descriptor["images"] if image["role"] == "document_picture"]


def assert_blue_picture(path, *, jpeg=False):
    from PIL import Image

    with Image.open(path) as image:
        assert image.size == (8, 10)
        value = image.convert("RGB").getpixel((4, 5))
    tolerance = 3 if jpeg else 0
    assert all(abs(actual - expected) <= tolerance
               for actual, expected in zip(value, (0, 100, 220))), value


def test_real_iccbased_flate_picture_is_exported_as_source_bound_pixels(tmp_path, monkeypatch):
    import pypdfium2 as pdfium

    monkeypatch.setattr(pdfium.PdfPage, "render", lambda *args, **kwargs: pytest.fail("Full ingestion rendered a whole page"))
    descriptor, loaded = parse_picture(tmp_path, picture_pdf())

    rows = picture_rows(descriptor)
    assert len(rows) == 1
    assert rows[0]["ref"], descriptor["gaps"]
    assert_blue_picture(tmp_path / rows[0]["ref"])
    assert rows[0]["locator"]["source_sha256"] == descriptor["source_sha256"]
    assert rows[0]["provenance"][0]["page_no"] == 1
    assert "<!-- image -->" not in loaded["markdown"]
    assert not any(gap["code"] == "IMAGE_UNAVAILABLE" for gap in descriptor["gaps"])
    assert "Actual image requirement" in loaded["text"]


@pytest.mark.parametrize("repeat", [12, 2000])
def test_repeated_missing_pictures_reuse_one_asset_and_preserve_every_draw(tmp_path, repeat):
    descriptor, loaded = parse_picture(tmp_path, picture_pdf(repeat=repeat))

    rows = picture_rows(descriptor)
    assert len(rows) == repeat
    assert all(row["ref"] for row in rows), descriptor["gaps"][:3]
    assert len({row["element_ref"] for row in rows}) == repeat
    assert all(row["provenance"] and row["provenance"][0]["page_no"] == 1 for row in rows)
    references = {row["ref"] for row in rows}
    assert len(references) == 1, "Repeated draws must not write thousands of identical image assets"
    assert len(list((tmp_path / next(iter(references))).parent.iterdir())) == 1
    assert_blue_picture(tmp_path / next(iter(references)))
    assert len(loaded["document"]["pictures"]) == repeat
    assert "<!-- image -->" not in loaded["markdown"]


@pytest.mark.parametrize("jpeg", [False, True])
def test_already_decodable_rgb_and_jpeg_pictures_keep_correct_pixels(tmp_path, jpeg):
    descriptor, loaded = parse_picture(tmp_path, picture_pdf(color_space="rgb", jpeg=jpeg))

    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    assert_blue_picture(tmp_path / rows[0]["ref"], jpeg=jpeg)
    assert "<!-- image -->" not in loaded["markdown"]
    assert not any(gap["code"] == "IMAGE_UNAVAILABLE" for gap in descriptor["gaps"])


def test_rotated_icc_picture_keeps_its_original_draw_location(tmp_path):
    from PIL import Image

    descriptor, loaded = parse_picture(tmp_path, picture_pdf(rotated=True))

    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    with Image.open(tmp_path / rows[0]["ref"]) as image:
        assert sorted(image.size) == [8, 10]
        assert image.convert("RGB").getpixel((image.width // 2, image.height // 2)) == (0, 100, 220)
    bbox = rows[0]["provenance"][0]["bbox"]
    assert sorted([round(abs(bbox["r"] - bbox["l"])), round(abs(bbox["t"] - bbox["b"]))]) == [8, 10]
    assert "<!-- image -->" not in loaded["markdown"]


@pytest.mark.parametrize("color_space", ["rgb", "icc"])
def test_native_picture_respects_its_soft_mask(tmp_path, color_space):
    from PIL import Image

    descriptor, _ = parse_picture(tmp_path, picture_pdf(color_space=color_space, mask=True))

    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    with Image.open(tmp_path / rows[0]["ref"]) as image:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        rendered = Image.alpha_composite(white, rgba).convert("RGB")
        assert rendered.getpixel((1, 5)) == (255, 255, 255)
        assert rendered.getpixel((6, 5)) == (0, 100, 220)


def geometry_pdf(*, form=False, crop=False, rotation=0):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject, RectangleObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(picture_pdf())))
    page = writer.pages[0]
    if form:
        image = page["/Resources"]["/XObject"].raw_get(NameObject("/Tiny"))
        group = DecodedStreamObject()
        group.set_data(b"q 8 0 0 10 5 7 cm /Tiny Do Q")
        group.update({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): RectangleObject([0, 0, 100, 100]),
            NameObject("/Resources"): DictionaryObject({
                NameObject("/XObject"): DictionaryObject({NameObject("/Tiny"): image}),
            }),
        })
        page["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/Group"): writer._add_object(group)})
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 20 175 Td (Actual image requirement.) Tj ET\n"
                         b"q 2 0 0 3 30 40 cm /Group Do Q")
        page[NameObject("/Contents")] = writer._add_object(content)
    if crop:
        page.cropbox = RectangleObject([10, 20, 280, 180])
    page[NameObject("/Rotate")] = NumberObject(rotation)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


@pytest.mark.parametrize("form,crop,rotation,expected", [
    (True, False, 0, (40, 61, 56, 91)),
    (False, True, 0, (10, 125, 18, 135)),
    (False, False, 90, (145, 272, 155, 280)),
    (False, False, 180, (272, 45, 280, 55)),
    (False, False, 270, (45, 20, 55, 28)),
    (True, True, 90, (41, 224, 71, 240)),
    (True, True, 270, (89, 30, 119, 46)),
])
def test_form_crop_and_page_rotation_keep_the_correct_picture_and_physical_box(
        tmp_path, form, crop, rotation, expected):
    descriptor, loaded = parse_picture(tmp_path, geometry_pdf(form=form, crop=crop, rotation=rotation))

    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    assert_blue_picture(tmp_path / rows[0]["ref"])
    provenance = rows[0]["provenance"][0]
    assert provenance["page_no"] == 1
    bbox = provenance["bbox"]
    assert bbox["coord_origin"] == "BOTTOMLEFT"
    assert (bbox["l"], bbox["b"], bbox["r"], bbox["t"]) == pytest.approx(expected, abs=0.001)
    assert "<!-- image -->" not in loaded["markdown"]


@pytest.mark.parametrize("same_pixels", [False, True])
def test_overlapping_pictures_require_unambiguous_pixels(tmp_path, same_pixels):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(picture_pdf())))
    page = writer.pages[0]
    second = PdfReader(BytesIO(picture_pdf(color=(0, 100, 220) if same_pixels else (220, 0, 0))))
    image = second.pages[0]["/Resources"]["/XObject"].raw_get(NameObject("/Tiny"))
    page["/Resources"]["/XObject"][NameObject("/Second")] = image.clone(writer)
    content = DecodedStreamObject()
    content.set_data(page.get_contents().get_data() + b"\nq 8 0 0 10 20 145 cm /Second Do Q")
    page[NameObject("/Contents")] = writer._add_object(content)
    data = BytesIO()
    writer.write(data)

    descriptor, loaded = parse_picture(tmp_path, data.getvalue())

    rows = picture_rows(descriptor)
    assert len(rows) == 2
    if same_pixels:
        assert all(row["ref"] for row in rows), descriptor["gaps"]
        assert len({row["ref"] for row in rows}) == 1
        assert_blue_picture(tmp_path / rows[0]["ref"])
        assert "<!-- image -->" not in loaded["markdown"]
    else:
        assert descriptor["parse_status"] == "partial"
        assert all(row["ref"] is None for row in rows)
        assert len([gap for gap in descriptor["gaps"] if gap["code"] == "IMAGE_UNAVAILABLE"]) == 2
        assert loaded["markdown"].count("<!-- image -->") == 2


@pytest.mark.parametrize("upgrade", ["picture-policy", "pdfium-version"])
def test_picture_profile_upgrade_creates_a_new_cache_without_rewriting_old_materials(
        tmp_path, monkeypatch, upgrade):
    source = {"id": "synthetic-pdf-pictures", "path": "docs-raw/specs/pictures.pdf"}
    data = picture_pdf()
    with monkeypatch.context() as previous:
        if upgrade == "picture-policy":
            current_profile = parser._profile

            def old_profile(*args):
                profile = current_profile(*args)
                profile.pop("picture_export", None)
                return profile

            previous.setattr(parser, "_profile", old_profile)
        else:
            version = parser.metadata.version
            previous.setattr(parser.metadata, "version", lambda name: "previous-pdfium-version"
                             if name == "pypdfium2" else version(name))
        first = parser.prepare_pdf(tmp_path, source, data)
    old_bundle = (tmp_path / first["manifest_ref"]).parent
    fixed_bytes = {path.relative_to(old_bundle): path.read_bytes()
                   for path in old_bundle.rglob("*") if path.is_file()}

    current = parser.prepare_pdf(tmp_path, source, data)

    assert current["source_sha256"] == first["source_sha256"]
    assert current["profile_sha256"] != first["profile_sha256"]
    assert current["manifest_ref"] != first["manifest_ref"]
    assert {path.relative_to(old_bundle): path.read_bytes()
            for path in old_bundle.rglob("*") if path.is_file()} == fixed_bytes
    for descriptor in (first, current):
        loaded = parser.load(tmp_path, descriptor, expected_source_id=source["id"],
                             expected_sha256=parser.sha256_bytes(data))
        assert "<!-- image -->" not in loaded["markdown"]
        assert loaded["manifest"]["images"][0]["ref"]


def test_unrecovered_picture_remains_an_explicit_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, "_pdf_picture_recovery", lambda *args, **kwargs: None, raising=False)

    descriptor, loaded = parse_picture(tmp_path, picture_pdf())

    assert descriptor["parse_status"] == "partial"
    assert any(gap["code"] == "IMAGE_UNAVAILABLE" for gap in descriptor["gaps"])
    assert any(row["ref"] is None for row in picture_rows(descriptor))
    assert "Actual image requirement" in loaded["text"]


def test_a_changed_recovered_picture_is_rejected_on_load(tmp_path):
    data = picture_pdf()
    descriptor, _ = parse_picture(tmp_path, data)
    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    path = tmp_path / rows[0]["ref"]
    path.write_bytes(path.read_bytes() + b"changed pixels after handoff")

    with pytest.raises(ContractError, match="PARSE_MATERIAL_CHANGED"):
        parser.load(tmp_path, descriptor, expected_source_id="synthetic-pdf-pictures",
                    expected_sha256=parser.sha256_bytes(data))


def test_windows_picture_uri_export_stays_portable_without_changing_body_backslashes(tmp_path, monkeypatch):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(picture_pdf())))
    page = writer.pages[0]
    content = DecodedStreamObject()
    content.set_data(page.get_contents().get_data()
                     + b"\nBT /F1 12 Tf 20 160 Td (Keep C:\\\\radio\\\\trace literal.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    data = stream.getvalue()
    (tmp_path / "ordinary").mkdir()
    (tmp_path / "windows-spelling").mkdir()
    _, original = parse_picture(tmp_path / "ordinary", data)

    class WindowsSpellingPath(type(Path())):
        def __str__(self):
            return super().__str__().replace("/", "\\")

    recovery = parser._pdf_picture_recovery

    def windows_recovery(document, *args):
        recovery(document, *args)
        for picture in document.pictures:
            if picture.image is not None:
                picture.image.uri = WindowsSpellingPath(picture.image.uri)
                assert "\\" in str(picture.image.uri), "The simulated Windows path must reach the real exporter"

    monkeypatch.setattr(parser, "_pdf_picture_recovery", windows_recovery)

    descriptor, loaded = parse_picture(tmp_path / "windows-spelling", data)

    images = loaded["document"]["pictures"]
    assert images and all(item["image"]["uri"].startswith("images/") for item in images)
    assert all("\\" not in item["image"]["uri"] for item in images)
    assert "![Image](images/" in loaded["markdown"]
    assert loaded["markdown"] == original["markdown"]
    assert "C:\\radio\\trace" in loaded["text"]
    assert loaded["text"] == original["text"]
    assert loaded["document"]["texts"] == original["document"]["texts"]
    assert all(row["ref"] for row in picture_rows(descriptor))


@pytest.mark.parametrize("change", ["case-alias", "case-shadow", "same-size-corruption"])
def test_fixed_picture_directory_checks_reject_aliases_shadows_and_changed_bytes(tmp_path, change):
    data = picture_pdf(repeat=12)
    descriptor, _ = parse_picture(tmp_path, data)
    path = tmp_path / picture_rows(descriptor)[0]["ref"]
    # parse_picture has already performed a successful load. A later operation
    # must see new directory entries and new bytes instead of trusting it.
    if change in {"case-alias", "case-shadow"}:
        alternate = path.with_name(path.name.upper())
        if alternate.exists():
            pytest.skip("The filesystem cannot represent distinct case spellings")
        if change == "case-alias":
            path.rename(alternate)
        else:
            alternate.write_bytes(path.read_bytes())
    else:
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])

    expected = "PATH_CASE_ALIAS" if change == "case-alias" else "PARSE_MATERIAL_CHANGED"
    with pytest.raises(ContractError, match=expected):
        parser.load(tmp_path, descriptor, expected_source_id="synthetic-pdf-pictures",
                    expected_sha256=parser.sha256_bytes(data))


@pytest.mark.parametrize("clip_sliver", [0.04, 0.02])
def test_thin_clipped_picture_keeps_visible_subpixel_alpha(tmp_path, clip_sliver):
    from PIL import Image
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter(clone_from=PdfReader(BytesIO(picture_pdf(color_space="rgb", pixel_size=(3, 3)))))
    page = writer.pages[0]
    x, y, width = 20.0, 40.0, 2.448
    # The clip's bounding box contains the whole bitmap. Its triangle only
    # touches a subpixel sliver at the upper-right corner: normalizing to the
    # source pixel grid can erase this real, low-alpha painted edge.
    clip = (f"q {x - width} {y + width * (3 - clip_sliver)} m "
            f"{x + width * (3 - clip_sliver)} {y - width} l "
            f"{x + width * 3} {y + width * 3} l h W n "
            f"{width} 0 0 {width} {x} {y} cm /Tiny Do Q")
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 175 Td (Actual image requirement.) Tj ET\n" + clip.encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    data = BytesIO()
    writer.write(data)

    descriptor, loaded = parse_picture(tmp_path, data.getvalue())

    rows = picture_rows(descriptor)
    assert len(rows) == 1 and rows[0]["ref"], descriptor["gaps"]
    with Image.open(tmp_path / rows[0]["ref"]) as image:
        alpha = image.convert("RGBA").getchannel("A")
        assert alpha.getbbox() is not None, "The source's visible clipped edge became fully transparent"
    assert "<!-- image -->" not in loaded["markdown"]
    assert not any(gap["code"] == "IMAGE_UNAVAILABLE" for gap in descriptor["gaps"])
