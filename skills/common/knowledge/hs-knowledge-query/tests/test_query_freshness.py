"""Public queries distinguish a stale active index from retained receipt reads."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "query_freshness_fixture", ROOT / "himate-knowledge-wifi-mp/evals/pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_new_formal_queries_reject_retired_card_until_index_activation(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    original = b"# Fixture\nCapture marker is an explicit synthetic rule.\n"
    bundle_ref, bundle = p.capture("create", original)
    view_ref = p.view("create", bundle_ref, "retired-rule", p.card("retired-rule", bundle))
    p.apply("create", view_ref)
    first = p.call("knowledge-index-build", {"operation_id": "first-build"})["data"]
    p.call("knowledge-index-build", {"operation_id": "first-activate", **first}, "activate")
    initial = p.call("knowledge-query", {"operation_id": "initial-search", "query": "capture"})["data"]
    assert [row["card_id"] for row in initial["matches"]] == ["retired-rule"]
    active_path = p.root / "artifacts/indexes/local/active.json"
    original_active = active_path.read_bytes()

    retire_bundle_ref, _ = p.capture("retire", original)
    planned = p.call("knowledge-change-plan", {
        "operation_id": "retire", "bundle_ref": retire_bundle_ref,
        "decisions": [{"candidate_id": "retire-rule", "decision": "deprecate",
                       "reason": "Explicit synthetic user retirement request",
                       "replaces": ["retired-rule"], "card_inputs": []}],
    })
    retired_view_ref = p.call("knowledge-view-materialize", {
        "operation_id": "retire", "plan_ref": planned["data"]["plan_ref"],
    })["data"]["view_ref"]
    p.apply("retire", retired_view_ref)
    assert b"lifecycle: deprecated" in (p.root / "knowledge/rules/retired-rule.md").read_bytes()
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == original

    for action, payload in (
        ("search", {"query": "capture"}),
        ("receipt", {"query": "capture", "purpose": "guidance"}),
        ("read", {"card_id": "retired-rule", "purpose": "implementation"}),
    ):
        refused = p.call("knowledge-query", {
            "operation_id": "stale-" + action, **payload,
        }, action, expected=3)
        assert refused["status"] == "blocked"
        assert refused["diagnostics"][0]["code"] == "INDEX_STALE"
        assert refused["data"] == {}
    assert active_path.read_bytes() == original_active

    # Existing receipts retain their exact generation; historical and explicit
    # evaluation requests keep their documented snapshot semantics.
    retained = p.call("knowledge-query", {
        "operation_id": "retained-read", "receipt_ref": initial["receipt_ref"],
        "card_id": "retired-rule",
    }, "read")["data"]
    assert retained["generation_ref"] == first["generation_ref"]
    assert [row["id"] for row in retained["claims"]] == ["c1"]
    history = p.call("knowledge-query", {
        "operation_id": "historical-search", "purpose": "historical", "query": "capture",
    })["data"]
    assert [row["card_id"] for row in history["matches"]] == ["retired-rule"]
    evaluation = p.call("knowledge-query", {
        "operation_id": "candidate-evaluation", "evaluation": True,
        "generation_ref": first["generation_ref"], "query": "capture",
    })["data"]
    assert [row["card_id"] for row in evaluation["matches"]] == ["retired-rule"]

    second = p.call("knowledge-index-build", {"operation_id": "second-build"})["data"]
    p.call("knowledge-index-build", {"operation_id": "second-activate", **second}, "activate")
    fresh = p.call("knowledge-query", {"operation_id": "fresh-search", "query": "capture"})["data"]
    assert fresh["matches"] == []
    assert fresh["generation_ref"] == second["generation_ref"]


def test_formal_bytes_changing_during_read_are_a_stale_index_not_invalid_input(tmp_path):
    p = FIXTURE.Pipeline(tmp_path)
    p.write("knowledge/index.md", b"# Empty synthetic knowledge\n")
    generation = p.call("knowledge-index-build", {"operation_id": "build"})["data"]
    p.call("knowledge-index-build", {"operation_id": "activate", **generation}, "activate")
    target = p.root / "knowledge/index.md"
    incoming, outgoing = tmp_path / "race-input.json", tmp_path / "race-output.json"
    incoming.write_bytes(FIXTURE.canonical({"operation_id": "concurrent-read", "query": "capture"}))
    # Deterministic I/O boundary: another writer changes the formal file after
    # one read has observed the original bytes. The real CLI and checks run.
    program = """
from pathlib import Path
import runpy
import sys
target, cli = Path(sys.argv[1]).resolve(), sys.argv[2]
read_bytes = Path.read_bytes
changed = False
def concurrent_read(path):
    global changed
    raw = read_bytes(path)
    if not changed and path.samefile(target):
        changed = True
        target.write_bytes(raw + b'\\n# Concurrent synthetic edit\\n')
    return raw
Path.read_bytes = concurrent_read
sys.path.insert(0, str(Path(cli).parent))
sys.argv = sys.argv[2:]
runpy.run_path(cli, run_name='__main__')
"""
    completed = subprocess.run([
        sys.executable, "-c", program, str(target),
        str(p.skills / "hs-knowledge-query/scripts/cli.py"),
        "--input", str(incoming), "--output", str(outgoing),
        "--knowledge-root", str(p.root), "--action", "search",
    ], capture_output=True, timeout=60)
    response = json.loads(outgoing.read_bytes())
    assert response["status"] == "blocked", response
    assert response["diagnostics"][0]["code"] == "INDEX_STALE", response
    assert completed.returncode == 3, completed.stderr
    assert response["data"] == {}
    assert b"Concurrent synthetic edit" in target.read_bytes()
