"""Public checks preserve native DOCX references without rewriting old cards."""

from pathlib import Path
import sys

from docx import Document
import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


@pytest.mark.parametrize("paragraph, expected", [(2, "passed"), (3, "failed")])
def test_legacy_docx_paragraph_is_checked_against_native_document(tmp_path, paragraph, expected):
    root = tmp_path / "library"
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / directory).mkdir(parents=True)
    original = root / "docs-raw/design.docx"
    document = Document()
    document.add_paragraph("First documented requirement.")
    document.add_paragraph("Second documented requirement.")
    document.save(original)
    original_bytes = original.read_bytes()
    registered, status = module("library").sources(root, "register", {
        "kind": "raw", "path": "docs-raw/design.docx", "source_id": "doc-design",
    })
    assert status == "registered", registered
    metadata = {
        "schema_version": "2.0", "id": "requirement", "profile": "entity", "title": "Requirement",
        "summary": "A documented requirement", "lifecycle": "stable", "owner": "synthetic",
        "review_mode": "manual_document", "scope": {"applicability": "unknown", "contexts": []},
        "aliases": [], "relations": [], "sources": [{
            "evidence_ref": "doc", "source_id": "doc-design", "snapshot_id": "old-doc",
            "locator": {"kind": "paragraph", "paragraph": paragraph},
        }], "claims": [{
            "id": "answer", "text_ref": "#answer", "usage": "guidance", "evidence_kind": "design",
            "source_refs": ["doc"], "context_ids": [], "verification_requirements": [],
        }],
    }
    old_bytes = ("---\n" + yaml.safe_dump(metadata, sort_keys=False)
                 + '---\n# Requirement\n\n<a id="answer"></a>\nSecond documented requirement.\n').encode()
    formal = root / "knowledge/requirement.md"
    formal.write_bytes(old_bytes)
    task, status = module("ingest").scan(root, {"source": "doc-design"})
    assert status == "prepared", task
    draft = root / ".build/cards/requirement.md"
    draft.write_bytes(old_bytes)

    checked, status = module("ingest").check(root, {})

    assert status == expected, checked
    if expected == "failed":
        assert any(item["code"] == "INVALID_SOURCE_LOCATOR" for item in checked["findings"])
    else:
        assert checked["findings"] == []
    assert formal.read_bytes() == old_bytes
    assert draft.read_bytes() == old_bytes
    assert original.read_bytes() == original_bytes
