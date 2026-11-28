"""New code sources retain an explicit encoding without manufacturing snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


CODE = "int wait_reply(void) {\n    /* 等待回复 */\n    return 1;\n}\n"


@pytest.fixture
def library(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/library"
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / directory).mkdir(parents=True)
    code = project / "main/wifi/reply.c"
    code.parent.mkdir(parents=True)
    code.write_bytes(CODE.encode("gb18030"))
    (root / "docs-raw/design.md").write_text("# Reply\n\nWait for a reply.\n", encoding="utf-8")
    (root / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "encoding-test",
        "code_root": "../../main", "modules": [{"path": "wifi"}],
    }), encoding="utf-8")
    _, status = module("library").sources(root, "register", {
        "kind": "doc", "path": "docs-raw/design.md", "source_id": "doc-design",
    })
    assert status == "registered"
    return root, code


def register(root, encoding):
    return module("library").sources(root, "register", {
        "kind": "code", "path": "main/wifi/reply.c", "source_id": "code-reply", "encoding": encoding,
    })


def test_explicit_encoding_is_returned_and_survives_catalog_rebuild(library):
    root, code = library
    original = code.read_bytes()
    registered, status = register(root, "gb18030")
    assert status == "registered", registered
    assert registered["source"]["encoding"] == "gb18030"

    with module("catalog").Catalog(root) as catalog:
        catalog.rebuild()
    listed, status = module("library").sources(root, "list", {"code_id": "code-reply"})
    assert status == "listed"
    assert listed["source"]["encoding"] == "gb18030"
    registry = yaml.safe_load((root / "governance/sources.lock.yaml").read_bytes())
    assert registry["snapshots"] == []
    assert code.read_bytes() == original


def test_referenced_gb18030_source_is_readable_in_maintenance_and_checked(library):
    root, code = library
    original = code.read_bytes()
    register(root, "gb18030")
    header = {
        "id": "wait-reply", "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
        "code_ref": [{"code_id": "code-reply", "line_start": 1, "line_end": 4, "symbol": "wait_reply"}],
    }
    (root / "knowledge/wait-reply.md").write_text(
        "---\n" + yaml.safe_dump(header) + "---\n# Wait reply\n\nDocumented waiting rule.\n", encoding="utf-8")

    task, status = module("ingest").scan(root, {"source": "code-reply"})

    assert status == "prepared", task
    assert task["gaps"] == []
    assert task["source"]["encoding"] == "gb18030"
    assert (root / task["source"]["text_ref"]).read_text(encoding="utf-8") == CODE
    assert (root / task["source"]["original_ref"]).read_bytes() == original
    candidate = root / ".build/cards/wait-reply.md"
    candidate.write_text("---\n" + yaml.safe_dump(header, sort_keys=False)
                         + "---\n# Wait reply\n\nThe function returns one.\n", encoding="utf-8")
    draft_bytes = candidate.read_bytes()
    write_plan(root, [("wait-reply", "knowledge/wait-reply.md")])

    checked, status = module("ingest").check(root, {})

    assert status == "passed", checked
    assert checked["findings"] == []
    assert candidate.read_bytes() == draft_bytes
    assert code.read_bytes() == original
    registry = yaml.safe_load((root / "governance/sources.lock.yaml").read_bytes())
    assert registry["snapshots"] == []


@pytest.mark.parametrize("encoding", ["latin-1", "auto"])
def test_invalid_encoding_is_rejected_without_registering_source(library, encoding):
    root, code = library
    registry = root / "governance/sources.lock.yaml"
    original_registry = registry.read_bytes()
    original_code = code.read_bytes()

    with pytest.raises(ValueError, match="INVALID_SOURCE_ENCODING"):
        register(root, encoding)

    assert registry.read_bytes() == original_registry
    assert code.read_bytes() == original_code
    result, _ = module("library").sources(root, "list", {"code_id": "code-reply"})
    assert result["source"] is None


def test_reregistering_encoding_does_not_advance_processed_hash(library):
    root, code = library
    code.write_bytes(CODE.encode("utf-8"))
    old_hash = hashlib.sha256(code.read_bytes()).hexdigest()
    register(root, "utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed("code-reply", old_hash)
        catalog.mark_reference_reviewed("code-reply", old_hash, True)
    (root / "knowledge/wait-reply.md").write_text(
        "---\nid: wait-reply\ndoc_ref:\n- doc_id: doc-design\n  line_start: 1\n  line_end: 3\n"
        "code_ref:\n- code_id: code-reply\n  line_start: 1\n  line_end: 4\n  symbol: wait_reply\n"
        "---\n# Wait reply\n\nDocumented waiting rule.\n", encoding="utf-8")
    code.write_bytes(CODE.encode("gb18030"))

    result, status = register(root, "gb18030")

    assert status == "registered", result
    assert result["source"]["id"] == "code-reply"
    assert result["source"]["encoding"] == "gb18030"
    assert result["source"]["processed_hash"] == old_hash
    ingest = module("ingest")
    task, status = ingest.scan(root, {"source": "code-reply"})
    assert status == "prepared", task
    # A legacy file-level review does not establish a checked fragment version.
    assert task["source"]["change"] == "baseline_missing"
    assert task["source"]["hash"] != old_hash
    reviewed_hash = task["source"]["hash"]
    write_plan(root, [])
    checked, status = ingest.check(root, {})
    assert status == "passed", checked
    assert ingest.commit(root, {"reason": "The decoded current function and its existing card were reviewed."})[1] == "completed"
    with module("catalog").Catalog(root) as catalog:
        version = catalog.get_card("wait-reply")["code_ref"][0]["evidence_version"]
        assert version
        assert catalog.get_file("code-reply")["processed_hash"] == old_hash

    # Once actually confirmed, identical decoded text survives an encoding-only
    # change even though the raw bytes and file hash differ from that review.
    code.write_bytes(CODE.encode("utf-8"))
    result, status = register(root, "utf-8")
    assert status == "registered", result
    assert hashlib.sha256(code.read_bytes()).hexdigest() != reviewed_hash
    task, status = ingest.scan(root, {"source": "code-reply"})
    assert status == "unchanged", task
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("code-reply")["processed_hash"] == old_hash
        assert catalog.get_card("wait-reply")["code_ref"][0]["evidence_version"] == version


def test_existing_catalog_without_encoding_column_accepts_new_code_registration(library):
    root, _ = library
    document_hash = hashlib.sha256((root / "docs-raw/design.md").read_bytes()).hexdigest()
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed("doc-design", document_hash)
    database = root / "artifacts/knowledge.sqlite"
    database.unlink()
    # The released files table predates explicit source encoding. This is a
    # historical storage fixture; migration is exercised through public calls.
    with sqlite3.connect(database) as connection:
        connection.execute("""
            CREATE TABLE files (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, repo TEXT NOT NULL,
                processed_hash TEXT, processed_exists INTEGER, processed_at TEXT,
                source_commit TEXT, last_attempt TEXT, UNIQUE(kind,path,repo)
            )
        """)

    registered, status = register(root, "gb18030")

    assert status == "registered", registered
    assert registered["source"]["encoding"] == "gb18030"
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("doc-design")["processed_hash"] == document_hash
        assert catalog.get_file("code-reply")["encoding"] == "gb18030"
