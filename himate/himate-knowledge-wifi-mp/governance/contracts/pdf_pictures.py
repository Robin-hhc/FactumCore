"""Recover native PDF bitmaps and export bounded, content-addressed pictures.

PDFium is used synchronously after document conversion.  Page rendering and
knowledge interpretation are deliberately outside this adapter.
"""
from __future__ import annotations

from collections import defaultdict
from io import BytesIO
import hashlib
from itertools import product
import math
from pathlib import Path
import time

from .validation import _workspace_no_links


_TOLERANCE = 0.1
_NEIGHBOURS = tuple(product((-1, 0, 1), repeat=4))
_MAX_PAGE_OBJECTS = 100_000
_MAX_FILES = 99_996  # Leave room for the four fixed document-material files.
_MISSING = object()


class _Assets:
    def __init__(self, output, options):
        self.output = output
        self.deadline = time.monotonic() + options["timeout_seconds"]
        self.limit = options["max_output_bytes"]
        self.pixel_limit = self.limit // 4
        self.refs = {}
        self.bytes = 0
        self.files = 0
        self.available = False
        try:
            _workspace_no_links(output)
            for path in output.rglob("*"):
                if path.is_file():
                    self.bytes += path.stat().st_size
                    self.files += 1
            (output / "images").mkdir(exist_ok=True)
            _workspace_no_links(output / "images")
            self.available = True
        except (OSError, ValueError):
            pass

    def ready(self):
        return self.available and time.monotonic() < self.deadline

    def image_fits(self, width, height):
        return (self.ready() and type(width) is int and type(height) is int
                and width > 0 and height > 0 and width * height <= self.pixel_limit)

    def save(self, image, digest):
        if digest in self.refs:
            return self.refs[digest]
        if not self.image_fits(*image.size) or self.files >= _MAX_FILES:
            return None
        try:
            from docling_core.types.doc import ImageRef, Size

            buffer = BytesIO()
            image.save(buffer, format="PNG")
            raw = buffer.getvalue()
            if not self.ready() or self.bytes + len(raw) > self.limit:
                return None
            relative = Path("images") / (digest + ".png")
            target = self.output / relative
            _workspace_no_links(target)
            target.write_bytes(raw)
            self.bytes += len(raw)
            self.files += 1
            reference = ImageRef(mimetype="image/png", dpi=72,
                                 size=Size(width=image.width, height=image.height), uri=relative)
            self.refs[digest] = reference
            return reference
        except (OSError, ValueError, TypeError):
            return None


def _rgba(image, assets):
    if image is None or not assets.image_fits(*image.size):
        return None
    # Both source ImageRefs and PDFium-to-PIL views can be borrowed.  Retain an
    # independent image; closing either borrowed image can corrupt its owner.
    return image.copy() if image.mode == "RGBA" else image.convert("RGBA")


def _fingerprint(image):
    digest = hashlib.sha256(b"himate-pdf-rgba:1\0")
    digest.update(image.width.to_bytes(8, "big"))
    digest.update(image.height.to_bytes(8, "big"))
    # Bound temporary pixel copies independently of an image's full dimensions.
    for top in range(0, image.height, 256):
        digest.update(image.crop((0, top, image.width, min(top + 256, image.height))).tobytes())
    return digest.hexdigest()


def _picture_bounds(picture, document):
    if len(picture.prov) != 1:
        return None
    provenance = picture.prov[0]
    page = document.pages.get(provenance.page_no)
    if page is None:
        return None
    box = provenance.bbox.to_bottom_left_origin(page.size.height)
    values = (box.l, box.b, box.r, box.t)
    if (not all(math.isfinite(value) for value in values)
            or values[0] >= values[2] or values[1] >= values[3]):
        return None
    return provenance.page_no, values


def _page_geometry(page, expected):
    left, bottom, right, top = page.get_bbox()
    width, height = right - left, top - bottom
    rotation = page.get_rotation()
    shown = (height, width) if rotation in (90, 270) else (width, height)
    if (rotation not in (0, 90, 180, 270)
            or not all(math.isfinite(value) for value in (left, bottom, width, height))
            or min(width, height) <= 0
            or abs(shown[0] - expected.width) > _TOLERANCE
            or abs(shown[1] - expected.height) > _TOLERANCE):
        return None
    return left, bottom, width, height, rotation


