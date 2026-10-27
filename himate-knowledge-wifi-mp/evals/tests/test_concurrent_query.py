"""Single-writer/multiple-reader behavior through real isolated node CLIs."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "concurrent_query_fixture", ROOT / "himate-knowledge-wifi-mp/evals/pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_independent_queries_keep_receipt_generation_during_activation(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = pipeline.capture("seed", b"# Fixture\nCapture concurrency marker.\n")
    view = pipeline.view("seed", bundle_ref, "concurrent-rule", pipeline.card("concurrent-rule", bundle))
    pipeline.apply("seed", view)
    first = pipeline.call("knowledge-index-build", {"operation_id": "build-first"})["data"]
    pipeline.call("knowledge-index-build", {"operation_id": "activate-first",
        "generation_ref": first["generation_ref"], "expected_active": None}, "activate")
    second = pipeline.call("knowledge-index-build", {"operation_id": "build-second"})["data"]
    ready = Barrier(3)

    def search(number):
        incoming = tmp_path / f"parallel-input-{number}.json"
        outgoing = tmp_path / f"parallel-output-{number}.json"
        incoming.write_bytes(FIXTURE.canonical({
            "operation_id": f"parallel-search-{number}", "query": "capture", "purpose": "current",
        }))
        ready.wait(timeout=10)
        completed = subprocess.run([
            sys.executable, str(pipeline.skills / "hs-knowledge-query/scripts/cli.py"),
            "--input", str(incoming), "--output", str(outgoing),
            "--knowledge-root", str(pipeline.root), "--rules-digest", pipeline.rules,
            "--catalog", str(pipeline.catalog_path), "--action", "search",
        ], capture_output=True, timeout=180)
        result = json.loads(outgoing.read_bytes())
        assert completed.returncode == 0, (result, completed.stderr)
        assert result["digest"] == FIXTURE.sha(FIXTURE.canonical(
            {key: value for key, value in result.items() if key != "digest"}))
        assert [row["card_id"] for row in result["data"]["matches"]] == ["concurrent-rule"]
        return result["data"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(search, number) for number in range(2)]
        ready.wait(timeout=10)
        pipeline.call("knowledge-index-build", {"operation_id": "activate-second",
            "generation_ref": second["generation_ref"], "expected_active": second["expected_active"]}, "activate")
        searches = [future.result() for future in futures]

    assert len({row["receipt_ref"] for row in searches}) == 2
    for number, searched in enumerate(searches):
        assert searched["generation_ref"] in {first["generation_ref"], second["generation_ref"]}
        read = pipeline.call("knowledge-query", {
            "operation_id": f"parallel-read-{number}", "receipt_ref": searched["receipt_ref"],
            "card_id": "concurrent-rule",
        }, "read")["data"]
        assert read["generation_ref"] == searched["generation_ref"]
        assert read["card_digest"] == searched["matches"][0]["card_digest"]
