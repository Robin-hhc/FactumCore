"""Inspect staged materials and publish a complete document with its attachments."""

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile

from . import raw_materials
from .document_parser import IMAGE_FORMATS, SUPPORTED_FORMATS
from .markdown_images import markdown_image_tokens
from .validation import ContractError


MARKER = raw_materials.PACKAGE_MARKER
TEMP_PREFIX = ".intake-"
ATTACHMENTS = IMAGE_FORMATS | {".gif"}
MAX_FILES = 100
MAX_BYTES = 128 * 1024 * 1024
MAX_EXCERPT = 1500


def _relative(value):
    if (not isinstance(value, str) or len(value) > 1024
            or not all(raw_materials._visible(part) and part not in {".", ".."} for part in value.split("/"))):
        raise ContractError("INTAKE_PATH_INVALID", "资料路径无效")
    return value


def _rows(request, *, save=False):
    items = request.get("files")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_FILES:
        raise ContractError("INTAKE_FILES_INVALID", "每批应有 1–100 个文件")
    result, names = {}, set()
    for row in items:
        if not isinstance(row, dict):
            raise ContractError("INTAKE_FILES_INVALID", "资料记录无效")
        name = _relative(row.get("path"))
        size = row.get("expected_size" if save else "size")
        digest = row.get("expected_sha256" if save else "sha256")
        if (name.casefold() in names or type(size) is not int or not 0 <= size <= MAX_BYTES
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ContractError("INTAKE_FILES_INVALID", "资料路径重复或文件大小、摘要无效", name)
        names.add(name.casefold())
        result[name] = {"path": name, "size": size, "sha256": digest, "staged_path": row.get("staged_path")}
    return result


def _file_digest(stream, output=None):
    digest = sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise ContractError("RAW_STAGE_MISMATCH", "资料超过大小限制")
        digest.update(chunk)
        if output is not None:
            output.write(chunk)
    return size, digest.hexdigest()


def _logical_attachment(document, uri):
    if not uri:
        return None
    try:
        link = urlsplit(uri)
        decoded = unquote(link.path)
        if link.scheme or link.netloc or not decoded or decoded.startswith("/"):
            return None
        logical = posixpath.normpath(posixpath.join(posixpath.dirname(document), decoded))
        return _relative(logical)
    except ValueError:
        return None


def _text_sample(stream, suffix):
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(stream)
            title = str((reader.metadata or {}).get("/Title") or "")
            sample = []
            for index in range(min(4, len(reader.pages))):
                sample.append((reader.pages[index].extract_text() or "")[:MAX_EXCERPT])
                if sum(map(len, sample)) >= MAX_EXCERPT:
                    break
            return title, "\n".join(sample)
        except (ImportError, OSError, ValueError, KeyError, TypeError, RuntimeError):
            return "", ""
    if suffix in {".md", ".txt", ".html", ".htm", ".csv"}:
        cap = MAX_BYTES + 1 if suffix == ".md" else 64 * 1024
        text = stream.read(cap).decode("utf-8-sig", errors="replace")
        heading = re.search(r"^\s*#{1,6}\s+([^\r\n]+)", text, re.MULTILINE)
        return heading[1].strip() if heading else "", text
    if suffix == ".docx":
        try:
            from docx import Document

            document = Document(stream)
            title = document.core_properties.title or ""
            paragraphs = [row.text[:MAX_EXCERPT] for row in document.paragraphs[:24]]
            return title, "\n".join(paragraphs)
        except (ImportError, OSError, ValueError, KeyError, TypeError, BadZipFile):
            return "", ""
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook

            workbook = load_workbook(stream, read_only=True, data_only=True)
            try:
                sample = workbook.sheetnames[:3]
                for sheet in workbook.worksheets[:3]:
                    for row in sheet.iter_rows(max_row=8, max_col=8, values_only=True):
                        sample.append(" ".join(str(cell)[:160] for cell in row if cell is not None))
                return workbook.properties.title or "", "\n".join(sample)
            finally:
                workbook.close()
        except (ImportError, OSError, ValueError, KeyError, TypeError, BadZipFile):
            return "", ""
    if suffix == ".pptx":
        try:
            from pptx import Presentation

            presentation = Presentation(stream)
            paragraphs = [shape.text[:400] for slide in list(presentation.slides)[:4]
                          for shape in list(slide.shapes)[:12] if shape.has_text_frame]
            return presentation.core_properties.title or "", "\n".join(paragraphs)
        except (ImportError, OSError, ValueError, KeyError, TypeError, BadZipFile):
            return "", ""
    return "", ""


def _attachment_rows(document, text, files):
    result = []
    seen = set()
    for _start, _end, uri in markdown_image_tokens(text):
        if uri in seen:
            continue
        seen.add(uri)
        if uri and re.match(r"data:image/(?:png|jpe?g|gif|webp|bmp|tiff?);base64,", uri, re.IGNORECASE):
            result.append({"reference": "内嵌图片", "status": "embedded"})
            continue
        logical = _logical_attachment(document, uri)
        if logical is None or PurePosixPath(logical).suffix.lower() not in ATTACHMENTS:
            result.append({"reference": (uri or "图片引用")[:256], "status": "external"})
            continue
        result.append({"reference": uri[:256], "path": logical,
                       "status": "present" if logical in files else "missing"})
    return result


def _excerpt(text, suffix):
    if suffix == ".md":
        chunks, cursor = [], 0
        for start, end, _uri in markdown_image_tokens(text):
            chunks.append(text[cursor:start])
            cursor = end
            if start >= MAX_EXCERPT:
                break
        chunks.append(text[cursor:cursor + MAX_EXCERPT])
        text = " ".join(chunks)
    return text.strip()[:MAX_EXCERPT]


def preflight(root, request):
    files = _rows(request)
    items, ignored, attached = [], [], set()
    for name, row in files.items():
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in SUPPORTED_FORMATS or PurePosixPath(name).name.casefold() in raw_materials.RESERVED_NAMES:
            ignored.append({"path": name, "reason": "当前不支持作为独立原件保存"})
            continue
        with raw_materials._open_stage(row["staged_path"]) as stream:
            if os.fstat(stream.fileno()).st_size != row["size"]:
                raise ContractError("RAW_STAGE_MISMATCH", "暂存文件大小已变化", name)
            title, text = _text_sample(stream, suffix)
        attachments = _attachment_rows(name, text, files) if suffix == ".md" else []
        attached.update(asset["path"] for asset in attachments if asset["status"] == "present")
        items.append({"path": name, "title": (title or PurePosixPath(name).stem)[:200],
                      "excerpt": _excerpt(text, suffix), "attachments": attachments})
    return {"categories": raw_materials.categories(root), "items": [item for item in items if item["path"] not in attached],
            "ignored": [item for item in ignored if item["path"] not in attached]}


def _receipt(category, name, row):
    return {"path": "/".join(part for part in (category, name) if part), "name": PurePosixPath(name).name,
            "kind": "file", "size": row["size"], "sha256": row["sha256"]}


def _verified_file(target, row):
    try:
        with raw_materials._open_stage(str(target)) as stream:
            return _file_digest(stream) == (row["size"], row["sha256"])
    except ContractError:
        return False


def package_manifest(directory):
    marker = directory / MARKER
    if not marker.is_file():
        return None
    try:
        with raw_materials._open_stage(str(marker)) as stream:
            content = json.loads(stream.read(128 * 1024).decode("utf-8"))
        rows = content["files"]
        document = _relative(content["document_path"])
        if (content.get("schema_version") != "1.0" or not isinstance(rows, list)
                or not 2 <= len(rows) <= MAX_FILES):
            raise ValueError
        names = set()
        for row in rows:
            name = _relative(row["path"])
            if (name in names or type(row["size"]) is not int or not 0 <= row["size"] <= MAX_BYTES
                    or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])):
                raise ValueError
            names.add(name)
        if document not in names:
            raise ValueError
        return content
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ContractError("INTAKE_PACKAGE_INVALID", "资料包清单无效", str(marker)) from error


