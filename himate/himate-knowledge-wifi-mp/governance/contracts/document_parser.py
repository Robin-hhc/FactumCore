"""Per-operation document materials; legacy extraction remains independently readable.

This module never starts installation, downloads models, or interprets knowledge.
Descriptors bind an operation's fixed inputs and files, not a persistent cache.
"""
from __future__ import annotations

from collections import defaultdict
from importlib import metadata
from io import BytesIO
import hashlib
import math
from pathlib import Path, PurePosixPath
import re
import sys
import time
from urllib.parse import unquote

from .validation import ContractError, _workspace_no_links, canonical_bytes, read_json, safe_path as _relative_path, sha256_bytes, validate_id


SUPPORTED_FORMATS = frozenset({
    ".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".csv",
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
})
IMAGE_FORMATS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})
_DEFAULTS = {
    "pipeline": "native", "models_path": None, "ocr_languages": ["ch"], "threads": 4,
    "timeout_seconds": 300, "max_input_bytes": 256 * 1024 * 1024,
    "max_pages": 2000, "max_output_bytes": 256 * 1024 * 1024, "images_scale": 1.0,
}
_HASH = re.compile(r"[0-9a-f]{64}")
_CELL = re.compile(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]{0,6})")
_PREVIEW_LIMITS = {"max_pages": 8, "max_pixels": 16_000_000, "max_png_bytes": 16 * 1024 * 1024, "scale": 1.5}


def safe_path(root, reference, allowed_prefixes=None):
    path = _relative_path(root, reference, allowed_prefixes)
    _workspace_no_links(path)
    return path


def _output(root, reference):
    path = safe_path(root, reference)
    parts = PurePosixPath(reference).parts
    if (parts == (".build", "materials", "parsed")
            or (len(parts) == 4 and parts[:3] == (".build", "materials", "references"))):
        return path
    if (len(parts) == 4 and parts[:2] == ("artifacts", "source-read")
            and parts[3] == "parsed" and re.fullmatch(r"[0-9a-f]{32}", parts[2])):
        return path
    raise ContractError("PARSE_OUTPUT_UNSAFE", "Use this operation's materials or source-read directory", reference)


def _options(root, value):
    if value is not None and not isinstance(value, dict):
        raise ContractError("PARSE_OPTIONS_INVALID", "Parser options must be an object")
    if set(value or {}) - set(_DEFAULTS):
        raise ContractError("PARSE_OPTIONS_INVALID", "Unknown parser options: " + ", ".join(sorted(set(value) - set(_DEFAULTS))))
    result = {**_DEFAULTS, **(value or {})}
    if not isinstance(result["pipeline"], str) or result["pipeline"] not in {"native", "standard"}:
        raise ContractError("PARSE_OPTIONS_INVALID", "pipeline must be native or standard")
    for field in ("threads", "max_input_bytes", "max_pages", "max_output_bytes"):
        if type(result[field]) is not int or result[field] < 1:
            raise ContractError("PARSE_OPTIONS_INVALID", field + " must be a positive integer")
        maximum = {"threads": 32, "max_input_bytes": 256 * 1024 * 1024,
                   "max_output_bytes": 256 * 1024 * 1024}.get(field)
        if maximum is not None and result[field] > maximum:
            raise ContractError("PARSE_OPTIONS_INVALID", field + " exceeds the supported operation limit")
    for field in ("timeout_seconds", "images_scale"):
        if type(result[field]) not in (int, float) or not 0 < result[field] <= sys.float_info.max:
            raise ContractError("PARSE_OPTIONS_INVALID", field + " must be positive and finite")
        if result[field] > {"timeout_seconds": 3600, "images_scale": 4}[field]:
            raise ContractError("PARSE_OPTIONS_INVALID", field + " exceeds the supported operation limit")
    languages = result["ocr_languages"]
    if (not isinstance(languages, list) or not languages
            or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,40}", x) for x in languages)):
        raise ContractError("PARSE_OPTIONS_INVALID", "ocr_languages must contain explicit language codes")
    result["ocr_languages"] = list(languages)
    if result["models_path"] is not None:
        safe_path(root, result["models_path"], ["artifacts/models"])
        if not result["models_path"].startswith("artifacts/models/"):
            raise ContractError("PARSE_OPTIONS_INVALID", "models_path must be beneath artifacts/models")
    return result


def _page_range(value):
    if value is None:
        return None
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(x) is not int for x in value) or not 1 <= value[0] <= value[1]):
        raise ContractError("PARSE_RANGE_INVALID", "Expected inclusive positive page_start/page_end")
    return list(value)


