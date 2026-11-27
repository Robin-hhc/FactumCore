"""Behavioral checks for the public five-step ingest operations.

Fixtures contain only synthetic documents/cards/code. Author decisions and
independent review are represented by actual draft content and explicit intent;
the tests do not recreate the retired frozen-view pipeline.
"""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


def digest(data):
    return hashlib.sha256(data).hexdigest()


def library_root(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def retain_fixture_history(root):
    for arguments in (["init"], ["config", "core.autocrlf", "false"], ["add", "."],
                      ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Retain synthetic history"]):
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", str(root), *arguments],
                       check=True, capture_output=True)


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
    write_plan(root, [("waiting", "knowledge/waiting.md")])
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
        assert catalog.registry["snapshots"] == []
    assert not (root / "artifacts/evidence").exists()
    assert not (root / ".build").exists()
    assert not (root / "logs").exists()
    resolved, status = module("library").sources(root, "resolve", {
        "source_id": task["source"]["doc_id"]})
    assert status == "resolved", resolved
    assert (root / resolved["original_ref"]).read_bytes() == original.read_bytes()
    next_task = scan(root)
    assert next_task["source"]["hash"] == new_hash
    assert next_task["source"]["change"] == "modified"


def test_p5_does_not_repeat_the_p4_check(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    draft(root, "waiting", [task["source"]["doc_id"]])
    plan = write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    plan.unlink()

    def forbidden(*args, **kwargs):
        raise AssertionError("P5 must not rerun P4 quality checks")

    monkeypatch.setattr(module("ingest"), "check", forbidden)
    result, status = module("ingest").commit(root, {})
    assert status == "completed", result


@pytest.mark.parametrize("keep_readme", [False, True], ids=["without-readme", "with-readme"])
def test_failed_p5_keeps_drafts_and_same_task_can_be_retried(tmp_path, monkeypatch, keep_readme):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    readme = root / ".build/README.md"
    readme_bytes = b"Temporary ingest staging lives here.\r\n"
    if keep_readme:
        readme.write_bytes(readme_bytes)
    candidate = draft(root, "waiting", [task["source"]["doc_id"]])
    expected = candidate.read_bytes()
    staged_bytes = {path.relative_to(root): path.read_bytes()
                    for path in (root / ".build").rglob("*") if path.is_file()}
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
    assert {path.relative_to(root): path.read_bytes()
            for path in (root / ".build").rglob("*") if path.is_file()} == staged_bytes
    assert candidate.read_bytes() == expected
    assert (root / ".build/task.json").is_file()
    assert (root / "knowledge/waiting.md").read_bytes() == expected
    with catalog_type(root) as catalog:
        assert catalog.get_file(task["source"]["doc_id"])["processed"] is False

    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    assert not candidate.exists()
    if keep_readme:
        assert list((root / ".build").iterdir()) == [readme]
        assert readme.read_bytes() == readme_bytes
    else:
        assert not (root / ".build").exists()
    with catalog_type(root) as catalog:
        assert [card["id"] for card in catalog.cards_for(task["source"]["doc_id"])] == ["waiting"]


def test_failed_panel_publication_preserves_view_and_p5_retry(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    module("library").patrol(root, "reindex", {})
    panel = module("panel")
    previous_view, _ = panel.run(root, "overview", {})
    candidate = draft(root, "pending", [task["source"]["doc_id"]])
    original_lock = (root / "governance/sources.lock.yaml").read_bytes()
    original_publish = panel.publish

    def fail_after_writing_view(*args):
        original_publish(*args)
        raise OSError("Synthetic panel publication failure")

    with monkeypatch.context() as patch:
        patch.setattr(panel, "publish", fail_after_writing_view)
        with pytest.raises(OSError, match="panel publication failure"):
            module("ingest").commit(root, {})
    assert panel.run(root, "overview", {})[0] == previous_view
    assert (root / "governance/sources.lock.yaml").read_bytes() == original_lock
    assert not (root / "artifacts/ingest/latest.json").exists()
    assert candidate.is_file() and (root / ".build/task.json").is_file()

    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    new_view, _ = panel.run(root, "overview", {})
    assert new_view["card_count"] == 1 and new_view["view_revision"] != previous_view["view_revision"]



def test_final_sqlite_commit_failure_restores_source_lock_and_preserves_receipt(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    ingest = module("ingest")
    panel = module("panel")
    catalog_type = module("catalog").Catalog
    module("library").patrol(root, "reindex", {})
    previous, _ = panel.run(root, "overview", {})
    candidate = draft(root, "pending", [task["source"]["doc_id"]])
    lock = root / "governance/sources.lock.yaml"
    original_lock = lock.read_bytes()
    receipt = root / "artifacts/ingest/latest.json"
    receipt.parent.mkdir()
    previous_receipt = b'{"source_id":"previous","source_complete":true}\n'
    receipt.write_bytes(previous_receipt)
    save_registry = catalog_type._save_registry

    # The read transaction sees the old view and blocks only the final writer commit.
    with closing(sqlite3.connect(root / "artifacts/knowledge.sqlite", isolation_level=None)) as reader:
        def save_and_hold_reader(catalog):
            save_registry(catalog)
            assert lock.read_bytes() != original_lock
            catalog.connection.execute("PRAGMA busy_timeout=50")
            reader.execute("BEGIN")
            assert reader.execute("SELECT count(*) FROM panel_cards").fetchone()[0] == 0

        with monkeypatch.context() as patch:
            patch.setattr(catalog_type, "_save_registry", save_and_hold_reader)
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                ingest.commit(root, {})

    assert lock.read_bytes() == original_lock
    assert receipt.read_bytes() == previous_receipt
    assert panel.run(root, "overview", {})[0] == previous
    assert candidate.is_file() and (root / ".build/task.json").is_file()
    with catalog_type(root, refresh=False) as catalog:
        assert [row["source_id"] for row in ingest.observe(root, catalog)] == [task["source"]["source_id"]]

    result, phase = ingest.commit(root, {})
    assert phase == "completed" and result["source_complete"] is True
    assert json.loads(receipt.read_bytes()) == result
    new, _ = panel.run(root, "overview", {})
    assert new["card_count"] == 1 and new["view_revision"] != previous["view_revision"]



def test_failed_receipt_replacement_preserves_committed_result_and_previous_receipt(tmp_path, monkeypatch):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    ingest = module("ingest")
    panel = module("panel")
    catalog_type = module("catalog").Catalog
    module("library").patrol(root, "reindex", {})
    candidate = draft(root, "pending", [task["source"]["doc_id"]])
    receipt = root / "artifacts/ingest/latest.json"
    receipt.parent.mkdir()
    previous_receipt = b'{"source_id":"previous","source_complete":true}\n'
    receipt.write_bytes(previous_receipt)
    replace = os.replace

    def fail_receipt_replacement(source, destination):
        if destination == receipt:
            # A complete receipt has been staged, but the final replacement fails.
            assert json.loads(source.read_bytes())["source_complete"] is True
            assert panel.run(root, "overview", {})[0]["card_count"] == 1
            raise PermissionError("Synthetic receipt replacement failure")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", fail_receipt_replacement)
        result, phase = ingest.commit(root, {})

    assert phase == "completed" and result["source_complete"] is True
    assert result["receipt_warning"] == {
        "code": "INGEST_RECEIPT_WRITE_FAILED",
        "message": "Synthetic receipt replacement failure",
        "path": "artifacts/ingest/latest.json",
    }
    assert receipt.read_bytes() == previous_receipt
    assert list(receipt.parent.iterdir()) == [receipt]
    assert not candidate.exists() and not (root / ".build/task.json").exists()
    with catalog_type(root, refresh=False) as catalog:
        assert catalog.get_file(task["source"]["doc_id"])["processed_hash"] == task["source"]["hash"]
    assert ingest.scan(root, {}) == ({"pending": 0}, "unchanged")


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
    write_plan(root, [("stable", "knowledge/a-new.md"), ("extra", "knowledge/z-extra.md")])
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
    deletes = []
    if decision == "create":
        draft(root, "new", [primary["id"], other["id"]])
        expected = {"new"}
    elif decision == "update":
        draft(root, "old", [primary["id"], other["id"]], body="Updated waiting knowledge.")
        expected = {"old"}
    elif decision == "merge":
        draft(root, "old", [primary["id"], other["id"]], body="Merged waiting knowledge; retain the principal card identity.")
        deletes = ["knowledge/duplicate.md"]
        expected = {"old"}
    elif decision == "split":
        draft(root, "waiting", [primary["id"]], body="Waiting knowledge.")
        draft(root, "diagnosis", [other["id"]], body="Independent diagnosis knowledge.")
        deletes = ["knowledge/old.md"]
        expected = {"waiting", "diagnosis"}
    else:
        draft(root, "replacement", [primary["id"], other["id"]], body="Replacement waiting knowledge.")
        draft(root, "old", [primary["id"], other["id"]],
              body="Deprecated: the new design replaces this rule. Use [replacement](replacement.md).",
              lifecycle="deprecated")
        expected = {"old", "replacement"}
    if deletes:
        (root / ".build/changes.json").write_text(json.dumps({"delete": deletes}))
    write_plan(root, [(identity, f"knowledge/{identity}.md") for identity in sorted(expected)],
               body=f"{decision}: preserve valid knowledge and all required references.")
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
    retain_fixture_history(root)
    original.unlink()
    task, phase = module("ingest").maintenance_prepare(root, {"source": source["id"]})
    assert phase == "prepared", task
    assert task["source"]["change"] == "deleted"
    assert "original_ref" not in task["source"]
    assert [card["id"] for card in task["affected_cards"]] == ["historical"]
    assert (root / "knowledge/historical.md").is_file()
    write_plan(root, [])
    assert module("ingest").maintenance_check(root, {})[1] == "passed"
    result, status = module("ingest").maintenance_commit(root, {"reason": "Keep the historical card; source retirement is reviewed."})
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
    (root / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "synthetic",
        "code_root": "../../code", "modules": [{"path": "wifi", "chips": ["chip12"], "sides": ["host"]}],
    }))
    original = put_doc(root)
    with module("catalog").Catalog(root) as catalog:
        doc = catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
        source = catalog.register("code", "code/wifi/wait.c", source_id="code-wait")
        catalog.mark_processed(doc["id"], digest(original.read_bytes()))
        catalog.mark_processed(source["id"], digest(code.read_bytes()))
        catalog.mark_reference_reviewed(source["id"], digest(code.read_bytes()), True)
    formal(root, "waiting", [doc["id"]], code_refs=[{
        "code_id": source["id"], "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    return root, code, doc["id"], source["id"]


@pytest.mark.parametrize("selector", [{"symbol": "wait_reply"},
                                      {"selector": {"kind": "function", "name": "wait_reply"}}],
                         ids=["symbol", "selector-without-symbol"])
def test_code_patrol_detects_inserted_lines_and_check_requires_updated_location(tmp_path, selector):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_text("// Added header\n// Added explanation\nint wait_reply(void) {\n    return 5;\n}\n")
    planned, status = module("library").patrol(root, "plan", {})
    assert status == "needs_maintenance", planned
    assert planned["next_file"]["source_id"] == code_id
    task = scan(root, code_id)
    assert task["source"]["kind"] == "code"
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 1, "line_end": 3, **selector}])
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 3, "line_end": 5, **selector}])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked


