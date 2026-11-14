"""Independent source reads never start ingestion or hold its SQLite writer lock."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def library(tmp_path, suffix=".md", data=b"# Design\n\nA documented requirement.\n", *, source_id="doc-design"):
    root = tmp_path / "library"
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / directory).mkdir(parents=True)
    path = root / "docs-raw" / ("design" + suffix)
    path.write_bytes(data)
    registered, status = module("library").sources(root, "register", {
        "kind": "raw", "path": "docs-raw/" + path.name, "source_id": source_id})
    assert status == "registered", registered
    return root, registered["source"], path


def tree_bytes(path):
    return {item.relative_to(path).as_posix(): item.read_bytes() for item in path.rglob("*") if item.is_file()}


def test_two_source_reads_have_independent_handles_and_preserve_ingestion(tmp_path):
    root, source, path = library(tmp_path)
    task, status = module("ingest").scan(root, {"source": source["id"]})
    assert status == "prepared", task
    staged = tree_bytes(root / ".build")
    registry = (root / "governance/sources.lock.yaml").read_bytes()
    original = path.read_bytes()
    first, phase = module("library").sources(root, "extract", {"source_id": source["id"]})
    second, second_phase = module("library").sources(root, "extract", {"source_id": source["id"]})
    try:
        assert phase == second_phase == "extracted"
        assert first["read_id"] != second["read_id"]
        assert first["parsed"]["manifest_ref"].startswith("artifacts/source-read/" + first["read_id"] + "/parsed/")
        assert (root / first["original_ref"]).read_bytes() == original
        assert (root / second["parsed"]["text_ref"]).read_bytes() == original
        renewed, phase = module("library").sources(root, "renew", {"read_id": second["read_id"]})
        assert phase == "renewed" and renewed["read_id"] == second["read_id"]
        released, phase = module("library").sources(root, "release", {"read_id": first["read_id"]})
        assert phase == "released" and released["released"]
        assert not (root / first["parsed"]["manifest_ref"]).exists()
        assert (root / second["parsed"]["manifest_ref"]).is_file()
        assert tree_bytes(root / ".build") == staged
        assert (root / "governance/sources.lock.yaml").read_bytes() == registry
        assert path.read_bytes() == original
    finally:
        module("library").sources(root, "release", {"read_id": first["read_id"]})
        module("library").sources(root, "release", {"read_id": second["read_id"]})


def test_extract_converts_without_blocking_a_simultaneous_search(tmp_path, monkeypatch):
    root, source, _ = library(tmp_path)
    parser = module("document_parser")
    parse = parser.parse
    entered, proceed = Event(), Event()

    def slow_conversion(*args, **kwargs):
        entered.set()
        assert proceed.wait(15)
        return parse(*args, **kwargs)

    monkeypatch.setattr(parser, "parse", slow_conversion)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(module("library").sources, root, "extract", {"source_id": source["id"]})
        try:
            assert entered.wait(10)
            result, phase = module("library").query(root, {"query": "requirement"})
            assert phase == "searched" and result["matches"] == []
        finally:
            proceed.set()
        reading, phase = future.result()
    assert phase == "extracted"
    module("library").sources(root, "release", {"read_id": reading["read_id"]})


@pytest.mark.parametrize("payload", [
    {"source_id": "missing"}, {"source_id": "doc-design", "page_start": 1},
    {"source_id": "doc-design", "page_start": True, "page_end": 2},
    {"source_id": "doc-design", "page_start": 1, "page_end": 2},
])
def test_extract_requires_a_registered_document_and_valid_pdf_range(tmp_path, payload):
    root, _, _ = library(tmp_path)
    marker = root / ".build/task.json"
    marker.parent.mkdir()
    marker.write_bytes(b'{"author_work":"in progress"}')
    with pytest.raises(module("validation").ContractError):
        module("library").sources(root, "extract", payload)
    assert marker.read_bytes() == b'{"author_work":"in progress"}'
    assert not (root / "artifacts/source-read").exists()


def test_pdf_page_range_keeps_original_page_numbers_and_current_source(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    root, source, path = library(tmp_path, ".pdf", b"placeholder")
    writer = PdfWriter()
    for number in range(1, 4):
        page = writer.add_blank_page(width=300, height=180)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 24 140 Td (Original page {number} requirement) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as stream:
        writer.write(stream)
    original = path.read_bytes()
    reading, phase = module("library").sources(root, "extract", {
        "source_id": source["id"], "page_start": 2, "page_end": 2})
    try:
        assert phase == "extracted", reading
        loaded = module("document_parser").load(root, reading["parsed"],
                                                 expected_source_id=source["id"], expected_sha256=module("ingest").sha(original))
        assert "Original page 2" in loaded["text"]
        assert "Original page 1" not in loaded["text"] and "Original page 3" not in loaded["text"]
        assert module("document_parser").select(loaded, {"kind": "page", "page": 2})
        with pytest.raises(module("validation").ContractError):
            module("document_parser").select(loaded, {"kind": "page", "page": 1})
        assert path.read_bytes() == original
        assert not (root / ".build").exists()
    finally:
        module("library").sources(root, "release", {"read_id": reading["read_id"]})


def test_read_lifecycle_actions_do_not_need_or_create_a_catalog(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    result, phase = module("library").sources(root, "cleanup", {})
    assert phase == "cleaned" and result["removed"] == []
    assert not (root / "artifacts/knowledge.sqlite").exists()
    assert not (root / "governance/sources.lock.yaml").exists()


def test_historical_resolve_accepts_a_registered_source_id_with_a_colon(tmp_path):
    root, source, path = library(tmp_path, source_id="doc:design")
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update(GIT_AUTHOR_NAME="Synthetic test", GIT_COMMITTER_NAME="Synthetic test",
                       GIT_AUTHOR_EMAIL="synthetic@example.invalid", GIT_COMMITTER_EMAIL="synthetic@example.invalid")

    def git(*arguments):
        result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", "-C", str(root),
                                 *arguments], env=environment, capture_output=True, check=True, timeout=20)
        return result.stdout.decode().strip()

    old_bytes = path.read_bytes()
    git("init", "--quiet")
    git("add", "--", "docs-raw/design.md")
    git("commit", "--quiet", "-m", "A synthetic retained document")
    old_commit = git("rev-parse", "HEAD")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed(source["id"], module("ingest").sha(old_bytes), source_commit=old_commit)
    path.write_text("# New source\n\nA newer requirement.\n", encoding="utf-8")
    current = path.read_bytes()
    resolved, phase = module("library").sources(root, "resolve", {"source_id": source["id"]})
    assert phase == "resolved" and resolved["source_id"] == "doc:design"
    assert (root / resolved["original_ref"]).read_bytes() == old_bytes
    assert (root / resolved["text_ref"]).read_bytes() == old_bytes
    assert path.read_bytes() == current
