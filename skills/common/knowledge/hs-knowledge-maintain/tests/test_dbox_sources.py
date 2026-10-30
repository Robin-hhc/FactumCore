"""Read-only source inspection distinguishes local access from lost evidence."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "dbox_maintenance_contract_helpers", ROOT / "himate-knowledge-wifi-mp/evals/contract_test_support.py"
)
HELPERS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPERS)


@pytest.fixture
def inspection(tmp_path):
    root = tmp_path / "knowledge-root"
    reference = {"evidence_ref": "dbox", "source_id": "external-doc", "snapshot_id": "old",
                 "locator": {"kind": "lines", "start": 1, "end": 2}}
    claims = [{"id": usage, "usage": usage, "source_records": [reference]}
              for usage in ("guidance", "current", "historical")]
    card = {"metadata": {"id": "dbox-card", "relations": [], "sources": [reference]},
            "claims": claims}
    path = root / "knowledge/rules/dbox.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic card transport")
    resolved = {"current_source_matches": None, "current_source_sha256": None,
                "current_source_binding": None, "current_source_path": None,
                "current_source_observation": {"status": "unavailable", "code": "DBOX_CONFIG_REQUIRED"}}
    modules = {"validation": HELPERS.module("validation"),
               "source_operations": SimpleNamespace(resolve_source=lambda *args: resolved),
               "knowledge": SimpleNamespace(decode_card=lambda *args: card)}
    context = SimpleNamespace(root=root, operation="dbox-inspection", modules=modules,
                              args=SimpleNamespace(rules_digest="synthetic"), rules={},
                              record=lambda ref, kind: json.loads((root / ref).read_bytes()))
    return context, resolved


@pytest.mark.parametrize("code", ["DBOX_CONFIG_REQUIRED", "DBOX_ROOT_UNAVAILABLE", "SOURCE_READ_FAILED"])
def test_local_source_unavailable_is_distinct_from_changed_or_lost_fixed_evidence(inspection, code):
    context, resolved = inspection
    resolved["current_source_observation"]["code"] = code
    result, phase = HELPERS.module("maintenance").inspect_context(context)
    assert phase == "inspected"
    assert {(row["claim_id"], row["reason"], row["details"]) for row in result["affected_claims"]} == {
        (usage, "source_current_unavailable", code) for usage in ("guidance", "current")}
    assert result["source_observations"][0]["current_source_observation"] == resolved["current_source_observation"]
    assert result["source_observations"][0]["claim_ids"] == ["guidance", "current", "historical"]
    assert not (context.root / "logs/events").exists()


def test_actual_source_byte_change_keeps_existing_restrictions(inspection):
    context, resolved = inspection
    resolved.update(current_source_matches=False, current_source_sha256="b" * 64,
                    current_source_observation={"status": "available"})
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert {(row["claim_id"], row["reason"]) for row in result["affected_claims"]} == {
        (usage, "source_changed") for usage in ("guidance", "current")}


def test_missing_fixed_evidence_still_restricts_historical_usage(inspection):
    context, _ = inspection
    def missing_evidence(*args):
        raise HELPERS.module("runtime").NodeError("SOURCE_INPUT_UNAVAILABLE", "Fixed original is missing")
    context.modules["source_operations"].resolve_source = missing_evidence
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert {(row["claim_id"], row["reason"]) for row in result["affected_claims"]} == {
        (usage, "source_unavailable") for usage in ("guidance", "current", "historical")}


def test_unavailable_local_mapping_does_not_clear_shared_semantic_restriction(inspection):
    context, _ = inspection
    path = context.root / "logs/events/state.json"
    path.parent.mkdir(parents=True)
    raw = json.dumps({"validity_epoch": 1, "blocked_claims": [{"card_id": "dbox-card",
        "claim_id": "historical", "reason": "semantic_review_required"}]}).encode()
    path.write_bytes(raw)
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert any(row["claim_id"] == "historical" and row["reason"] == "semantic_review_required"
               for row in result["affected_claims"])
    assert path.read_bytes() == raw


def test_internal_raw_scope_does_not_observe_unselected_dbox_or_clear_durable_blocks(inspection):
    context, _ = inspection
    context.request = {"dbox_observation_scope": []}
    resources = HELPERS.module("source_resources")
    context.modules["source_resources"] = SimpleNamespace(is_dbox_path=resources.is_dbox_path,
        read_source_lock=lambda *args: {"resources": [{"source_id": "external-doc", "kind": "raw",
                                                     "path": "docs-raw/sources/dbox/source.md"}]})
    def unexpected_read(*args):
        raise AssertionError("An ordinary raw scan must not observe this dbox source")
    context.modules["source_operations"].resolve_source = unexpected_read
    state = context.root / "logs/events/state.json"
    state.parent.mkdir(parents=True)
    before = json.dumps({"validity_epoch": 1, "blocked_claims": [{"card_id": "dbox-card",
        "claim_id": "current", "source_id": "external-doc", "reason": "source_changed"}]}).encode()
    state.write_bytes(before)
    result, _ = HELPERS.module("maintenance").inspect_context(context)
    assert [(row["claim_id"], row["reason"]) for row in result["affected_claims"]] == [("current", "source_changed")]
    assert result["coverage"]["all_sources_checked"] is False
    assert state.read_bytes() == before


@pytest.fixture(scope="module")
def public_inspection(tmp_path_factory):
    spec = importlib.util.spec_from_file_location(
        "dbox_maintenance_public_source_fixture",
        ROOT / "skills/common/knowledge/hs-knowledge-query/tests/test_dbox_sources.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    return fixtures.public_dbox_case(tmp_path_factory.mktemp("dbox-maintenance-public"))


@pytest.fixture
def public_case(public_inspection):
    harness, source, original = public_inspection
    local = harness.root / "docs-raw/sources/dbox.local.yml"
    config = local.read_bytes()
    yield harness, source, original
    local.write_bytes(config)
    source.write_bytes(original)


def formal_bytes(harness):
    paths = [harness.root / "governance/sources.lock.yaml"]
    for prefix in ("knowledge", "logs/events"):
        paths.extend(path for path in (harness.root / prefix).rglob("*") if path.is_file())
    return {path.relative_to(harness.root).as_posix(): path.read_bytes() for path in paths}


def test_public_inspect_distinguishes_missing_mapping_without_shared_writes(public_case):
    harness, source, _ = public_case
    before = formal_bytes(harness)
    (harness.root / "docs-raw/sources/dbox.local.yml").unlink()
    result = harness.run("maintain", {"operation_id": "dbox-missing-inspect"}, "inspect-context")["data"]
    assert {(row["claim_id"], row["reason"], row["details"]) for row in result["affected_claims"]} == {
        (usage, "source_current_unavailable", "DBOX_CONFIG_REQUIRED") for usage in ("guidance", "current")}
    assert result["source_observations"][0]["current_source_observation"] == {
        "status": "unavailable", "code": "DBOX_CONFIG_REQUIRED"}
    assert str(source.parent) not in json.dumps(result)
    assert formal_bytes(harness) == before


def test_public_inspect_reports_actual_dbox_change_and_keeps_history(public_case):
    harness, source, _ = public_case
    before = formal_bytes(harness)
    source.write_bytes(b"# Changed document\nA different synthetic statement.\n")
    result = harness.run("maintain", {"operation_id": "dbox-changed-inspect"}, "inspect-context")["data"]
    assert {(row["claim_id"], row["reason"]) for row in result["affected_claims"]} == {
        (usage, "source_changed") for usage in ("guidance", "current")}
    assert result["source_observations"][0]["current_source_observation"]["status"] == "available"
    assert formal_bytes(harness) == before


def test_public_same_bytes_in_new_root_do_not_register_a_team_source_change(public_case):
    harness, _, original = public_case
    before = formal_bytes(harness)
    other = harness.base / "relocated"
    other.mkdir()
    (other / "source.md").write_bytes(original)
    harness.run("source", {"operation_id": "dbox-relocate", "path": str(other)}, "configure")
    result = harness.run("maintain", {"operation_id": "dbox-relocated-inspect"}, "inspect-context")["data"]
    assert result["affected_claims"] == []
    assert result["source_observations"][0]["current_source_matches"] is True
    assert formal_bytes(harness) == before


def ordinary_raw_call(harness, operation, action):
    incoming, outgoing = harness.base / (operation + "-input.json"), harness.base / (operation + "-output.json")
    trace = harness.base / (operation + "-dbox-calls.json")
    incoming.write_text(json.dumps({"operation_id": operation, "source": "docs-raw/specs"}), encoding="utf-8")
    program = """