def test_function_body_change_is_patrol_work_and_not_a_fixed_check_semantic_verdict(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    with module("catalog").Catalog(root) as catalog:
        old_doc_hash = catalog.get_file(doc_id)["processed_hash"]
    code.write_text("int wait_reply(void) {\n    return 8;\n}\n")
    planned, status = module("library").patrol(root, "plan", {})
    assert status == "needs_maintenance", planned
    assert planned["next_file"]["source_id"] == code_id
    task = scan(root, code_id)
    draft(root, "waiting", [doc_id], body="The design requires a wait; implementation changed and needs reviewer judgement.",
          code_refs=[{"code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    assert checked["review_required"] is True
    result, status = module("ingest").commit(root, {})
    assert status == "completed", result
    with module("catalog").Catalog(root) as catalog:
        assert catalog.get_file(code_id)["reference_review"]["source_sha256"] == task["source"]["hash"]
        assert catalog.get_file(doc_id)["processed_hash"] == old_doc_hash


def test_deleted_function_is_reported_by_fixed_check(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_text("int unrelated(void) {\n    return 0;\n}\n")
    scan(root, code_id)
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert any(item["code"] == "CODE_SYMBOL_MISSING" for item in checked["findings"])


def test_typed_macro_enum_and_alias_refs_cover_the_plan_without_function_symbols(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_text("#define RETRY_CLASS 3\n"
                    "typedef enum { RETRY_LOW, RETRY_HIGH } retry_class_t;\n"
                    "enum retry_state { RETRY_READY };\n"
                    "int wait_reply(void) { return RETRY_CLASS; }\n", encoding="utf-8")
    task, phase = module("ingest").scan(root, {"source": doc_id, "reprocess": True})
    assert phase == "prepared", task
    names = ["RETRY_CLASS", "retry_class_t", "retry_state", "wait_reply"]
    plan = {"cards": [{"id": "waiting", "path": "knowledge/waiting.md",
                       "required_code_refs": [{"path": "wifi/wait.c", "symbol": name} for name in names]}]}
    (root / ".build/plan.md").write_text("---\n" + yaml.safe_dump(plan) + "---\nKeep all four references.\n",
                                      encoding="utf-8")
    references = [{"code_id": code_id, "line_start": line, "line_end": line, "symbol": name}
                  for line, name in enumerate(names, 1)]
    draft(root, "waiting", [doc_id], code_refs=references)
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    missing = [item for item in checked["findings"] if item["code"] == "CODE_SYMBOL_MISSING"]
    assert len(missing) == 3
    for name in names[:3]:
        assert any(f"function {name}: symbol lookup missing" in item["message"] for item in missing)
    assert sum(item["code"] == "PLANNED_CODE_REF_MISSING" for item in checked["findings"]) == 3
    for reference, kind in zip(references, ("macro", "type_alias", "enum")):
        reference["selector"] = {"kind": kind, "name": reference.pop("symbol")}
    draft(root, "waiting", [doc_id], code_refs=references)
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    assert checked["review_required"] is True


def test_ingest_check_retains_why_source_parsing_is_unavailable(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    code.write_bytes(b"int wait_reply(void) {\n    return 5;\0\n}\n")
    module("ingest").scan(root, {"source": doc_id, "reprocess": True})
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": code_id, "line_start": 1, "line_end": 3, "symbol": "wait_reply"}])
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    finding = next(item for item in checked["findings"] if item["code"] == "CODE_SYMBOL_UNAVAILABLE")
    assert "NUL bytes prevent reliable source parsing" in finding["message"]
    assert not (root / ".build/document-review-check.json").exists()


def test_ingest_check_retains_ambiguous_function_lookup_reason(tmp_path):
    root, code, doc_id, _ = code_project(tmp_path)
    overloaded = code.with_suffix(".cpp")
    overloaded.write_text("int wait_reply(int value) { return value; }\n"
                          "int wait_reply(float value) { return 0; }\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        source = catalog.register("code", "code/wifi/wait.cpp")
    module("ingest").scan(root, {"source": doc_id, "reprocess": True})
    draft(root, "waiting", [doc_id], code_refs=[{
        "code_id": source["id"], "line_start": 1, "line_end": 1, "symbol": "wait_reply"}])
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    finding = next(item for item in checked["findings"] if item["code"] == "CODE_SYMBOL_AMBIGUOUS")
    assert "function wait_reply: symbol lookup ambiguous" in finding["message"]


def test_code_review_cannot_finish_against_an_outdated_source(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    ingest = module("ingest")
    catalog_type = module("catalog").Catalog
    with catalog_type(root) as catalog:
        baseline = catalog.get_file(code_id)["processed_hash"]
    code.write_text("int wait_reply(void) {\n    return 6;\n}\n", encoding="utf-8")
    task, phase = ingest.scan(root, {"source": code_id, "code_review": True})
    assert phase == "prepared" and task["source"]["change"] == "modified"
    write_plan(root, [])
    assert ingest.check(root, {})[1] == "passed"

    code.write_text("int wait_reply(void) {\n    return 8;\n}\n", encoding="utf-8")
    with pytest.raises(ingest.ContractError, match="SOURCE_CHANGED"):
        ingest.commit(root, {"reason": "No change to the design requirement."})
    with catalog_type(root) as catalog:
        assert catalog.get_file(code_id)["processed_hash"] == baseline
        assert catalog.get_card("waiting")["doc_ref"][0]["doc_id"] == doc_id
    refreshed, phase = ingest.scan(root, {"source": code_id, "code_review": True})
    assert phase == "prepared" and refreshed["source"]["hash"] != task["source"]["hash"]


def test_code_review_detects_a_deleted_source_and_its_return(tmp_path):
    root, code, _, code_id = code_project(tmp_path)
    ingest, library = module("ingest"), module("library")
    original = code.read_bytes()
    retain_fixture_history(root.parents[1])
    code.unlink()
    plan, phase = library.patrol(root, "plan", {})
    assert phase == "needs_maintenance" and plan["next_file"]["change"] == "deleted"
    task, phase = ingest.scan(root, {"source": code_id, "code_review": True})
    assert phase == "prepared" and task["source"]["exists"] is False
    assert [card["id"] for card in task["affected_cards"]] == ["waiting"]
    write_plan(root, [])
    assert ingest.check(root, {})[1] == "passed"
    assert ingest.commit(root, {"reason": "Retain the documented requirement and past source reference."})[1] == "completed"
    assert library.patrol(root, "plan", {})[0]["pending"] == 0

    code.write_bytes(original)
    plan, phase = library.patrol(root, "plan", {})
    assert phase == "needs_maintenance" and plan["next_file"]["change"] == "modified"


def test_code_review_rechecks_card_membership_before_publishing(tmp_path):
    root, code, doc_id, code_id = code_project(tmp_path)
    ingest = module("ingest")
    code.write_text("int wait_reply(void) {\n    return 6;\n}\n", encoding="utf-8")
    assert ingest.scan(root, {"source": code_id, "code_review": True})[1] == "prepared"
    draft(root, "waiting", [doc_id], body="Proposed change from code review.")
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    assert ingest.check(root, {})[1] == "passed"

    formal(root, "waiting", [doc_id], body="Updated separately with no code reference.")
    with pytest.raises(ingest.ContractError, match="MAINTENANCE_SCOPE"):
        ingest.commit(root, {})
    assert "Updated separately" in (root / "knowledge/waiting.md").read_text(encoding="utf-8")


def test_required_code_ref_distinguishes_scoped_symbols_in_one_file(tmp_path):
    root, existing_code, doc_id, _ = code_project(tmp_path)
    code = existing_code.with_name("dispatch.cpp")
    code.write_text("namespace archived {\nint send() { return -1; }\n}\n"
                    "namespace current {\nint send() { return 1; }\n}\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        source = catalog.register("code", "code/wifi/dispatch.cpp")
    task, phase = module("ingest").scan(root, {"source": doc_id, "reprocess": True})
    assert phase == "prepared", task

    requirement = {"path": "wifi/dispatch.cpp", "symbol": "current::send"}
    plan = {"cards": [{"id": "waiting", "path": "knowledge/waiting.md", "required_code_refs": [requirement]}]}
    (root / ".build/plan.md").write_text(
        "---\n" + yaml.safe_dump(plan) + "---\nUse the current dispatch implementation.\n", encoding="utf-8")

    archived = {"code_id": source["id"], "line_start": 2, "line_end": 2,
                "selector": {"kind": "function", "name": "send", "scope": ["archived"]}}
    draft(root, "waiting", [doc_id], code_refs=[archived])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert [item["code"] for item in checked["findings"]] == ["PLANNED_CODE_REF_MISSING"]

    current = {**archived, "line_start": 5, "line_end": 5,
               "selector": {**archived["selector"], "scope": ["current"]}}
    draft(root, "waiting", [doc_id], code_refs=[current])
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked


def test_p4_rejects_line_ranges_outside_a_document(tmp_path):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    data = card_bytes("waiting", [task["source"]["doc_id"]]).replace(b"line_end: 3", b"line_end: 999")
    (root / ".build/cards/waiting.md").write_bytes(data)
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert any(item["code"] == "SOURCE_RANGE_INVALID" for item in checked["findings"])


@pytest.mark.parametrize("objects", ["artifacts/evidence/objects", "logs/evidence/objects"])
def test_bound_git_citation_uses_the_same_retained_version_for_review_and_preview(tmp_path, objects):
    root = library_root(tmp_path)
    source_path = "docs-raw/specs/design.md"
    put_doc(root, "specs/design.md", "# Latest version\n")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", source_path, source_id="doc-design")
    old_bytes = b"# Design\n\nAn older requirement.\n"
    old_digest = digest(old_bytes)
    retained = root / objects / f"{old_digest}.bin"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(old_bytes)
    registry_path = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(registry_path.read_bytes())
    registry["snapshots"].append({
        "snapshot_id": "snap-previous", "source_id": "doc-design", "sha256": old_digest,
        "bytes": len(old_bytes), "card_references": [],
        "recovery": {"method": "git", "commit": "0" * 40, "path": source_path},
    })
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    formal(root, "previous", [], doc_ref=[{
        "doc_id": "doc-design", "snapshot_id": "snap-previous", "line_start": 1, "line_end": 3}])
    request = {"source_id": "doc-design", "snapshot_id": "snap-previous", "hash": old_digest}
    checked, status = module("ingest").check(root, {"formal": True})
    assert status == "passed", checked
    resolved, status = module("library").sources(root, "resolve", request)
    assert status == "resolved", resolved
    assert (root / resolved["original_ref"]).read_bytes() == old_bytes

    retained.write_bytes(b"Invalid evidence".ljust(len(old_bytes)))
    checked, status = module("ingest").check(root, {"formal": True})
    assert status == "failed" and checked["findings"][0]["code"] == "EVIDENCE_OBJECT_CHANGED", checked
    with pytest.raises(module("validation").ContractError) as failure:
        module("library").sources(root, "resolve", request)
    assert failure.value.code == "EVIDENCE_OBJECT_CHANGED"


@pytest.mark.parametrize("extra", [{"aliases": ["old_alias"]}, {"summary": "Old summary"},
                                    {"scope": {"applicability": "unknown", "contexts": []}}])
def test_p4_rejects_legacy_fields_in_new_candidate_but_formal_copy_remains_readable(tmp_path, extra):
    root = library_root(tmp_path)
    put_doc(root)
    task = scan(root)
    identity = task["source"]["doc_id"]
    old = formal(root, "old", [identity], **extra)
    before = old.read_bytes()
    checked, status = module("ingest").check(root, {"formal": True})
    assert status == "passed", checked
    draft(root, "old", [identity], **extra)
    write_plan(root, [("old", "knowledge/old.md")])
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert checked["findings"]
    assert old.read_bytes() == before


def test_typo_update_of_deprecated_card_preserves_explicit_lifecycle(tmp_path):
    root = library_root(tmp_path)
    put_doc(root)
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
    formal(root, "old", ["doc-design"], lifecycle="deprecated", body="Historical waiting requirment.")
    scan(root)
    draft(root, "old", ["doc-design"], lifecycle="deprecated", body="Historical waiting requirement; retired with no replacement.")
    write_plan(root, [("old", "knowledge/old.md")], body="Fix spelling; keep the whole card retired.")
    checked, phase = module("ingest").check(root, {})
    assert phase == "passed", checked
    result, phase = module("ingest").commit(root, {})
    assert phase == "completed", result
    read, phase = module("library").query(root, {"card_id": "old"}, read=True)
    assert phase == "read" and read["lifecycle"] == "deprecated"
    searched, _ = module("library").query(root, {"query": "requirement"})
    assert searched["matches"] == []
