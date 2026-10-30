"""Repository-only public CLI journeys; reviewer declarations are synthetic data."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SPEC = importlib.util.spec_from_file_location(
    "repository_cli_journey_fixture", Path(__file__).parents[1] / "support/pipeline.py"
)
FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLOW)


def test_repository_only_document_publication_and_receipt_read(tmp_path, monkeypatch):
    # A normal Windows non-UTF8 terminal must not turn a successful Chinese
    # card read into a CLI failure or a non-JSON stdout response.
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    p = FLOW.Pipeline(tmp_path, repository_cli=True)
    assert not (p.base / "installed-skills").exists()
    assert (p.root / "knowledge.py").is_file()
    original = b"# Source\nCapture marker is an explicit synthetic rule.\n"
    bundle_ref, bundle = p.capture("repository-document", original)
    assert bundle["tool_identity"]["executor"] == "knowledge-cli"
    assert len(bundle["tool_identity"]["runtime_digest"]) == 64
    view_ref = p.view(
        "repository-document", bundle_ref, "repository-card",
        p.card("repository-card", bundle),
        queries=[{"id": "find-repository", "query": "capture", "required": ["repository-card"]}],
    )
    p.review("repository-document", view_ref)
    prepared = p.prepared["repository-document"]
    record_ref = p.call("knowledge-source", {
        "operation_id": "repository-document", "scan_ref": prepared["scan_ref"],
        "view_ref": view_ref,
        "disposition_preview_ref": p.record(view_ref)["disposition_preview_ref"],
    }, "record")["data"]["ingest_record_ref"]
    result = p.call("knowledge-apply", {
        "operation_id": "repository-document", "view_ref": view_ref,
        "ingest_record_ref": record_ref,
    }, "batch")
    assert result["phase"] == "completed"
    assert result["data"]["published"] is True
    assert result["data"]["batch_complete"] is True
    assert result["data"]["activated"] is True
    assert (p.root / "knowledge/rules/repository-card.md").is_file()
    assert not (p.root / view_ref).exists()
    search = p.call("knowledge-query", {
        "operation_id": "repository-search", "query": "capture",
    }, "search")["data"]
    assert [row["card_id"] for row in search["matches"]] == ["repository-card"]
    read = p.call("knowledge-query", {
        "operation_id": "repository-read", "receipt_ref": search["receipt_ref"],
        "card_id": "repository-card",
    }, "read")["data"]
    assert read["card_digest"] == search["matches"][0]["card_digest"]
    assert "Capture marker" in str(read)
    # Construct the old, valid identity shape as a distinct synthetic receipt.
    # The original receipt and the retained old-shape bytes remain unchanged.
    legacy_receipt = p.record(search["receipt_ref"])
    legacy_receipt["tool_identity"].pop("executor")
    legacy_receipt["tool_identity"].pop("runtime_digest")
    legacy_receipt.pop("digest")
    legacy_receipt["digest"] = FLOW.sha(FLOW.canonical(legacy_receipt))
    legacy_bytes = FLOW.canonical(legacy_receipt)
    legacy_ref = p.write(".build/operations/legacy-search/receipt.json", legacy_bytes)
    legacy_read = p.call("knowledge-query", {
        "operation_id": "repository-read-legacy", "receipt_ref": legacy_ref,
        "card_id": "repository-card",
    }, "read")["data"]
    assert legacy_read["card_digest"] == read["card_digest"]
    assert legacy_read["claims"] == read["claims"]
    assert (p.root / legacy_ref).read_bytes() == legacy_bytes
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == original
    repeated = p.call("knowledge-source", {"operation_id": "repository-repeat"}, "scan")
    assert p.record(repeated["data"]["scan_ref"])["units"][0]["change"] == "unchanged"
    assert not (p.base / "installed-skills").exists()


def configure_workspace(p):
    workspace = p.root.parent
    (workspace / "main").mkdir(exist_ok=True)
    (workspace / "config.yml").write_bytes(FLOW.canonical({
        "schema_version": "2.0", "workspace_id": "repository-patrol",
        "knowledge_roots": {"wifi": p.root.name}, "code_root": "main", "modules": [],
    }))


def test_repository_formal_lint_keeps_explicit_local_report_scope(tmp_path):
    p = FLOW.Pipeline(tmp_path, repository_cli=True)
    incoming = p.base / "formal-lint-input.json"
    incoming.write_text("{}", encoding="utf-8")
    output = p.root / ".build/reports/formal-lint.json"
    before = {path.relative_to(p.root).as_posix(): path.read_bytes()
              for path in (p.root / "governance").rglob("*") if path.is_file()}
    process = subprocess.run([
        sys.executable, str(p.root / "knowledge.py"), "lint", "--json",
        "--input", str(incoming), "--output", str(output),
    ], capture_output=True, timeout=60)
    assert process.returncode in {0, 1, 2}, process.stderr
    report = json.loads(output.read_bytes())
    assert report["checks"] and report["scope"]["kind"] == "full", report
    assert report["status"] in {"passed", "failed", "incomplete"}
    presentation = json.loads(process.stdout.decode("utf-8"))
    assert presentation["cli_transport"]["stage_result_digest"] == report["digest"]
    assert {path.relative_to(p.root).as_posix(): path.read_bytes()
            for path in (p.root / "governance").rglob("*") if path.is_file()} == before


def test_repository_only_patrol_rebuild_noop_and_unresolved_document(tmp_path):
    p = FLOW.Pipeline(tmp_path, repository_cli=True)
    configure_workspace(p)
    first = p.call("knowledge-maintain", {"operation_id": "patrol-empty"}, "patrol-plan")
    assert first["phase"] == "needs_index"
    request = {"operation_id": "patrol-empty", "plan_ref": first["data"]["plan_ref"]}
    indexed = p.call("knowledge-maintain", request, "patrol-reindex")
    assert indexed["phase"] == "indexed" and indexed["data"]["activated"] is True
    assert p.call("knowledge-maintain", request, "patrol-complete")["phase"] == "completed"
    baseline = (p.root / ".build/runtime/patrol-state.json").read_bytes()
    noop = p.call("knowledge-maintain", {"operation_id": "patrol-noop"}, "patrol-plan")
    assert noop["phase"] == "unchanged"
    p.write("docs-raw/specs/new.md", b"# New source\nCapture marker is a documented rule.\n")
    changed = p.call("knowledge-maintain", {"operation_id": "patrol-new"}, "patrol-plan")
    assert changed["phase"] == "needs_ingest"
    plan = p.record(changed["data"]["plan_ref"])
    assert [row["path"] for row in plan["required_units"]] == ["docs-raw/specs/new.md"]
    pending = p.call("knowledge-maintain", {
        "operation_id": "patrol-new", "plan_ref": changed["data"]["plan_ref"],
    }, "patrol-complete")
    assert pending["phase"] == "pending"
    assert (p.root / ".build/runtime/patrol-state.json").read_bytes() == baseline
    p.write("docs-raw/specs/new.md", b"# Changed after observation\n")
    drift = p.call("knowledge-maintain", {"operation_id": "patrol-new"}, "patrol-plan", expected=3)
    assert drift["diagnostics"][0]["code"] == "PATROL_INPUT_CHANGED"
    assert (p.root / ".build/runtime/patrol-state.json").read_bytes() == baseline
    assert not (p.base / "installed-skills").exists()


@pytest.mark.parametrize("change", ["insert", "delete"])
def test_repository_only_code_patrol_keeps_original_evidence(tmp_path, change):
    domain = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "repository_patrol_code_fixture",
        domain / "evals/support/stages/maintain_audit.py",
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    p = fixture._fixture.Harness(tmp_path)
    p.repository_cli = True
    # Even the compatibility installation paths and optional catalog are absent.
    p.packages = tmp_path / "uninstalled-skills"
    p.catalog.write_text(json.dumps({"schema_version": "2.0", "skills": {}}), encoding="utf-8")
    source, raw, _, _ = fixture.code_fixture(p)
    original_card = (p.root / "knowledge/rules/audit-current.md").read_bytes()
    original_lock = (p.root / "governance/sources.lock.yaml").read_bytes()
    if change == "insert":
        source.write_bytes(b"// Extra line\n" + raw)
    else:
        source.unlink()
    result = p.run("maintain", {"operation_id": "repository-code"}, "patrol-plan")
    assert result["phase"] == "needs_ingest"
    plan = p.record(result["data"]["plan_ref"])
    assert plan["candidate_card_ids"] == ["audit-current"]
    assert (p.root / "knowledge/rules/audit-current.md").read_bytes() == original_card
    assert (p.root / "governance/sources.lock.yaml").read_bytes() == original_lock
    assert not (p.root / ".build/runtime/patrol-state.json").exists()
    if change == "insert":
        prepared = p.run("source", result["data"]["source_request"], "prepare")
        assert prepared["phase"] == "prepared"
    assert not p.packages.exists()