def package_for_source(root, source_path):
    parts = PurePosixPath(source_path).parts
    if len(parts) < 3 or parts[0] != "docs-raw" or parts[1] == "sources":
        return None
    for end in range(3, len(parts)):
        directory = root.joinpath(*parts[:end])
        manifest = package_manifest(directory)
        if manifest:
            return directory, manifest
    return None


def package_assets(root, source_path, *, expected_sha256=None):
    package = package_for_source(root, source_path)
    if not package:
        return {}
    directory, manifest = package
    document = manifest["document_path"]
    if root / source_path != directory / document:
        return {}
    entries = {row["path"]: row for row in manifest["files"]}
    if expected_sha256 and entries[document]["sha256"] != expected_sha256:
        return {}
    with raw_materials._open_stage(str(directory / document)) as stream:
        text = stream.read(MAX_BYTES + 1)
    if len(text) > MAX_BYTES or sha256(text).hexdigest() != entries[document]["sha256"]:
        return {}
    assets = {}
    for _start, _end, uri in markdown_image_tokens(text.decode("utf-8-sig", errors="replace")):
        name = _logical_attachment(document, uri)
        if name in entries and PurePosixPath(name).suffix.lower() in ATTACHMENTS:
            assets[uri] = directory / name, entries[name]["sha256"]
    return assets