def _profile(options, suffix, root):
    versions = {}
    packages = [] if suffix in {".md", ".txt"} else ["docling-slim", "docling", "docling-core"]
    packages += {".pdf": ["docling-parse"], ".docx": ["python-docx"], ".xlsx": ["openpyxl"], ".pptx": ["python-pptx"]}.get(suffix, [])
    if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS):
        packages += ["rapidocr", "onnxruntime", "torch", "transformers", "docling-ibm-models"]
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    models = []
    if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS) and options["models_path"]:
        directory = safe_path(root, options["models_path"], ["artifacts/models"])
        for path in sorted(directory.rglob("*")):
            if path.is_file() and ".cache" not in path.parts and path.suffix in {".json", ".safetensors", ".onnx", ".bin", ".pth", ".txt", ".yaml"}:
                safe_path(root, path.relative_to(root).as_posix(), [options["models_path"]])
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                models.append({"ref": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    return {"adapter": "himate-document:1", "format": suffix, "versions": versions, "model_files": models,
            "options": options, "remote_services": False, "external_plugins": False,
            "remote_resource_fetch": False, "local_resource_fetch": False,
            "picture_description": "host_agent", "generate_page_images": False,
            "generate_picture_images": True}


def _gap(code, message, *, locator=None, severity="warning"):
    value = {"code": code, "message": str(message), "severity": severity}
    if locator is not None:
        value["locator"] = locator
    return value


def _write_json(path, value):
    path.write_bytes(canonical_bytes(value))


def _external_images(data, suffix):
    text = data.decode("utf-8-sig", errors="replace") if suffix in {".html", ".htm"} else ""
    matches = re.findall(r"<img\b[^>]*\bsrc\s*=\s*(?:['\"]([^'\"]+)['\"]|([^\s>]+))", text, re.IGNORECASE)
    refs = [quoted or bare for quoted, bare in matches]
    return [ref for ref in refs if not ref.lower().startswith("data:")]


def _sanitize_markdown_images(text):
    """Native Markdown cannot authorize image fetches through its rendered view."""
    found = []
    patterns = [r"<img\b[^>]*>", r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)",
                r"!\[[^\]]*\]\s*\[[^\]]*\]", r"!\[[^\]]*\]"]
    def replace(match):
        found.append(match[0])
        return "[Image not read; inspect the original source]" + "\n" * match[0].count("\n")
    for pattern in patterns:
        text = re.sub(pattern, replace, text, flags=re.IGNORECASE)
    return text, found


def _markdown_image_uris(text):
    values = []
    for match in re.finditer(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))", text):
        values.append(match[1] or match[2])
    if re.search(r"<img\b|!\[[^\]]*\]\s*\[", text, re.IGNORECASE):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Unsupported raw/reference image syntax in material Markdown")
    return values


def _native_text(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractError("UNREADABLE_DOCUMENT", "Text documents require UTF-8") from exc
    if not text.strip() or "\x00" in text:
        raise ContractError("UNREADABLE_DOCUMENT", "Text must be nonempty without NUL")
    return text


def _models(root, options):
    if options["models_path"] is None:
        raise ContractError("PARSER_MODELS_REQUIRED", "standard OCR requires preinstalled artifacts/models assets")
    directory = safe_path(root, options["models_path"], ["artifacts/models"])
    if not directory.is_dir():
        raise ContractError("PARSER_MODELS_REQUIRED", "The configured local model directory is unavailable")
    required = ["docling-project--docling-layout-heron/config.json",
                "docling-project--docling-layout-heron/preprocessor_config.json",
                "docling-project--docling-layout-heron/model.safetensors",
                "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
                "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
                "RapidOcr/PP-OCRv6_det_small.onnx", "RapidOcr/PP-OCRv6_rec_small.onnx",
                "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx"]
    for reference in required:
        path = safe_path(directory, reference)
        if not path.is_file() or not path.stat().st_size:
            raise ContractError("PARSER_MODELS_REQUIRED", "Preinstalled standard model set is incomplete: " + reference)
    return directory


def _converter(root, suffix, options):
    models = _models(root, options) if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS) else None
    from docling.document_converter import (
        DocumentConverter, ExcelFormatOption, HTMLFormatOption, ImageFormatOption,
        NativePdfFormatOption, PdfFormatOption, PowerpointFormatOption, WordFormatOption,
    )
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.backend_options import HTMLBackendOptions, MsExcelBackendOptions, MsPowerpointBackendOptions, MsWordBackendOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import ConvertPipelineOptions, NativePdfPipelineOptions, PdfPipelineOptions, RapidOcrOptions

    common = {"accelerator_options": AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=options["threads"]),
              "document_timeout": options["timeout_seconds"], "enable_remote_services": False,
              "allow_external_plugins": False, "do_picture_description": False,
              "do_picture_classification": False, "do_chart_extraction": False}
    native = NativePdfPipelineOptions(**common, generate_page_images=False, generate_picture_images=True, parser_threads=options["threads"],
                                     images_scale=options["images_scale"])
    formats = {
        InputFormat.PDF: NativePdfFormatOption(pipeline_options=native),
        InputFormat.DOCX: WordFormatOption(pipeline_options=ConvertPipelineOptions(**common), backend_options=MsWordBackendOptions(enable_remote_fetch=False, enable_local_fetch=False, render_chart_images=False)),
        InputFormat.XLSX: ExcelFormatOption(pipeline_options=ConvertPipelineOptions(**common), backend_options=MsExcelBackendOptions(enable_remote_fetch=False, enable_local_fetch=False, render_chart_images=False)),
        InputFormat.PPTX: PowerpointFormatOption(pipeline_options=ConvertPipelineOptions(**common), backend_options=MsPowerpointBackendOptions(enable_remote_fetch=False, enable_local_fetch=False, render_chart_images=False)),
        InputFormat.HTML: HTMLFormatOption(pipeline_options=ConvertPipelineOptions(**common), backend_options=HTMLBackendOptions(enable_remote_fetch=False, enable_local_fetch=False)),
    }
    if models is not None:
        standard = PdfPipelineOptions(**common, artifacts_path=models, do_ocr=True,
                                      generate_page_images=False, generate_picture_images=True,
                                      images_scale=options["images_scale"])
        standard.ocr_options = RapidOcrOptions(backend="onnxruntime", lang=options["ocr_languages"], force_full_page_ocr=True)
        formats[InputFormat.PDF] = PdfFormatOption(pipeline_options=standard)
        formats[InputFormat.IMAGE] = ImageFormatOption(pipeline_options=standard)
    return DocumentConverter(format_options=formats)


