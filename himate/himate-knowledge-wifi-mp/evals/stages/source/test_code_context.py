"""P1 fixes actual adopted code metadata; it does not infer product evidence."""

import hashlib
import json
import time

import yaml


def workspace(harness):
    root = harness.root.parent
    (root / "AGENTS.md").write_text("Synthetic project entry.\n", encoding="utf-8")
    harness.write("AGENTS.md", b"Synthetic knowledge entry.\n")
    config = {
        "schema_version": "2.0", "workspace_id": "selected-code",
        "knowledge_roots": {"wifi": harness.root.name}, "code_root": "main",
        "modules": [{"path": "host", "sides": ["host"]}],
    }
    (root / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    code = root / "main/host"
    code.mkdir(parents=True)
    (code / "first.c").write_bytes(b"int first(void) { return 1; }\n")
    (code / "unrelated.c").write_bytes(b"\x00\xffunselected bytes")
    discovery = harness.run("explore", {"operation_id": "discovery", "target_path": str(code)})
    loaded = harness.record(discovery["data"]["context_ref"])
    repo_id = next(iter(loaded["repos"]))
    assert loaded["repos"][repo_id]["files"] == {}
    return code, repo_id, discovery["data"]["context_ref"]


def selected(repo_id, relative="first.c"):
    return {"kind": "code", "repo_id": repo_id, "relative_path": relative}


def test_prepare_automatically_fixes_only_adopted_code_context(harness):
    code, repo_id, discovery_ref = workspace(harness)
    discovery_bytes = (harness.root / discovery_ref).read_bytes()
    first_bytes = (code / "first.c").read_bytes()
    result = harness.run("source", {"operation_id": "prepare-code", "targets": [selected(repo_id)]}, "prepare")
    material = harness.record(result["data"]["material_ref"])
    assert material.get("context_ref"), "P1 must supply actual code context without author-written JSON"
    context = harness.record(material["context_ref"])
    assert result["data"]["context_ref"] == material["context_ref"]
    assert result["data"]["context_digest"] == context["digest"] == material["context_digest"]
    assert harness.record(material["bundle_ref"])["context_ref"] == material["context_ref"]
    assert material["context_ref"].startswith(".build/operations/prepare-code/")
    assert set(context["repos"]) == {repo_id}
    assert context["repos"][repo_id]["files"] == {"first.c": hashlib.sha256(first_bytes).hexdigest()}
    assert context["target"] is None and context["build_evidence"] is None
    assert context["repos"][repo_id]["head"] is None
    assert context["repos"][repo_id]["dirty"] == "unknown"
    assert context["tool_identity"]["skill"] == "hs-knowledge-source"
    assert {item["path"] for item in context["entries"]} == {
        str(harness.root.parent / "AGENTS.md"), str(harness.root / "AGENTS.md"),
    }
    guarded = {item["path"] for item in context["current_files"]}
    assert {str(harness.root.parent / "AGENTS.md"), str(harness.root / "AGENTS.md")} <= guarded
    assert (harness.root / discovery_ref).read_bytes() == discovery_bytes
    assert (code / "first.c").read_bytes() == first_bytes
    assert not (harness.root / "knowledge").exists()


def test_prepare_pure_document_does_not_require_or_generate_code_context(harness):
    harness.write("docs-raw/specs/readme.md", b"# Independent document\n")
    result = harness.run("source", {"operation_id": "document", "targets": [
        {"source_path": "docs-raw/specs/readme.md"},
    ]}, "prepare")
    material = harness.record(result["data"]["material_ref"])
    assert material["context_ref"] is None
    assert not material["current_code"]


def test_discovery_is_derived_without_rewriting_the_explicit_record(harness):
    _, repo_id, discovery_ref = workspace(harness)
    original = (harness.root / discovery_ref).read_bytes()
    result = harness.run("source", {"operation_id": "from-discovery", "context_ref": discovery_ref,
                                   "targets": [selected(repo_id)]}, "prepare")
    assert result["data"]["context_ref"] != discovery_ref
    assert harness.record(result["data"]["context_ref"])["repos"][repo_id]["files"]
    assert (harness.root / discovery_ref).read_bytes() == original


def test_document_material_can_be_supplemented_with_code_in_the_same_operation(harness):
    _, repo_id, _ = workspace(harness)
    harness.write("docs-raw/specs/design.md", b"# Design\nThe first function returns one.\n")
    request = {"operation_id": "design", "targets": [{"source_path": "docs-raw/specs/design.md"}]}
    first = harness.run("source", request, "prepare")
    old_ref = first["data"]["material_ref"]
    original = (harness.root / old_ref).read_bytes()
    result = harness.run("source", {"operation_id": "design", "existing_material_ref": old_ref,
                                   "targets": [selected(repo_id)]}, "prepare")
    material = harness.record(result["data"]["material_ref"])
    assert material["context_ref"]
    assert {row["kind"] for row in harness.record(material["bundle_ref"])["resources"]} == {"raw", "code"}
    assert (harness.root / old_ref).read_bytes() == original
    assert harness.record(old_ref)["context_ref"] is None


def test_automatic_context_supplement_extends_files_in_a_new_record(harness):
    code, repo_id, _ = workspace(harness)
    first = harness.run("source", {"operation_id": "extend", "targets": [selected(repo_id)]}, "prepare")
    first_context = first["data"]["context_ref"]
    original = (harness.root / first_context).read_bytes()
    second = b"int second(void) { return 2; }\n"
    (code / "second.c").write_bytes(second)
    result = harness.run("source", {"operation_id": "extend", "existing_material_ref": first["data"]["material_ref"],
                                   "targets": [selected(repo_id, "second.c")]}, "prepare")
    assert result["data"]["context_ref"] != first_context
    assert harness.record(result["data"]["context_ref"])["repos"][repo_id]["files"] == {
        "first.c": hashlib.sha256((code / "first.c").read_bytes()).hexdigest(),
        "second.c": hashlib.sha256(second).hexdigest(),
    }
    assert (harness.root / first_context).read_bytes() == original


def test_explicit_complete_context_is_preserved_and_cannot_silently_expand(harness):
    code, repo_id, _ = workspace(harness)
    first = harness.run("source", {"operation_id": "explicit", "targets": [selected(repo_id)]}, "prepare")
    context_ref = first["data"]["context_ref"]
    original = (harness.root / context_ref).read_bytes()
    again = harness.run("source", {"operation_id": "adopt", "context_ref": context_ref,
                                  "targets": [selected(repo_id)]}, "prepare")
    assert again["data"]["context_ref"] == context_ref
    (code / "second.c").write_bytes(b"int second(void) { return 2; }\n")
    rejected = harness.run("source", {"operation_id": "cannot-expand", "context_ref": context_ref,
                                     "targets": [selected(repo_id, "second.c")]}, "prepare", expected=3)
    assert rejected["diagnostics"][0]["code"] == "CODE_CONTEXT_STALE"
    assert (harness.root / context_ref).read_bytes() == original


def test_automatic_context_keeps_its_original_entry_binding_on_supplement(harness):
    _, repo_id, _ = workspace(harness)
    first = harness.run("source", {"operation_id": "entry", "targets": [selected(repo_id)]}, "prepare")
    (harness.root.parent / "AGENTS.md").write_text("Changed project entry.\n", encoding="utf-8")
    rejected = harness.run("source", {"operation_id": "entry", "existing_material_ref": first["data"]["material_ref"],
                                     "targets": []}, "prepare", expected=3)
    assert rejected["diagnostics"][0]["code"] == "SOURCE_CHANGED"


def test_prepare_accepts_legacy_code_without_inventing_missing_agent_entries(harness):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "support/stages/source_code.py"
    spec = importlib.util.spec_from_file_location("context_code_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    _, _ = fixture.setup_code(harness)
    result = harness.run("source", {"operation_id": "no-entries", "targets": [selected("code", "sample.c")]}, "prepare")
    context = harness.record(result["data"]["context_ref"])
    assert context["entries"] == []
    assert context["current_files"] == []


def test_exact_retry_keeps_the_automatic_context_bytes(harness):
    _, repo_id, _ = workspace(harness)
    request = {"operation_id": "retry-code", "targets": [selected(repo_id)]}
    first = harness.run("source", request, "prepare")
    context_ref = first["data"]["context_ref"]
    original = (harness.root / context_ref).read_bytes()
    again = harness.run("source", request, "prepare")
    assert again["data"]["context_ref"] == context_ref
    assert (harness.root / context_ref).read_bytes() == original


def authored_code_view(harness, *, change_entry=False):
    """Synthetic author decisions over actual public P1/P2/P3, no gate bypass."""
    _, repo_id, _ = workspace(harness)
    harness.write("docs-raw/specs/design.md", b"# Design\nThe first function returns one.\n")
    raw = harness.run("source", {"operation_id": "mixed", "targets": [
        {"source_path": "docs-raw/specs/design.md"},
    ]}, "prepare")
    prepared = harness.run("source", {"operation_id": "mixed", "existing_material_ref": raw["data"]["material_ref"],
                                     "targets": [selected(repo_id)]}, "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    resources = {row["source_id"]: row for row in bundle["resources"]}
    sources = [{"evidence_ref": resources[row["source_id"]]["kind"], "source_id": row["source_id"],
                "snapshot_id": row["snapshot_id"],
                "locator": {"kind": "lines", "start": 1, "end": 1 if resources[row["source_id"]]["kind"] == "code" else 2},
                **({"code_ref": {"kind": "function", "language": "c", "name": "first", "scope": []}}
                   if resources[row["source_id"]]["kind"] == "code" else {})}
               for row in bundle["snapshots"]]
    units = [row["unit_id"] for row in material["units"]]
    semantic = harness.run("change-plan", {"operation_id": "mixed", "material_ref": prepared["data"]["material_ref"],
        "author_id": "synthetic-author", "units": [{"unit_id": unit, "outcome": "content", "reason": "Design and code support one statement"} for unit in units],
        "claim_changes": [{"unit_ids": units, "card_id": "first-rule", "claim_id": "first-rule-claim", "action": "create",
            "before": None, "after": "Function first returns one", "conditions": "Static source guidance only",
            "evidence": sources, "preserved": [], "reason": "Design agrees with actual function"}],
        "card_actions": [{"card_id": "first-rule", "decision": "create", "author_id": "synthetic-author", "unit_ids": units, "reason": "One rule"}],
        "target_queries": [{"id": "first", "query": "first returns one", "purpose": "guidance", "required": ["first-rule"],
                            "expected_claim_ids": ["first-rule#first-rule-claim"]}]}, "plan")
    _, front, body = harness.card("first-rule", bundle, lifecycle="stable").decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["review_mode"] = "code_gate"
    metadata["sources"] = sources
    metadata["claims"][0].update(evidence_kind="implementation", source_refs=[row["evidence_ref"] for row in sources],
                                  verification_requirements=["semantic-support"])
    draft = harness.write(".build/operations/mixed/draft.md", ("---\n" + yaml.safe_dump(metadata, sort_keys=False)
        + "---" + body.replace("Synthetic fixture statement.", "Function first returns one.")).encode())
    if change_entry:
        (harness.root.parent / "AGENTS.md").write_bytes(b"Changed after P1.\n")
    response = harness.run("view-materialize", {"operation_id": "mixed", "semantic_plan_ref": semantic["data"]["semantic_plan_ref"],
                                                "cards": {"first-rule": draft}}, expected=2 if change_entry else 0)
    return response, prepared, semantic, sources, bundle


def test_document_then_code_context_flows_through_p3_and_independent_code_check(harness):
    response, prepared, semantic, sources, bundle = authored_code_view(harness)
    view = harness.record(response["data"]["view_ref"])
    assert view["context_ref"] == prepared["data"]["context_ref"]
    context = harness.record(view["context_ref"])
    original_by_snapshot = {row["snapshot_id"]: row["sha256"] for row in bundle["snapshots"]}
    report = {"schema_version": "2.0", "record_kind": "semantic_review", "reviewer_id": "synthetic-independent-reviewer",
        "payload": {"view_digest": view["digest"], "context_digest": context["digest"], "mode": "local", "issued_at": time.time(),
            "findings": [], "claims": [{"card_id": "first-rule", "claim_id": "first-rule-claim", "status": "supported",
                "reason": "Synthetic review fixture read the one literal return and matching design sentence",
                "evidence": [{key: source[key] for key in ("source_id", "snapshot_id", "locator")} | {
                    "sha256": original_by_snapshot[source["snapshot_id"]]} for source in sources]}]}}
    report_ref = harness.write(".build/operations/mixed/semantic-review.json", json.dumps(report).encode())
    result = harness.run("lint", {"operation_id": "mixed", "view_ref": response["data"]["view_ref"],
                                "context_ref": view["context_ref"], "semantic_report_ref": report_ref}, "code-check")
    assert result["data"]["check_status"] == "passed"
    assert len(harness.record(result["data"]["local_check_ref"])["code_identity"]["repos"]) == 1


def test_p3_detects_project_entry_drift_after_automatic_context(harness):
    response, *_ = authored_code_view(harness, change_entry=True)
    assert response["diagnostics"][0]["code"] == "INPUT_CHANGED"
    assert not (harness.root / ".build/operations/mixed/final-view.json").exists()
