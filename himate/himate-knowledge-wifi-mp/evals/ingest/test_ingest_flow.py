"""Behavioral checks for the public five-step ingest operations.

Fixtures contain only synthetic documents/cards/code. Author decisions and
independent review are represented by actual draft content and explicit intent;
the tests do not recreate the retired frozen-view pipeline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def library_root(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def put_doc(root, name="design.md", text="# Waiting\n\nWait for a reply.\n"):
    path = root / "docs-raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def card_bytes(identity, doc_ids, *, body="Wait for a reply.", code_refs=(), **extra):
    metadata = {"id": identity,
                "doc_ref": [{"doc_id": doc_id, "line_start": 1, "line_end": 3} for doc_id in doc_ids],
                "code_ref": list(code_refs), **extra}
    return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + f"---\n# {identity}\n\n{body}\n").encode()


def draft(root, identity, doc_ids, *, body="Wait for a reply.", code_refs=(), **extra):
    target = root / ".build/cards" / f"{identity}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(card_bytes(identity, doc_ids, body=body, code_refs=code_refs, **extra))
    return target


def formal(root, identity, doc_ids, **extra):
    target = root / "knowledge" / f"{identity}.md"
    target.write_bytes(card_bytes(identity, doc_ids, **extra))
    return target


def scan(root, source=None):
    data, status = module("ingest").scan(root, {"source": source} if source else {})
    assert status == "prepared", data
    return data


def test_scan_selects_one_document_and_hands_off_its_reverse_references(tmp_path):
    root = library_root(tmp_path)
    put_doc(root, "a.md")
    put_doc(root, "b.md")
    with module("catalog").Catalog(root) as catalog:
        a = catalog.register("raw", "docs-raw/a.md", source_id="doc-a")
        catalog.register("raw", "docs-raw/b.md", source_id="doc-b")
    formal(root, "waiting", [a["id"]])
    (root / ".build/previous").mkdir(parents=True)
    (root / ".build/previous/old.md").write_text("Previous draft must not be handed off")
    (root / "artifacts/query").mkdir()
    query_result = root / "artifacts/query/user-result.json"
    query_result.write_text('{"matches": []}')

    task = scan(root)

    assert task["source"]["doc_id"] == "doc-a"
    assert task["source"]["path"] == "docs-raw/a.md"
    assert task["pending_at_least"] == 1
    assert task["affected_cards"] == [{"id": "waiting", "path": "knowledge/waiting.md", "title": "waiting"}]
    assert (root / task["source"]["original_ref"]).read_bytes() == (root / "docs-raw/a.md").read_bytes()
    assert not (root / ".build/previous").exists()
    assert query_result.read_text() == '{"matches": []}'
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file("doc-a")["processed"] is False
        assert catalog.get_file("doc-b")["processed"] is False
    next_task = scan(root)
    assert next_task["source"]["doc_id"] == "doc-b"
    assert next_task["source"]["path"] == "docs-raw/b.md"


def test_reviewed_no_card_result_is_remembered_and_scan_does_not_repeat_it(tmp_path):
    root = library_root(tmp_path)
    original = put_doc(root)
    task = scan(root)
    source_id = task["source"]["source_id"]
    result, status = module("ingest").commit(root, {"reason": "Fully read; the document adds no useful knowledge."})
    assert status == "completed"
    assert result["card_ids"] == []
    assert not (root / ".build").exists()
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file(source_id)["processed_hash"] == digest(original.read_bytes())
        assert catalog.cards_for(source_id) == []
    result, status = module("ingest").scan(root, {})
    assert status == "unchanged"
    assert result["pending"] == 0


def test_p5_uses_p1_hash_without_reading_the_changed_source_again(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    original = put_doc(root)
    task = scan(root)
    p1_hash = task["source"]["hash"]
    draft(root, "waiting", [task["source"]["doc_id"]])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    original.write_text("# Waiting\n\nA newer version written after review.\n", encoding="utf-8")
    new_hash = digest(original.read_bytes())
    read_bytes = Path.read_bytes

    def forbid_source_read(path):
        if path == original:
            raise AssertionError("P5 reread the raw source instead of using P1's version")
        return read_bytes(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", forbid_source_read)
        result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file(task["source"]["doc_id"])["processed_hash"] == p1_hash
    next_task = scan(root)
    assert next_task["source"]["hash"] == new_hash
    assert next_task["source"]["change"] == "modified"


def test_p5_does_not_repeat_the_p4_check(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    draft(root, "waiting", [task["source"]["doc_id"]])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked

    def forbidden(*args, **kwargs):
        raise AssertionError("P5 must not rerun P4 quality checks")

    monkeypatch.setattr(module("ingest"), "check", forbidden)
    result, status = module("ingest").commit(root, {})
    assert status == "completed", result


def test_failed_p5_keeps_drafts_and_same_task_can_be_retried(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    candidate = draft(root, "waiting", [task["source"]["doc_id"]])
    expected = candidate.read_bytes()
    catalog_type = module("catalog").Catalog
    original_rebuild, calls = catalog_type.rebuild, []

    def fail_once(catalog):
        calls.append(True)
        if len(calls) == 1:
            raise OSError("Synthetic temporary indexing failure")
        return original_rebuild(catalog)

    monkeypatch.setattr(catalog_type, "rebuild", fail_once)
    with pytest.raises(OSError, match="indexing failure"):
        module("ingest").commit(root, {})
    assert candidate.read_bytes() == expected
    assert (root / ".build/task.json").is_file()
    assert (root / "knowledge/waiting.md").read_bytes() == expected
    with catalog_type(root) as catalog:
        assert catalog.get_file(task["source"]["doc_id"])["processed"] is False

    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    assert not candidate.exists()
    with catalog_type(root) as catalog:
        assert [card["id"] for card in catalog.cards_for(task["source"]["doc_id"])] == ["waiting"]


def test_failed_p5_can_retry_a_card_move_with_its_stable_id(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    ingest, catalog_type = module("ingest"), module("catalog").Catalog
    with catalog_type(root) as catalog:
        source = catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
    old = root / "knowledge/old.md"
    old.write_bytes(card_bytes("stable", [source["id"]], body="Original knowledge."))
    task = scan(root)
    candidates = root / ".build/cards"
    moved = candidates / "a-new.md"
    moved.write_bytes(card_bytes("stable", [source["id"]], body="Updated knowledge at its new path."))
    extra = candidates / "z-extra.md"
    extra.write_bytes(card_bytes("extra", [source["id"]], body="Independent knowledge."))
    (root / ".build/changes.json").write_text(json.dumps({"delete": ["knowledge/old.md"]}))
    checked, phase = ingest.check(root, {})
    assert phase == "passed", checked
    write, failures = ingest.atomic_write, []

    def fail_second_copy_once(path, data):
        if path.name == "z-extra.md" and not failures:
            failures.append(True)
            raise OSError("Synthetic second-card copy failure")
        write(path, data)

    monkeypatch.setattr(ingest, "atomic_write", fail_second_copy_once)
    with pytest.raises(OSError, match="second-card copy failure"):
        ingest.commit(root, {})
    assert old.is_file()
    assert (root / "knowledge/a-new.md").read_bytes() == moved.read_bytes()
    assert (root / ".build/task.json").is_file()
    registry = yaml.safe_load((root / "governance/sources.lock.yaml").read_bytes())
    assert registry["resources"][0].get("processed_hash") is None

    result, phase = ingest.commit(root, {})
    assert phase == "completed", result
    assert not old.exists()
    assert not (root / ".build").exists()
    with catalog_type(root) as catalog:
        assert catalog.get_card("stable")["path"] == "knowledge/a-new.md"
        assert {card["id"] for card in catalog.cards_for(source["id"])} == {"stable", "extra"}
        assert catalog.get_file(source["id"])["processed_hash"] == task["source"]["hash"]


@pytest.mark.parametrize("decision", ["create", "update", "merge", "split", "deprecate"])
def test_card_decisions_publish_complete_cards_and_reference_sets(tmp_path, decision):
    root = library_root(tmp_path)
    put_doc(root)
    put_doc(root, "other.md", "# Other\n\nOther valid knowledge.\n")
    with module("catalog").Catalog(root) as catalog:
        primary = catalog.register("raw", "docs-raw/design.md", source_id="doc-main")
        other = catalog.register("raw", "docs-raw/other.md", source_id="doc-other")
    if decision != "create":
        formal(root, "old", [primary["id"], other["id"]], body="Old waiting knowledge.")
    if decision == "merge":
        formal(root, "duplicate", [primary["id"]], body="Repeated waiting knowledge.")
    task = scan(root, "docs-raw/design.md")
    (root / ".build/plan.md").write_text(f"{decision}: preserve valid knowledge and all required references.\n")
    deletes = []
    if decision == "create":
        draft(root, "new", [primary["id"], other["id"]])
        expected = {"new"}
    elif decision == "update":
        draft(root, "old", [primary["id"], other["id"]], body="Updated waiting knowledge.")
        expected = {"old"}
    elif decision == "merge":
        draft(root, "merged", [primary["id"], other["id"]], body="Merged waiting knowledge.")
        deletes = ["knowledge/old.md", "knowledge/duplicate.md"]
        expected = {"merged"}
    elif decision == "split":
        draft(root, "waiting", [primary["id"]], body="Waiting knowledge.")
        draft(root, "diagnosis", [other["id"]], body="Independent diagnosis knowledge.")
        deletes = ["knowledge/old.md"]
        expected = {"waiting", "diagnosis"}
    else:
        draft(root, "replacement", [primary["id"], other["id"]], body="Replacement waiting knowledge.")
        draft(root, "old", [primary["id"], other["id"]], body="Deprecated. Use replacement.",
              lifecycle="deprecated", replacement="replacement", deprecation_reason="New design replaces the old rule.")
        expected = {"old", "replacement"}
    if deletes:
        (root / ".build/changes.json").write_text(json.dumps({"delete": deletes}))
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    with module("catalog").Catalog(root) as catalog:
        assert {card["id"] for card in catalog.all_cards()} == expected
        assert catalog.get_file(primary["id"])["processed_hash"] == task["source"]["hash"]
        assert catalog.get_file(other["id"])["processed"] is False
        if decision in {"create", "update", "merge"}:
            target = next(iter(expected))
            assert {source["id"] for source in catalog.files_for(target)} == {primary["id"], other["id"]}
        if decision == "split":
            assert [card["id"] for card in catalog.cards_for(primary["id"])] == ["waiting"]
            assert [card["id"] for card in catalog.cards_for(other["id"])] == ["diagnosis"]
    for reference in deletes:
        assert not (root / reference).exists()


def test_defer_preserves_task_and_does_not_advance_success(tmp_path):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    candidate = draft(root, "waiting", [task["source"]["doc_id"]])
    result, status = module("ingest").commit(root, {"defer": True, "reason": "Need implementation evidence."})
    assert status == "deferred", result
    assert candidate.is_file()
    assert not (root / "knowledge/waiting.md").exists()
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file(task["source"]["doc_id"])["processed"] is False


def test_deleted_document_is_handed_off_without_automatically_deleting_cards(tmp_path):
    root = library_root(tmp_path)
    original = put_doc(root)
    with module("catalog").Catalog(root) as catalog:
        source = catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
        catalog.mark_processed(source["id"], digest(original.read_bytes()))
    formal(root, "historical", [source["id"]], body="Still useful historical knowledge.")
    original.unlink()
    task = scan(root)
    assert task["source"]["change"] == "deleted"
    assert "original_ref" not in task["source"]
    assert [card["id"] for card in task["affected_cards"]] == ["historical"]
    assert (root / "knowledge/historical.md").is_file()
    result, status = module("ingest").commit(root, {"reason": "Keep the historical card; source retirement is reviewed."})
    assert status == "completed", result
    assert (root / "knowledge/historical.md").is_file()
    _, status = module("ingest").scan(root, {})
    assert status == "unchanged"


def code_project(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/library"
    for name in ("docs-raw", "knowledge", "governance"):
        (root / name).mkdir(parents=True, exist_ok=True)
    code = project / "code/wifi/wait.c"
    code.parent.mkdir(parents=True)
    code.write_text("int wait_reply(void) {\n    return 5;\n}\n")
    (project / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "synthetic", "knowledge_roots": {"wifi": "himate/library"},
        "code_root": "code", "modules": [{"path": "wifi", "chips": ["chip12"], "sides": ["host"]}],
    }))
    original = put_doc(root)
    with module("catalog").Catalog(root) as catalog:
        doc = catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
        source = catalog.register("code", "code/wifi/wait.c", source_id="code-wait")
        catalog.mark_processed(doc["id"], digest(original.read_bytes()))
        catalog.mark_processed(source["id"], digest(code.read_bytes()))
    formal(root, "waiting", [doc["id"]], code_refs=[{
        "code_id": source["id"], "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    return root, code, doc["id"], source["id"]


def test_code_patrol_detects_inserted_lines_and_check_requires_updated_location(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_text("// Added header\n// Added explanation\nint wait_reply(void) {\n    return 5;\n}\n")
    planned, status = module("library").patrol(root, "plan", {})
    assert status == "needs_ingest", planned
    assert planned["next_file"]["source_id"] == code_id
    task = scan(root, code_id)
    assert task["source"]["kind"] == "code"
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 3, "line_end": 5, "symbol": "wait_reply"}])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked


def test_function_body_change_is_patrol_work_and_not_a_fixed_check_semantic_verdict(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    with module("catalog").Catalog(root) as catalog:
        old_doc_hash = catalog.get_file(doc_id)["processed_hash"]
    code.write_text("int wait_reply(void) {\n    return 8;\n}\n")
    planned, status = module("library").patrol(root, "plan", {})
    assert status == "needs_ingest", planned
    assert planned["next_file"]["source_id"] == code_id
    task = scan(root, code_id)
    draft(root, "waiting", [doc_id], body="The design requires a wait; implementation changed and needs reviewer judgement.",
          code_refs=[{"code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    assert checked["review_required"] is True
    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file(code_id)["processed_hash"] == task["source"]["hash"]
        assert catalog.get_file(doc_id)["processed_hash"] == old_doc_hash


def test_deleted_function_is_reported_by_fixed_check(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_text("int unrelated(void) {\n    return 0;\n}\n")
    scan(root, code_id)
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert any(item["code"] == "CODE_SYMBOL_MISSING" for item in checked["findings"])


def test_p4_rejects_line_ranges_outside_a_document(tmp_path):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    data = card_bytes("waiting", [task["source"]["doc_id"]]).replace(b"line_end: 3", b"line_end: 999")
    (root / ".build/cards/waiting.md").write_bytes(data)
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert any(item["code"] == "SOURCE_RANGE_INVALID" for item in checked["findings"])