def _raster_document(data, name):
    from PIL import Image
    from docling_core.types.doc import BoundingBox, CoordOrigin, DoclingDocument, ImageRef, ProvenanceItem, Size
    image = Image.open(BytesIO(data))
    image.load()
    document = DoclingDocument(name=name)
    document.add_page(page_no=1, size=Size(width=image.width, height=image.height))
    document.add_picture(image=ImageRef.from_pil(image=image, dpi=72),
                         prov=ProvenanceItem(page_no=1, charspan=(0, 0), bbox=BoundingBox(l=0, t=0, r=image.width, b=image.height, coord_origin=CoordOrigin.TOPLEFT)))
    return document


def _multiframe_gap(data, suffix, pages):
    """A first-frame image backend cannot certify a multi-frame original."""
    if suffix not in IMAGE_FORMATS:
        return None
    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as image:
            count = getattr(image, "n_frames", 1)
    except ImportError:
        return None  # The conversion failure already reports missing dependencies.
    except (OSError, ValueError, EOFError):
        return _gap("IMAGE_FRAME_COUNT_UNAVAILABLE", "The original image frame count could not be verified", severity="review")
    if count <= 1:
        return None
    read = 1 if 1 in pages else 0
    gap = _gap("UNSUPPORTED_MULTIFRAME",
               f"Image contains {count} frames; this backend reads at most the first frame. "
               f"Read {read}; unprocessed {count - read}; later frames have not been interpreted or OCR-processed.",
               severity="review")
    gap.update(total_frames=count, read_frames=read, unread_frames=count - read)
    return gap


def _pdf_page_previews(root, data, output, options, page_range, pages, source_hash):
    """Render only an explicit, small physical-page request, separately from extraction."""
    if page_range is None:
        return [], [], None
    metadata_record = {**_PREVIEW_LIMITS, "requested_range": list(page_range), "rendered_pages": [],
                       "pixels": 0, "png_bytes": 0, "assets": [], "source_sha256": source_hash}
    images, gaps = [], []
    started = time.perf_counter()
    first, last = page_range
    if last - first + 1 > _PREVIEW_LIMITS["max_pages"]:
        return [], [_gap("PAGE_PREVIEW_PAGE_LIMIT", "Page previews support at most eight explicitly selected pages", severity="review")], metadata_record
    selected = list(range(first, last + 1))
    if not set(selected).issubset(pages):
        return [], [_gap("PAGE_PREVIEW_RANGE_UNAVAILABLE", "Not all requested physical pages were extracted", severity="review")], metadata_record
    pdf = None
    try:
        import pypdfium2 as pdfium
        metadata_record["renderer"] = "pypdfium2:" + metadata.version("pypdfium2")
        pdf = pdfium.PdfDocument(data)
        if last > len(pdf):
            raise ValueError("Preview page range is outside the original PDF")
        dimensions = []
        for number in selected:
            page = pdf[number - 1]
            try:
                width, height = page.get_size()
            finally:
                page.close()
            if (not math.isfinite(width) or not math.isfinite(height) or min(width, height) <= 0
                    or max(width, height) > _PREVIEW_LIMITS["max_pixels"]):
                raise ValueError("PDF page geometry is outside the preview budget")
            dimensions.append((math.ceil(width * _PREVIEW_LIMITS["scale"]), math.ceil(height * _PREVIEW_LIMITS["scale"])))
        if sum(width * height for width, height in dimensions) > _PREVIEW_LIMITS["max_pixels"]:
            gaps.append(_gap("PAGE_PREVIEW_PIXEL_LIMIT", "Selected pages exceed the total preview pixel budget; no pages were rendered", severity="review"))
        else:
            existing = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
            byte_budget = min(_PREVIEW_LIMITS["max_png_bytes"], max(0, options["max_output_bytes"] - existing))
            for number, (width, height) in zip(selected, dimensions):
                page, bitmap = pdf[number - 1], None
                try:
                    bitmap = page.render(scale=_PREVIEW_LIMITS["scale"])
                    image = bitmap.to_pil()
                    try:
                        buffer = BytesIO()
                        image.save(buffer, format="PNG")
                        raw = buffer.getvalue()
                    finally:
                        image.close()
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
                if metadata_record["png_bytes"] + len(raw) > byte_budget:
                    gaps.append(_gap("PAGE_PREVIEW_BYTE_LIMIT", "PNG previews exceed the preview or remaining operation byte budget; later pages were not saved", locator={"kind": "page", "page": number}, severity="review"))
                    break
                local_ref = f"images/page_preview_{number:06}.png"
                target = safe_path(output, local_ref, ["images"])
                target.parent.mkdir(exist_ok=True)
                _workspace_no_links(target.parent)
                target.write_bytes(raw)
                ref = target.relative_to(root).as_posix()
                asset = {"ref": ref, "local_ref": local_ref, "page": number, "width": width, "height": height, "bytes": len(raw)}
                metadata_record["assets"].append(asset)
                metadata_record["rendered_pages"].append(number)
                metadata_record["pixels"] += width * height
                metadata_record["png_bytes"] += len(raw)
                images.append({"ref": ref, "element_ref": None, "locator": {"kind": "page", "page": number},
                               "role": "page_preview", "source_sha256": source_hash,
                               "provenance": [{"page_no": number}], "ocr_status": "not_requested", "description_status": "agent_required"})
    except Exception as error:
        gaps.append(_gap("PAGE_PREVIEW_UNAVAILABLE", "Physical-page rendering failed without replacing extracted text: " + str(error), severity="review"))
    finally:
        if pdf is not None:
            pdf.close()
    metadata_record["seconds"] = time.perf_counter() - started
    return images, gaps, metadata_record


