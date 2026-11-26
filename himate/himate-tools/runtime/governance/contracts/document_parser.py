"""Fixed document materials and disposable PDF parse caches.

This module never starts installation, downloads models, or interprets knowledge.
Descriptors bind fixed inputs and files; cached materials never own review progress.
"""
from __future__ import annotations

from base64 import b64decode
from bisect import bisect_right
from collections import Counter, defaultdict
from importlib import metadata
from io import BytesIO
import hashlib
import math
from pathlib import Path, PurePosixPath
import re
import secrets
import sys
import time
from urllib.parse import unquote

from .runtime import native_path
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
_PREVIEW_LIMITS = {"max_pixels": 16_000_000, "max_png_bytes": 16 * 1024 * 1024, "scale": 1.5}
_PATTERN_PREVIEW_PAGES = 32
_MAX_PARSE_FILES = 100_000
_PDF_CONVERSION_PAGES = 200
_DESCRIPTOR_FIELDS = ("source_id", "source_sha256", "profile_sha256", "extractor", "parse_status",
                      "text_ref", "markdown_ref", "document_ref", "locators_ref", "statistics")
OCR_MODEL_FILES = (
    "docling-project--docling-layout-heron/config.json",
    "docling-project--docling-layout-heron/preprocessor_config.json",
    "docling-project--docling-layout-heron/model.safetensors",
    "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
    "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
    "RapidOcr/PP-OCRv6_det_small.onnx",
    "RapidOcr/PP-OCRv6_rec_small.onnx",
    "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
)


def safe_path(root, reference, allowed_prefixes=None, *, directory_entries=None):
    path = _relative_path(Path(native_path(root)), reference, allowed_prefixes, _directory_entries=directory_entries)
    _workspace_no_links(path)
    # Native Windows paths are for IO. Manifest and locator paths stay portable.
    text = str(path)
    if text.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + text[8:])
    if text.startswith("\\\\?\\"):
        return Path(text[4:])
    return path


def _material_files(output):
    """Pair portable bundle names with the native paths used for filesystem I/O."""
    directory = Path(native_path(output))
    for path in directory.rglob("*"):
        if path.is_file():
            yield path.relative_to(directory), path


