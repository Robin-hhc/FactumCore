"""External raw sources keep fixed evidence separate from local observations."""

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
    "dbox_query_contract_helpers", ROOT / "himate-knowledge-wifi-mp/evals/contract_test_support.py"
)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


def source_observation(tmp_path, *, binding="a", matches=True):
    reference = {"evidence_ref": "dbox", "source_id": "external-doc", "snapshot_id": "old",
                 "locator": {"kind": "lines", "start": 1, "end": 2}}
    return {"source_ref": reference, "source_kind": "raw",
            "resource": {"source_id": "external-doc", "kind": "raw",
                         "path": "docs-raw/sources/dbox/topic/source.md"},
            "snapshot_digest": "fixed-snapshot", "sha256": "f" * 64,
            "original_ref": "logs/evidence/published/objects/" + "f" * 64 + ".bin",
            "locator": reference["locator"], "current_source_matches": matches,
            "current_source_sha256": "f" * 64 if matches else "b" * 64,
            "current_source_path": str(tmp_path / "outside/topic/source.md"),
            "current_source_binding": {"config_sha256": binding * 64, "root_token": binding * 64},
            "current_source_observation": {"status": "available"}}


def context(tmp_path, resolved):
    return SimpleNamespace(root=tmp_path, operation="dbox-query", modules={
        "validation": HELPERS.module("validation"),
        "source_operations": SimpleNamespace(resolve_source=lambda *args: resolved)})


@pytest.mark.parametrize("matches", [True, False])
def test_current_address_uses_native_observed_path_and_fixed_evidence(tmp_path, matches):
    query = HELPERS.module("query_runtime")
    source = source_observation(tmp_path, matches=matches)
    link = query.source_links(context(tmp_path, source), [source])[0]
    assert link["evidence"] == {"base": "knowledge_root", "path": source["original_ref"],
                                "locator": source["locator"], "sha256": source["sha256"]}
    assert link["current"] == {"base": "absolute", "path": source["current_source_path"],
                              "sha256": source["current_source_sha256"],
                              "locator": source["locator"] if matches else None}
    assert link["current_source_matches"] is matches
    assert "current_source_binding" not in link


def test_exact_registered_dbox_fallback_has_an_absolute_evidence_address(tmp_path):
    query = HELPERS.module("query_runtime")
    source = source_observation(tmp_path)
    source["original_ref"] = source["current_source_path"]
    ctx = context(tmp_path, source)
    ctx.modules["source_resources"] = HELPERS.module("source_resources")
    link = query.source_links(ctx, [source])[0]
    assert link["evidence"]["base"] == "absolute"
    assert link["evidence"]["path"] == source["current_source_path"]
    assert link["evidence"]["sha256"] == source["current_source_sha256"]


@pytest.mark.parametrize("fault", ["ordinary-resource", "different-path", "changed-bytes", "missing-binding"])
def test_absolute_evidence_is_not_a_general_path_escape(tmp_path, fault):
    query = HELPERS.module("query_runtime")
    source = source_observation(tmp_path)
    source["original_ref"] = source["current_source_path"]
    if fault == "ordinary-resource":
        source["resource"]["path"] = "docs-raw/specs/source.md"
    elif fault == "different-path":
        source["original_ref"] = str(tmp_path / "another/source.md")
    elif fault == "changed-bytes":
        source["current_source_matches"] = False
        source["current_source_sha256"] = "b" * 64
    else:
        source["current_source_binding"] = None
    ctx = context(tmp_path, source)
    ctx.modules["source_resources"] = HELPERS.module("source_resources")
    with pytest.raises(ValueError):
        query.source_links(ctx, [source])


@pytest.mark.parametrize("purpose", ["guidance", "historical", "current", "implementation"])
def test_same_byte_root_switch_is_detected_during_final_refresh(tmp_path, purpose):
    query, runtime = HELPERS.module("query_runtime"), HELPERS.module("runtime")
    previous = source_observation(tmp_path)
    fresh = source_observation(tmp_path, binding="b")
    with pytest.raises(runtime.NodeError) as error:
        query.refresh_sources(context(tmp_path, fresh), [previous], purpose)
    assert error.value.code == "SOURCE_CHANGED_DURING_QUERY"


@pytest.mark.parametrize("purpose,accepted", [("guidance", True), ("historical", True),
                                             ("current", False), ("implementation", False)])
def test_missing_local_root_does_not_destroy_fixed_evidence_or_grant_current_use(tmp_path, purpose, accepted):
    query = HELPERS.module("query_runtime")
    source = source_observation(tmp_path)
    source.update(current_source_matches=None, current_source_sha256=None,
                  current_source_binding=None, current_source_path=None,
                  current_source_observation={"status": "unavailable", "code": "DBOX_CONFIG_REQUIRED"})
    card = {"metadata": {"id": "dbox-card"}, "claims": [{"id": "c1", "usage": purpose,
            "source_records": [source["source_ref"]]}]}
    selected, _, _ = query.qualify_sources(context(tmp_path, source), card, {"c1"}, purpose, {})
    assert selected == ({"c1"} if accepted else set())
    link = query.source_links(context(tmp_path, source), [source])[0]
    assert link["evidence"]["path"] == source["original_ref"]
    assert link["current"] is None and link["current_source_matches"] is None


