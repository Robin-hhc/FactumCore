"""Public single-file entry points using an isolated synthetic knowledge root."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture
def knowledge(tmp_path):
    project = tmp_path / "project"
    root = project / "himate/knowledge-test"
    root.mkdir(parents=True)
    for directory in ("runtime", "governance"):
        shutil.copytree(SOURCE / directory, root / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv"))
    for name in ("knowledge.py", "knowledge.sh", "knowledge.cmd"):
        shutil.copyfile(SOURCE / name, root / name)
    (root / "governance/sources.lock.yaml").write_text(
        "schema_version: '2.0'\nresources: []\nsnapshots: []\n", encoding="utf-8",
    )
    (root / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: synthetic\n"
        "code_root: ../../main\nmodules: []\n",
        encoding="utf-8",
    )
    (root / "docs-raw/specs").mkdir(parents=True)
    (root / "knowledge").mkdir()
    return root


def invoke(root, *arguments, request=None):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    stdin = None if request is None else json.dumps(request)
    if stdin is not None:
        arguments = (*arguments, "--input", "-")
    result = subprocess.run(
        [sys.executable, "-B", str(root / "knowledge.py"), *arguments, "--json"],
        input=stdin,
        cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=60,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, json.loads(result.stdout)


def _panel(root, action, request=None):
    status, report = invoke(root, "panel", action, request=request)
    assert status == 0, report
    return report["data"]


def _panel_card(root, identity, references, body):
    directory = root / "knowledge/rules"
    directory.mkdir(exist_ok=True)
    target = directory / (identity + ".md")
    header = {"id": identity, "doc_ref": references, "code_ref": [], "tags": ["wifi"]}
    target.write_text("---\n" + yaml.safe_dump(header) + "---\n" + body, encoding="utf-8")
    return target


def test_panel_reads_published_cards_and_rejects_stale_revisions(knowledge):
    status, report = invoke(knowledge, "panel", "overview")
    assert status == 2 and report["diagnostics"][0]["code"] == "PANEL_VIEW_UNAVAILABLE"
    assert not (knowledge / "artifacts/knowledge.sqlite").exists()
    status, report = invoke(knowledge, "maintain", "reindex")
    assert status == 0 and _panel(knowledge, "overview")["card_count"] == 0, report

    raw = knowledge / "docs-raw/specs/original.md"
    raw.write_text("# Original\n", encoding="utf-8")
    status, report = invoke(knowledge, "source", "register",
                            request={"path": "docs-raw/specs/original.md", "source_id": "doc-a"})
    assert status == 0, report
    references = [{"doc_id": "doc-a", "line_start": 1, "line_end": 1}]
    card = _panel_card(knowledge, "a", references, "# First\n\nThe Alpha proof.\n")
    _panel_card(knowledge, "b", references, "# Second\n\nThe Alpha variant.\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0

    overview = _panel(knowledge, "overview")
    revision = overview["view_revision"]
    assert overview["card_count"] == 2 and overview["document_count"] == 1 and overview["code_count"] == 0
    assert overview["types"] == [{"type": "rule", "count": 2}]
    args = {"view_revision": revision, "limit": 1, "query": "alpha", "type": "rule", "tag": "wifi"}
    first = _panel(knowledge, "cards", args)
    assert [item["id"] for item in first["items"]] == ["a"] and first["next_cursor"]
    second = _panel(knowledge, "cards", {**args, "cursor": first["next_cursor"]})
    assert [item["id"] for item in second["items"]] == ["b"] and second["next_cursor"] is None
    search = {"query": "alpha", "tags": ["wifi"], "top_k": 1}
    legacy = invoke(knowledge, "search", request=search)[1]["data"]
    published = _panel(knowledge, "search", {**search, "view_revision": revision})
    assert published["matches"] == legacy["matches"] and published["truncated"] is True

    _panel_card(knowledge, "a", references, "# Changed\n\nA different fact.\n")
    assert invoke(knowledge, "read", "a")[1]["data"]["title"] == "Changed"
    status, report = invoke(knowledge, "read", request={"card_id": "a", "view_revision": revision})
    assert status == 0 and report["data"]["title"] == "First", report
    assert _panel(knowledge, "read", {"card_id": "a"})["view_revision"] == revision
    assert _panel(knowledge, "search", search) == published
    assert _panel(knowledge, "overview") == overview

    card.write_text("Unparseable card", encoding="utf-8")
    assert invoke(knowledge, "maintain", "reindex")[0] == 2
    assert _panel(knowledge, "overview") == overview
    _panel_card(knowledge, "a", references, "# Changed\n\nA different fact.\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0
    status, report = invoke(knowledge, "panel", "cards", request=args)
    assert status == 2 and report["diagnostics"][0]["code"] == "PANEL_REVISION_MISMATCH"
    status, report = invoke(knowledge, "panel", "read", request={"card_id": "a", "view_revision": revision})
    assert status == 2 and report["diagnostics"][0]["code"] == "PANEL_REVISION_MISMATCH"


def test_panel_graph_pages_high_degree_neighbors_and_filters_kinds(knowledge):
    resources = [{"source_id": f"doc-{index:03}", "kind": "raw",
                  "path": f"docs-raw/specs/item-{index:03}.md"} for index in range(80)]
    (knowledge / "governance/sources.lock.yaml").write_text(
        yaml.safe_dump({"schema_version": "2.0", "resources": resources, "snapshots": []}), encoding="utf-8")
    references = [{"doc_id": source["source_id"], "line_start": 1, "line_end": 1} for source in resources]
    references.append({"doc_id": "doc-000", "line_start": 2, "line_end": 2})
    _panel_card(knowledge, "hub", references, "# Hub\n\nMany references.\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0
    request = {"card_id": "hub", "limit": 50, "kinds": ["document"]}
    first = _panel(knowledge, "graph", request)
    second = _panel(knowledge, "graph", {**request, "cursor": first["next_cursor"],
                                        "view_revision": first["view_revision"]})
    assert (len(first["nodes"]), len(first["edges"]), len(second["nodes"]), len(second["edges"])) == (51, 50, 31, 30)
    assert not second["next_cursor"]
    assert [edge["target"] for edge in first["edges"] + second["edges"]] == [source["source_id"] for source in resources]
    for page in (first, second):
        ids = {node["id"] for node in page["nodes"]}
        assert all(edge["kind"] == "doc_ref" and edge["source"] in ids and edge["target"] in ids for edge in page["edges"])
    assert not _panel(knowledge, "graph", {**request, "kinds": ["code"]})["edges"]
    status, report = invoke(knowledge, "panel", "graph",
                            request={**request, "kinds": ["code"], "cursor": first["next_cursor"]})
    assert status == 2 and report["diagnostics"][0]["code"] == "PANEL_CURSOR_INVALID"


def test_panel_publishes_only_actual_markdown_card_links(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# Source\n", encoding="utf-8")
    assert invoke(knowledge, "source", "register",
                  request={"path": "docs-raw/specs/a.md", "source_id": "doc-a"})[0] == 0
    references = [{"doc_id": "doc-a", "line_start": 1, "line_end": 1}]
    _panel_card(knowledge, "a", references,
                "# A\n\n[Target](./b.md#detail), [Duplicate](b.md#启用-1) and [Via definition][target].\n\n"
                "![Image](b.md) [Missing anchor](b.md#missing) [Raw](../../docs-raw/specs/a.md)\n"
                "[External](https://example.test/b.md) [Navigation](README.md)\n\n"
                "\x60[Code](b.md)\x60\n\n[target]: b.md#%E4%B8%AD\n")
    _panel_card(knowledge, "b", references,
                "# B\n\n## Detail\n\n<a id=\"中\"></a>\n\n## 启用 \x60foo\x60\n\n## 启用 \x60bar\x60\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0
    read = _panel(knowledge, "read", {"card_id": "a"})
    assert read["card_links"] == [{"target": "./b.md#detail", "card_id": "b", "anchor": "detail"},
                                  {"target": "b.md#启用-1", "card_id": "b", "anchor": "启用-1"},
                                  {"target": "b.md#%E4%B8%AD", "card_id": "b", "anchor": "中"}]
    other = _panel(knowledge, "read", {"card_id": "b"})
    assert other["heading_anchors"] == [
        {"anchor": "b", "line": 1}, {"anchor": "detail", "line": 3},
        {"anchor": "启用", "line": 7}, {"anchor": "启用-1", "line": 9},
    ]
    expected = [{"source": "a", "target": "b", "kind": "card_link"}]
    for identity in ("a", "b"):
        graph = _panel(knowledge, "graph", {"card_id": identity, "kinds": ["card"], "limit": 1,
                                            "view_revision": read["view_revision"]})
        assert graph["edges"] == expected and graph["next_cursor"] is None


def test_checked_source_binding_survives_reindex_clone_and_recheck(knowledge, tmp_path):
    if not shutil.which("git"):
        pytest.skip("Git is required to exercise clean-checkout recovery")
    project = knowledge.parents[1]
    relative_root = knowledge.relative_to(project)
    raw = knowledge / "docs-raw/specs/a.md"
    older = b"# Original\nExact evidence from the first review.\n"
    newer = b"# Updated\nEvidence checked during the second review.\n"
    raw.write_bytes(older)

    def git(*args):
        return subprocess.run(["git", "-C", str(project), "-c", "user.name=Synthetic Test",
                               "-c", "user.email=test@example.invalid", *args],
                              capture_output=True, text=True, check=True, timeout=30)

    git("init", "-q")
    git("add", (knowledge / "config.yml").relative_to(project).as_posix(), raw.relative_to(project).as_posix())
    git("commit", "-qm", "Track original")
    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, scanned
    source_id = scanned["data"]["source"]["doc_id"]
    header = {"id": "fixed", "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 2}], "code_ref": []}
    markdown = ("---\n" + yaml.safe_dump(header) + "---\n# Fixed\n\nA checked citation.\n").encode()

    def check_and_publish():
        (knowledge / ".build/cards/fixed.md").write_bytes(markdown)
        (knowledge / ".build/plan.md").write_text(
            "---\ncards:\n- id: fixed\n  path: knowledge/fixed.md\n---\nReview the fixed reference.\n",
            encoding="utf-8")
        status, checked = invoke(knowledge, "ingest", "check")
        assert status == 0, checked
        status, published = invoke(knowledge, "ingest", "commit")
        assert status == 0, published

    raw.write_bytes(newer)
    check_and_publish()
    formal = knowledge / "knowledge/fixed.md"
    assert formal.read_bytes() == markdown
    original_ref = _panel(knowledge, "read", {"card_id": "fixed"})["doc_ref"][0]
    old_hash = hashlib.sha256(older).hexdigest()
    assert original_ref["source_version"] == "bound" and original_ref["source_sha256"] == old_hash
    registry = knowledge / "governance/sources.lock.yaml"
    git("add", raw.relative_to(project).as_posix(), formal.relative_to(project).as_posix(),
        registry.relative_to(project).as_posix())
    git("commit", "-qm", "Publish reference and advance live source")

    clone = tmp_path / "fresh"
    git("clone", "--no-local", str(project), str(clone))
    fresh = clone / relative_root
    for directory in ("runtime", "governance"):
        shutil.copytree(knowledge / directory, fresh / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("sources.lock.yaml", "__pycache__"))
    for name in ("knowledge.py", "knowledge.cmd", "knowledge.sh"):
        shutil.copyfile(knowledge / name, fresh / name)
    (fresh / "knowledge/fixed.md").write_bytes(markdown.replace(b"\n", b"\r\n"))
    assert invoke(fresh, "maintain", "reindex")[0] == 0
    cloned_ref = _panel(fresh, "read", {"card_id": "fixed"})["doc_ref"][0]
    assert cloned_ref == original_ref
    status, resolved = invoke(fresh, "source", "resolve",
                              request={"source_id": source_id, "snapshot_id": cloned_ref["snapshot_id"], "hash": old_hash})
    assert status == 0, resolved
    assert (fresh / resolved["data"]["original_ref"]).read_bytes() == older

    assert invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")[0] == 0
    check_and_publish()
    rebound = _panel(knowledge, "read", {"card_id": "fixed"})["doc_ref"][0]
    assert rebound["source_version"] == "bound" and rebound["source_sha256"] == hashlib.sha256(newer).hexdigest()
    assert rebound["snapshot_id"] != original_ref["snapshot_id"]


def test_panel_raw_saves_once_and_lists_without_registering(knowledge, tmp_path):
    original = b"# Uploaded\n\nComplete document.\n"
    staged = tmp_path / "staged"
    staged.write_bytes(original)
    digest = hashlib.sha256(original).hexdigest()
    request = {"path": "specs/uploaded.md", "staged_path": str(staged),
               "expected_size": len(original), "expected_sha256": digest}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda path: invoke(knowledge, "panel", "raw-save", request={**request, "path": path}),
                                [request["path"], "specs/Uploaded.md"]))
    successful = [report for code, report in results if code == 0]
    failed = [report for code, report in results if code != 0]
    assert len(successful) == len(failed) == 1
    assert successful[0]["data"]["sha256"] == digest
    assert failed[0]["diagnostics"][0]["code"] == "RAW_TARGET_EXISTS"
    item = _panel(knowledge, "raw-list", {"path": "specs"})["items"][0]
    assert item == {key: successful[0]["data"][key] for key in ("name", "path", "kind", "size")}
    resolved = _panel(knowledge, "raw-path", {"path": item["path"]})
    assert Path(resolved["absolute_path"]).read_bytes() == staged.read_bytes() == original
    assert not (knowledge / ".build").exists()
    assert not list((knowledge / "docs-raw/specs").glob(".upload-*"))
    assert not invoke(knowledge, "source", "list")[1]["data"]["files"]

    for path, expected_code in (("../formal.md", "RAW_UNSAFE_PATH"),
                                ("specs/README.md", "RAW_UNSUPPORTED_TARGET"),
                                ("specs/mismatch.md", "RAW_STAGE_MISMATCH")):
        status, report = invoke(knowledge, "panel", "raw-save",
                                request={**request, "path": path, "expected_sha256": "0" * 64})
        assert status == 2 and report["diagnostics"][0]["code"] == expected_code
    assert not (knowledge / "docs-raw/specs/mismatch.md").exists()


def test_source_resolve_binds_snapshot_to_source_and_hash(knowledge):
    original = b"# Original\n\nHistorical evidence.\n"
    frozen = knowledge / "logs/evidence/objects/retained.bin"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(original)
    digest = hashlib.sha256(original).hexdigest()
    resource = {"source_id": "doc-a", "kind": "raw", "path": "docs-raw/specs/a.md"}
    snapshot = {"snapshot_id": "snap-a", "source_id": "doc-a", "sha256": digest, "bytes": len(original),
                "recovery": {"method": "evidence_object", "path": frozen.relative_to(knowledge).as_posix()}}
    (knowledge / "governance/sources.lock.yaml").write_text(
        yaml.safe_dump({"schema_version": "2.0", "resources": [resource], "snapshots": [snapshot]}),
        encoding="utf-8")
    (knowledge / resource["path"]).write_text("# Changed\n", encoding="utf-8")
    _panel_card(knowledge, "a", [{"doc_id": "doc-a", "snapshot_id": "snap-a", "line_start": 1, "line_end": 2}],
                "# A\n\nA fixed citation.\n")
    assert invoke(knowledge, "maintain", "reindex")[0] == 0
    revision = _panel(knowledge, "overview")["view_revision"]
    status, report = invoke(knowledge, "read", request={"card_id": "a", "view_revision": revision})
    assert status == 0 and report["data"]["doc_ref"][0]["source_sha256"] == digest
    args = {"source_id": "doc-a", "snapshot_id": "snap-a", "hash": digest}
    status, report = invoke(knowledge, "source", "resolve", request=args)
    assert status == 0 and report["data"]["hash"] == digest, report
    assert (knowledge / report["data"]["original_ref"]).read_bytes() == original
    status, report = invoke(knowledge, "source", "resolve", request={**args, "hash": "0" * 64})
    assert status == 2 and report["diagnostics"][0]["code"] == "SOURCE_HASH_MISMATCH"


def test_ingest_scan_returns_one_document_without_legacy_operation_request(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# A\nA new bounded conclusion.\n", encoding="utf-8")
    (knowledge / "docs-raw/specs/b.md").write_text("# B\nAnother conclusion.\n", encoding="utf-8")
    status, report = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, report
    assert report["phase"] == "prepared"
    assert report["data"]["source"]["path"] == "docs-raw/specs/a.md"
    assert report["data"]["source"]["doc_id"]
    assert report["data"]["affected_cards"] == []
    assert (knowledge / report["data"]["task_ref"]).is_file()
    assert not list((knowledge / "knowledge").rglob("*.md"))


def test_local_configuration_is_used_outside_git_without_reading_ancestor_config(knowledge):
    workspace = knowledge.parents[1]
    config = knowledge / "config.yml"
    original = config.read_bytes()
    (workspace / "config.yml").write_text("this: [is invalid", encoding="utf-8")
    assert not (workspace / ".git").exists()
    code = workspace / "main/driver/sample.c"
    code.parent.mkdir(parents=True)
    code.write_text("int receive(void) { return 1; }\n", encoding="utf-8")
    config.write_bytes(original.replace(b"modules: []", b"modules:\n- path: driver"))

    status, report = invoke(knowledge, "source", "register", request={
        "kind": "code", "path": "main/driver/sample.c", "source_id": "code-sample",
    })
    assert status == 0 and report["phase"] == "registered", report

    digest = hashlib.sha256(code.read_bytes()).hexdigest()
    status, report = invoke(knowledge, "source", "resolve", request={"source_id": "code-sample", "hash": digest})
    assert status == 0 and report["phase"] == "resolved", report
    assert report["data"]["hash"] == digest
    (knowledge / "docs-raw/specs/a.md").write_text("# RX\nDocument in a manifest workspace.\n", encoding="utf-8")

    status, report = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")

    assert status == 0 and report["phase"] == "prepared", report
    assert report["data"]["source"]["path"] == "docs-raw/specs/a.md"
    assert config.read_bytes() == original.replace(b"modules: []", b"modules:\n- path: driver")


def test_no_card_commit_keeps_receipt_under_artifacts_without_creating_logs(knowledge):
    original = knowledge / "docs-raw/specs/a.md"
    original.write_text("# A\n\nAn already covered conclusion.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    (knowledge / ".build/plan.md").write_text(
        "---\ncards: []\n---\nThe source adds no new knowledge after full review.\n", encoding="utf-8")
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0, checked
    request = knowledge / "artifacts/commit-request.json"
    request.write_text(json.dumps({"reason": "Fully reviewed; existing knowledge covers this source."}), encoding="utf-8")

    status, committed = invoke(knowledge, "ingest", "commit", "--input", str(request))

    assert status == 0 and committed["phase"] == "completed", committed
    assert _panel(knowledge, "overview")["card_count"] == 0
    receipt = knowledge / "artifacts/ingest/latest.json"
    assert receipt.is_file()
    assert json.loads(receipt.read_bytes()) == committed["data"]
    assert not (knowledge / "logs").exists()
    assert not (knowledge / ".build").exists()
    registry = yaml.safe_load((knowledge / "governance/sources.lock.yaml").read_bytes())
    resource = next(row for row in registry["resources"] if row["source_id"] == scanned["data"]["source"]["doc_id"])
    assert resource["processed_hash"] == hashlib.sha256(original.read_bytes()).hexdigest()
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "completed", report
    assert report["data"] == committed["data"]


@pytest.mark.parametrize("keep_readme", [False, True], ids=["without-readme", "with-readme"])
def test_public_ingest_cleans_staging_but_preserves_only_its_root_readme(knowledge, keep_readme):
    (knowledge / "docs-raw/specs/a.md").write_text(
        "# A\n\nAn already covered conclusion.\n", encoding="utf-8")
    staging = knowledge / ".build"
    staging.mkdir()
    readme = staging / "README.md"
    readme_bytes = b"\xef\xbb\xbfTemporary ingest staging lives here.\r\n"
    if keep_readme:
        readme.write_bytes(readme_bytes)
    stale_files = ["stale.txt", ".hidden", "nested/README.md", ".cache/deep/stale.txt"]

    def add_stale_files():
        for relative in stale_files:
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Previous operation data.\n", encoding="utf-8")

    add_stale_files()
    (staging / "task.json").write_text("Old task must be discarded.", encoding="utf-8")

    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")

    assert status == 0 and scanned["phase"] == "prepared", scanned
    assert all(not (staging / relative).exists() for relative in stale_files)
    assert not (staging / "nested").exists()
    assert not (staging / ".cache").exists()
    assert list((staging / "cards").iterdir()) == []
    assert json.loads((staging / "task.json").read_bytes())["source"] == scanned["data"]["source"]
    if keep_readme:
        assert readme.read_bytes() == readme_bytes
    else:
        assert not readme.exists()
    (staging / "plan.md").write_text(
        "---\ncards: []\n---\nThe source adds no new knowledge after full review.\n", encoding="utf-8")
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0 and checked["phase"] == "passed", checked
    add_stale_files()
    request = knowledge / "artifacts/commit-request.json"
    request.write_text(json.dumps({"reason": "Fully reviewed; no new card is needed."}), encoding="utf-8")

    status, committed = invoke(knowledge, "ingest", "commit", "--input", str(request))

    assert status == 0 and committed["phase"] == "completed", committed
    if keep_readme:
        assert list(staging.iterdir()) == [readme]
        assert readme.read_bytes() == readme_bytes
    else:
        assert not staging.exists()

    add_stale_files()
    (staging / "task.json").write_text("An obsolete completed task.", encoding="utf-8")

    status, unchanged = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")

    assert status == 0 and unchanged["phase"] == "unchanged", unchanged
    assert list(staging.iterdir()) == ([readme] if keep_readme else [])
    if keep_readme:
        assert readme.read_bytes() == readme_bytes


def test_status_reads_legacy_receipt_without_migration_and_prefers_current_work(knowledge):
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "idle", report
    assert not (knowledge / "logs").exists()
    assert not (knowledge / "artifacts/ingest").exists()

    old = knowledge / "logs/ingest/latest.json"
    old.parent.mkdir(parents=True)
    legacy_bytes = b'{"source_id":"legacy-source","card_ids":[]}\n'
    old.write_bytes(legacy_bytes)
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "completed", report
    assert report["data"]["source_id"] == "legacy-source"
    assert old.read_bytes() == legacy_bytes
    assert not (knowledge / "artifacts/ingest").exists()

    latest = knowledge / "artifacts/ingest/latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text('{"source_id":"new-source","card_ids":[]}', encoding="utf-8")
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["data"]["source_id"] == "new-source", report
    task = knowledge / ".build/task.json"
    task.parent.mkdir()
    task.write_text('{"source":{"source_id":"pending-source"}}', encoding="utf-8")
    status, report = invoke(knowledge, "status")
    assert status == 0 and report["phase"] == "prepared", report
    assert report["data"]["source"]["source_id"] == "pending-source"
    assert old.read_bytes() == legacy_bytes


def test_formal_check_needs_no_private_ingest_or_review_ticket(knowledge):
    status, report = invoke(knowledge, "lint")
    assert status == 0, report
    assert report["phase"] == "passed"
    assert report["data"]["findings"] == []
    assert report["data"]["review_required"] is True
    assert not (knowledge / ".build").exists()


def test_formal_check_reports_invalid_frontmatter_as_a_finding(knowledge):
    (knowledge / "knowledge/bad.md").write_text("---\nid: missing-references\n---\n# Broken\n", encoding="utf-8")
    status, report = invoke(knowledge, "lint")
    assert status == 1, report
    assert report["phase"] == "failed"
    assert report["data"]["findings"]
    assert not (knowledge / ".build").exists()


def test_public_p4_blocks_a_misplaced_card_and_p5_copies_the_corrected_path(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# Reply\n\nWait for a reply.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, scanned
    identity = scanned["data"]["source"]["doc_id"]
    (knowledge / ".build/plan.md").write_text(
        "---\ncards:\n- id: waiting\n  path: knowledge/rules/waiting.md\n---\n"
        "Keep this documented rule under rules.\n", encoding="utf-8")
    misplaced = knowledge / ".build/cards/waiting.md"
    misplaced.write_text(
        "---\nid: waiting\ndoc_ref:\n- doc_id: " + identity
        + "\n  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Waiting\n\nWait for a reply.\n",
        encoding="utf-8")
    expected = misplaced.read_bytes()

    status, report = invoke(knowledge, "ingest", "check")

    assert status == 1, report
    assert report["phase"] == "failed"
    finding = next(item for item in report["data"]["findings"] if item["code"] == "PLAN_CARD_MISMATCH")
    assert finding["card_id"] == "waiting"
    assert finding["expected_path"] == "knowledge/rules/waiting.md"
    assert finding["actual_path"] == "knowledge/waiting.md"
    assert not (knowledge / "knowledge/waiting.md").exists()
    assert not (knowledge / "knowledge/rules/waiting.md").exists()
    corrected = misplaced.parent / "rules/waiting.md"
    corrected.parent.mkdir()
    misplaced.rename(corrected)
    status, report = invoke(knowledge, "ingest", "check")
    assert status == 0, report
    assert report["phase"] == "passed"
    status, report = invoke(knowledge, "ingest", "commit")
    assert status == 0, report
    assert report["phase"] == "completed"
    assert (knowledge / "knowledge/rules/waiting.md").read_bytes() == expected
    assert not (knowledge / "knowledge/waiting.md").exists()
    assert not (knowledge / ".build").exists()


@pytest.mark.parametrize("arguments,output", [
    (("search", "fresh"), ".build/task.json"),
    (("query", "fresh"), ".build/task.json"),
    (("query", "search", "fresh"), ".build/task.json"),
    (("read", "formal"), ".build/task.json"),
    (("query", "read", "formal"), ".build/task.json"),
    (("search", "fresh"), "artifacts/query/../../.build/task.json"),
    (("query", "fresh"), "artifacts/knowledge.sqlite"),
    (("read", "formal"), "artifacts/query/../knowledge.sqlite"),
])
def test_query_output_cannot_overwrite_ingest_or_database(knowledge, arguments, output):
    (knowledge / "docs-raw/specs/a.md").write_text("# A\n\nA fresh conclusion.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    identity = scanned["data"]["source"]["doc_id"]
    (knowledge / "knowledge/formal.md").write_text(
        "---\nid: formal\ndoc_ref:\n- doc_id: " + identity
        + "\n  line_start: 1\n  line_end: 3\ncode_ref: []\n---\n# Formal\nA fresh conclusion.\n",
        encoding="utf-8",
    )
    before = {p.relative_to(knowledge).as_posix(): p.read_bytes()
              for p in knowledge.rglob("*") if p.is_file()}
    status, report = invoke(knowledge, *arguments, "--output", output)
    assert status == 2, report
    assert report["status"] == "error"
    assert report["diagnostics"][0]["code"] == "OUTPUT_OUTSIDE_WORKSPACE"
    assert {p.relative_to(knowledge).as_posix(): p.read_bytes()
            for p in knowledge.rglob("*") if p.is_file()} == before


def test_query_can_save_its_actual_response_in_query_artifacts(knowledge):
    status, report = invoke(knowledge, "search", "fresh", "--output", "artifacts/query/answer.json")
    assert status == 0, report
    assert json.loads((knowledge / "artifacts/query/answer.json").read_bytes()) == report
    assert not (knowledge / ".build").exists()


def test_public_three_field_card_is_private_until_commit_then_searchable_without_purpose(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text(
        "# RX design\n\nThe RX design budget is 8 ms; no timing measurement is supplied.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan", "--source", "docs-raw/specs/a.md")
    assert status == 0, scanned
    source_id = scanned["data"]["source"]["doc_id"]
    metadata = {"id": "rx-flow", "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 3}], "code_ref": []}
    draft = knowledge / ".build/cards/rx-flow.md"
    draft.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False)
                     + "---\n# RX design budget\n\nrx_budget is 8 ms by design.\n\n"
                     "Timing has not been measured; implementation applicability is unknown.\n", encoding="utf-8")
    (knowledge / ".build/plan.md").write_text(
        "---\ncards:\n- id: rx-flow\n  path: knowledge/rx-flow.md\n---\nCreate the documented design budget.\n", encoding="utf-8")
    expected = draft.read_bytes()
    status, before = invoke(knowledge, "search", "rx_budget")
    assert status == 0 and before["data"]["matches"] == []
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0, checked
    status, committed = invoke(knowledge, "ingest", "commit")
    assert status == 0, committed
    assert (knowledge / "knowledge/rx-flow.md").read_bytes() == expected
    status, result = invoke(knowledge, "query", "rx_budget")
    assert status == 0, result
    hit = result["data"]["matches"][0]
    assert hit["card_id"] == "rx-flow"
    assert set(hit) == {"card_id", "path", "title", "tags", "lifecycle", "score"}
    assert "purpose" not in result["data"]
    status, read = invoke(knowledge, "read", "rx-flow")
    assert status == 0, read
    assert read["data"]["metadata"] == metadata
    assert read["data"]["code_ref"] == []
    assert "not been measured" in read["data"]["body"]
    assert "eligible_claim_ids" not in read["data"]
    assert read["data"]["sources"][0]["processed_hash"] == scanned["data"]["source"]["hash"]


@pytest.mark.parametrize("arguments", [
    ("search", "RX", "--purpose", "current"), ("query", "RX", "--purpose", ""),
    ("read", "absent", "--purpose", "guidance"), ("query", "read", "absent", "--purpose", ""),
])
def test_public_old_purpose_option_reports_migration_before_search(knowledge, arguments):
    status, result = invoke(knowledge, *arguments)
    assert status == 2, result
    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "QUERY_PARAMETERS_REMOVED"
    assert not (knowledge / "artifacts/query").exists()
    assert not (knowledge / ".build").exists()


@pytest.mark.parametrize("extra", [{"purpose": None}, {"purpose": ""}, {"purpose": "current"}, {"context": {}}, {"context": None}])
@pytest.mark.parametrize("command", ["search", "read"])
def test_public_old_json_fields_report_migration_even_when_empty(knowledge, extra, command):
    request = {"query": "RX"} if command == "search" else {"card_id": "absent"}
    request_path = knowledge.parent / "request.json"
    request_path.write_text(json.dumps({**request, **extra}), encoding="utf-8")
    status, result = invoke(knowledge, command, "--input", str(request_path))
    assert status == 2, result
    assert result["diagnostics"][0]["code"] == "QUERY_PARAMETERS_REMOVED"
    assert not (knowledge / "artifacts/query").exists()


def test_public_include_deprecated_flag_adds_retired_cards_without_changing_read_state(knowledge):
    (knowledge / "docs-raw/specs/a.md").write_text("# RX\n\nRX history.\n", encoding="utf-8")
    status, scanned = invoke(knowledge, "ingest", "scan")
    assert status == 0, scanned
    source_id = scanned["data"]["source"]["doc_id"]
    for identity, lifecycle in (("normal", "stable"), ("old", "deprecated")):
        header = {"id": identity, "doc_ref": [{"doc_id": source_id, "line_start": 1, "line_end": 3}],
                  "code_ref": [], "tags": ["RX"], "lifecycle": lifecycle}
        (knowledge / "knowledge" / (identity + ".md")).write_text(
            "---\n" + yaml.safe_dump(header) + "---\n# RX history\n\nrx_timeout history.\n", encoding="utf-8")
    status, result = invoke(knowledge, "search", "rx_timeout")
    assert status == 0 and [hit["card_id"] for hit in result["data"]["matches"]] == ["normal"]
    status, result = invoke(knowledge, "search", "rx_timeout", "--include-deprecated")
    assert status == 0, result
    assert {hit["card_id"] for hit in result["data"]["matches"]} == {"normal", "old"}
    status, result = invoke(knowledge, "read", "old")
    assert status == 0 and result["data"]["lifecycle"] == "deprecated"