def _output(root, reference):
    path = safe_path(root, reference)
    parts = PurePosixPath(reference).parts
    if (parts == (".build", "materials", "parsed")
            or (len(parts) == 4 and parts[:3] == (".build", "materials", "references"))):
        return path
    if (len(parts) == 4 and parts[:2] == ("artifacts", "source-read")
            and parts[3] == "parsed" and re.fullmatch(r"[0-9a-f]{32}", parts[2])):
        return path
    if (len(parts) == 4 and parts[:3] == ("artifacts", "ingest", "parsed")
            and re.fullmatch(r"[0-9a-f]{64}-[0-9a-f]{32}", parts[3])):
        return path
    raise ContractError("PARSE_OUTPUT_UNSAFE", "Use fixed materials, a PDF cache bundle or a source-read directory", reference)


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
        maximum = {"threads": 32, "max_input_bytes": 256 * 1024 * 1024}.get(field)
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
    packages += {".pdf": ["docling-parse", "pypdfium2"], ".docx": ["python-docx"], ".xlsx": ["openpyxl"], ".pptx": ["python-pptx"]}.get(suffix, [])
    if suffix == ".pdf" and options["pipeline"] == "native":
        packages += ["pypdf", "Pillow"]
    if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS):
        packages += ["rapidocr", "onnxruntime", "torch", "transformers", "docling-ibm-models"]
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    models = []
    if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS):
        directory = _model_directory(root, options)
        for path in sorted(directory.rglob("*")):
            if path.is_file() and ".cache" not in path.relative_to(directory).parts and path.suffix in {".json", ".safetensors", ".onnx", ".bin", ".pth", ".txt", ".yaml"}:
                safe_path(directory, path.relative_to(directory).as_posix())
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                models.append({"ref": path.relative_to(directory).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    profile = {"adapter": "himate-document:1", "format": suffix, "versions": versions, "model_files": models,
            "options": options, "remote_services": False, "external_plugins": False,
            "remote_resource_fetch": False, "local_resource_fetch": False,
            "picture_description": "host_agent", "generate_page_images": False,
            "generate_picture_images": True}
    if suffix == ".pdf":
        profile["picture_export"] = "pdfium-rgba-dedup:1"
        profile["text_export"] = "margin-line-numbers:1"
        if options["pipeline"] == "native":
            profile["conversion"] = "bounded-native-pages:1"
            profile["pattern_preview"] = "fill-mask:1"
    return profile


def _operation_profile(root, suffix, data, requested):
    options = _options(root, requested)
    if not isinstance(data, bytes) or not data:
        raise ContractError("UNREADABLE_DOCUMENT", "Expected nonempty original bytes")
    if len(data) > options["max_input_bytes"]:
        raise ContractError("PARSE_INPUT_LIMIT", "Original exceeds max_input_bytes")
    profile = _profile(options, suffix, root)
    if suffix == ".pdf" and "max_pages" not in (requested or {}):
        try:
            total = pdf_page_count(data)
        except ContractError:
            # Conversion records the diagnostic in the material bundle.
            return options, profile
        if total > options["max_pages"]:
            # Preserve the recipe hash for previously supported PDFs and keep
            # the automatically expanded operation distinct from an explicit cap.
            profile["effective_max_pages"] = total
            options = {**options, "max_pages": total}
    return options, profile


def _gap(code, message, *, locator=None, severity="warning"):
    value = {"code": code, "message": str(message), "severity": severity}
    if locator is not None:
        value["locator"] = locator
    return value


def summarize_gaps(gaps, details_ref):
    """Bound handoff diagnostics while retaining counts and the fixed evidence."""
    groups = {}
    overflow, overflow_review = 0, False
    for gap in gaps:
        key = (str(gap.get("code", ""))[:80], str(gap.get("severity", "warning"))[:32],
               str(gap.get("message", ""))[:240])
        if key not in groups:
            if len(groups) >= 64:
                overflow += 1
                overflow_review = overflow_review or key[1] == "review"
                continue
            groups[key] = {"code": key[0], "severity": key[1], "message": key[2],
                           "count": 0, "example_locators": [], "details_ref": details_ref}
        row = groups[key]
        row["count"] += 1
        locator = gap.get("locator")
        if (locator is not None and len(row["example_locators"]) < 3
                and len(canonical_bytes(locator)) <= 1024 and locator not in row["example_locators"]):
            row["example_locators"].append(locator)
    result = list(groups.values())
    if overflow:
        result.append({"code": "OTHER_PARSE_GAPS", "severity": "review" if overflow_review else "warning",
                       "message": "Additional diagnostic groups are retained in the fixed manifest",
                       "count": overflow, "example_locators": [], "details_ref": details_ref})
    return result


def _cache_descriptor(descriptor, manifest):
    return {"descriptor_kind": "manifest-reference", **{key: manifest[key] for key in _DESCRIPTOR_FIELDS},
            "manifest_ref": descriptor["manifest_ref"], "manifest_sha256": descriptor["manifest_sha256"],
            "gaps": summarize_gaps(manifest["gaps"], descriptor["manifest_ref"])}


def _write_json(path, value):
    Path(native_path(path)).write_bytes(canonical_bytes(value))


def pdf_page_count(data):
    """Read the original PDF's physical extent independently of conversion."""
    if not isinstance(data, bytes) or not data:
        raise ContractError("PDF_PAGE_COUNT_UNAVAILABLE", "Expected nonempty original PDF bytes")
    document = None
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        count = len(document)
        if count < 1:
            raise ValueError("The original PDF has no physical pages")
        return count
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        raise ContractError("PDF_PAGE_COUNT_UNAVAILABLE", "Cannot read the original PDF page count: " + str(error)) from error
    finally:
        if document is not None:
            document.close()


def prepare_pdf(root, source, data, options=None):
    """Reuse historical PDF materials for read/compatibility callers."""
    if (not isinstance(source, dict) or not isinstance(source.get("path"), str)
            or PurePosixPath(source["path"]).suffix.lower() != ".pdf"):
        raise ContractError("PARSE_SOURCE_INVALID", "PDF cache preparation requires a PDF source")
    return _prepare_cached(root, source, data, options, complete=False)[0]


def prepare_document(root, source, data, options=None):
    """Prepare a complete P1 reading bundle, publishing only verified cache entries."""
    return _prepare_cached(root, source, data, options, complete=True)


def _prepare_cached(root, source, data, options, *, complete):
    root = Path(root).absolute()
    _workspace_no_links(root)
    root = root.resolve(strict=True)
    suffix = PurePosixPath(source["path"]).suffix.lower()
    source_id = validate_id(source.get("id") or source.get("source_id"))
    effective, profile = _operation_profile(root, suffix, data, options)
    source_hash = sha256_bytes(data)
    profile_hash = sha256_bytes(canonical_bytes(profile))
    identity = {"source_id": source_id, "source_sha256": source_hash, "profile_sha256": profile_hash}
    if complete:
        identity["material_version"] = 1
        if suffix == ".docx":
            identity["docx_picture_policy"] = 1
        models = _model_directory(root, effective)
        identity["image_ocr_files"] = [
            sha256_bytes(path.read_bytes()) if path.is_file() else None
            for path in (safe_path(models, reference) for reference in OCR_MODEL_FILES if reference.startswith("RapidOcr/"))
        ] if models.is_dir() else []
        identity["max_output_bytes"] = (options or {}).get("max_output_bytes", 1024 ** 3)
    key = sha256_bytes(canonical_bytes(identity))
    cache_ref = "artifacts/ingest/parsed/"
    index_ref = cache_ref + key + ".json"
    index = Path(native_path(safe_path(root, index_ref)))
    if index.is_file():
        try:
            descriptor = read_json(index)
            loaded = load(root, descriptor, expected_source_id=source_id, expected_sha256=source_hash)
            if (descriptor["profile_sha256"] == profile_hash
                    and (not complete or descriptor["parse_status"] == "parsed")
                    and re.fullmatch(key + r"-[0-9a-f]{32}", PurePosixPath(loaded["output_ref"]).name)
                    and loaded["manifest"].get("page_range") is None):
                compact = _cache_descriptor(descriptor, loaded["manifest"])
                if compact != descriptor:
                    _write_json(index, compact)
                return compact, loaded
        except (ContractError, OSError, ValueError):
            # Damaged disposable material is rebuilt without changing any
            # previously handed-off bundle or formal source progress.
            pass
    index.parent.mkdir(parents=True, exist_ok=True)
    _workspace_no_links(index.parent)
    output_ref = cache_ref + key + "-" + secrets.token_hex(16)
    descriptor = parse(root, source, data, output_ref, options=options, complete=complete)
    loaded = load(root, descriptor, expected_source_id=source_id, expected_sha256=source_hash)
    if descriptor["profile_sha256"] != profile_hash:
        raise ContractError("PARSE_PROFILE_CHANGED", "Parser profile changed while preparing PDF materials")
    compact = _cache_descriptor(descriptor, loaded["manifest"])
    if not complete or descriptor["parse_status"] == "parsed":
        _write_json(safe_path(root, index_ref), compact)
    return compact, loaded


def _external_images(data, suffix):
    text = data.decode("utf-8-sig", errors="replace") if suffix in {".html", ".htm"} else ""
    matches = re.findall(r"<img\b[^>]*\bsrc\s*=\s*(?:['\"]([^'\"]+)['\"]|([^\s>]+))", text, re.IGNORECASE)
    refs = [quoted or bare for quoted, bare in matches]
    return [ref for ref in refs if not ref.lower().startswith("data:")]


def _sanitize_markdown_images(text):
    """Native Markdown cannot authorize image fetches through its rendered view."""
    from .markdown_images import mask_markdown_literals

    found = []
    patterns = [r"<img\b[^>]*>", r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)",
                r"!\[[^\]]*\]\s*\[[^\]]*\]", r"!\[[^\]]*\]"]
    masked = mask_markdown_literals(text)
    chunks, cursor = [], 0
    for match in re.finditer("|".join(patterns), masked, flags=re.IGNORECASE):
        original = text[match.start():match.end()]
        found.append(original)
        chunks.extend((text[cursor:match.start()], "[Image not read; inspect the original source]",
                       "\n" * original.count("\n")))
        cursor = match.end()
    return "".join((*chunks, text[cursor:])), found


def _markdown_image_uris(text):
    from .markdown_images import markdown_image_tokens, mask_markdown_literals

    masked = mask_markdown_literals(text)
    values = []
    for match in re.finditer(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))", masked):
        values.append(match[1] or match[2])
    if re.search(r"<img\b|!\[[^\]]*\]\s*\[", masked, re.IGNORECASE):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Unsupported raw/reference image syntax in material Markdown")
    values.extend(uri for _start, _end, uri in markdown_image_tokens(text, masked=masked) if uri)
    return values