def public_dbox_case(base):
    """Seed only formal synthetic assets, then exercise the real consumer CLIs."""
    spec = importlib.util.spec_from_file_location(
        "dbox_consumer_public_harness", ROOT / "skills/common/knowledge/hs-knowledge-maintain/tests/conftest.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    harness = fixtures.Harness(base)
    external = base / "外部资料"
    external.mkdir()
    original = b"# External document\nSynthetic fixture statement.\n"
    source = external / "source.md"
    source.write_bytes(original)
    harness.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    harness.run("source", {"operation_id": "configure-dbox", "path": str(external)}, "configure")
    captured = harness.run("source", {"operation_id": "capture-dbox",
        "source_path": "docs-raw/sources/dbox/source.md", "source_id": "external-doc"}, "capture")["data"]
    bundle = harness.record(captured["bundle_ref"])
    for entry in bundle["staged_objects"]:
        harness.write(entry["final_ref"], (harness.root / entry["stage_ref"]).read_bytes())
        (harness.root / entry["stage_ref"]).unlink()
    harness.write("governance/sources.lock.yaml", json.dumps({"schema_version": "2.0",
        "resources": bundle["resources"], "snapshots": bundle["snapshots"]}).encode())
    _, header, body = harness.card("dbox-rule", bundle, lifecycle="stable").decode().split("---", 2)
    metadata = yaml.safe_load(header)
    metadata["scope"] = {"applicability": "universal", "contexts": []}
    template = metadata["claims"][0]
    metadata["claims"] = [{**template, "id": usage, "usage": usage,
                           "evidence_kind": "implementation" if usage == "current" else "design"}
                          for usage in ("guidance", "current", "historical")]
    harness.write("knowledge/rules/dbox-rule.md", ("---\n" + yaml.safe_dump(metadata, sort_keys=False)
        + "---" + body).encode())
    built = harness.run("apply", {"operation_id": "dbox-index"}, "index-build")["data"]
    harness.run("apply", {"operation_id": "dbox-activate", "generation_ref": built["generation_ref"],
                         "expected_active": built["expected_active"]}, "index-activate")
    return harness, source, original


@pytest.fixture(scope="module")
def indexed_dbox(tmp_path_factory):
    return public_dbox_case(tmp_path_factory.mktemp("dbox-query-public"))


@pytest.fixture
def public_case(indexed_dbox):
    harness, source, original = indexed_dbox
    local = harness.root / "docs-raw/sources/dbox.local.yml"
    config = local.read_bytes()
    yield harness, source, original
    local.write_bytes(config)
    source.write_bytes(original)


def test_public_search_and_receipt_read_show_native_current_and_published_evidence(public_case):
    harness, source, original = public_case
    search = harness.run("query", {"operation_id": "dbox-search", "query": "Synthetic",
                                  "purpose": "guidance"}, "search")["data"]
    assert [row["card_id"] for row in search["matches"]] == ["dbox-rule"]
    link = search["matches"][0]["source_links"][0]
    assert link["current"]["base"] == "absolute"
    assert link["current"]["path"] == str(source)
    assert link["current_source_matches"] is True
    assert (harness.root / link["evidence"]["path"]).read_bytes() == original
    assert link["evidence"]["path"].startswith("logs/evidence/published/objects/")
    receipt = harness.record(search["receipt_ref"])
    assert receipt["result"]["matches"][0]["source_links"][0] == link
    read = harness.run("query", {"operation_id": "dbox-read", "receipt_ref": search["receipt_ref"],
                                 "card_id": "dbox-rule"}, "read")["data"]
    assert read["generation_ref"] == search["generation_ref"]
    assert read["source_links"][0] == link


def test_public_missing_mapping_preserves_fixed_evidence_without_current_qualification(public_case):
    harness, _, _ = public_case
    baseline = harness.run("query", {"operation_id": "dbox-current-before", "query": "Synthetic"}, "search")["data"]
    assert baseline["matches"][0]["claim_ids"] == ["current"]
    (harness.root / "docs-raw/sources/dbox.local.yml").unlink()
    for purpose in ("guidance", "historical"):
        response = harness.run("query", {"operation_id": "dbox-no-map-" + purpose,
            "query": "Synthetic", "purpose": purpose}, "search")["data"]
        assert [row["card_id"] for row in response["matches"]] == ["dbox-rule"]
        assert response["matches"][0]["source_links"][0]["current"] is None
    for purpose in ("current", "implementation"):
        response = harness.run("query", {"operation_id": "dbox-no-map-" + purpose,
            "query": "Synthetic", "purpose": purpose}, "search")["data"]
        assert response["matches"] == []
    rebuilt = harness.run("apply", {"operation_id": "dbox-consumer-build"}, "index-build")["data"]
    harness.run("apply", {"operation_id": "dbox-consumer-activate", "generation_ref": rebuilt["generation_ref"],
                         "expected_active": rebuilt["expected_active"]}, "index-activate")


def test_public_query_recovers_exact_current_dbox_when_retained_original_is_missing(public_case):
    harness, source, original = public_case
    lock = yaml.safe_load((harness.root / "governance/sources.lock.yaml").read_bytes())
    retained = harness.root / lock["snapshots"][0]["recovery"]["path"]
    retained_bytes = retained.read_bytes()
    retained.unlink()
    try:
        search = harness.run("query", {"operation_id": "dbox-current-fallback-search", "query": "Synthetic",
                                      "purpose": "guidance"}, "search")["data"]
        link = search["matches"][0]["source_links"][0]
        assert link["evidence"]["base"] == "absolute"
        assert link["evidence"]["path"] == str(source)
        assert Path(link["evidence"]["path"]).read_bytes() == original
        assert link["evidence"]["sha256"] == lock["snapshots"][0]["sha256"]
        read = harness.run("query", {"operation_id": "dbox-current-fallback-read", "receipt_ref": search["receipt_ref"],
                                     "card_id": "dbox-rule"}, "read")["data"]
        assert read["source_links"][0]["evidence"] == link["evidence"]
    finally:
        retained.write_bytes(retained_bytes)


def changing_public_query(harness, request, action, local, replacement, attempt):
    incoming, outgoing = harness.base / (request["operation_id"] + "-input.json"), harness.base / (request["operation_id"] + "-output.json")
    incoming.write_text(json.dumps(request), encoding="utf-8")
    program = """
from pathlib import Path
import runpy
import sys
cli, config, replacement, attempt = sys.argv[1:5]
sys.path.insert(0, str(Path(sys.argv[sys.argv.index("--knowledge-root") + 1]) / "runtime"))
from himate_knowledge import protocol as support
from himate_knowledge.stage_dispatch import run_stage
load_domain = support.domain
def changing_domain(root, expected):
    modules, rules = load_domain(root, expected)
    resolve = modules['source_operations'].resolve_source
    attempts = 0
    def changing_source(ctx, reference, bundle=None):
        nonlocal attempts
        result = resolve(ctx, reference, bundle=bundle)
        attempts += 1
        if attempts == int(attempt):
            Path(config).write_bytes(bytes.fromhex(replacement))
        return result
    modules['source_operations'].resolve_source = changing_source
    return modules, rules
support.domain = changing_domain
sys.argv = [cli, *sys.argv[5:]]
raise SystemExit(run_stage('query', sys.argv[1:]))
"""
    process = subprocess.run([sys.executable, "-X", "utf8", "-c", program,
        str(harness.packages / "hs-knowledge-query/scripts/cli.py"), str(local), replacement.hex(), str(attempt),
        "--knowledge-root", str(harness.root), "--input", str(incoming), "--output", str(outgoing),
        "--action", action], capture_output=True, timeout=60)
    assert "Traceback" not in process.stderr.decode(), process.stderr.decode()
    return process, json.loads(outgoing.read_bytes())


@pytest.mark.parametrize("action,attempt", [("search", 1), ("search", 2), ("read", 1), ("read", 2)])
@pytest.mark.parametrize("change", ["same-byte-root", "source-bytes"])
def test_public_query_rejects_source_change_within_the_call(public_case, action, attempt, change):
    harness, source, original = public_case
    if change == "same-byte-root":
        other = harness.base / ("same-bytes-" + action + str(attempt))
        other.mkdir()
        (other / "source.md").write_bytes(original)
        target = harness.root / "docs-raw/sources/dbox.local.yml"
        replacement = yaml.safe_dump({"schema_version": "1.0", "path": str(other)}).encode()
    else:
        target, replacement = source, b"# Changed document\nA different synthetic statement.\n"
    request = {"operation_id": "dbox-switch-" + action + str(attempt) + change, "purpose": "guidance"}
    request.update({"query": "Synthetic"} if action == "search" else {"card_id": "dbox-rule"})
    process, response = changing_public_query(harness, request, action, target, replacement, attempt)
    assert process.returncode == 3, response
    assert response["diagnostics"][0]["code"] == "SOURCE_CHANGED_DURING_QUERY"
    assert response["data"] == {}


def test_public_receipt_bound_later_read_observes_new_root_without_rebinding_formal_source(public_case):
    harness, _, original = public_case
    search = harness.run("query", {"operation_id": "dbox-before-switch", "query": "Synthetic",
                                  "purpose": "guidance"}, "search")["data"]
    other = harness.base / "later-root"
    other.mkdir()
    replacement = other / "source.md"
    replacement.write_bytes(original)
    lock_before = (harness.root / "governance/sources.lock.yaml").read_bytes()
    harness.run("source", {"operation_id": "dbox-switch-config", "path": str(other)}, "configure")
    read = harness.run("query", {"operation_id": "dbox-after-switch", "receipt_ref": search["receipt_ref"],
                                 "card_id": "dbox-rule"}, "read")["data"]
    assert read["source_links"][0]["current"]["path"] == str(replacement)
    assert read["source_links"][0]["current_source_matches"] is True
    assert (harness.root / "governance/sources.lock.yaml").read_bytes() == lock_before
