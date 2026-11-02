"""PDF page counts and disposable parse caches never own review progress."""

from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def pdf_bytes(pages=3, title="Synthetic PDF"):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_metadata({"/Title": title})
    for _ in range(pages):
        writer.add_blank_page(width=300, height=180)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def conversion(monkeypatch):
    parser = module("document_parser")
    calls = []

    def convert(root, source, data, output, options, page_range, source_hash, profile_hash):
        calls.append({"source_id": source.get("id") or source["source_id"],
                      "source_hash": source_hash, "profile_hash": profile_hash})
        pages = list(range(1, parser.pdf_page_count(data) + 1))
        segments = [{"locator": {"kind": "page", "page": page},
                     "text": f"Original physical page {page}."} for page in pages]
        text = "\n\n".join(item["text"] for item in segments)
        (output / "document.md").write_text(text, encoding="utf-8")
        parser._write_json(output / "document.json", {"schema_name": "SyntheticPDF", "pictures": []})
        return text, segments, [], [], pages

    monkeypatch.setattr(parser, "_docling", convert)
    return parser, calls


def source(identity="doc-pdf"):
    return {"id": identity, "path": "docs-raw/specs/design.pdf"}


def test_page_count_uses_all_physical_pages_of_the_original_pdf():
    assert module("document_parser").pdf_page_count(pdf_bytes(17)) == 17


@pytest.mark.parametrize("data", [b"", b"not a PDF", None, "not bytes"])
def test_page_count_rejects_unreadable_originals(data):
    with pytest.raises(module("validation").ContractError):
        module("document_parser").pdf_page_count(data)


def test_page_count_rejects_a_pdf_without_pages():
    with pytest.raises(module("validation").ContractError):
        module("document_parser").pdf_page_count(pdf_bytes(0))


def test_matching_pdf_cache_is_verified_and_reused_without_conversion(tmp_path, conversion):
    parser, calls = conversion
    data = pdf_bytes()
    first = parser.prepare_pdf(tmp_path, source(), data)
    manifest = tmp_path / first["manifest_ref"]
    before = manifest.read_bytes()

    second = parser.prepare_pdf(tmp_path, source(), data)

    assert second == first
    assert len(calls) == 1
    assert first["manifest_ref"].startswith("artifacts/ingest/parsed/")
    assert not (tmp_path / ".build").exists()
    assert not {"processing", "reviewed_pages", "remaining_pages"} & set(second)
    assert manifest.read_bytes() == before
    loaded = parser.load(tmp_path, second, expected_source_id="doc-pdf",
                         expected_sha256=parser.sha256_bytes(data))
    assert loaded["manifest"]["pages"] == [1, 2, 3]


@pytest.mark.parametrize("damage", ["markdown", "manifest", "extra-file", "missing-file"])
def test_damaged_cache_rebuilds_a_fresh_bundle_without_rewriting_the_old_one(tmp_path, conversion, damage):
    parser, calls = conversion
    data = pdf_bytes()
    first = parser.prepare_pdf(tmp_path, source(), data)
    manifest = tmp_path / first["manifest_ref"]
    if damage == "markdown":
        (tmp_path / first["markdown_ref"]).write_bytes(b"Changed after handoff.")
    elif damage == "manifest":
        manifest.write_bytes(b"Damaged fixed manifest.")
    elif damage == "extra-file":
        (manifest.parent / "unexpected.txt").write_bytes(b"Unregistered cache output.")
    else:
        (tmp_path / first["locators_ref"]).unlink()
    old_manifest = manifest.read_bytes()

    rebuilt = parser.prepare_pdf(tmp_path, source(), data)

    assert len(calls) == 2
    assert rebuilt["manifest_ref"] != first["manifest_ref"]
    assert manifest.read_bytes() == old_manifest
    parser.load(tmp_path, rebuilt, expected_source_id="doc-pdf",
                expected_sha256=parser.sha256_bytes(data))


def test_deleting_all_cached_materials_allows_reconstruction(tmp_path, conversion):
    parser, calls = conversion
    data = pdf_bytes()
    first = parser.prepare_pdf(tmp_path, source(), data)
    cache = tmp_path / "artifacts/ingest/parsed"
    assert cache.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(cache)

    rebuilt = parser.prepare_pdf(tmp_path, source(), data)

    assert len(calls) == 2
    assert (tmp_path / rebuilt["manifest_ref"]).is_file()
    assert rebuilt["manifest_ref"] != first["manifest_ref"]


