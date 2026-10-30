"""Public query/source/patrol regression tests with real synthetic libraries."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def root_at(path):
    for directory in ("docs-raw", "knowledge", "governance", "artifacts"):
        (path / directory).mkdir(parents=True, exist_ok=True)
    return path


def document(root, name="design.md", text="# Design\n\nA valid requirement.\n"):
    path = root / "docs-raw" / name
    path.write_text(text, encoding="utf-8")
    return path


def card(root, identity, source_id, text, *, stage=False, **extra):
    metadata = {"id": identity, "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 3,
                                            "evidence_ref": "doc-proof"}], "code_ref": [], **extra}
    body = f"# {identity}\n\n<a id=\"answer\"></a>\n{text}\n"
    data = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n" + body).encode()
    target = root / (".build/cards" if stage else "knowledge") / f"{identity}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def register(root, name="design.md", identity="doc-design"):
    result, status = module("library").sources(root, "register", {
        "kind": "raw", "path": "docs-raw/" + name, "source_id": identity})
    assert status == "registered", result
    return result["source"]


def query(root, text, **request):
    data, status = module("library").query(root, {"query": text, "purpose": "guidance", **request})
    assert status == "searched", data
    return data


def git(repository, *arguments):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update(GIT_AUTHOR_NAME="Synthetic test", GIT_COMMITTER_NAME="Synthetic test",
                       GIT_AUTHOR_EMAIL="synthetic@example.invalid", GIT_COMMITTER_EMAIL="synthetic@example.invalid")
    result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", "-C", str(repository),
                             *arguments], capture_output=True, env=environment, check=True)
    return result.stdout.decode("utf-8").strip()


def test_source_registration_lists_both_reference_directions(tmp_path):
    root = root_at(tmp_path / "library")
    document(root)
    source = register(root)
    card(root, "waiting", source["id"], "rx_timeout causes bounded retries.")
    by_file, status = module("library").sources(root, "list", {"doc_id": source["id"]})
    assert status == "listed"
    assert by_file["source"]["path"] == "docs-raw/design.md"
    assert by_file["cards"] == [{"id": "waiting", "path": "knowledge/waiting.md", "title": "waiting"}]
    by_card, _ = module("library").sources(root, "list", {"card_id": "waiting"})
    assert [item["id"] for item in by_card["files"]] == [source["id"]]
    used, _ = module("library").sources(root, "list", {"kind": "raw", "referenced": True})
    assert [item["id"] for item in used["files"]] == [source["id"]]


def test_search_uses_exact_identifier_tokens_and_requires_all_query_terms(tmp_path):
    root = root_at(tmp_path / "library")
    document(root)
    source = register(root)
    card(root, "exact", source["id"], "rx_timeout causes bounded retries.", tags=["wifi"])
    card(root, "plural", source["id"], "rx_timeouts causes bounded retries.", tags=["wifi"])
    card(root, "similar", source["id"], "timer expiry causes bounded retries.", tags=["wifi"])
    assert [item["card_id"] for item in query(root, "rx_timeout")["matches"]] == ["exact"]
    assert [item["card_id"] for item in query(root, "RX_TIMEOUT retries", tags=["wifi"])["matches"]] == ["exact"]
    assert query(root, "rx_timeout transmit")["matches"] == []
    assert query(root, "rx_timeout", tags=["bluetooth"])["matches"] == []


def test_query_purposes_preserve_claim_scope_and_read_reports_eligible_claims(tmp_path):
    root = root_at(tmp_path / "library")
    document(root)
    source = register(root)
    scope = {"applicability": "constrained", "contexts": [
        {"context_id": "host", "chip": "chip12", "side": "host", "features_all": ["retry"]}]}
    def claims(kind):
        return [{"id": "answer", "text_ref": "#answer", "usage": "current", "evidence_kind": kind,
                 "source_refs": ["doc-proof"], "context_ids": ["host"], "verification_requirements": []}]
    card(root, "guidance", source["id"], "rx_timeout background.")
    card(root, "design", source["id"], "rx_timeout design.", scope=scope, claims=claims("design"))
    card(root, "implementation", source["id"], "rx_timeout implementation.", scope=scope, claims=claims("implementation"))
    card(root, "old", source["id"], "rx_timeout prior implementation.", scope=scope, claims=claims("implementation"), lifecycle="deprecated")
    context = {"chip": "chip12", "side": "host", "features": ["retry"]}
    current = query(root, "rx_timeout", purpose="current", context=context)
    assert {item["card_id"] for item in current["matches"]} == {"design", "implementation"}
    actual = query(root, "rx_timeout", purpose="implementation", context=context)
    assert [item["card_id"] for item in actual["matches"]] == ["implementation"]
    assert query(root, "rx_timeout", purpose="current", context={"chip": "chip12", "side": "host"})["matches"] == []
    history = query(root, "rx_timeout", purpose="historical", context=context)
    assert {item["card_id"] for item in history["matches"]} == {"guidance", "design", "implementation", "old"}
    read, status = module("library").query(root, {"card_id": "implementation", "purpose": "implementation", "context": context}, read=True)
    assert status == "read"
    assert read["eligible_claim_ids"] == ["answer"]
    assert [item["id"] for item in read["sources"]] == [source["id"]]


def test_query_indexes_formal_cards_only_and_rebuilds_after_database_removal(tmp_path):
    root = root_at(tmp_path / "library")
    document(root)
    source = register(root)
    card(root, "status", source["id"], "oldtoken describes the prior rule.")
    task, status = module("ingest").scan(root, {})
    assert status == "prepared"
    card(root, "status", source["id"], "newtoken describes the revised rule.", stage=True)
    assert query(root, "newtoken")["matches"] == []
    assert [item["card_id"] for item in query(root, "oldtoken")["matches"]] == ["status"]
    _, status = module("ingest").commit(root, {})
    assert status == "completed"
    assert query(root, "oldtoken")["matches"] == []
    assert [item["card_id"] for item in query(root, "newtoken")["matches"]] == ["status"]
    (root / "artifacts/knowledge.sqlite").unlink()
    assert [item["card_id"] for item in query(root, "newtoken")["matches"]] == ["status"]
    listed, _ = module("library").sources(root, "list", {"source_id": source["id"]})
    assert listed["source"]["processed_hash"] == task["source"]["hash"]


@pytest.mark.parametrize("deleted", [False, True])
def test_source_resolve_recovers_processed_git_version_without_modifying_current_source(tmp_path, deleted):
    project = tmp_path / "repository"
    root = root_at(project / "himate/library")
    original = document(root, text="# Design\n\nOriginal requirement.\n")
    old_bytes = original.read_bytes()
    git(project, "init", "--quiet")
    relative = original.relative_to(project).as_posix()
    git(project, "add", "--", relative)
    git(project, "commit", "--quiet", "-m", "Original synthetic document")
    old_commit = git(project, "rev-parse", "HEAD")
    source = register(root)
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed(source["id"], hashlib.sha256(old_bytes).hexdigest(), source_commit=old_commit)
    original.write_text("# Design\n\nNewer committed requirement.\n", encoding="utf-8")
    git(project, "add", "--", relative)
    git(project, "commit", "--quiet", "-m", "Change synthetic document")
    if deleted:
        original.unlink()
        current = None
    else:
        original.write_text("# Design\n\nUncommitted local requirement.\n", encoding="utf-8")
        current = original.read_bytes()
    resolved, status = module("library").sources(root, "resolve", {"source_id": source["id"]})
    assert status == "resolved"
    assert resolved["commit"] == old_commit
    assert (root / resolved["original_ref"]).read_bytes() == old_bytes
    assert (original.read_bytes() if original.exists() else None) == current


def test_source_resolve_reports_missing_uncommitted_history(tmp_path):
    project = tmp_path / "repository"
    root = root_at(project / "himate/library")
    original = document(root)
    git(project, "init", "--quiet")
    git(project, "commit", "--allow-empty", "--quiet", "-m", "Empty synthetic repository")
    source = register(root)
    with module("catalog").Catalog(root) as catalog:
        catalog.mark_processed(source["id"], hashlib.sha256(original.read_bytes()).hexdigest())
    original.write_text("# Design\n\nReplaced before its first commit.\n")
    with pytest.raises(ValueError, match="OLD_SOURCE_UNAVAILABLE"):
        module("library").sources(root, "resolve", {"source_id": source["id"]})


def test_dbox_configured_directory_is_registered_and_scanned_by_logical_path(tmp_path):
    root = root_at(tmp_path / "library")
    external = tmp_path / "external"
    external.mkdir()
    original = external / "design.md"
    original.write_text("# External\n\nAn externally mapped requirement.\n")
    result, status = module("library").sources(root, "configure", {"path": str(external)})
    assert status == "configured", result
    registered, status = module("library").sources(root, "register", {
        "kind": "raw", "path": "docs-raw/sources/dbox/design.md", "source_id": "external-design"})
    assert status == "registered", registered
    task, status = module("ingest").scan(root, {})
    assert status == "prepared", task
    assert task["source"]["doc_id"] == "external-design"
    assert (root / task["source"]["original_ref"]).read_bytes() == original.read_bytes()
    assert not (root / "docs-raw/sources/dbox/design.md").exists()


def test_serial_patrol_drains_multiple_documents_and_rebuilds_derived_index(tmp_path):
    root = root_at(tmp_path / "library")
    document(root, "a.md")
    document(root, "b.md")
    _, status = module("library").patrol(root, "sync", {})
    assert status == "synced"
    processed = []
    for expected in ("docs-raw/a.md", "docs-raw/b.md"):
        planned, status = module("library").patrol(root, "plan", {})
        assert status == "needs_ingest", planned
        assert planned["next_file"]["path"] == expected
        task, status = module("ingest").scan(root, {"source": planned["next_file"]["source_id"]})
        assert status == "prepared", task
        _, status = module("ingest").commit(root, {"reason": "Fully reviewed; no independent knowledge to add."})
        assert status == "completed"
        processed.append(task["source"]["doc_id"])
    planned, status = module("library").patrol(root, "plan", {})
    if status == "needs_reindex":
        _, status = module("library").patrol(root, "reindex", {})
        assert status == "reindexed"
        planned, status = module("library").patrol(root, "plan", {})
    assert status == "unchanged", planned
    result, status = module("library").patrol(root, "complete", {})
    assert status == "completed"
    assert result["remaining"] == 0
    assert len(set(processed)) == 2


@pytest.mark.parametrize("after_scan", ["# Changed\n", "# Changed\n\nA different requirement.\n"])
def test_p4_checks_the_p1_document_copy_when_the_external_file_changes(tmp_path, after_scan):
    root = root_at(tmp_path / "library")
    original = document(root)
    task, status = module("ingest").scan(root, {})
    assert status == "prepared"
    card(root, "waiting", task["source"]["doc_id"], "A valid requirement.", stage=True)
    original.write_text(after_scan)
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked


def test_p4_cannot_accept_a_section_added_only_after_p1(tmp_path):
    root = root_at(tmp_path / "library")
    original = document(root)
    task, _ = module("ingest").scan(root, {})
    target = card(root, "waiting", task["source"]["doc_id"], "An unsupported later requirement.", stage=True)
    metadata = {"id": "waiting", "doc_ref": [{"doc_id": task["source"]["doc_id"], "section": "LaterSection"}], "code_ref": []}
    target.write_text("---\n" + yaml.safe_dump(metadata) + "---\n# Waiting\n\nLater requirement.\n")
    original.write_text("# Design\n\nLaterSection now exists only in the outside file.\n")
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked
    assert any(item["code"] == "SOURCE_SECTION_MISSING" for item in checked["findings"])


def test_new_reference_header_cannot_hide_another_claim_source(tmp_path):
    root = root_at(tmp_path / "library")
    document(root)
    document(root, "other.md", "# Other\n\nA different requirement.\n")
    main = register(root)
    other = register(root, "other.md", "doc-other")
    _, status = module("ingest").scan(root, {"source": main["id"]})
    assert status == "prepared"
    legacy_sources = [{"evidence_ref": "legacy-proof", "source_id": other["id"],
                       "snapshot_id": "old-other", "locator": {"kind": "lines", "start": 1, "end": 3}}]
    claims = [{"id": "answer", "text_ref": "#answer", "usage": "guidance", "evidence_kind": "design",
               "source_refs": ["legacy-proof"], "context_ids": [], "verification_requirements": []}]
    card(root, "waiting", main["id"], "A claim whose declared evidence is the other document.",
         stage=True, sources=legacy_sources, claims=claims)
    checked, status = module("ingest").check(root, {})
    assert status == "failed", checked


@pytest.mark.parametrize("encoding, extractor", [
    ("utf-8", "code-utf8:1"), ("gb18030", "code-gb18030:1"),
])
def test_legacy_struct_reference_retains_its_symbol_kind_in_public_check(tmp_path, encoding, extractor):
    project = tmp_path / "project"
    root = root_at(project / "himate/library")
    document(root)
    code = project / "code/wifi/packet.c"
    code.parent.mkdir(parents=True)
    code_bytes = "struct packet {\n    int size; /* 大小字段 */\n};\n".encode(encoding)
    code.write_bytes(code_bytes)
    (project / "config.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "workspace_id": "synthetic", "knowledge_roots": {"wifi": "himate/library"},
        "code_root": "code", "modules": [{"path": "wifi"}],
    }))
    source = register(root)
    registered, status = module("library").sources(root, "register", {
        "kind": "code", "path": "code/wifi/packet.c", "source_id": "packet-code"})
    assert status == "registered", registered
    evidence = root / "logs/evidence/old-code.bin"
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(code_bytes)
    registry_path = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(registry_path.read_bytes())
    registry["snapshots"].append({
        "source_id": "packet-code", "snapshot_id": "old-code",
        "sha256": hashlib.sha256(code_bytes).hexdigest(), "bytes": len(code_bytes),
        "recovery": {"method": "evidence_object", "path": "logs/evidence/old-code.bin"},
        "extraction": {"extractor": extractor},
    })
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    metadata = {
        "schema_version": "2.0", "id": "packet", "profile": "entity", "title": "Packet",
        "summary": "A packet record", "lifecycle": "stable", "owner": "synthetic",
        "review_mode": "code_gate", "scope": {"applicability": "unknown", "contexts": []},
        "aliases": [], "relations": [], "sources": [
            {"evidence_ref": "doc", "source_id": source["id"], "snapshot_id": "old-doc", "locator": {"kind": "lines", "start": 1, "end": 3}},
            {"evidence_ref": "code", "source_id": "packet-code", "snapshot_id": "old-code", "locator": {"kind": "lines", "start": 1, "end": 3},
             "code_ref": {"kind": "struct", "name": "packet"}},
        ], "claims": [{"id": "answer", "text_ref": "#answer", "usage": "guidance", "evidence_kind": "implementation",
                        "source_refs": ["doc", "code"], "context_ids": [], "verification_requirements": []}],
    }
    old_bytes = ("---\n" + yaml.safe_dump(metadata)
                 + "---\n# Packet\n\n<a id=\"answer\"></a>\nThe packet has a size field.\n").encode("utf-8")
    formal = root / "knowledge/packet.md"
    formal.write_bytes(old_bytes)
    _, status = module("ingest").scan(root, {"source": source["id"]})
    assert status == "prepared"
    target = root / ".build/cards/packet.md"
    target.write_bytes(old_bytes)
    checked, status = module("ingest").check(root, {})
    assert status == "passed", checked
    assert formal.read_bytes() == old_bytes
    assert target.read_bytes() == old_bytes
    assert code.read_bytes() == code_bytes