def _attach_previews(output, preview):
    document = read_json(output / "document.json")
    body = document.setdefault("body", {})
    body["meta"] = body.get("meta") or {}
    body["meta"]["himate__page_previews"] = preview
    _write_json(output / "document.json", document)
    additions = "".join(f"\n\nPhysical page {asset['page']} preview (rendered, not an extracted source bitmap):\n\n![Page {asset['page']}]({asset['local_ref']})" for asset in preview["assets"])
    if additions:
        with (output / "document.md").open("ab") as stream:
            stream.write(additions.encode("utf-8"))


def _validate_previews(root, output, manifest, document, registered):
    preview = manifest.get("page_preview")
    image_rows = [row for row in manifest.get("images", []) if row.get("role") == "page_preview"]
    document_preview = ((document.get("body") or {}).get("meta") or {}).get("himate__page_previews")
    if preview is None:
        if image_rows or document_preview is not None:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Unregistered page-preview metadata")
        return
    if not isinstance(preview, dict) or document_preview != preview:
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "JSON and manifest page previews differ")
    bounds = _page_range(manifest.get("page_range"))
    if (bounds is None or preview.get("requested_range") != bounds
            or preview.get("source_sha256") != manifest["source_sha256"]):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview source/page scope differs")
    for field, maximum in _PREVIEW_LIMITS.items():
        value = preview.get(field)
        if type(value) not in (int, float) or not 0 < value <= maximum:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Invalid preview resource budget")
    assets = preview.get("assets")
    if not isinstance(assets, list) or len(assets) > preview["max_pages"] or len(image_rows) != len(assets):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Invalid page-preview asset set")
    rendered, pixels, byte_count, refs = [], 0, 0, set()
    for asset in assets:
        page = asset.get("page")
        if (type(page) is not int or not bounds[0] <= page <= bounds[1]
                or page not in manifest.get("pages", []) or page in rendered):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview is not an extracted physical page")
        ref, local_ref = asset.get("ref"), asset.get("local_ref")
        path = safe_path(output, local_ref, ["images"])
        if path.relative_to(root).as_posix() != ref or ref not in registered or ref in refs:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview asset is not registered inside images")
        matches = [row for row in image_rows if row.get("ref") == ref]
        if (len(matches) != 1 or matches[0].get("locator") != {"kind": "page", "page": page}
                or matches[0].get("element_ref") is not None
                or matches[0].get("source_sha256") != manifest["source_sha256"]):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview image identity differs")
        from PIL import Image
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != (asset.get("width"), asset.get("height")):
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview PNG geometry differs")
            image.verify()
        if path.stat().st_size != asset.get("bytes"):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview byte count differs")
        rendered.append(page)
        refs.add(ref)
        pixels += asset["width"] * asset["height"]
        byte_count += asset["bytes"]
    if (rendered != preview.get("rendered_pages") or pixels != preview.get("pixels")
            or byte_count != preview.get("png_bytes") or pixels > preview["max_pixels"]
            or byte_count > preview["max_png_bytes"]):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview coverage or resource accounting differs")


