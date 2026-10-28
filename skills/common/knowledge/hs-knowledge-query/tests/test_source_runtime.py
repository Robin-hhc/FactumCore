"""Source-resolution runtime failures remain failures at the public query CLI."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "query_runtime_document_fixture",
    ROOT / "himate-knowledge-wifi-mp/evals/tests/test_post_ingest_correction.py",
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


@pytest.fixture(scope="module")
def completed_document(tmp_path_factory):
    harness = FIXTURE.frozen_harness(tmp_path_factory.mktemp("source-runtime"))
    harness.write(
        "docs-raw/specs/source.md",
        b"# Source\nSynthetic fixture statement for test readers.\n",
    )
    FIXTURE.complete_document_operation(
        harness, "runtime-baseline", "create", "Synthetic fixture statement."
    )
    return harness


def timed_out_query(harness, request, action, *, resolve_attempt=1):
    incoming = harness.base / (request["operation_id"] + "-input.json")
    outgoing = harness.base / (request["operation_id"] + "-output.json")
    incoming.write_text(json.dumps(request), encoding="utf-8")
    # Inject at the subprocess boundary; the public CLI and its source/error
    # qualification logic execute unchanged. No source or index is modified.
    program = """
from pathlib import Path
import runpy
import subprocess
import sys
cli, attempt = sys.argv[1], int(sys.argv[2])
run = subprocess.run
resolutions = 0
def timeout_source(command, *args, **kwargs):
    global resolutions
    if (isinstance(command, (list, tuple))
            and any('hs-knowledge-source-capture' in str(part) for part in command)
            and 'resolve-source' in command):
        resolutions += 1
        if resolutions == attempt:
            raise subprocess.TimeoutExpired(command, kwargs.get('timeout', 120))
    return run(command, *args, **kwargs)
subprocess.run = timeout_source
sys.path.insert(0, str(Path(cli).parent))
sys.argv = [cli, *sys.argv[3:]]
runpy.run_path(cli, run_name='__main__')
"""
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(harness.packages / "hs-knowledge-query/scripts/cli.py"),
            str(resolve_attempt),
            "--knowledge-root",
            str(harness.root),
            "--input",
            str(incoming),
            "--output",
            str(outgoing),
            "--action",
            action,
        ],
        capture_output=True,
        timeout=60,
    )
    return process, json.loads(outgoing.read_bytes())


def test_search_preserves_source_resolution_timeout(completed_document):
    harness = completed_document
    normal = harness.run(
        "query",
        {"operation_id": "source-runtime-normal", "query": "Synthetic", "purpose": "guidance"},
        "search",
    )["data"]
    assert [row["card_id"] for row in normal["matches"]] == ["rule"]
    assets = [
        harness.root / ref
        for ref in (
            "docs-raw/specs/source.md",
            "knowledge/rules/rule.md",
            "governance/sources.lock.yaml",
            "artifacts/indexes/local/active.json",
        )
    ]
    before = {path: path.read_bytes() for path in assets}
    process, response = timed_out_query(
        harness,
        {"operation_id": "source-runtime-timeout", "query": "Synthetic", "purpose": "guidance"},
        "search",
    )
    assert process.returncode == 3, response
    assert response["status"] == "blocked", response
    assert response["diagnostics"][0]["code"] == "SIBLING_TIMEOUT", response
    assert "120-second call budget" in response["diagnostics"][0]["message"]
    assert response["data"] == {}
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert not (harness.root / ".build/operations/source-runtime-timeout/receipts").exists()


@pytest.mark.parametrize(
    "action,resolve_attempt,from_receipt",
    [
        ("search", 2, False),
        ("search", 3, False),
        ("receipt", 1, False),
        ("read", 1, False),
        ("read", 2, False),
        ("read", 3, False),
        ("read", 1, True),
        ("read", 3, True),
    ],
)
def test_query_timeout_stays_blocked_during_rechecks_and_reads(
    completed_document, action, resolve_attempt, from_receipt
):
    harness = completed_document
    suffix = f"{action}-{resolve_attempt}-{int(from_receipt)}"
    operation = "runtime-" + suffix
    request = {"operation_id": operation, "purpose": "guidance"}
    if action == "read":
        request["card_id"] = "rule"
    else:
        request["query"] = "Synthetic"
    if from_receipt:
        search = harness.run(
            "query",
            {"operation_id": "search-before-" + suffix,
             "query": "Synthetic", "purpose": "guidance"},
            "search",
        )["data"]
        request["receipt_ref"] = search["receipt_ref"]
    process, response = timed_out_query(
        harness, request, action, resolve_attempt=resolve_attempt
    )
    assert process.returncode == 3, response
    assert response["status"] == "blocked", response
    assert response["diagnostics"][0]["code"] == "SIBLING_TIMEOUT", response
    assert response["diagnostics"][0]["path"] == "hs-knowledge-source-capture"
    assert response["data"] == {}
    operation_path = harness.root / ".build/operations" / operation
    assert list(operation_path.glob("calls/*/request.json"))
    assert not (operation_path / "receipts").exists()