from pathlib import Path
import json
import runpy
import sys
cli, trace = sys.argv[1:3]
calls = []
def profile(frame, event, value):
    if event == 'call' and Path(frame.f_code.co_filename).name == 'source_resources.py':
        if frame.f_code.co_name in {'read_dbox', 'dbox_root'}:
            calls.append(frame.f_code.co_name)
sys.path.insert(0, str(Path(cli).parent))
sys.argv = [cli, *sys.argv[3:]]
sys.setprofile(profile)
try:
    runpy.run_path(cli, run_name='__main__')
finally:
    sys.setprofile(None)
    Path(trace).write_text(json.dumps(calls), encoding='utf-8')
"""
    process = subprocess.run([sys.executable, "-X", "utf8", "-c", program,
        str(harness.packages / "hs-knowledge-source/scripts/cli.py"), str(trace),
        "--knowledge-root", str(harness.root), "--input", str(incoming), "--output", str(outgoing),
        "--action", action], capture_output=True, timeout=60)
    response = json.loads(outgoing.read_bytes())
    assert process.returncode == 0, (response, process.stderr.decode())
    assert json.loads(trace.read_bytes()) == [], "Explicit ordinary raw scope read unrelated dbox state"
    return response


@pytest.mark.parametrize("change", ["unconfigured", "changed"])
def test_public_explicit_ordinary_raw_scope_ignores_unrelated_current_dbox(public_case, change):
    harness, source, _ = public_case
    if change == "unconfigured":
        (harness.root / "docs-raw/sources/dbox.local.yml").unlink()
    else:
        source.write_bytes(b"# Changed external document\nUnrelated changed statement.\n")
    harness.write("docs-raw/specs/current.md", b"# Ordinary source\nSynthetic ordinary statement.\n")
    scanned = ordinary_raw_call(harness, "ordinary-scan-" + change, "scan")["data"]
    inventory = harness.record(scanned["scan_ref"])
    assert inventory["current_context"]["affected_claims"] == []
    assert inventory["current_context"].get("source_observations", []) == []
    prepared = ordinary_raw_call(harness, "ordinary-run-" + change, "run")
    assert prepared["phase"] == "prepared"
    assert prepared["data"].get("context_gaps", []) == []