def _item_text(item):
    if hasattr(item, "text"):
        return item.text
    if getattr(item, "label", None) == "table" or hasattr(item, "data"):
        rows = defaultdict(list)
        for cell in getattr(getattr(item, "data", None), "table_cells", []):
            rows[cell.start_row_offset_idx].append((cell.start_col_offset_idx, cell.text))
        return "\n".join(" | ".join(text for _, text in sorted(rows[row])) for row in sorted(rows))
    description = getattr(getattr(item, "meta", None), "description", None)
    return getattr(description, "text", "")


def _column(number):
    text = ""
    while number:
        number, rest = divmod(number - 1, 26)
        text = chr(65 + rest) + text
    return text


def _range_box(reference):
    parts = reference.split(":") if isinstance(reference, str) else []
    if len(parts) not in (1, 2) or any(not _CELL.fullmatch(x) for x in parts):
        raise ContractError("INVALID_SOURCE_LOCATOR", "Expected an Excel cell or cell range")
    values = []
    for part in parts:
        match = _CELL.fullmatch(part)
        column = 0
        for char in match[1].upper():
            column = column * 26 + ord(char) - 64
        row = int(match[2])
        if column > 16384 or row > 1048576:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Excel cell is out of bounds")
        values.append((column - 1, row - 1))
    first, last = values[0], values[-1]
    if first[0] > last[0] or first[1] > last[1]:
        raise ContractError("INVALID_SOURCE_LOCATOR", "Cell range must be ordered")
    return first[0], first[1], last[0] + 1, last[1] + 1


def _document_segments(document, suffix, source_hash, profile_hash):
    segments, pages = [], defaultdict(list)
    groups = {group.self_ref: group for group in document.groups}
    for item, _ in document.iterate_items(traverse_pictures=True):
        reference = getattr(item, "self_ref", None)
        if not reference:
            continue
        text = _item_text(item)
        locator = {"kind": "element", "ref": reference, "source_sha256": source_hash, "profile_sha256": profile_hash}
        segments.append({"locator": locator, "text": text})
        for page in sorted({p.page_no for p in getattr(item, "prov", [])}):
            if text:
                pages[page].append(text)
        if suffix == ".xlsx" and hasattr(item, "data") and getattr(item, "prov", []):
            parent = getattr(item, "parent", None)
            sheet = None
            seen = set()
            while parent and parent.cref in groups and parent.cref not in seen:
                seen.add(parent.cref)
                group = groups[parent.cref]
                if str(group.label) in {"sheet", "GroupLabel.SHEET"}:
                    sheet = group.name
                    break
                parent = getattr(group, "parent", None)
            if sheet is not None:
                box = item.prov[0].bbox
                left, top = int(box.l), int(box.t)
                for cell in item.data.table_cells:
                    start_col = left + cell.start_col_offset_idx
                    start_row = top + cell.start_row_offset_idx
                    end_col = start_col + cell.col_span
                    end_row = start_row + cell.row_span
                    cell_range = f"{_column(start_col + 1)}{start_row + 1}:{_column(end_col)}{end_row}"
                    segments.append({"locator": {"kind": "cell_range", "sheet": sheet, "range": cell_range}, "text": cell.text})
    for page in sorted(document.pages):
        kind = "slide" if suffix == ".pptx" else "page"
        if suffix in {".pdf", ".pptx"} | IMAGE_FORMATS:
            segments.append({"locator": {"kind": kind, kind: page}, "text": "\n\n".join(pages[page])})
    return segments


