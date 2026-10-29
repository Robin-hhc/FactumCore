"""Fixed evidence and current symbolic navigation remain separate public data."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "navigation_contract_helpers", ROOT / "himate-knowledge-wifi-mp/evals/contract_test_support.py"
)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture
def code_context(tmp_path):
    root = tmp_path / "knowledge-root"
    (root / "governance").mkdir(parents=True)
    code = tmp_path / "main/shared/file.c"
    code.parent.mkdir(parents=True)
    old = b"int selected(void) { return 1; }\n"
    code.write_bytes(b"// inserted line\nint selected(void) { return 2; }\n")
    config = {"schema_version": "2.0", "workspace_id": "navigation-fixture",
              "knowledge_roots": {"wifi": root.name}, "code_root": "main",
              "modules": [{"path": "shared", "chips": ["chip12"], "sides": ["host"]}]}
    (tmp_path / "config.yml").write_bytes(canonical(config))
    repo_id = "repo-" + sha(b"main/shared")[:16]
    evidence = root / "logs/evidence"
    evidence.mkdir(parents=True)
    (evidence / "source.c").write_bytes(old)
    (evidence / "source.txt").write_bytes(old)
    locators = canonical({"locators": [{"kind": "lines", "start": 1, "end": 1,
                                       "text": "int selected(void) { return 1; }"}]})
    (evidence / "locators.json").write_bytes(locators)
    snapshot = {"source_id": "code", "snapshot_id": "code-v1", "sha256": sha(old),
                "bytes": len(old), "format": ".c",
                "recovery": {"method": "evidence_object", "path": "logs/evidence/source.c"},
                "extraction": {"text_ref": "logs/evidence/source.txt",
                               "locator_ref": "logs/evidence/locators.json",
                               "text_sha256": sha(old), "locator_sha256": sha(locators),
                               "extractor": "code-utf8:1", "limitations": []}}
    lock = {"schema_version": "2.0", "resources": [{"source_id": "code", "kind": "code",
            "repo_id": repo_id, "path": "file.c"}], "snapshots": [snapshot]}
    (root / "governance/sources.lock.yaml").write_bytes(canonical(lock))
    reference = {"evidence_ref": "e1", "source_id": "code", "snapshot_id": "code-v1",
                 "locator": {"kind": "lines", "start": 1, "end": 1},
                 "code_ref": {"kind": "function", "name": "selected", "scope": [],
                              "parameter_types": []}}
    modules = {name: HELPERS.module(name) for name in
               ("source_operations", "source_resources", "query_runtime", "runtime", "validation")}
    context = SimpleNamespace(root=root, modules=modules, operation="navigation",
                              rules={"schemas": {"workspace": json.loads(
                                  (ROOT / "himate-knowledge-wifi-mp/governance/schemas/workspace.schema.json").read_bytes())}})
    return context, reference, old, code


def test_source_resolution_retains_old_evidence_and_returns_current_navigation(code_context):
    context, reference, old, code = code_context
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert resolved["text"] == old.decode()
    assert resolved["sha256"] == sha(old)
    assert resolved["locator"] == {"kind": "lines", "start": 1, "end": 1}
    assert resolved["source_ref"] == reference
    assert resolved["current_source_matches"] is False
    assert resolved["code_navigation"]["status"] == "resolved"
    assert resolved["code_navigation"]["sha256"] == sha(code.read_bytes())
    assert resolved["code_navigation"]["range"]["start_line"] == 2


@pytest.mark.parametrize("current, status", [
    (b"// different navigation file\nint selected(void) { return 3; }\n", "resolved"),
    (b"int selected(void) { return 2; }\nint selected(void) { return 3; }\n", "ambiguous"),
    (None, "missing"),
])
def test_public_link_address_hash_and_match_follow_the_actual_navigation_file(code_context, current, status):
    context, reference, old, resource_file = code_context
    resource_file.write_bytes(old)
    navigation_file = resource_file.with_name("redirected.c")
    reference["locator"]["path"] = navigation_file.name
    if current is not None:
        navigation_file.write_bytes(current)
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert resolved["current_source_matches"] is True
    assert resolved["current_source_sha256"] == sha(old)
    assert resolved["code_navigation"]["status"] == status
    link = context.modules["query_runtime"].source_links(context, [resolved])[0]
    assert link["evidence"]["sha256"] == sha(old)
    if current is None:
        assert link["current"] is None
        assert link["current_source_matches"] is None
    else:
        assert link["current"] == {"base": "workspace", "path": "main/shared/redirected.c",
            "locator": {"kind": "lines", "start": 2, "end": 2} if status == "resolved" else None,
            "sha256": sha(current)}
        assert link["current_source_matches"] is False
    assert resolved["current_source_matches"] is True


def test_public_link_uses_available_navigation_when_the_resource_file_is_missing(code_context):
    context, reference, _, resource_file = code_context
    navigation_file = resource_file.with_name("redirected.c")
    navigation_file.write_bytes(resource_file.read_bytes())
    resource_file.unlink()
    reference["locator"]["path"] = navigation_file.name
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert resolved["current_source_matches"] is None
    link = context.modules["query_runtime"].source_links(context, [resolved])[0]
    assert link["current"]["path"] == "main/shared/redirected.c"
    assert link["current"]["sha256"] == sha(navigation_file.read_bytes())
    assert link["current_source_matches"] is False


@pytest.mark.parametrize("current", [None, b"int renamed(void) { return 2; }\n",
                                   b"int selected(void) { return 2; }\nint selected(void) { return 3; }\n"])
def test_source_resolution_preserves_old_evidence_when_current_navigation_is_not_unique(code_context, current):
    context, reference, old, code = code_context
    if current is None:
        code.unlink()
    else:
        code.write_bytes(current)
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert resolved["text"] == old.decode()
    assert resolved["sha256"] == sha(old)
    assert resolved["code_navigation"]["status"] in {"missing", "ambiguous"}
    assert any("navigation" in limitation for limitation in resolved["limitations"])


def test_current_navigation_never_recovers_corrupt_fixed_evidence(code_context):
    context, reference, _, _ = code_context
    (context.root / "logs/evidence/source.c").write_bytes(b"corrupt fixed evidence")
    with pytest.raises(context.modules["runtime"].NodeError) as error:
        context.modules["source_operations"].resolve_source(context, reference)
    assert error.value.code == "SOURCE_INTEGRITY_ERROR"


def test_legacy_source_resolution_does_not_add_symbol_navigation(code_context):
    context, reference, old, _ = code_context
    reference.pop("code_ref")
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert "code_navigation" not in resolved
    assert resolved["text"] == old.decode()
    assert resolved["current_source_matches"] is False


def test_current_code_validation_reuses_the_operation_symbol_parse(code_context, monkeypatch):
    import tree_sitter

    context, reference, old, code = code_context
    code.write_bytes(old)
    parser = tree_sitter.Parser
    constructions = []

    def counted_parser(*args, **kwargs):
        constructions.append(True)
        return parser(*args, **kwargs)

    monkeypatch.setattr(tree_sitter, "Parser", counted_parser)
    resolved = context.modules["source_operations"].resolve_source(context, reference)
    assert resolved["code_navigation"]["status"] == "resolved"
    assert len(constructions) == 1
    scope = {"applicability": "universal", "contexts": []}
    claim = {"id": "c1", "scope": scope, "source_records": [reference]}
    card = {"metadata": {"id": "code", "scope": scope, "sources": [reference]}, "claims": [claim]}
    context.modules["query_runtime"].validate_live_code_claim(context, card, claim)
    assert len(constructions) == 1


def navigation(*, line=1, parameters=(), status="resolved"):
    match = {"kind": "function", "name": "selected", "scope": [],
             "parameter_types": list(parameters), "qualifiers": [],
             "range": {"start_line": line, "end_line": line}}
    return {"status": status, "code": "CODE_SYMBOL_" + status.upper(), "reason": "fixture",
            "path": "file.c", "sha256": str(line) * 64,
            "matches": [match] if status == "resolved" else [],
            **({"range": match["range"]} if status == "resolved" else {})}


def refresh_context(fresh):
    return SimpleNamespace(operation="refresh", modules={"source_operations": SimpleNamespace(
        resolve_source=lambda *args: fresh)})


def resolved_source(nav, *, code_ref=True):
    reference = {"evidence_ref": "code", "source_id": "code", "snapshot_id": "old",
                 "locator": {"kind": "lines", "start": 1, "end": 1}}
    if code_ref:
        reference["code_ref"] = {"kind": "function", "name": "selected", "scope": []}
    return {"source_ref": reference, "snapshot_digest": "old-snapshot",
            "current_source_sha256": nav["sha256"], "current_source_matches": False,
            "code_navigation": nav}


def test_guidance_refresh_accepts_same_symbol_with_new_body_and_position():
    query = HELPERS.module("query_runtime")
    old, fresh = resolved_source(navigation()), resolved_source(navigation(line=3))
    assert query.refresh_sources(refresh_context(fresh), [old], "guidance", {"code"}) == [fresh]


@pytest.mark.parametrize("fresh_status", ["resolved", "ambiguous"])
def test_guidance_refresh_retries_if_initially_missing_navigation_changes_status(fresh_status):
    query, runtime = HELPERS.module("query_runtime"), HELPERS.module("runtime")
    old = resolved_source(navigation(status="missing"))
    fresh = resolved_source(navigation(status=fresh_status))
    with pytest.raises(runtime.NodeError) as error:
        query.refresh_sources(refresh_context(fresh), [old], "guidance", {"code"})
    assert error.value.code == "SOURCE_CHANGED_DURING_QUERY"


@pytest.mark.parametrize("new_navigation", [navigation(status="missing"), navigation(status="ambiguous"),
                                          navigation(status="unavailable"), navigation(parameters=("int",))])
def test_guidance_refresh_retries_if_previously_resolved_symbol_is_no_longer_the_same(new_navigation):
    query, runtime = HELPERS.module("query_runtime"), HELPERS.module("runtime")
    old, fresh = resolved_source(navigation()), resolved_source(new_navigation)
    with pytest.raises(runtime.NodeError, match="source changed") as error:
        query.refresh_sources(refresh_context(fresh), [old], "guidance", {"code"})
    assert error.value.code == "SOURCE_CHANGED_DURING_QUERY"


@pytest.mark.parametrize("purpose,code_ref", [("current", True), ("implementation", True),
                                            ("guidance", False), ("historical", True)])
def test_symbol_navigation_does_not_relax_other_freshness_requirements(purpose, code_ref):
    query, runtime = HELPERS.module("query_runtime"), HELPERS.module("runtime")
    old = resolved_source(navigation(), code_ref=code_ref)
    fresh = resolved_source(navigation(line=3), code_ref=code_ref)
    with pytest.raises(runtime.NodeError):
        query.refresh_sources(refresh_context(fresh), [old], purpose, {"code"})


@pytest.mark.parametrize("status", ["missing", "ambiguous", "unavailable"])
def test_guidance_keeps_fixed_document_claim_and_reports_navigation_gap(status):
    query = HELPERS.module("query_runtime")
    source = resolved_source(navigation(status=status))
    context = refresh_context(source)
    card = {"metadata": {"id": "design"}, "claims": [{"id": "c1", "usage": "guidance",
            "source_records": [source["source_ref"]]}]}
    accepted, sources, gaps = query.qualify_sources(context, card, {"c1"}, "guidance", {}, {"code"})
    assert accepted == {"c1"}
    assert sources[0]["code_navigation"]["status"] == status
    assert gaps == [{"code": "CODE_SYMBOL_" + status.upper(), "card_id": "design", "claim_id": "c1",
                     "source_ref": source["source_ref"], "reason": "fixture"}]


def public_code_navigation_case(tmp_path):
    directory = ROOT / "skills/common/knowledge/hs-knowledge-maintain/tests"
    spec = importlib.util.spec_from_file_location("query_navigation_public_harness", directory / "conftest.py")
    harness_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness_module)
    spec = importlib.util.spec_from_file_location("query_navigation_public_code", directory / "test_reference_audit.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    harness = harness_module.Harness(tmp_path)
    source, old, _, _ = fixture.code_fixture(harness, ("guidance",))
    path = harness.root / "knowledge/rules/audit-guidance.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(header)
    selector = {"kind": "function", "name": "selected_fixture", "scope": [], "parameter_types": []}
    metadata["sources"][0]["code_ref"] = selector
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
    built = harness.run("apply", {"operation_id": "symbol-index"}, "index-build")["data"]
    return harness, source, old, selector, built


def test_public_query_links_old_evidence_and_current_symbol_without_source_objects(tmp_path):
    harness, source, old, selector, built = public_code_navigation_case(tmp_path)
    source.write_bytes(b"// shifted navigation\n" + old.replace(b"1", b"2"))
    response = harness.run("query", {"operation_id": "symbol-search", "query": "Synthetic",
        "purpose": "guidance", "generation_ref": built["generation_ref"], "evaluation": True,
        "context": {"target_id": "chip12-host", "chip": "chip12", "side": "host"}}, "search")
    matches = response["data"]["matches"]
    assert [match["card_id"] for match in matches] == ["audit-guidance"]
    assert "sources" not in matches[0]
    result = matches[0]["source_links"][0]
    assert result["evidence"]["locator"] == {"kind": "lines", "start": 1, "end": 1}
    assert result["evidence"]["base"] == "knowledge_root"
    assert (harness.root / result["evidence"]["path"]).read_bytes() == old
    assert result["evidence"]["sha256"] == sha(old)
    assert result["current"]["base"] == "workspace"
    assert result["current"]["path"] == "main/shared/file.c"
    assert result["current"]["locator"] == {"kind": "lines", "start": 2, "end": 2}
    assert result["current"]["sha256"] == sha(source.read_bytes())
    assert result["navigation_status"] == "resolved" and result["current_source_matches"] is False
    assert not {"source_ref", "code_ref", "snapshot", "resource", "text", "bytes_b64"} & result.keys()
    assert matches[0]["card_ref"] == harness.record(built["generation_ref"])["documents"]["audit-guidance"]["blob_ref"]


def query_with_source_change(harness, source, request, action, *, change_after, new_source):
    incoming, outgoing = harness.base / "changing-query-input.json", harness.base / "changing-query-output.json"
    incoming.write_text(json.dumps(request), encoding="utf-8")
    program = """