def _markdown_material(root, output, text, assets, max_bytes):
    from .markdown_images import markdown_image_tokens
    from .raw_materials import _open_stage

    try:
        from PIL import Image
    except ImportError:
        Image = None
    image_errors = (OSError, ValueError, SyntaxError) + ((Image.DecompressionBombError,) if Image else ())

    replacements, images, refs, unresolved = {}, [], {}, []
    chunks = []
    used_bytes = used_files = 0
    cursor = 0
    newlines = [match.start() for match in re.finditer("\n", text)]
    marker = secrets.token_hex(16)
    for start, end, uri in markdown_image_tokens(text):
        original = text[start:end]
        if uri in refs:
            local = refs[uri]
        else:
            local = None
            try:
                if Image is None:
                    data = b""
                elif uri in assets:
                    asset, expected_sha256 = assets[uri]
                    with _open_stage(str(asset)) as stream:
                        data = stream.read(max_bytes - used_bytes + 1)
                    if len(data) > max_bytes - used_bytes or sha256_bytes(data) != expected_sha256:
                        data = b""
                elif uri and re.match(r"data:image/(?:png|jpe?g|gif|webp|bmp|tiff?);base64,", uri, re.IGNORECASE):
                    encoded = uri.partition(",")[2]
                    data = b64decode(encoded, validate=True) if len(encoded) <= (max_bytes - used_bytes) * 4 // 3 + 4 else b""
                else:
                    data = b""
                if data and len(data) <= max_bytes - used_bytes:
                    with Image.open(BytesIO(data)) as picture:
                        suffix = {"PNG": "png", "JPEG": "jpg", "GIF": "gif", "WEBP": "webp",
                                  "BMP": "bmp", "TIFF": "tiff"}.get(picture.format)
                        if picture.width * picture.height > _PREVIEW_LIMITS["max_pixels"]:
                            suffix = None
                        picture.verify()
                    if suffix:
                        local = "images/" + sha256_bytes(data) + "." + suffix
                        destination = output / local
                        if not destination.exists():
                            if used_files >= _MAX_PARSE_FILES - 4:
                                local = None
                            else:
                                destination.parent.mkdir(exist_ok=True)
                                destination.write_bytes(data)
                                used_bytes += len(data)
                                used_files += 1
            except image_errors:
                local = None
            refs[uri] = local
        placeholder = f"{marker}:{len(replacements)}:{marker}"
        if local:
            line = bisect_right(newlines, start) + 1
            image_ref = (output / local).relative_to(root).as_posix()
            images.append({"ref": image_ref, "locator": {"kind": "lines", "start": line, "end": line},
                           "role": "document_picture", "provenance": [], "ocr_status": "not_requested",
                           "description_status": "agent_required"})
            match = re.match(r"!\[([^\]\n]*)\]", original)
            alt = match[1] if match else "Image"
            replacements[placeholder] = f"![{alt}]({local})"
        else:
            unresolved.append(original)
            replacements[placeholder] = "[Image not read; inspect the original source]"
        chunks.extend((text[cursor:start], placeholder, "\n" * original.count("\n")))
        cursor = end
    chunks.append(text[cursor:])
    markdown, remaining = _sanitize_markdown_images("".join(chunks))
    if replacements:
        markdown = re.sub(f"{marker}:[0-9]+:{marker}", lambda match: replacements[match[0]], markdown)
    return markdown, unresolved + remaining, images


