"""Queries keep a complete catalog while short indexing commands run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import threading

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def library_at(root):
    for directory in ("docs-raw", "knowledge", "governance"):
        (root / directory).mkdir(parents=True)
    (root / "docs-raw/design.md").write_text("# Design\n\nA bounded requirement.\n", encoding="utf-8")
    source, _ = module("library").sources(root, "register", {
        "kind": "raw", "path": "docs-raw/design.md", "source_id": "doc-design"})
    return source["source"]["id"]


def write_card(root, source, text, *, stage=False):
    target = root / (".build/cards" if stage else "knowledge") / "rule.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\n" + yaml.safe_dump({
        "id": "rule", "doc_ref": [{"doc_id": source, "section": "Design"}], "code_ref": [],
    }) + "---\n# Rule\n\n" + text + "\n", encoding="utf-8")


def search(root, text):
    data, phase = module("library").query(root, {"query": text, "purpose": "guidance"})
    assert phase == "searched"
    return data


@pytest.mark.parametrize("read", [False, True], ids=["search", "read"])
@pytest.mark.parametrize("operation", ["rebuild", "commit"])
def test_query_started_before_writer_keeps_a_complete_catalog(tmp_path, monkeypatch, read, operation):
    root = tmp_path / "library"
    source = library_at(root)
    write_card(root, source, "oldtoken describes the reviewed rule.")
    ingest, library, catalog_type = module("ingest"), module("library"), module("catalog").Catalog
    search(root, "oldtoken")
    if operation == "commit":
        task, phase = ingest.scan(root, {})
        assert phase == "prepared", task
        write_card(root, source, "newtoken describes the updated rule.", stage=True)

    allow_writer, writer_started = threading.Event(), threading.Event()
    cleared, reader_finished = threading.Event(), threading.Event()
    failures = []
    original_rebuild = catalog_type.rebuild

    def paused_rebuild(catalog):
        original_sync = catalog._sync_resources

        def after_clear():
            cleared.set()
            assert reader_finished.wait(5), "Reader did not finish"
            original_sync()

        catalog._sync_resources = after_clear
        try:
            return original_rebuild(catalog)
        finally:
            catalog._sync_resources = original_sync

    monkeypatch.setattr(catalog_type, "rebuild", paused_rebuild)

    def writer():
        try:
            assert allow_writer.wait(5)
            writer_started.set()
            if operation == "commit":
                result, phase = ingest.commit(root, {})
                assert phase == "completed", result
            else:
                with catalog_type(root) as catalog:
                    catalog.rebuild()
                    library.build_search(catalog)
        except BaseException as error:
            failures.append(error)

    def before_read(original, *args):
        allow_writer.set()
        assert writer_started.wait(5), "Writer did not start"
        # A serialized writer cannot reach its clear step until this command
        # finishes. The unfixed writer reaches it and exposes an empty catalog.
        cleared.wait(0.3)
        return original(*args)

    if read:
        original_get = catalog_type.get_card
        monkeypatch.setattr(catalog_type, "get_card", lambda *args: before_read(original_get, *args))
    else:
        original_stale = library.search_stale
        monkeypatch.setattr(library, "search_stale", lambda *args: before_read(original_stale, *args))
    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        if read:
            result, phase = library.query(root, {"card_id": "rule", "purpose": "guidance"}, read=True)
            assert phase == "read"
            assert "oldtoken" in result["body"]
        else:
            assert [item["card_id"] for item in search(root, "oldtoken")["matches"]] == ["rule"]
    finally:
        reader_finished.set()
        thread.join(6)
    assert not thread.is_alive(), "Writer remained blocked"
    assert not failures, failures


def test_query_leaves_ingest_workspace_unchanged_and_candidates_private(tmp_path):
    root = tmp_path / "library"
    source = library_at(root)
    write_card(root, source, "oldtoken describes the reviewed rule.")
    _, phase = module("ingest").scan(root, {})
    assert phase == "prepared"
    write_card(root, source, "newtoken is an unreviewed candidate.", stage=True)
    (root / ".build/plan.md").write_text("The current source controls this task.\n", encoding="utf-8")

    def snapshot():
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (root / ".build").rglob("*") if path.is_file()}

    before = snapshot()
    assert search(root, "newtoken")["matches"] == []
    assert [item["card_id"] for item in search(root, "oldtoken")["matches"]] == ["rule"]
    module("library").query(root, {"card_id": "rule", "purpose": "guidance"}, read=True)
    assert snapshot() == before


@pytest.mark.parametrize("read", [False, True], ids=["search", "read"])
def test_query_waits_for_commit_then_reads_completed_publication(tmp_path, monkeypatch, read):
    root = tmp_path / "library"
    source = library_at(root)
    write_card(root, source, "oldtoken describes the reviewed rule.")
    ingest, library = module("ingest"), module("library")
    task, _ = ingest.scan(root, {})
    write_card(root, source, "newtoken describes the updated rule.", stage=True)
    copied, finish_commit, reader_started, reader_finished = (threading.Event() for _ in range(4))
    outcomes, failures = {}, []
    original_write = ingest.atomic_write

    def pause_after_card(path, data):
        original_write(path, data)
        copied.set()
        assert finish_commit.wait(5), "Commit was not released"

    monkeypatch.setattr(ingest, "atomic_write", pause_after_card)

    def writer():
        try:
            outcomes["commit"] = ingest.commit(root, {})
        except BaseException as error:
            failures.append(error)

    def reader():
        try:
            reader_started.set()
            outcomes["query"] = (library.query(root, {"card_id": "rule", "purpose": "guidance"}, read=True)
                                 if read else library.query(root, {"query": "newtoken", "purpose": "guidance"}))
        except BaseException as error:
            failures.append(error)
        finally:
            reader_finished.set()

    writer_thread = threading.Thread(target=writer, daemon=True)
    reader_thread = threading.Thread(target=reader, daemon=True)
    writer_thread.start()
    try:
        assert copied.wait(5), "Commit did not copy its card"
        reader_thread.start()
        assert reader_started.wait(5)
        assert not reader_finished.wait(0.2), "Query exposed an incomplete publication"
    finally:
        finish_commit.set()
        writer_thread.join(6)
        if reader_thread.ident is not None:
            reader_thread.join(6)
    assert not writer_thread.is_alive() and not reader_thread.is_alive()
    assert not failures, failures
    result, phase = outcomes["query"]
    assert outcomes["commit"][1] == "completed"
    if read:
        assert phase == "read" and "newtoken" in result["body"]
        assert result["sources"][0]["processed_hash"] == task["source"]["hash"]
    else:
        assert phase == "searched" and [item["card_id"] for item in result["matches"]] == ["rule"]


def test_each_search_report_has_its_own_artifact(tmp_path):
    root = tmp_path / "library"
    source = library_at(root)
    write_card(root, source, "exacttoken describes a reviewed rule.")
    first = search(root, "exacttoken")
    second = search(root, "missingtoken")
    assert first["report_ref"] != second["report_ref"]
    for result in (first, second):
        reference = result["report_ref"]
        assert reference.startswith("artifacts/query/")
        assert json.loads((root / reference).read_text(encoding="utf-8")) == result
    assert not (root / "artifacts/query/latest.json").exists()
