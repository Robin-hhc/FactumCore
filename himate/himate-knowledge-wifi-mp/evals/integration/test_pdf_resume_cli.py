"""Real native PDF ingestion resumes through the shipped CLI after cache loss."""

import hashlib
from io import BytesIO
import json
import shutil

import pytest
import yaml

from integration import test_single_file_cli as cli_support


knowledge = cli_support.knowledge
invoke = cli_support.invoke


@pytest.fixture(autouse=True)
def native_pdf_dependencies(monkeypatch):
    pytest.importorskip("docling.document_converter")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


def write_pdf(root):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
    for number in range(1, 4):
        page = writer.add_blank_page(width=400, height=220)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
            DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 24 170 Td (SYNTHETIC_RESUME_PAGE_{number}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    path = root / "docs-raw/specs/resume.pdf"
    path.write_bytes(stream.getvalue())
    return path


def request_file(root, name, value):
    path = root / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def write_plan(root, page, cards):
    header = {"cards": cards, "source_pages": [[page, page]]}
    (root / ".build/plan.md").write_text(
        "---\n" + yaml.safe_dump(header, sort_keys=False)
        + "---\nEvaluate all material on this physical page; retain already published knowledge.\n",
        encoding="utf-8")


def source_view(root, identity):
    payload = request_file(root, "source-list.json", {"source_id": identity})
    status, report = invoke(root, "source", "list", "--input", payload)
    assert status == 0 and report["phase"] == "listed", report
    return report["data"]


@pytest.mark.parametrize("page_budget", [None, 1], ids=["agent-selected", "explicit-one-page"])
def test_pdf_batches_publish_partial_cards_then_resume_after_cache_and_database_deletion(knowledge, page_budget):
    original = write_pdf(knowledge)
    original_bytes = original.read_bytes()
    expected_hash = hashlib.sha256(original_bytes).hexdigest()
    scan_options = {"source": "docs-raw/specs/resume.pdf"}
    if page_budget is not None:
        scan_options["review_page_budget"] = page_budget
    scan_request = request_file(knowledge, "pdf-scan.json", scan_options)
    identity = None
    card_path = knowledge / "knowledge/pdf-first-page.md"
    published_bytes = None

    for page in range(1, 4):
        status, scanned = invoke(knowledge, "ingest", "scan", "--input", scan_request)
        assert status == 0 and scanned["phase"] == "prepared", scanned
        task = scanned["data"]
        identity = identity or task["source"]["source_id"]
        assert task["source"]["source_id"] == identity
        review = task["pdf_review"]
        end = page if page_budget is not None else 3
        assert (review["total_pages"], review["start_page"], review["end_page"]) == (3, page, end)
        assert review["page_budget"] == page_budget and review["text_budget"] == 400000
        assert review["reviewed_pages"] == ([] if page == 1 else [[1, page - 1]])
        packet = (knowledge / review["packet_ref"]).read_text(encoding="utf-8")
        assert all((f"SYNTHETIC_RESUME_PAGE_{other}" in packet) == (page <= other <= end)
                   for other in range(1, 4))

        cards = []
        if page == 1:
            cards = [{"id": "pdf-first-page", "path": "knowledge/pdf-first-page.md"}]
            metadata = {"id": "pdf-first-page",
                        "doc_ref": [{"doc_id": identity, "page_start": 1, "page_end": 1}],
                        "code_ref": []}
            (knowledge / ".build/cards/pdf-first-page.md").write_text(
                "---\n" + yaml.safe_dump(metadata, sort_keys=False)
                + "---\n# First physical page\n\nThe source declares SYNTHETIC_RESUME_PAGE_1.\n",
                encoding="utf-8")
        write_plan(knowledge, page, cards)
        (knowledge / ".build/review.md").write_text(
            f"Evaluated all material on physical page {page}; candidate evidence matches.\n",
            encoding="utf-8")
        command = ("review",) if page == 1 else ("ingest", "check")
        status, checked = invoke(knowledge, *command)
        assert status == 0 and checked["phase"] == "passed", checked
        commit_request = request_file(knowledge, "pdf-commit.json", {
            "reason": "The full planned page was evaluated; retain the existing first-page card.",
        })
        command = ("apply",) if page == 1 else ("ingest", "commit")
        status, committed = invoke(knowledge, *command, "--input", commit_request)
        assert status == 0 and committed["phase"] == "completed", committed
        result = committed["data"]
        listed = source_view(knowledge, identity)
        registered = listed["source"]
        assert listed["cards"] == [{"id": "pdf-first-page", "path": "knowledge/pdf-first-page.md",
                                    "title": "First physical page"}]
        if published_bytes is None:
            published_bytes = card_path.read_bytes()
        assert card_path.read_bytes() == published_bytes
        assert original.read_bytes() == original_bytes

        if page < 3:
            expected_processing = {"source_sha256": expected_hash, "reviewed_pages": [[1, page]]}
            assert result["source_complete"] is False
            assert result["processed_hash"] is None
            assert result["processing"] == expected_processing
            assert result["remaining_pages"] == [[page + 1, 3]]
            assert registered["processing"] == expected_processing
            assert registered.get("processed_hash") is None
        else:
            assert result["source_complete"] is True
            assert result["processed_hash"] == expected_hash
            assert registered["processed_hash"] == expected_hash
            assert "processing" not in registered
            resources = yaml.safe_load((knowledge / "governance/sources.lock.yaml").read_bytes())["resources"]
            assert "processing" not in next(item for item in resources if item["source_id"] == identity)

        if page == 1:
            registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
            cache = knowledge / "artifacts/ingest/parsed"
            assert cache.resolve().is_relative_to(knowledge.resolve())
            shutil.rmtree(cache)
            (knowledge / "artifacts/knowledge.sqlite").unlink()
            assert (knowledge / "governance/sources.lock.yaml").read_bytes() == registry

    status, unchanged = invoke(knowledge, "ingest", "scan", "--input", scan_request)
    assert status == 0 and unchanged["phase"] == "unchanged", unchanged
    assert unchanged["data"]["pending"] == 0
    assert card_path.read_bytes() == published_bytes


def test_direct_pdf_apply_without_an_explicit_page_scope_cannot_publish_or_complete(knowledge):
    write_pdf(knowledge)
    scan_request = request_file(knowledge, "pdf-scan.json", {
        "source": "docs-raw/specs/resume.pdf", "review_page_budget": 1,
    })
    status, scanned = invoke(knowledge, "ingest", "scan", "--input", scan_request)
    assert status == 0 and scanned["phase"] == "prepared", scanned
    (knowledge / ".build/plan.md").write_text("---\ncards: []\n---\nLegacy plan without page coverage.\n",
                                               encoding="utf-8")
    registry = (knowledge / "governance/sources.lock.yaml").read_bytes()
    request = request_file(knowledge, "pdf-commit.json", {"reason": "No card is needed."})

    status, rejected = invoke(knowledge, "apply", "--input", request)

    assert status == 2 and rejected["phase"] == "invalid", rejected
    assert rejected["diagnostics"][0]["code"] == "PDF_REVIEW_SCOPE_REQUIRED"
    assert (knowledge / "governance/sources.lock.yaml").read_bytes() == registry
    assert not list((knowledge / "knowledge").rglob("*.md"))
    assert (knowledge / ".build/task.json").exists()
