"""Query exposes readable addresses, while internal source objects stay complete."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location("query_output_contracts", Path(__file__).parents[1] / "support/contracts.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
query = SUPPORT.module("query_runtime")
validation = SUPPORT.module("validation")


@pytest.fixture
def workspace(tmp_path):
    project = tmp_path / "workspace"
    root = project / "nested/knowledge"
    root.mkdir(parents=True)
    code = project / "main/shared/file.c"
    code.parent.mkdir(parents=True)
    code.write_bytes(b"// shifted\nint selected(void) { return 2; }\n")
    config = {"schema_version": "2.0", "workspace_id": "output-fixture",
              "knowledge_roots": {"wifi": "nested/knowledge"}, "code_root": "main",
              "modules": [{"path": "shared", "sides": ["host"]}]}
    (project / "config.yml").write_text(json.dumps(config), encoding="utf-8")
    ctx = SimpleNamespace(root=root, modules={"validation": validation})
    return ctx, project, code


def source(ctx, *, kind="code", original="logs/evidence/original.bin", matches=False):
    path = ctx.root / "logs/evidence/original.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"int selected(void) { return 1; }\n")
    resource = {"kind": kind, "path": "file.c", "source_id": "source",
                "repo_id": "repo-" + validation.sha256_bytes(b"main/shared")[:16]}
    reference = {"evidence_ref": "entry", "source_id": "source", "snapshot_id": "old",
                 "locator": {"kind": "lines", "start": 1, "end": 1},
                 "code_ref": {"kind": "function", "name": "selected", "scope": [], "parameter_types": []}}
    result = {"source_kind": kind, "source_ref": reference, "resource": resource,
              "original_ref": original, "locator": reference["locator"], "sha256": "a" * 64,
              "bytes_b64": "SOURCE_BYTES_MUST_NOT_ESCAPE" * 1000, "text": "SOURCE_TEXT_MUST_NOT_ESCAPE",
              "snapshot": {"extraction": {"text_ref": ".build/removed/text.txt"}, "private": "SOURCE_SNAPSHOT_MUST_NOT_ESCAPE"},
              "current_source_matches": matches, "current_source_sha256": ("a" if matches else "b") * 64,
              "code_navigation": {"status": "resolved", "path": "file.c", "repo_id": resource["repo_id"],
                                  "sha256": ("a" if matches else "b") * 64,
                                  "config_digest": validation.sha256_bytes((ctx.root.parents[1] / "config.yml").read_bytes()),
                                  "range": {"start_line": 2, "end_line": 2}}}
    if kind != "code":
        resource.update(path="docs-raw/specs/original.md")
        resource.pop("repo_id")
        reference.pop("code_ref")
        result.pop("code_navigation")
        current = ctx.root / resource["path"]
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("new document", encoding="utf-8")
    return result


def assert_compact(value):
    if isinstance(value, dict):
        assert not {"sources", "source_ref", "snapshot", "resource", "bytes_b64", "text", "code_ref"} & value.keys()
        for child in value.values():
            assert_compact(child)
    elif isinstance(value, list):
        for child in value:
            assert_compact(child)
    assert "MUST_NOT_ESCAPE" not in json.dumps(value)


def test_code_links_separate_fixed_evidence_and_current_symbol_in_nested_workspace(workspace):
    ctx, _, _ = workspace
    original = source(ctx)
    links = query.source_links(ctx, [original])
    assert links == [{"evidence_ref": "entry", "kind": "code",
        "evidence": {"base": "knowledge_root", "path": "logs/evidence/original.bin",
                     "locator": {"kind": "lines", "start": 1, "end": 1}, "sha256": "a" * 64},
        "current": {"base": "workspace", "path": "main/shared/file.c",
                    "locator": {"kind": "lines", "start": 2, "end": 2}, "sha256": "b" * 64},
        "navigation_status": "resolved", "current_source_matches": False}]
    assert_compact(links)
    assert original["bytes_b64"].startswith("SOURCE_BYTES")


@pytest.mark.parametrize("matches", [True, False, None])
def test_raw_current_address_does_not_reuse_old_lines_after_source_change(workspace, matches):
    ctx, _, _ = workspace
    original = source(ctx, kind="raw", matches=matches)
    link = query.source_links(ctx, [original])[0]
    assert link["evidence"]["path"] == "logs/evidence/original.bin"
    if matches is None:
        assert link["current"] is None
    else:
        assert link["current"]["path"] == "docs-raw/specs/original.md"
        assert link["current"]["locator"] == (original["locator"] if matches else None)
    assert link["navigation_status"] == "not_applicable"
    assert_compact(link)


@pytest.mark.parametrize("locator", [
    {"kind": "lines", "start": 1, "end": 2},
    {"kind": "bytes", "start": 0, "end": 4},
    {"kind": "pages", "page": 1, "end": 2},
    {"kind": "paragraphs", "paragraph": 1, "end": 2},
    {"kind": "table_row", "table": 1, "row": 2},
    {"kind": "pages", "number": 1, "end": 2},
    {"kind": "paragraphs", "id": 1, "end": 2},
])
def test_public_locator_keeps_native_address_fields_without_arbitrary_source_payload(workspace, locator):
    ctx, _, _ = workspace
    original = source(ctx, kind="raw", matches=True)
    internal_locator = {**locator, "text": "MUST_NOT_ESCAPE", "bytes_b64": "MUST_NOT_ESCAPE",
                        "path": "private/duplicate-path", "repo_id": "duplicate-repository",
                        "anchor": "unsupported-extra", "private": {"text": "MUST_NOT_ESCAPE"}}
    internal_locator.setdefault("number", {"text": "MUST_NOT_ESCAPE"})
    internal_locator.setdefault("id", True)
    original["locator"] = original["source_ref"]["locator"] = internal_locator
    link = query.source_links(ctx, [original])[0]
    assert link["evidence"]["locator"] == locator
    assert link["current"]["locator"] == locator
    assert_compact(link)
    assert original["locator"]["text"] == "MUST_NOT_ESCAPE"


@pytest.mark.parametrize("status", ["missing", "ambiguous", "unavailable"])
def test_nonunique_code_navigation_never_claims_a_current_function_range(workspace, status):
    ctx, _, _ = workspace
    original = source(ctx)
    original["code_navigation"].update(status=status)
    original["code_navigation"].pop("range")
    if status != "ambiguous":
        original["code_navigation"].pop("sha256")
    link = query.source_links(ctx, [original])[0]
    assert link["navigation_status"] == status
    assert link["evidence"]["locator"]["start"] == 1
    if status == "ambiguous":
        assert link["current"]["locator"] is None
    else:
        assert link["current"] is None
        assert link["current_source_matches"] is None
    assert_compact(link)


def test_actual_code_recovery_address_maps_to_configured_file_and_keeps_snapshot_hash(workspace):
    ctx, _, _ = workspace
    original = source(ctx, matches=True)
    repo = original["resource"]["repo_id"]
    original["original_ref"] = "code:" + repo + ":file.c"
    link = query.source_links(ctx, [original])[0]
    assert link["evidence"] == {"base": "workspace", "path": "main/shared/file.c",
        "locator": {"kind": "lines", "start": 1, "end": 1}, "sha256": "a" * 64}
    assert_compact(link)


def test_legacy_code_link_uses_the_resource_address_that_produced_its_current_hash(workspace):
    ctx, _, _ = workspace
    original = source(ctx, matches=True)
    original["source_ref"].pop("code_ref")
    original.pop("code_navigation")
    original["source_ref"]["locator"]["path"] = "unobserved.c"
    link = query.source_links(ctx, [original])[0]
    assert link["current"] == {"base": "workspace", "path": "main/shared/file.c",
        "locator": {"kind": "lines", "start": 1, "end": 1}, "sha256": "a" * 64}
    assert link["current_source_matches"] is True


@pytest.mark.parametrize("kind", ["raw", "code"])
def test_git_recovery_is_an_exact_git_address_not_a_fake_local_path(workspace, kind):
    ctx, _, _ = workspace
    original = source(ctx, kind=kind, original="git:" + "c" * 40 + ":nested/old.md")
    link = query.source_links(ctx, [original])[0]
    expected = {"base": "git", "path": "nested/old.md", "commit": "c" * 40,
                "locator": original["locator"], "sha256": "a" * 64}
    if kind == "code":
        expected["repo_id"] = original["resource"]["repo_id"]
    assert link["evidence"] == expected
    assert_compact(link)


def test_external_legacy_repository_keeps_explicit_repository_base(workspace, tmp_path):
    ctx, project, _ = workspace
    original = source(ctx)
    external = tmp_path / "external"
    external.mkdir()
    (external / "file.c").write_text("int selected(void) { return 2; }\n", encoding="utf-8")
    repo = original["resource"]["repo_id"]
    (project / "config.yml").write_text(json.dumps({"schema_version": "2.0", "workspace_id": "legacy",
        "knowledge_roots": {"wifi": "nested/knowledge"}, "repos": [{"repo_id": repo, "root": str(external)}],
        "architecture": [{"repo_id": repo, "module_root": "."}]}), encoding="utf-8")
    original["code_navigation"]["config_digest"] = validation.sha256_bytes((project / "config.yml").read_bytes())
    link = query.source_links(ctx, [original])[0]
    assert link["current"] == {"base": "repository", "repo_id": repo, "path": "file.c",
        "locator": {"kind": "lines", "start": 2, "end": 2}, "sha256": "b" * 64}


def test_public_gap_has_identifiers_without_returning_source_reference_object():
    original = {"code": "SOURCE_NOT_CURRENT", "card_id": "card", "claim_id": "claim",
                "source_ref": {"source_id": "source", "evidence_ref": "entry", "snapshot_id": "old",
                               "locator": {"kind": "lines", "start": 1, "end": 9}}, "reason": "changed"}
    assert query.public_gaps([original]) == [{"code": "SOURCE_NOT_CURRENT", "card_id": "card", "claim_id": "claim",
        "source_id": "source", "evidence_ref": "entry", "reason": "changed"}]
    assert "source_ref" in original