from pathlib import Path
import runpy
import sys
cli, source, change_after, replacement = sys.argv[1:5]
sys.path.insert(0, str(Path(cli).parent))
import support
load_domain = support.domain

def changing_domain(root, expected):
    modules, rules = load_domain(root, expected)
    resolve = modules['source_operations'].resolve_source
    attempts = 0
    def changing_source(ctx, reference, bundle=None):
        nonlocal attempts
        result = resolve(ctx, reference, bundle=bundle)
        attempts += 1
        if attempts == int(change_after):
            Path(source).write_bytes(bytes.fromhex(replacement))
        return result
    modules['source_operations'].resolve_source = changing_source
    return modules, rules

support.domain = changing_domain
sys.argv = [cli, *sys.argv[5:]]
runpy.run_path(cli, run_name='__main__')
"""
    process = subprocess.run([
        sys.executable, "-c", program, str(harness.packages / "hs-knowledge-query/scripts/cli.py"),
        str(source), str(change_after), new_source.hex(),
        "--knowledge-root", str(harness.root), "--input", str(incoming), "--output", str(outgoing),
        "--action", action,
    ], capture_output=True, timeout=60)
    assert "Traceback" not in process.stderr.decode(), process.stderr.decode()
    return process, json.loads(outgoing.read_bytes())


@pytest.mark.parametrize("replacement", [b"int selected_fixture(void) { return 2; }\n",
    b"int selected_fixture(void) { return 2; }\nint selected_fixture(void) { return 3; }\n"])
def test_public_search_retries_navigation_change_between_candidate_and_fresh_evaluators(tmp_path, replacement):
    harness, source, _, _, built = public_code_navigation_case(tmp_path)
    source.write_bytes(b"int renamed(void) { return 2; }\n")
    request = {"operation_id": "changing-search", "query": "Synthetic", "purpose": "guidance",
               "generation_ref": built["generation_ref"], "evaluation": True,
               "context": {"target_id": "chip12-host", "chip": "chip12", "side": "host"}}
    process, response = query_with_source_change(
        harness, source, request, "search", change_after=1, new_source=replacement)
    assert process.returncode == 3, {"status": response["status"], "data": response["data"]}
    assert response["diagnostics"][0]["code"] == "SOURCE_CHANGED_DURING_QUERY"
    assert response["data"] == {}


def test_public_read_retries_navigation_change_during_final_eligibility_evaluation(tmp_path):
    harness, source, _, _, built = public_code_navigation_case(tmp_path)
    request = {"operation_id": "changing-read", "card_id": "audit-guidance", "purpose": "guidance",
               "generation_ref": built["generation_ref"], "evaluation": True,
               "context": {"target_id": "chip12-host", "chip": "chip12", "side": "host"}}
    process, response = query_with_source_change(
        harness, source, request, "read", change_after=2,
        new_source=b"int renamed(void) { return 2; }\n")
    assert process.returncode == 3, {"status": response["status"], "data": response["data"]}
    assert response["diagnostics"][0]["code"] == "SOURCE_CHANGED_DURING_QUERY"
    assert response["data"] == {}