def _native_text(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractError("UNREADABLE_DOCUMENT", "Text documents require UTF-8") from exc
    if not text.strip() or "\x00" in text:
        raise ContractError("UNREADABLE_DOCUMENT", "Text must be nonempty without NUL")
    return text


def _model_directory(root, options):
    if options["models_path"] is not None:
        return safe_path(root, options["models_path"], ["artifacts/models"])
    directory = Path.home() / ".himate/knowledge/tools/deploy/models/docling-cpu"
    _workspace_no_links(directory)
    return directory


def _models(root, options):
    directory = _model_directory(root, options)
    if not directory.is_dir():
        raise ContractError("PARSER_MODELS_REQUIRED", "OCR models are unavailable. Install @himate/knowledge-models with npm.")
    for reference in OCR_MODEL_FILES:
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
    if suffix == ".docx":
        from .docx_pictures import DocxPictureBackend

        formats[InputFormat.DOCX].backend = DocxPictureBackend
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


def _pdf_page_previews(root, data, output, options, page_range, pages, source_hash, *, pattern_pages=()):
    """Render requested pages or a bounded set of pages containing pattern masks."""
    automatic = page_range is None
    limits = _PREVIEW_LIMITS
    max_pages = _PATTERN_PREVIEW_PAGES if automatic else page_range[1] - page_range[0] + 1
    request = {"requested_pages": list(pattern_pages)} if automatic else {"requested_range": list(page_range)}
    metadata_record = {**limits, **request, "max_pages": max_pages, "rendered_pages": [],
                       "pixels": 0, "png_bytes": 0, "assets": [], "source_sha256": source_hash}
    images, gaps = [], []
    started = time.perf_counter()
    if automatic:
        selected = pattern_pages[:max_pages]
    else:
        first, last = page_range
        selected = range(first, last + 1)
    if (not automatic and max_pages > len(pages)) or not set(selected).issubset(pages):
        return [], [_gap("PAGE_PREVIEW_RANGE_UNAVAILABLE", "Not all requested physical pages were extracted", severity="review")], metadata_record
    pdf = None
    try:
        import pypdfium2 as pdfium
        metadata_record["renderer"] = "pypdfium2:" + metadata.version("pypdfium2")
        pdf = pdfium.PdfDocument(data)
        if selected[-1] > len(pdf):
            raise ValueError("Preview page range is outside the original PDF")
        existing = sum(path.stat().st_size for _, path in _material_files(output))
        byte_budget = min(limits["max_png_bytes"], max(0, options["max_output_bytes"] - existing))
        for number in selected:
            pending = {"kind": "pages", "start": number, "end": selected[-1]} if not automatic else {"kind": "page", "page": number}
            page, bitmap = pdf[number - 1], None
            try:
                width, height = page.get_size()
                if not (math.isfinite(width) and math.isfinite(height) and min(width, height) > 0):
                    raise ValueError("PDF page geometry is invalid")
                width, height = math.ceil(width * limits["scale"]), math.ceil(height * limits["scale"])
                if metadata_record["pixels"] + width * height > limits["max_pixels"]:
                    gaps.append(_gap("PAGE_PREVIEW_PIXEL_LIMIT", f"Preview pixel budget reached at physical page {number}; open the original or request a narrower range",
                                     locator=pending, severity="review"))
                    break
                bitmap = page.render(scale=limits["scale"])
                with bitmap.to_pil() as image:
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    raw = buffer.getvalue()
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
            if metadata_record["png_bytes"] + len(raw) > byte_budget:
                gaps.append(_gap("PAGE_PREVIEW_BYTE_LIMIT", f"Preview byte budget reached at physical page {number}; open the original or request a narrower range",
                                 locator=pending, severity="review"))
                break
            local_ref = f"images/page_preview_{number:06}.png"
            target = safe_path(output, local_ref, ["images"])
            target.parent.mkdir(exist_ok=True)
            _workspace_no_links(target.parent)
            Path(native_path(target)).write_bytes(raw)
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


def _attach_previews(output, preview, max_output_bytes):
    document_path = output / "document.json"
    document = read_json(document_path)
    body = document.setdefault("body", {})
    body["meta"] = body.get("meta") or {}
    body["meta"]["himate__page_previews"] = preview
    encoded = canonical_bytes(document)
    additions = "".join(f"\n\nPhysical page {asset['page']} preview (rendered, not an extracted source bitmap):\n\n![Page {asset['page']}]({asset['local_ref']})" for asset in preview["assets"]).encode("utf-8")
    sizes = [path.stat().st_size for _, path in _material_files(output)]
    output_bytes = sum(sizes) - document_path.stat().st_size + len(encoded) + len(additions)
    if len(sizes) > _MAX_PARSE_FILES:
        return _gap("PAGE_PREVIEW_FILE_LIMIT", "Page previews exceed the remaining output file budget", severity="review")
    if output_bytes > max_output_bytes:
        return _gap("PAGE_PREVIEW_BYTE_LIMIT", "Page previews and their metadata exceed the remaining output byte budget", severity="review")
    document_path.write_bytes(encoded)
    if additions:
        with (output / "document.md").open("ab") as stream:
            stream.write(additions)
    return None


def _pattern_tiles_by_page(images):
    counts = Counter()
    for image in images:
        if image.get("role") == "pattern_texture":
            provenance = image.get("provenance", [])
            if len(provenance) != 1 or type(provenance[0].get("page_no")) is not int:
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Pattern texture requires one physical page")
            counts[provenance[0]["page_no"]] += 1
    return counts


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
    pages = set(manifest.get("pages", []))
    if bounds is None:
        selected = sorted(_pattern_tiles_by_page(manifest["images"]))
        if not selected or preview.get("requested_pages") != selected or not set(selected).issubset(pages):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Pattern preview page scope differs")
        allowed = set(selected[:_PATTERN_PREVIEW_PAGES])
        limits = {**_PREVIEW_LIMITS, "max_pages": _PATTERN_PREVIEW_PAGES}
    else:
        if preview.get("requested_range") != bounds:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview page range differs")
        allowed = {number for number in pages if bounds[0] <= number <= bounds[1]}
        # Older bundles recorded the fixed limit of eight, even for a single page.
        limits = {**_PREVIEW_LIMITS, "max_pages": max(8, bounds[1] - bounds[0] + 1)}
    if preview.get("source_sha256") != manifest["source_sha256"]:
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview source/page scope differs")
    for field, maximum in limits.items():
        value = preview.get(field)
        if type(value) not in (int, float) or not 0 < value <= maximum:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Invalid preview resource budget")
    assets = preview.get("assets")
    if not isinstance(assets, list) or len(assets) > preview["max_pages"] or len(image_rows) != len(assets):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Invalid page-preview asset set")
    rendered, pixels, byte_count, refs = [], 0, 0, set()
    for asset in assets:
        page = asset.get("page")
        if type(page) is not int or page not in allowed or page in rendered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview is not an extracted physical page")
        ref, local_ref = asset.get("ref"), asset.get("local_ref")
        path = safe_path(output, local_ref, ["images"])
        if path.relative_to(root).as_posix() != ref or ref not in registered or ref in refs:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview asset is not registered inside images")
        matches = [row for row in image_rows if row.get("ref") == ref]
        if (len(matches) != 1 or matches[0].get("locator") != {"kind": "page", "page": page}
                or matches[0].get("provenance") != [{"page_no": page}]
                or matches[0].get("element_ref") is not None
                or matches[0].get("source_sha256") != manifest["source_sha256"]):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview image identity differs")
        from PIL import Image
        disk = Path(native_path(path))
        with Image.open(disk) as image:
            if image.format != "PNG" or image.size != (asset.get("width"), asset.get("height")):
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Preview PNG geometry differs")
            image.verify()
        if disk.stat().st_size != asset.get("bytes"):
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


def _document_segments(document, suffix, source_hash, profile_hash, *, hidden_text_refs=None, layers=None):
    segments, pages = [], defaultdict(list)
    groups = {group.self_ref: group for group in document.groups}
    for item, _ in document.iterate_items(traverse_pictures=True, included_content_layers=layers):
        reference = getattr(item, "self_ref", None)
        if not reference:
            continue
        text = _item_text(item)
        locator = {"kind": "element", "ref": reference, "source_sha256": source_hash, "profile_sha256": profile_hash}
        segments.append({"locator": locator, "text": text})
        for page in sorted({p.page_no for p in getattr(item, "prov", [])}):
            if text:
                pages[page].append(text)
        if suffix == ".xlsx" and (text or hasattr(item, "data")) and getattr(item, "prov", []):
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
                if not hasattr(item, "data"):
                    cell_range = f"{_column(left + 1)}{top + 1}:{_column(int(box.r))}{int(box.b)}"
                    segments.append({"locator": {"kind": "cell_range", "sheet": sheet, "range": cell_range}, "text": text})
                    continue
                for cell in item.data.table_cells:
                    start_col = left + cell.start_col_offset_idx
                    start_row = top + cell.start_row_offset_idx
                    end_col = start_col + cell.col_span
                    end_row = start_row + cell.row_span
                    cell_range = f"{_column(start_col + 1)}{start_row + 1}:{_column(end_col)}{end_row}"
                    segments.append({"locator": {"kind": "cell_range", "sheet": sheet, "range": cell_range}, "text": cell.text})
    # Reading decoration remains addressable as an original, identity-bound
    # element, while the page aggregates continue to contain body text only.
    for item in document.texts if hidden_text_refs else ():
        if item.self_ref in hidden_text_refs:
            locator = {"kind": "element", "ref": item.self_ref,
                       "source_sha256": source_hash, "profile_sha256": profile_hash}
            segments.append({"locator": locator, "text": _item_text(item)})
    for page in sorted(document.pages):
        kind = "slide" if suffix == ".pptx" else "page"
        if suffix in {".pdf", ".pptx"} | IMAGE_FORMATS:
            segments.append({"locator": {"kind": kind, kind: page}, "text": "\n\n".join(pages[page])})
    return segments


def _pdf_picture_recovery(document, data, output, options):
    from .pdf_pictures import recover_and_export

    return recover_and_export(document, data, output, options)


def _native_pdf_document(root, source, data, options, page_range):
    """Release native page cells between conversions, preserving physical pages."""
    from docling_core.types.doc import ContentLayer, DoclingDocument
    from docling.datamodel.base_models import DocumentStream

    deadline = time.monotonic() + options["timeout_seconds"]
    total = pdf_page_count(data)
    if total > options["max_pages"]:
        raise ContractError("PARSE_PAGE_LIMIT", f"Original has {total} pages, exceeding max_pages={options['max_pages']}")
    first, last = page_range if page_range is not None else (1, total)
    if first > total:
        raise ContractError("PARSE_RANGE_INVALID", "Requested range starts beyond the original PDF")
    last = min(last, total)
    documents, gaps, page_map = [], [], {}
    combined_last = 0
    for start in range(first, last + 1, _PDF_CONVERSION_PAGES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            gaps.append(_gap("DOCUMENT_CONVERSION_ERROR", "PDF conversion exceeded timeout_seconds", severity="review"))
            break
        converter = _converter(root, ".pdf", {**options, "timeout_seconds": remaining})
        end = min(start + _PDF_CONVERSION_PAGES - 1, last)
        arguments = {"max_file_size": options["max_input_bytes"],
                     "max_num_pages": options["max_pages"],
                     "page_range": (start, end),
                     "raises_on_error": False}
        result = converter.convert(DocumentStream(name=PurePosixPath(source["path"]).name,
                                                   stream=BytesIO(data)), **arguments)
        document = result.document
        if getattr(result.status, "value", str(result.status)) != "success":
            gaps.append(_gap("DOCUMENT_PARTIAL", "Docling did not report a clean conversion", severity="review"))
        if set(document.pages) != set(range(start, end + 1)):
            gaps.append(_gap("DOCUMENT_PARTIAL", "PDF conversion did not return all requested physical pages",
                             locator={"kind": "pages", "start": start, "end": end}, severity="review"))
        gaps.extend(_gap("DOCUMENT_CONVERSION_ERROR", getattr(error, "error_message", str(error)), severity="review")
                    for error in result.errors)
        # The result retains all parsed native page cells alongside its document.
        # Keep only the document before starting another bounded conversion.
        del result, converter
        if document.pages:
            offset = combined_last - min(document.pages) + 1
            page_map.update({number + offset: number for number in document.pages})
            combined_last = max(document.pages) + offset
            documents.append(document)
        del document
    if not documents:
        return DoclingDocument(name=PurePosixPath(source["path"]).stem), gaps
    if len(documents) == 1:
        return documents[0], gaps
    origin = documents[0].origin
    document = DoclingDocument.concatenate(documents)
    documents.clear()
    document.origin = origin
    # concatenate normalizes each fragment to contiguous page numbers. Restore
    # original physical numbers, including missing pages and non-one starts.
    for item, _ in document.iterate_items(traverse_pictures=True,
                                          included_content_layers=set(ContentLayer)):
        for provenance in getattr(item, "prov", []):
            provenance.page_no = page_map[provenance.page_no]
    pages = {}
    for number, page in document.pages.items():
        page.page_no = page_map[number]
        pages[page.page_no] = page
    document.pages = pages
    return document, gaps


def _docling(root, source, data, output, options, page_range, source_hash, profile_hash):
    from docling_core.types.doc import ContentLayer, ImageRefMode
    from docling.datamodel.base_models import DocumentStream
    suffix = PurePosixPath(source["path"]).suffix.lower()
    gaps, original_images = [], set()
    if suffix in IMAGE_FORMATS and options["pipeline"] == "native":
        document = _raster_document(data, PurePosixPath(source["path"]).stem)
    elif suffix == ".pdf" and options["pipeline"] == "native":
        document, gaps = _native_pdf_document(root, source, data, options, page_range)
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
    office_layers = set(ContentLayer) if options.get("complete_material") and suffix in {".docx", ".xlsx"} else None
    if office_layers is not None and suffix == ".xlsx" and not gaps:
        from .document_material import retain_workbook_formulas

        retain_workbook_formulas(document, data)
    hidden_text_refs, pattern_textures, rendered, omitted = set(), set(), set(), set()
    missing_body_pictures = 0
    if suffix == ".docx":
        from .docx_pictures import export_docx

        markdown, exported, omitted, missing_body_pictures = export_docx(
            document, result.input._backend, output, office_layers,
            max_bytes=options["max_output_bytes"], max_images=_MAX_PARSE_FILES - 4,
        )
        Path(native_path(output / "document.md")).write_bytes(markdown.encode("utf-8"))
        _write_json(output / "document.json", exported)
    elif suffix == ".pdf":
        from .pdf_text import mark_margin_line_numbers

        hidden_text_refs = mark_margin_line_numbers(document)
        pattern_textures = _pdf_picture_recovery(document, data, output, options) or set()
        if options.get("complete_material"):
            from . import document_material

            rendered = document_material.retain_pdf_views(document, data, output, options["max_output_bytes"])
            pattern_textures.difference_update(rendered)
            markdown = document_material.pdf_markdown(document, rendered)
        else:
            markdown = document.export_to_markdown(image_mode=ImageRefMode.REFERENCED,
                                                  traverse_pictures=True, mark_meta=True)
        # Assets already have content-addressed local references. The save_as_*
        # helpers would write a new PNG for every repeated drawing occurrence.
        Path(native_path(output / "document.md")).write_bytes(markdown.encode("utf-8"))
        exported = document.export_to_dict()
        for picture in exported.get("pictures", []):
            image = picture.get("image")
            if image is not None and isinstance(image.get("uri"), str):
                image["uri"] = image["uri"].replace("\\", "/")
        _write_json(output / "document.json", exported)
    else:
        native_output = Path(native_path(output))
        document.save_as_markdown(native_output / "document.md", artifacts_dir=Path("images"),
                                  image_mode=ImageRefMode.REFERENCED, traverse_pictures=True, mark_meta=True,
                                  included_content_layers=office_layers)
        document_path = native_output / "document.json"
        document.save_as_json(document_path, artifacts_dir=Path("images"), image_mode=ImageRefMode.REFERENCED, ensure_ascii=False)
        exported = read_json(document_path)
        if sys.platform == "win32":
            changed = False
            for picture in exported.get("pictures", []):
                image = picture.get("image") or {}
                uri = image.get("uri")
                if isinstance(uri, str) and uri.startswith("images\\"):
                    image["uri"] = uri.replace("\\", "/")
                    changed = True
            if changed:
                _write_json(document_path, exported)
    segments = _document_segments(document, suffix, source_hash, profile_hash,
                                  hidden_text_refs=hidden_text_refs, layers=office_layers)
    text = "\n\n".join(segment["text"] for segment in segments
                       if segment["locator"]["kind"] == "element" and segment["text"]
                       and segment["locator"]["ref"] not in hidden_text_refs)
    images, image_refs, image_directories = [], {}, {}
    image_pages = set()
    for picture in exported.get("pictures", []):
        if picture["self_ref"] in omitted:
            continue
        provenance = picture.get("prov", [])
        locator = {"kind": "element", "ref": picture["self_ref"], "source_sha256": source_hash, "profile_sha256": profile_hash}
        uri = (picture.get("image") or {}).get("uri")
        image_ref = None
        if isinstance(uri, str) and uri.startswith("images/"):
            if uri not in image_refs:
                asset = safe_path(output, uri, ["images"], directory_entries=image_directories)
                image_refs[uri] = asset.relative_to(root).as_posix() if Path(native_path(asset)).is_file() else None
            image_ref = image_refs[uri]
        pattern_texture = picture["self_ref"] in pattern_textures
        if image_ref is None and not pattern_texture:
            gaps.append(_gap("IMAGE_UNAVAILABLE", "An extracted picture has no saved local image", locator=locator, severity="review"))
        role = "source_bitmap" if picture["self_ref"] in original_images else "document_picture"
        if picture["self_ref"] in rendered:
            role = "source_page_view"
        elif pattern_texture:
            role = "pattern_texture"
        images.append({"ref": image_ref, "element_ref": picture["self_ref"], "locator": locator,
                       "role": role,
                       "provenance": provenance, "ocr_status": "unverified" if options["pipeline"] == "standard" and suffix in ({".pdf"} | IMAGE_FORMATS) else "not_requested",
                       "description_status": "agent_required"})
        image_pages.update(p["page_no"] for p in provenance)
    if options.get("complete_material") and missing_body_pictures and not any(gap["code"] == "IMAGE_UNAVAILABLE" for gap in gaps):
        gaps.append(_gap("DOCUMENT_IMAGE_COVERAGE", "At least one original DOCX body image was not exported", severity="review"))
    if options["pipeline"] == "native" and suffix in ({".pdf"} | IMAGE_FORMATS):
        for segment in segments:
            locator = segment["locator"]
            if locator["kind"] == "page" and locator["page"] in image_pages and not segment["text"].strip():
                gaps.append(_gap("OCR_REQUIRED", "Image-only page retained; configure preinstalled standard OCR or read the image", locator=locator, severity="review"))
    return text, segments, images, gaps, sorted(document.pages)


def parse(root, source, data, output_ref, options=None, page_range=None, *, local_images=None, page_preview=True,
          complete=False):
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
    requested = options
    options, profile = _operation_profile(root, suffix, data, requested)
    if complete and "max_output_bytes" not in (requested or {}):
        options = {**options, "max_output_bytes": 1024 ** 3}
    page_range = _page_range(page_range)
    if page_range is not None and suffix not in ({".pdf", ".pptx", ".xlsx"} | IMAGE_FORMATS):
        raise ContractError("PARSE_RANGE_INVALID", "Page ranges apply to paginated formats")
    output = _output(root, output_ref)
    io_output = Path(native_path(output))
    if io_output.exists():
        raise ContractError("PARSE_OUTPUT_EXISTS", "Every parse requires a fresh operation directory", output_ref)
    if page_range is not None:
        profile["page_range"] = list(page_range)
    if suffix == ".md":
        profile["picture_export"] = "verified-markdown-bitmaps:1"
    source_hash, profile_hash = sha256_bytes(data), sha256_bytes(canonical_bytes(profile))
    io_output.mkdir(parents=True)
    _workspace_no_links(io_output)
    gaps, images, pages = [], [], []
    conversion_started = time.perf_counter()
    if suffix in {".md", ".txt"}:
        text = _native_text(data)
        if suffix == ".md":
            text, unresolved, images = _markdown_material(root, output, text, local_images or {}, options["max_output_bytes"])
            gaps.extend(_gap("EXTERNAL_IMAGE_NOT_READ", "Markdown image was not read: " + ref[:200],
                             severity="review") for ref in unresolved)
        segments = [{"locator": {"kind": "lines", "start": n, "end": n}, "text": line} for n, line in enumerate(text.splitlines(), 1)]
        (io_output / "document.md").write_bytes(text.encode("utf-8"))
        _write_json(output / "document.json", {"schema_name": "HiMateTextDocument", "text": text})
        extractor = "himate-native-text:1"
    else:
        extractor = "docling:" + profile["versions"].get("docling-slim", profile["versions"].get("docling", "unavailable"))
        try:
            conversion_options = {**options, "complete_material": True} if complete else options
            text, segments, images, gaps, pages = _docling(root, source, data, output, conversion_options, page_range, source_hash, profile_hash)
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            code = error.code if isinstance(error, ContractError) else "DOCUMENT_CONVERSION_UNAVAILABLE"
            gaps = [_gap(code, str(error), severity="review")]
            text, segments = "", []
            (io_output / "document.md").write_bytes(b"")
            _write_json(output / "document.json", {"schema_name": "HiMateUnavailableDocument"})
    for reference in (_external_images(data, suffix) if suffix != ".md" else []):
        gaps.append(_gap("EXTERNAL_IMAGE_NOT_READ", "Image reference was not fetched: " + reference, severity="review"))
    if complete:
        from . import document_material

        try:
            gaps = document_material.finish(root, output, suffix, data, images, gaps, pages, options)
        except (ContractError, ImportError, OSError, ValueError, RuntimeError) as error:
            gaps.append(_gap(getattr(error, "code", "DOCUMENT_IMAGE_PREPARATION_FAILED"), str(error), severity="review"))
    multiframe = _multiframe_gap(data, suffix, pages)
    if multiframe is not None:
        gaps.append(multiframe)
    (io_output / "text.txt").write_bytes(text.encode("utf-8"))
    _write_json(output / "locators.json", {"schema_version": "1.0", "source_sha256": source_hash, "profile_sha256": profile_hash, "segments": segments})
    preview = None
    pattern_counts = _pattern_tiles_by_page(images)
    if suffix == ".pdf" and page_preview and (page_range is not None or pattern_counts):
        preview_images, preview_gaps, preview = _pdf_page_previews(
            root, data, output, options, page_range, pages, source_hash, pattern_pages=sorted(pattern_counts))
        gaps.extend(preview_gaps)
        budget_gap = _attach_previews(output, preview, options["max_output_bytes"])
        if budget_gap is None:
            images.extend(preview_images)
        else:
            for asset in preview["assets"]:
                Path(native_path(safe_path(output, asset["local_ref"], ["images"]))).unlink()
            gaps.append(budget_gap)
            preview = None
    previews = {asset["page"]: asset["ref"] for asset in (preview or {}).get("assets", [])}
    for number, count in sorted(pattern_counts.items()):
        locator = {"kind": "page", "page": number}
        if number in previews:
            gap = _gap("PDF_PATTERN_PAGE_PREVIEW", "PDF fill masks are available in the rendered page preview", locator=locator)
            gap["preview_ref"] = previews[number]
        else:
            gap = _gap("PDF_PATTERN_PREVIEW_UNAVAILABLE", "Open the original page to review PDF fill masks", locator=locator, severity="review")
        gap["pattern_tiles"] = count
        gaps.append(gap)
    converted = time.perf_counter()
    files, directories = [], {}
    for local, path in sorted(_material_files(output)):
        relative = output_ref + "/" + local.as_posix()
        safe_path(root, relative, [output_ref], directory_entries=directories)
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
    if complete:
        manifest["material_version"] = 1
        manifest["material_output_limit"] = options["max_output_bytes"]
    _write_json(output / "manifest.json", manifest)
    descriptor = {key: manifest[key] for key in ("source_id", "source_sha256", "profile_sha256", "extractor", "parse_status", "text_ref", "markdown_ref", "document_ref", "locators_ref", "images", "gaps", "statistics")}
    return {**descriptor, "manifest_ref": output_ref + "/manifest.json", "manifest_sha256": sha256_bytes((io_output / "manifest.json").read_bytes())}


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
    path = Path(native_path(safe_path(root, manifest_ref, [output_ref])))
    if sha256_bytes(path.read_bytes()) != descriptor.get("manifest_sha256"):
        raise ContractError("PARSE_MATERIAL_CHANGED", "Parser manifest differs from the reviewed descriptor", manifest_ref)
    manifest = read_json(path)
    if (manifest.get("schema_version") != "1.0" or manifest.get("output_ref") != output_ref
            or manifest.get("source_id") != expected_source_id or manifest.get("source_sha256") != expected_sha256
            or not _HASH.fullmatch(str(expected_sha256))
            or sha256_bytes(canonical_bytes(manifest.get("profile"))) != manifest.get("profile_sha256")):
        raise ContractError("PARSE_SOURCE_MISMATCH", "Parser bundle identity does not match this source")
    compact = "descriptor_kind" in descriptor
    if compact and (descriptor["descriptor_kind"] != "manifest-reference"
                    or set(descriptor) != set(_DESCRIPTOR_FIELDS) | {"descriptor_kind", "manifest_ref", "manifest_sha256", "gaps"}):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Unknown manifest-reference descriptor fields or kind")
    for key in _DESCRIPTOR_FIELDS + (() if compact else ("images", "gaps")):
        if descriptor.get(key) != manifest.get(key):
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Descriptor differs from fixed manifest: " + key)
    if compact and descriptor["gaps"] != summarize_gaps(manifest.get("gaps", []), manifest_ref):
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Descriptor differs from fixed manifest: gaps")
    files = manifest.get("files")
    if not isinstance(files, list) or not 4 <= len(files) <= _MAX_PARSE_FILES:
        raise ContractError("PARSE_DESCRIPTOR_INVALID", "Expected bounded parser output list")
    registered, directories = set(), {}
    for row in files:
        ref = row.get("ref")
        if ref in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Duplicate parser output")
        registered.add(ref)
        asset = safe_path(root, ref, [output_ref], directory_entries=directories)
        raw = Path(native_path(asset)).read_bytes()
        if len(raw) != row.get("bytes") or sha256_bytes(raw) != row.get("sha256"):
            raise ContractError("PARSE_MATERIAL_CHANGED", "Parser output bytes differ", ref)
    expected_files = {manifest_ref} | registered
    actual_files = {output_ref + "/" + local.as_posix() for local, _ in _material_files(output)}
    if actual_files != expected_files:
        raise ContractError("PARSE_MATERIAL_CHANGED", "Parser output file set differs")
    for field in ("text_ref", "markdown_ref", "document_ref", "locators_ref"):
        if manifest[field] not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Missing registered parser output: " + field)
    for image in manifest.get("images", []):
        if image.get("ref") is not None and image["ref"] not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Image is not a registered parser asset")
    document = read_json(Path(native_path(safe_path(root, manifest["document_ref"], [output_ref]))))
    checked_image_uris = set()
    for image in document.get("pictures", []):
        uri = (image.get("image") or {}).get("uri")
        if uri is not None:
            if not isinstance(uri, str):
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Document image URI must be a local path")
            if uri in checked_image_uris:
                continue
            image_path = safe_path(output, uri, ["images"], directory_entries=directories)
            if image_path.relative_to(root).as_posix() not in registered:
                raise ContractError("PARSE_DESCRIPTOR_INVALID", "Document image is not a registered local asset")
            checked_image_uris.add(uri)
    markdown = Path(native_path(safe_path(root, manifest["markdown_ref"]))).read_text(encoding="utf-8")
    for uri in dict.fromkeys(_markdown_image_uris(markdown)):
        image_path = safe_path(output, unquote(uri), ["images"], directory_entries=directories)
        if image_path.relative_to(root).as_posix() not in registered:
            raise ContractError("PARSE_DESCRIPTOR_INVALID", "Markdown image is not a registered local asset")
    _validate_previews(root, output, manifest, document, registered)
    locators = read_json(Path(native_path(safe_path(root, manifest["locators_ref"], [output_ref]))))
    if locators.get("source_sha256") != expected_sha256 or locators.get("profile_sha256") != manifest["profile_sha256"]:
        raise ContractError("PARSE_SOURCE_MISMATCH", "Locator identity differs")
    return {"manifest": manifest, "text": Path(native_path(safe_path(root, manifest["text_ref"]))).read_text(encoding="utf-8"),
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