def _docling(root, source, data, output, options, page_range, source_hash, profile_hash):
    from docling_core.types.doc import ImageRefMode
    from docling.datamodel.base_models import DocumentStream
    suffix = PurePosixPath(source["path"]).suffix.lower()
    gaps, original_images = [], set()
    if suffix in IMAGE_FORMATS and options["pipeline"] == "native":
        document = _raster_document(data, PurePosixPath(source["path"]).stem)
    else:
        converter = _converter(root, suffix, options)
        arguments = {"max_num_pages": options["max_pages"], "max_file_size": options["max_input_bytes"]}
        if page_range is not None:
            arguments["page_range"] = tuple(page_range)
        result = converter.convert(DocumentStream(name=PurePosixPath(source["path"]).name, stream=BytesIO(data)), **arguments)
        document = result.document
        if getattr(result.status, "value", str(result.status)) != "success":
            gaps.append(_gap("DOCUMENT_PARTIAL", "Docling did not report a clean conversion", severity="review"))
        gaps.extend(_gap("DOCUMENT_CONVERSION_ERROR", getattr(error, "error_message", str(error)), severity="review") for error in result.errors)
        if suffix in ({".pdf"} | IMAGE_FORMATS) and options["pipeline"] == "standard":
            # Layout may turn a whole scanned page into TextItems. Retain the
            # embedded source bitmaps independently so OCR never erases the view.
            from docling_core.types.doc import ImageRef
            if suffix == ".pdf":
                native_options = {**options, "pipeline": "native"}
                native = _converter(root, suffix, native_options).convert(
                    DocumentStream(name=PurePosixPath(source["path"]).name, stream=BytesIO(data)), **arguments).document
            else:
                native = _raster_document(data, PurePosixPath(source["path"]).stem)
            for picture in native.pictures:
                image = picture.get_image(native)
                if image is not None:
                    kept = document.add_picture(image=ImageRef.from_pil(image=image, dpi=72),
                                                prov=picture.prov[0] if picture.prov else None)
                    original_images.add(kept.self_ref)
    document.save_as_markdown(output / "document.md", artifacts_dir=Path("images"), image_mode=ImageRefMode.REFERENCED, traverse_pictures=True, mark_meta=True)
    document.save_as_json(output / "document.json", artifacts_dir=Path("images"), image_mode=ImageRefMode.REFERENCED, ensure_ascii=False)
    segments = _document_segments(document, suffix, source_hash, profile_hash)
    text = "\n\n".join(segment["text"] for segment in segments if segment["locator"]["kind"] == "element" and segment["text"])
    exported = read_json(output / "document.json")
    images = []
    image_pages = set()
    for picture in exported.get("pictures", []):
        provenance = picture.get("prov", [])
        locator = {"kind": "element", "ref": picture["self_ref"], "source_sha256": source_hash, "profile_sha256": profile_hash}
        uri = (picture.get("image") or {}).get("uri")
        image_ref = None
        if isinstance(uri, str) and uri.startswith("images/"):
            asset = safe_path(output, uri, ["images"])
            if asset.is_file():
                image_ref = asset.relative_to(Path(root).resolve()).as_posix()
        if image_ref is None:
            gaps.append(_gap("IMAGE_UNAVAILABLE", "An extracted picture has no saved local image", locator=locator, severity="review"))
        images.append({"ref": image_ref, "element_ref": picture["self_ref"], "locator": locator,
                       "role": "source_bitmap" if picture["self_ref"] in original_images else "document_picture",
                       "provenance": provenance, "ocr_status": "unverified" if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS) else "not_requested",
                       "description_status": "agent_required"})
        image_pages.update(p["page_no"] for p in provenance)
    if options["pipeline"] == "native" and suffix in ({".pdf"} | IMAGE_FORMATS):
        for segment in segments:
            locator = segment["locator"]
            if locator["kind"] == "page" and locator["page"] in image_pages and not segment["text"].strip():
                gaps.append(_gap("OCR_REQUIRED", "Image-only page retained; configure preinstalled standard OCR or read the image", locator=locator, severity="review"))
    return text, segments, images, gaps, sorted(document.pages)


