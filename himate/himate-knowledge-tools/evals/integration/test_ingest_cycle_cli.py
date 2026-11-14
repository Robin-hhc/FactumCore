"""Workflow edges and real CLI state compose into bounded source-draining loops.

Plans and reviewer decisions below are synthetic test inputs. These checks do
not execute a host Agent or prove content-review quality or host scheduling.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from integration import test_pdf_resume_cli as pdf_support
from integration import test_single_file_cli as cli_support


knowledge = cli_support.knowledge
invoke = cli_support.invoke
SOURCE = Path(__file__).resolve().parents[2]


def edges(workflow="hs-knowledge-ingest"):
    graph = yaml.safe_load((SOURCE / "workflows" / workflow / "workflow.yaml").read_bytes())
    return {node["id"]: {edge["id"]: edge["target"] for edge in node["exits"]}
            for node in graph["nodes"]}


def request_file(root, name, value):
    path = root / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def scan(root, request):
    status, result = invoke(root, "ingest", "scan", "--input",
                            request_file(root, "cycle-scan.json", request))
    assert status == 0 and result["phase"] in {"prepared", "unchanged"}, result
    return result


def synthetic_plan(root, task):
    metadata = {"cards": []}
    if "pdf_review" in task:
        start = task["pdf_review"]["start_page"]
        metadata["source_pages"] = [[start, start]]
    (root / ".build/plan.md").write_text(
        "---\n" + yaml.safe_dump(metadata, sort_keys=False)
        + "---\nSynthetic fixture decision: this assessed material needs no new card.\n",
        encoding="utf-8")
    return metadata


def commit_no_card(root):
    status, result = invoke(root, "ingest", "commit", "--input", request_file(
        root, "cycle-commit.json", {"reason": "Synthetic complete assessment; no new card is required."}))
    assert status == 0 and result["phase"] == "completed", result
    return result["data"]


def publish_selected(root, task):
    synthetic_plan(root, task)
    status, checked = invoke(root, "ingest", "check")
    assert status == 0 and checked["phase"] == "passed", checked
    return commit_no_card(root)


def drive_ingest(root, first_request, continuation_request, expected_batches):
    """Follow the shipped graph; CLI calls, source state and cleanup are real.

    Explicit initial/continuation requests test the documented calling contract,
    rather than pretending this fixture is the product's host prompt interpreter.
    The bound is derived from the finite fixture and detects a non-draining loop.
    """
    graph = edges()
    node, task = "prepare_sources", None
    scans, batches, plans = [], [], []
    for _ in range(expected_batches * 5 + 2):
        if node == "__end__":
            break
        if node == "prepare_sources":
            result = scan(root, first_request if not scans else continuation_request)
            scans.append(result)
            task = result["data"]
            phase = result["phase"]
        elif node == "plan_change":
            plans.append(synthetic_plan(root, task))
            phase = "content_planned"
        elif node == "materialize_view":
            phase = "ready"
        elif node == "lint_view":
            status, result = invoke(root, "ingest", "check")
            assert status == 0 and result["phase"] == "passed", result
            phase = result["phase"]
        elif node == "apply_view":
            batches.append({"path": task["source"]["path"],
                            "source_id": task["source"]["source_id"],
                            "result": commit_no_card(root)})
            phase = "completed"
        else:
            pytest.fail("Unexpected ingestion node: " + node)
        node = graph[node][phase]
    assert node == "__end__", "The finite fixture did not drain through P1"
    assert len(batches) == expected_batches
    assert len(scans) == expected_batches + 1
    assert scans[-1]["phase"] == "unchanged" and scans[-1]["data"]["pending"] == 0
    return scans, batches, plans


def write_text(root, relative, body):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def assert_processed(root, paths):
    resources = yaml.safe_load((root / "governance/sources.lock.yaml").read_bytes())["resources"]
    for path in paths:
        resource = next(row for row in resources if row["path"] == path)
        assert resource["processed_hash"] == hashlib.sha256((root / path).read_bytes()).hexdigest()
        assert "processing" not in resource


def test_ingest_cycle_drains_multiple_sources_and_each_unfinished_pdf_batch(knowledge, monkeypatch):
    pytest.importorskip("docling.document_converter")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    first = "docs-raw/specs/a.md"
    second = "docs-raw/specs/b.md"
    write_text(knowledge, first, "# A\n\nSynthetic requirement A.\n")
    write_text(knowledge, second, "# B\n\nSynthetic requirement B.\n")
    pdf = pdf_support.write_pdf(knowledge)
    originals = {path: (knowledge / path).read_bytes()
                 for path in (first, second, pdf.relative_to(knowledge).as_posix())}
    request = {"review_page_budget": 1}

    scans, batches, plans = drive_ingest(knowledge, request, request, expected_batches=5)

    assert Counter(item["path"] for item in batches) == {
        first: 1, second: 1, "docs-raw/specs/resume.pdf": 3,
    }
    pdf_results = [item["result"] for item in batches if item["path"].endswith(".pdf")]
    assert [item["source_complete"] for item in pdf_results] == [False, False, True]
    assert pdf_results[0]["processing"]["reviewed_pages"] == [[1, 1]]
    assert pdf_results[1]["processing"]["reviewed_pages"] == [[1, 2]]
    assert [plan["source_pages"] for plan in plans if "source_pages" in plan] == [
        [[1, 1]], [[2, 2]], [[3, 3]],
    ]
    assert [item["data"]["pdf_review"]["start_page"] for item in scans[:-1]
            if "pdf_review" in item["data"]] == [1, 2, 3]
    assert_processed(knowledge, originals)
    assert all((knowledge / path).read_bytes() == data for path, data in originals.items())


@pytest.mark.parametrize("scope", ["docs-raw/specs/selected", "docs-raw/specs/selected/a.md"])
def test_ingest_cycle_keeps_original_directory_or_file_scope(knowledge, scope):
    selected = ["docs-raw/specs/selected/a.md", "docs-raw/specs/selected/b.md"]
    outside = "docs-raw/specs/outside.md"
    for path in [*selected, outside]:
        write_text(knowledge, path, "# Scope fixture\n\nA synthetic source.\n")
    expected = selected if scope.endswith("selected") else selected[:1]
    request = {"source": scope}

    _scans, batches, _plans = drive_ingest(knowledge, request, request, len(expected))

    assert {item["path"] for item in batches} == set(expected)
    assert_processed(knowledge, expected)
    pending = scan(knowledge, {})
    assert pending["phase"] == "prepared"
    assert pending["data"]["source"]["path"] not in expected
    assert pending["data"]["source"]["path"] in {*selected, outside}


def test_reprocess_request_is_consumed_once_then_normal_scan_can_terminate(knowledge):
    path = "docs-raw/specs/reviewed.md"
    write_text(knowledge, path, "# Reviewed\n\nA synthetic conclusion.\n")
    initial = scan(knowledge, {"source": path})
    publish_selected(knowledge, initial["data"])
    assert scan(knowledge, {"source": path})["phase"] == "unchanged"
    identity = initial["data"]["source"]["source_id"]

    scans, batches, _plans = drive_ingest(
        knowledge, {"source": identity, "reprocess": True}, {"source": identity}, 1)

    assert scans[0]["data"]["source"]["change"] == "reprocess"
    assert batches[0]["result"]["source_complete"] is True
    assert_processed(knowledge, [path])


def test_failed_apply_retries_same_materials_and_defer_keeps_remaining_work(knowledge):
    path = "docs-raw/specs/a.md"
    write_text(knowledge, path, "# Retry\n\nA synthetic requirement.\n")
    prepared = scan(knowledge, {"source": path})
    task = prepared["data"]
    synthetic_plan(knowledge, task)
    status, checked = invoke(knowledge, "ingest", "check")
    assert status == 0 and checked["phase"] == "passed", checked
    before_task = (knowledge / ".build/task.json").read_bytes()
    before_plan = (knowledge / ".build/plan.md").read_bytes()
    before_registry = (knowledge / "governance/sources.lock.yaml").read_bytes()

    status, failed = invoke(knowledge, "ingest", "commit")

    assert status == 2 and failed["phase"] == "invalid", failed
    assert failed["diagnostics"][0]["code"] == "NO_CHANGE_REASON_REQUIRED"
    assert (knowledge / ".build/task.json").read_bytes() == before_task
    assert (knowledge / ".build/plan.md").read_bytes() == before_plan
    assert (knowledge / "governance/sources.lock.yaml").read_bytes() == before_registry
    status, deferred = invoke(knowledge, "ingest", "commit", "--input", request_file(
        knowledge, "cycle-defer.json", {"defer": True, "reason": "Synthetic missing evidence."}))
    assert status == 0 and deferred["phase"] == "deferred", deferred
    assert (knowledge / ".build/task.json").read_bytes() == before_task
    assert (knowledge / "governance/sources.lock.yaml").read_bytes() == before_registry
    status, pending = invoke(knowledge, "patrol", "plan")
    assert status == 0 and pending["phase"] == "needs_ingest", pending
    assert pending["data"]["next_file"]["source_id"] == task["source"]["source_id"]
    assert edges()["plan_change"]["deferred"] == "__end__"

    # Retry P5 without calling scan: the same task is still sufficient to commit.
    result = commit_no_card(knowledge)
    assert result["source_complete"] is True
    assert_processed(knowledge, [path])


@pytest.mark.parametrize("first", ["docs-raw/specs/a.md", "docs-raw/agent-notes/a.md"])
def test_lint_reselects_when_its_selected_source_was_completed_before_p1(knowledge, first):
    second = "docs-raw/specs/b.md"
    write_text(knowledge, "docs-raw/agent-notes/README.md", "# Directory guidance\n")
    original = write_text(knowledge, first, "# A\n\nSynthetic source A.\n").read_bytes()
    write_text(knowledge, second, "# B\n\nSynthetic source B.\n")
    graph = edges("hs-knowledge-lint")
    status, selection = invoke(knowledge, "patrol", "plan")
    assert status == 0 and selection["phase"] == "needs_ingest", selection
    selected = selection["data"]["next_file"]
    assert selected["path"] == first
    assert graph["plan_patrol"][selection["phase"]] == "prepare_sources"

    # A completed separate operation makes L2's selection stale before its P1.
    prepared = scan(knowledge, {"source": selected["source_id"]})
    assert publish_selected(knowledge, prepared["data"])["card_ids"] == []
    assert (knowledge / first).read_bytes() == original
    unchanged = scan(knowledge, {"source": selected["source_id"]})
    assert unchanged["phase"] == "unchanged"
    assert graph["prepare_sources"][unchanged["phase"]] == "plan_patrol"
    status, next_selection = invoke(knowledge, "patrol", "plan")
    assert status == 0 and next_selection["phase"] == "needs_ingest", next_selection
    assert next_selection["data"]["next_file"]["path"] == second
    prepared = scan(knowledge, {"source": next_selection["data"]["next_file"]["source_id"]})
    publish_selected(knowledge, prepared["data"])
    assert graph["apply_view"]["completed"] == "plan_patrol"
    status, empty = invoke(knowledge, "patrol", "plan")
    assert status == 0 and empty["phase"] == "unchanged", empty
    assert graph["plan_patrol"][empty["phase"]] == "complete_patrol"
    assert_processed(knowledge, [first, second])