def _object_bounds(obj, geometry):
    points = obj.get_quad_points()
    parent = obj.container
    depth = 0
    while parent is not None:
        depth += 1
        if depth > 15:
            return None
        matrix = parent.get_matrix()
        points = tuple(matrix.on_point(*point) for point in points)
        parent = parent.container
    left, bottom, width, height, rotation = geometry
    transformed = []
    for x, y in points:
        x, y = x - left, y - bottom
        if rotation == 90:
            x, y = y, width - x
        elif rotation == 180:
            x, y = width - x, height - y
        elif rotation == 270:
            x, y = height - y, x
        transformed.append((x, y))
    bounds = (min(x for x, _ in transformed), min(y for _, y in transformed),
              max(x for x, _ in transformed), max(y for _, y in transformed))
    if (not all(math.isfinite(value) for value in bounds)
            or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        return None
    return bounds


def _bucket(bounds):
    return tuple(math.floor(value / _TOLERANCE) for value in bounds)


def _placed_pixels(obj, assets, width, height, *, sample_scale=None):
    left, bottom, right, top = obj.get_bounds()
    content_width, content_height = right - left, top - bottom
    if (not all(math.isfinite(value) for value in (content_width, content_height))
            or min(content_width, content_height) <= 0):
        return None
    if (width < height) != (content_width < content_height):
        width, height = height, width
    scale = sample_scale if sample_scale is not None else max(width / content_width, height / content_height)
    if not assets.image_fits(math.ceil(content_width * scale), math.ceil(content_height * scale)):
        return None
    if sample_scale is None:
        bitmap = obj.get_bitmap(render=True)
    else:
        matrix = obj.get_matrix()
        try:
            obj.set_matrix(matrix.scale(scale, scale))
            bitmap = obj.get_bitmap(render=True, scale_to_original=False)
        finally:
            obj.set_matrix(matrix)
    return _rgba(bitmap.to_pil(), assets)


def _decode(obj, assets):
    if not assets.ready():
        return None
    try:
        width, height = obj.get_px_size()
        if not assets.image_fits(width, height):
            return None
        # Decode the source pixels and its alpha mask, without resampling them
        # for each occurrence's placement/rotation.  Geometry matching already
        # used the original matrix; restore it even if PDFium cannot decode.
        matrix = obj.get_matrix()
        try:
            obj.set_matrix(type(matrix)(width, 0, 0, height, 0, 0))
            bitmap = obj.get_bitmap(render=True, scale_to_original=False)
        finally:
            obj.set_matrix(matrix)
        if not assets.image_fits(bitmap.width, bitmap.height):
            return None
        image = _rgba(bitmap.to_pil(), assets)
        if image is None:
            return None
        if image.getchannel("A").getbbox() is None:
            # A thin clipped edge can vanish when normalized to the source
            # pixel grid. Check the original placement before exporting an
            # empty image; its extra edge samples must not be silently lost.
            placed = _placed_pixels(obj, assets, width, height)
            if placed is None:
                return None
            if placed.getchannel("A").getbbox() is not None:
                image = placed
            else:
                # A second sampling grid retains subpixel clip edges that
                # also round to zero at the native placement's resolution.
                detailed = _placed_pixels(obj, assets, width, height, sample_scale=4)
                if detailed is None:
                    return None
                if detailed.getchannel("A").getbbox() is not None:
                    image = detailed
        return image, _fingerprint(image)
    except Exception:
        # A failed bitmap must leave the native text and its locations usable.
        return None


def _occurrence_ref(reference, picture, original_dpis):
    if reference is None:
        return None
    dpi = original_dpis.get(picture.self_ref)
    if dpi is None:
        width = picture.prov[0].bbox.width
        dpi = max(1, round(reference.size.width * 72 / width)) if width > 0 else 72
    return reference.model_copy(update={"dpi": dpi})


def _recover_page(page, pictures, document, assets, image_type, original_dpis):
    geometry = _page_geometry(page, document.pages[pictures[0][0].prov[0].page_no].size)
    if geometry is None:
        return
    groups, index = {}, defaultdict(list)
    for number, obj in enumerate(page.get_objects(filter=[image_type], max_depth=15)):
        if number >= _MAX_PAGE_OBJECTS or not assets.ready():
            return
        try:
            bounds = _object_bounds(obj, geometry)
        except Exception:
            continue
        if bounds is not None:
            # Group exact repeats first so overlapping repeated draws do not
            # create a quadratic scan for every native picture occurrence.
            key = tuple(round(value, 6) for value in bounds)
            if key not in groups:
                groups[key] = []
                index[_bucket(bounds)].append((bounds, groups[key]))
            groups[key].append(obj)

    recovered, fingerprints = {}, {}
    for picture, bounds in pictures:
        if not assets.ready():
            return
        key = tuple(round(value, 6) for value in bounds)
        if key in recovered:
            picture.image = _occurrence_ref(recovered[key], picture, original_dpis)
            continue
        candidates = []
        base = _bucket(bounds)
        for offset in _NEIGHBOURS:
            cell = tuple(value + shift for value, shift in zip(base, offset))
            for actual, objects in index.get(cell, ()):
                if all(abs(a - b) <= _TOLERANCE for a, b in zip(actual, bounds)):
                    candidates.extend(objects)

        selected, selected_digest, failed = None, None, False
        for obj in candidates:
            digest = fingerprints.get(id(obj), _MISSING)
            image = None
            if digest is _MISSING:
                decoded = _decode(obj, assets)
                if decoded is None:
                    digest = None
                else:
                    image, digest = decoded
                fingerprints[id(obj)] = digest
            if digest is None or (selected_digest is not None and digest != selected_digest):
                failed = True
                break
            if selected_digest is None:
                selected_digest, selected = digest, image
                if selected is None and digest not in assets.refs:
                    decoded = _decode(obj, assets)
                    if decoded is None:
                        failed = True
                        break
                    selected, _ = decoded
        reference = None
        if not failed and selected_digest is not None:
            reference = assets.refs.get(selected_digest)
            if reference is None and selected is not None:
                reference = assets.save(selected, selected_digest)
        recovered[key] = reference
        picture.image = _occurrence_ref(reference, picture, original_dpis)


def recover_and_export(document, data, output: Path, options: dict) -> None:
    """Recover bitmaps, retaining every occurrence's native provenance.

    Successful pictures share local assets by canonical RGBA content and size.
    Failures, ambiguity and exhausted budgets stay explicit missing pictures;
    the caller records its existing IMAGE_UNAVAILABLE diagnostics for them.
    """
    assets = _Assets(Path(output), options)
    missing = defaultdict(list)
    original_dpis = {}
    native = options.get("pipeline", "native") == "native"
    for picture in document.pictures:
        if picture.image is not None and picture.image.dpi > 0:
            original_dpis[picture.self_ref] = picture.image.dpi
        if native:
            # Even a decoded native RGB image can lack its separate alpha
            # mask.  Use the original PDF object for every native occurrence;
            # an unverified old bitmap is not a safe recovery fallback.
            picture.image = None
        elif picture.image is not None:
            try:
                image = _rgba(picture.get_image(document), assets)
                reference = assets.save(image, _fingerprint(image)) if image is not None else None
                picture.image = _occurrence_ref(reference, picture, original_dpis)
            except Exception:
                picture.image = None
        if picture.image is None:
            location = _picture_bounds(picture, document)
            if location is not None:
                number, bounds = location
                missing[number].append((picture, bounds))
    if not missing or not assets.ready():
        return
    pdf = None
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        for number, pictures in sorted(missing.items()):
            if not assets.ready():
                break
            if not 1 <= number <= len(pdf):
                continue
            page = pdf[number - 1]
            try:
                _recover_page(page, pictures, document, assets, pdfium.raw.FPDF_PAGEOBJ_IMAGE, original_dpis)
            except Exception:
                # One unsupported page geometry must not hide another page's
                # usable text or prevent recovery of later pages.
                pass
            finally:
                page.close()
    except Exception:
        pass
    finally:
        if pdf is not None:
            pdf.close()