def parse(root, source, data, output_ref, options=None, page_range=None):
    """Create a fresh operation bundle from already-fixed original bytes."""
    started = time.perf_counter()
    root = Path(root).absolute()
    _workspace_no_links(root)
    root = root.resolve(strict=True)
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        raise ContractError("PARSE_SOURCE_INVALID", "source requires id and path")
    source_id = validate_id(source.get("id") or source.get("source_id"))
    suffix = PurePosixPath(source["path"]).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ContractError("UNSUPPORTED_DOCUMENT_FORMAT", "No configured modern-format adapter", suffix)
    options = _options(root, options)
    page_range = _page_range(page_range)
    if page_range is not None and suffix not in ({".pdf", ".pptx", ".xlsx"} | IMAGE_FORMATS):
        raise ContractError("PARSE_RANGE_INVALID", "Page ranges apply to paginated formats")
    if not isinstance(data, bytes) or not data:
        raise ContractError("UNREADABLE_DOCUMENT", "Expected nonempty original bytes")
    if len(data) > options["max_input_bytes"]:
        raise ContractError("PARSE_INPUT_LIMIT", "Original exceeds max_input_bytes")
    output = _output(root, output_ref)
    if output.exists():
        raise ContractError("PARSE_OUTPUT_EXISTS", "Every parse requires a fresh operation directory", output_ref)
    profile = _profile(options, suffix, root)
    if page_range is not None:
        profile["page_range"] = list(page_range)
    source_hash, profile_hash = sha256_bytes(data), sha256_bytes(canonical_bytes(profile))
    output.mkdir(parents=True)
    _workspace_no_links(output)
    gaps, images, pages = [], [], []
    conversion_started = time.perf_counter()
    if suffix in {".md", ".txt"}:
        text = _native_text(data)
        if suffix == ".md":
            text, unresolved = _sanitize_markdown_images(text)
            gaps.extend(_gap("EXTERNAL_IMAGE_NOT_READ", "Markdown image was not fetched: " + ref, severity="review") for ref in unresolved)
        segments = [{"locator": {"kind": "lines", "start": n, "end": n}, "text": line} for n, line in enumerate(text.splitlines(), 1)]
        (output / "document.md").write_bytes(text.encode("utf-8"))
        _write_json(output / "document.json", {"schema_name": "HiMateTextDocument", "text": text})
        extractor = "himate-native-text:1"
    else:
        extractor = "docling:" + profile["versions"].get("docling-slim", profile["versions"].get("docling", "unavailable"))
        try:
            text, segments, images, gaps, pages = _docling(root, source, data, output, options, page_range, source_hash, profile_hash)
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            code = error.code if isinstance(error, ContractError) else "DOCUMENT_CONVERSION_UNAVAILABLE"
            gaps = [_gap(code, str(error), severity="review")]
            text, segments = "", []
            (output / "document.md").write_text("", encoding="utf-8")
            _write_json(output / "document.json", {"schema_name": "HiMateUnavailableDocument"})
    for reference in (_external_images(data, suffix) if suffix != ".md" else []):
        gaps.append(_gap("EXTERNAL_IMAGE_NOT_READ", "Image reference was not fetched: " + reference, severity="review"))
    multiframe = _multiframe_gap(data, suffix, pages)
    if multiframe is not None:
        gaps.append(multiframe)
    (output / "text.txt").write_bytes(text.encode("utf-8"))
    _write_json(output / "locators.json", {"schema_version": "1.0", "source_sha256": source_hash, "profile_sha256": profile_hash, "segments": segments})
    preview = None
    if suffix == ".pdf" and page_range is not None:
        preview_images, preview_gaps, preview = _pdf_page_previews(root, data, output, options, page_range, pages, source_hash)
        images.extend(preview_images)
        gaps.extend(preview_gaps)
        _attach_previews(output, preview)
    converted = time.perf_counter()
    files = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            safe_path(root, relative, [output_ref])
            raw = path.read_bytes()
            files.append({"ref": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    output_bytes = sum(row["bytes"] for row in files)
    if output_bytes > options["max_output_bytes"]:
        raise ContractError("PARSE_OUTPUT_LIMIT", "Parsed materials exceed max_output_bytes", output_ref)
    partial = any(gap.get("severity") == "review" for gap in gaps)
    manifest = {"schema_version": "1.0", "source_id": source_id, "source_path": source["path"],
                "source_sha256": source_hash, "profile_sha256": profile_hash, "profile": profile,
                "extractor": extractor, "parse_status": "partial" if partial else "parsed",
                "output_ref": output_ref, "page_range": page_range, "pages": pages,
                "text_ref": output_ref + "/text.txt", "markdown_ref": output_ref + "/document.md",
                "document_ref": output_ref + "/document.json", "locators_ref": output_ref + "/locators.json",
                "files": files, "images": images, "gaps": gaps, "page_preview": preview,
                "statistics": {"conversion_seconds": converted - conversion_started, "wall_seconds": time.perf_counter() - started,
                               "input_bytes": len(data), "output_bytes": output_bytes, "page_count": len(pages), "image_count": len(images)}}
    _write_json(output / "manifest.json", manifest)
    descriptor = {key: manifest[key] for key in ("source_id", "source_sha256", "profile_sha256", "extractor", "parse_status", "text_ref", "markdown_ref", "document_ref", "locators_ref", "images", "gaps", "statistics")}
    return {**descriptor, "manifest_ref": output_ref + "/manifest.json", "manifest_sha256": sha256_bytes((output / "manifest.json").read_bytes())}


def load(root, descriptor, *, expected_source_id, expected_sha256):
    """Verify a fixed bundle without converting or downloading anything."""
    root = Path(root).absolute()
    _workspace_no_links(root)
    root = root.resolve(strict=True)
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get("manifest_ref"), str):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "A fixed parser descriptor is required")
    manifest_ref = descriptor["manifest_ref"]
    output_ref = str(PurePosixPath(manifest_ref).parent)
    output = _output(root, output_ref)
    if PurePosixPath(manifest_ref).name != "manifest.json":
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Expected manifest.json")
    path = safe_path(root, manifest_ref, [output_ref])
    if sha256_bytes(path.read_bytes()) != descriptor.get("manifest_sha256"):
        raise ContractError("PARSE_MATERIAL_CHANGED", "Parser manifest differs from the reviewed descriptor", manifest_ref)
    manifest = read_json(path)
    if (manifest.get("schema_version") != "1.0" or manifest.get("output_ref") != output_ref
            or manifest.get("source_id") != expected_source_id or manifest.get("source_sha256") != expected_sha256
            or not _HASH.fullmatch(str(expected_sha256))
            or sha256_bytes(canonical_bytes(manifest.get("profile"))) != manifest.get("profile_sha256")):
        raise ContractError("PARSE_SOURCE_MISMATCH", "Parser bundle identity does not match this source")
    for key in ("source_id", "source_sha256", "profile_sha256", "extractor", "parse_status", "text_ref", "markdown_ref", "document_ref", "locators_ref", "images", "gaps", "statistics"):
        if descriptor.get(key) != manifest.get(key):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Descriptor differs from fixed manifest: " + key)
    files = manifest.get("files")
    if not isinstance(files, list) or not 4 <= len(files) <= 100000:
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Expected bounded parser output list")
    registered = set()
    for row in files:
        ref = row.get("ref")
        if ref in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Duplicate parser output")
        registered.add(ref)
        asset = safe_path(root, ref, [output_ref])
        raw = asset.read_bytes()
        if len(raw) != row.get("bytes") or sha256_bytes(raw) != row.get("sha256"):
            raise ContractError("PARSE_MATERIAL_CHANGED", "Parser output bytes differ", ref)
    expected_files = {manifest_ref} | registered
    actual_files = {p.relative_to(root).as_posix() for p in output.rglob("*") if p.is_file()}
    if actual_files != expected_files:
        raise ContractError("PARSE_MATERIAL_CHANGED", "Parser output file set differs")
    for field in ("text_ref", "markdown_ref", "document_ref", "locators_ref"):
        if manifest[field] not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Missing registered parser output: " + field)
    for image in manifest.get("images", []):
        if image.get("ref") is not None and image["ref"] not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Image is not a registered parser asset")
    document = read_json(safe_path(root, manifest["document_ref"], [output_ref]))
    for image in document.get("pictures", []):
        uri = (image.get("image") or {}).get("uri")
        if uri is not None:
            image_path = safe_path(output, uri, ["images"])
            if image_path.relative_to(root).as_posix() not in registered:
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Document image is not a registered local asset")
    markdown = safe_path(root, manifest["markdown_ref"]).read_text(encoding="utf-8")
    for uri in _markdown_image_uris(markdown):
        image_path = safe_path(output, unquote(uri), ["images"])
        if image_path.relative_to(root).as_posix() not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Markdown image is not a registered local asset")
    _validate_previews(root, output, manifest, document, registered)
    locators = read_json(safe_path(root, manifest["locators_ref"], [output_ref]))
    if locators.get("source_sha256") != expected_sha256 or locators.get("profile_sha256") != manifest["profile_sha256"]:
        raise ContractError("PARSE_SOURCE_MISMATCH", "Locator identity differs")
    return {"manifest": manifest, "text": safe_path(root, manifest["text_ref"]).read_text(encoding="utf-8"),
            "markdown": markdown, "document": document,
            "locators": locators, "root": root, "output_ref": output_ref}