def _copy_package(temporary, files):
    manifest_files = []
    for name, row in sorted(files.items()):
        destination = temporary / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with raw_materials._open_stage(row["staged_path"]) as source, destination.open("xb") as output:
            if _file_digest(source, output) != (row["size"], row["sha256"]):
                raise ContractError("RAW_STAGE_MISMATCH", "暂存文件内容已变化", name)
            output.flush()
            os.fsync(output.fileno())
        manifest_files.append({key: row[key] for key in ("path", "size", "sha256")})
    return manifest_files


def save(root, request):
    files = _rows(request, save=True)
    category = _relative(request.get("category"))
    directory, parent = raw_materials.category_directory(root, category, error="INTAKE_CATEGORY_INVALID")
    document = _relative(request.get("document_path"))
    file = PurePosixPath(document)
    if (document not in files or file.suffix.lower() not in SUPPORTED_FORMATS
            or file.name.casefold() in raw_materials.RESERVED_NAMES):
        raise ContractError("RAW_UNSUPPORTED_TARGET", "请选择受支持的主文档", document)
    row = files[document]
    if file.suffix.lower() == ".md":
        with raw_materials._open_stage(row["staged_path"]) as source:
            data = source.read(MAX_BYTES + 1)
        if len(data) != row["size"] or sha256(data).hexdigest() != row["sha256"]:
            raise ContractError("RAW_STAGE_MISMATCH", "暂存文件内容已变化", document)
        references = _attachment_rows(document, data.decode("utf-8-sig", errors="replace"), files)
        if (any(ref["status"] == "missing" for ref in references)
                or set(files) != {document} | {ref["path"] for ref in references if ref["status"] == "present"}):
            raise ContractError("INTAKE_ATTACHMENTS_INVALID", "图片需与 Markdown 引用对应并齐全")
    if len(files) == 1:
        receipt = _receipt(category, file.name, row)
        try:
            return raw_materials.save(root, {"path": receipt["path"], "staged_path": row["staged_path"],
                                             "expected_size": row["size"], "expected_sha256": row["sha256"]},
                                      category_only=True)
        except ContractError as error:
            if error.code != "RAW_TARGET_EXISTS" or not _verified_file(directory / file.name, row):
                raise
            return receipt

    if file.suffix.lower() != ".md":
        raise ContractError("INTAKE_ATTACHMENTS_INVALID", "目前仅 Markdown 支持随文归档本地配图")
    target = directory / _relative(file.stem)
    temporary = None
    try:
        with raw_materials._raw_write_lock(root):
            current, observed_parent = raw_materials.category_directory(root, category, error="INTAKE_CATEGORY_INVALID")
            if not os.path.samestat(parent, observed_parent):
                raise ContractError("RAW_UNSAFE_PATH", "原件目录在保存期间发生变化", category)
            temporary = Path(tempfile.mkdtemp(dir=current, prefix=TEMP_PREFIX))
        manifest = {"schema_version": "1.0", "document_path": document, "files": _copy_package(temporary, files)}
        (temporary / MARKER).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with raw_materials._raw_write_lock(root):
            current, observed_parent = raw_materials.category_directory(root, category, error="INTAKE_CATEGORY_INVALID")
            if not os.path.samestat(parent, observed_parent):
                raise ContractError("RAW_UNSAFE_PATH", "原件目录在保存期间发生变化", category)
            aliases = [child.name for child in current.iterdir() if child.name.casefold() == target.name.casefold()]
            if aliases:
                if (aliases != [target.name] or package_manifest(target) != manifest
                        or not all(_verified_file(target / name, item) for name, item in files.items())):
                    raise ContractError("RAW_TARGET_EXISTS", "归档目标已有不同内容", target.name)
            else:
                temporary.rename(target)
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)
    return _receipt(category, target.name + "/" + document, row)