@pytest.mark.parametrize("damage", ["missing", "invalid-json", "wrong-profile"])
def test_cache_pointer_cannot_skip_verifying_the_requested_profile(tmp_path, conversion, damage):
    parser, calls = conversion
    data = pdf_bytes()
    first = parser.prepare_pdf(tmp_path, source(), data)
    bundle = tmp_path / Path(first["manifest_ref"]).parent
    index = bundle.parent / (bundle.name[:64] + ".json")
    old_manifest = (tmp_path / first["manifest_ref"]).read_bytes()
    if damage == "missing":
        index.unlink()
    elif damage == "invalid-json":
        index.write_bytes(b"A damaged disposable cache pointer.")
    else:
        other = parser.prepare_pdf(tmp_path, source(), data, options={"threads": 3})
        index.write_bytes(parser.canonical_bytes(other))
    previous_calls = len(calls)

    rebuilt = parser.prepare_pdf(tmp_path, source(), data)

    assert len(calls) == previous_calls + 1
    assert rebuilt["profile_sha256"] == first["profile_sha256"]
    assert rebuilt["manifest_ref"] != first["manifest_ref"]
    assert (tmp_path / first["manifest_ref"]).read_bytes() == old_manifest


@pytest.mark.parametrize("change", ["source-id", "original", "options", "installed-profile"])
def test_cache_identity_tracks_the_source_and_current_actual_profile(tmp_path, conversion, monkeypatch, change):
    parser, calls = conversion
    data = pdf_bytes()
    first = parser.prepare_pdf(tmp_path, source(), data)
    next_source, next_data, options = source(), data, None
    if change == "source-id":
        next_source = source("doc-other-pdf")
    elif change == "original":
        next_data = pdf_bytes(title="A new original version")
    elif change == "options":
        options = {"threads": 3}
    else:
        version = parser.metadata.version
        monkeypatch.setattr(parser.metadata, "version", lambda name: "changed-parser-version"
                            if name == "docling-slim" else version(name))

    second = parser.prepare_pdf(tmp_path, next_source, next_data, options=options)

    assert len(calls) == 2
    assert second["manifest_ref"] != first["manifest_ref"]
    assert second["source_id"] == next_source["id"]
    assert second["source_sha256"] == parser.sha256_bytes(next_data)
    if change in {"options", "installed-profile"}:
        assert second["profile_sha256"] != first["profile_sha256"]


def test_partial_conversion_cannot_change_the_original_page_count(tmp_path, conversion, monkeypatch):
    parser, _ = conversion
    convert = parser._docling

    def partial(*args, **kwargs):
        text, segments, images, _, _ = convert(*args, **kwargs)
        return text, segments[:1], images, [{"code": "DOCUMENT_PARTIAL", "severity": "review",
                                            "message": "Only one page was converted."}], [1]

    monkeypatch.setattr(parser, "_docling", partial)
    data = pdf_bytes(12)

    parsed = parser.prepare_pdf(tmp_path, source(), data)

    assert parsed["parse_status"] == "partial"
    assert parsed["statistics"]["page_count"] == 1
    assert parser.pdf_page_count(data) == 12


def test_cache_preparation_keeps_original_input_limits(tmp_path, conversion):
    parser, calls = conversion
    with pytest.raises(module("validation").ContractError, match="PARSE_INPUT_LIMIT"):
        parser.prepare_pdf(tmp_path, source(), pdf_bytes(), options={"max_input_bytes": 1})
    assert calls == []


def test_arbitrary_artifact_directories_remain_forbidden_parse_outputs(tmp_path, conversion):
    parser, _ = conversion
    with pytest.raises(module("validation").ContractError, match="PARSE_OUTPUT_UNSAFE"):
        parser.parse(tmp_path, source(), pdf_bytes(), "artifacts/ingest/parsed/arbitrary")


def test_cache_parent_link_cannot_redirect_materials_into_originals(tmp_path, conversion):
    parser, calls = conversion
    originals = tmp_path / "docs-raw"
    originals.mkdir()
    marker = originals / "original.txt"
    marker.write_bytes(b"Read-only synthetic original.")
    parent = tmp_path / "artifacts/ingest"
    parent.mkdir(parents=True)
    link = parent / "parsed"
    if os.name == "nt":
        powershell = shutil.which("powershell.exe")
        if powershell is None:
            pytest.skip("PowerShell is unavailable for creating a synthetic junction")
        environment = dict(os.environ, FACTUM_CACHE_LINK=str(link), FACTUM_CACHE_TARGET=str(originals))
        result = subprocess.run([
            powershell, "-NoProfile", "-NonInteractive", "-Command",
            "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction "
            "-Path $env:FACTUM_CACHE_LINK -Target $env:FACTUM_CACHE_TARGET | Out-Null",
        ], env=environment, capture_output=True, text=True, timeout=30)
        if result.returncode:
            pytest.skip("Synthetic junction creation is unavailable: " + result.stderr)
    else:
        try:
            link.symlink_to(originals, target_is_directory=True)
        except OSError as error:
            pytest.skip("Synthetic symlink creation is unavailable: " + str(error))
    try:
        with pytest.raises(module("validation").ContractError):
            parser.prepare_pdf(tmp_path, source(), pdf_bytes())
        assert calls == []
        assert list(originals.iterdir()) == [marker]
        assert marker.read_bytes() == b"Read-only synthetic original."
    finally:
        assert link.absolute().is_relative_to(tmp_path.resolve())
        if link.is_symlink():
            link.unlink()
        else:
            link.rmdir()