def select(loaded, locator):
    """Select native locations or identity-bound Docling elements from a verified bundle."""
    if not isinstance(locator, dict):
        raise ContractError("INVALID_SOURCE_LOCATOR", "A source locator object is required")
    segments = loaded["locators"]["segments"]
    kind = locator.get("kind")
    if not isinstance(kind, str):
        raise ContractError("INVALID_SOURCE_LOCATOR", "Source locator kind must be a string")
    matches = []
    if kind == "element":
        manifest = loaded["manifest"]
        if locator.get("source_sha256") != manifest["source_sha256"] or locator.get("profile_sha256") != manifest["profile_sha256"]:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Element must bind the original and parser profile")
        if _options(loaded["root"], locator.get("parser")) != manifest["profile"]["options"]:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Element parser recipe does not reproduce this profile")
        core = {key: locator.get(key) for key in ("kind", "ref", "source_sha256", "profile_sha256")}
        matches = [row for row in segments if row["locator"] == core]
    elif kind in {"page", "pages", "slide"}:
        field = "slide" if kind == "slide" else "page"
        first = locator.get(field, locator.get("start", locator.get("number")))
        last = locator.get("end", first)
        if type(first) is not int or type(last) is not int or not 1 <= first <= last:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Expected positive native page/slide bounds")
        matches = [row for row in segments if row["locator"].get("kind") == field and first <= row["locator"].get(field, 0) <= last]
        if len(matches) != last - first + 1:
            matches = []
    elif kind == "cell_range":
        box = _range_box(locator.get("range"))
        if not isinstance(locator.get("sheet"), str) or not locator["sheet"]:
            raise ContractError("INVALID_SOURCE_LOCATOR", "Expected the actual sheet name")
        for row in segments:
            native = row["locator"]
            if native.get("kind") == kind and native.get("sheet") == locator["sheet"]:
                cell = _range_box(native["range"])
                if max(box[0], cell[0]) < min(box[2], cell[2]) and max(box[1], cell[1]) < min(box[3], cell[3]):
                    matches.append(row)
    elif kind == "lines":
        first, last = locator.get("start"), locator.get("end", locator.get("start"))
        if type(first) is int and type(last) is int and 1 <= first <= last:
            matches = [row for row in segments if row["locator"].get("kind") == "lines" and first <= row["locator"]["start"] <= last]
            if len(matches) != last - first + 1:
                matches = []
    if not matches:
        raise ContractError("INVALID_SOURCE_LOCATOR", "The requested original location is absent from this parse")
    return matches
