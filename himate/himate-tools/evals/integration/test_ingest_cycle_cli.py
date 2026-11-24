"""Workflow edges and real CLI state compose into bounded source-draining loops.

Plans and reviewer decisions below are synthetic test inputs. These checks do
not execute a host Agent or prove content-review quality or host scheduling.
"""

from collections import Counter
import hashlib
import json

import pytest
import yaml

from integration import test_pdf_resume_cli as pdf_support
from integration import test_single_file_cli as cli_support
from support.contracts import CAPABILITIES_ROOT


knowledge = cli_support.knowledge
invoke = cli_support.invoke


def edges(workflow="hs-knowledge-ingest"):
    graph = yaml.safe_load((CAPABILITIES_ROOT / "workflows" / workflow / "workflow.yaml").read_bytes())
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
    elif "document_review" in task:
        scope = task["document_review"]
        metadata["source_units"] = [[scope["start_unit"], scope["end_unit"]]]
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
    group = "maintain" if task.get("task_type") == "card_maintenance" else "ingest"
    status, checked = invoke(root, group, "check")
    assert status == 0 and checked["phase"] == "passed", checked
    if group == "maintain":
        status, receipt = invoke(root, "maintain", "commit", request={"reason": "Reviewed existing cards need no change."})
        assert status == 0 and receipt["phase"] == "completed", receipt
        assert "source_complete" not in receipt["data"]
        return receipt["data"]
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


@pytest.mark.parametrize("suffix", [".docx", ".xlsx"])
def test_office_cli_does_not_mark_the_source_complete_before_the_last_range(knowledge, suffix):
    relative = "docs-raw/specs/office" + suffix
    target = knowledge / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".docx":
        from docx import Document

        original = Document()
        for row in range(120):
            original.add_paragraph(f"Paragraph {row}: Assess all values and conditions in this source.")
        original.save(target)
    else:
        from openpyxl import Workbook

        original = Workbook()
        for row in range(120):
            original.active.append([row, f"Assess all values and conditions in this row {row}.", row + 42])
        original.save(target)
    request = {"source": relative, "review_text_budget": 2500}
    batches = []
    for _ in range(12):
        response = scan(knowledge, request)
        if response["phase"] == "unchanged":
            break
        task = response["data"]
        scope = task["document_review"]
        assert scope["start_unit"] == (batches[-1]["source_units"][0][1] + 1 if batches else 1)
        batches.append(publish_selected(knowledge, task))
    assert response["phase"] == "unchanged"
    assert len(batches) > 1
    assert all(not row["source_complete"] for row in batches[:-1])
    assert batches[-1]["source_complete"]


def test_cli_blocks_incomplete_document_without_an_eligible_task(knowledge):
    path = write_text(knowledge, "docs-raw/specs/broken.pdf", "%PDF-1.7\ntruncated")
    status, result = invoke(knowledge, "ingest", "scan", "--source", path.relative_to(knowledge).as_posix())
    assert status == 1 and result["phase"] == "blocked", result
    assert not (knowledge / ".build/task.json").exists()


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


def test_upload_workflow_returns_to_each_scoped_source_before_advancing(knowledge):
    paths = ["docs-raw/specs/z-uploaded.md", "docs-raw/specs/a-uploaded.md"]
    outside = "docs-raw/specs/0-unrelated.md"
    for path in [*paths, outside]:
        write_text(knowledge, path, "# Uploaded material\n\nSynthetic fixture assessment.\n")
    manifest = [
        {"path": path, "sha256": hashlib.sha256((knowledge / path).read_bytes()).hexdigest()}
        for path in paths
    ]
    graph = edges()
    node = "prepare_sources"
    for index, source in enumerate(manifest):
        assert node == "prepare_sources"
        status, checked_path = invoke(knowledge, "raw", "path", "--path",
                                      source["path"].removeprefix("docs-raw/"))
        assert status == 0 and checked_path["data"]["kind"] == "file", checked_path
        request = {"source": source["path"]}
        prepared = scan(knowledge, request)
        assert prepared["phase"] == "prepared"
        actual = prepared["data"]["source"]
        assert actual["path"] == source["path"] and actual["hash"] == source["sha256"]
        node = graph[node][prepared["phase"]]
        assert node == "plan_change"
        assert publish_selected(knowledge, prepared["data"])["source_complete"] is True
        node = graph["apply_view"]["completed"]
        assert node == "prepare_sources"
        assert scan(knowledge, request)["phase"] == "unchanged"
        exit_id = "next_upload_source" if index + 1 < len(manifest) else "unchanged"
        node = graph[node][exit_id]

    assert node == "__end__"
    assert_processed(knowledge, paths)
    remaining = scan(knowledge, {})
    assert remaining["phase"] == "prepared"
    assert remaining["data"]["source"]["path"] == outside


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
    if empty["phase"] == "needs_reindex":
        assert graph["plan_patrol"]["needs_reindex"] == "refresh_index"
        status, refreshed = invoke(knowledge, "patrol", "reindex")
        assert status == 0 and refreshed["phase"] == "reindexed", refreshed
        assert graph["refresh_index"]["reindexed"] == "plan_patrol"
        status, empty = invoke(knowledge, "patrol", "plan")
    assert status == 0 and empty["phase"] == "unchanged", empty
    assert graph["plan_patrol"][empty["phase"]] == "complete_patrol"
    assert_processed(knowledge, [first, second])


def patrol_task(root, path, change, *, code_review=False):
    status, selection = invoke(root, "patrol", "plan")
    assert status == 0 and selection["phase"] == ("needs_maintenance" if code_review else "needs_ingest"), selection
    selected = selection["data"]["next_file"]
    assert selected["path"] == path and selected.get("change") == change, selected
    request = {"source": selected["source_id"]}
    if code_review:
        status, prepared = invoke(root, "maintain", "prepare", request=request)
        assert status == 0, prepared
    else:
        prepared = scan(root, request)
    assert prepared["phase"] == "prepared", prepared
    task = prepared["data"]
    assert task["source"]["source_id"] == selected["source_id"]
    assert task["task_type"] == ("card_maintenance" if code_review else "document_ingest")
    return task


def stage_patrol_cards(root, task, cards):
    plan = {"cards": [{"id": header["id"], "path": path} for path, (header, _) in cards.items()]}
    if "document_review" in task:
        scope = task["document_review"]
        plan["source_units"] = [[scope["start_unit"], scope["end_unit"]]]
    write_text(root, ".build/plan.md", card_text(plan, "# Synthetic patrol assessment\n"))
    for path, (header, body) in cards.items():
        write_text(root, ".build/cards/" + path.removeprefix("knowledge/"), card_text(header, body))


def card_text(header, body):
    return "---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n" + body


def publish_patrol_candidates(root, expected_ids):
    task = json.loads((root / ".build/task.json").read_bytes())
    group = "maintain" if task["task_type"] == "card_maintenance" else "ingest"
    status, checked = invoke(root, group, "check")
    assert status == 0 and checked["phase"] == "passed", checked
    status, published = invoke(root, group, "commit")
    assert status == 0 and published["phase"] == "completed", published
    assert sorted(published["data"]["card_ids"]) == sorted(expected_ids)


def assert_patrol_drained(root):
    status, planned = invoke(root, "patrol", "plan")
    if planned["phase"] == "needs_reindex":
        status, refreshed = invoke(root, "patrol", "reindex")
        assert status == 0 and refreshed["phase"] == "reindexed", refreshed
        status, planned = invoke(root, "patrol", "plan")
    assert status == 0 and planned["phase"] == "unchanged", planned
    assert planned["data"]["pending"] == 0
    status, completed = invoke(root, "patrol", "complete")
    assert status == 0 and completed["phase"] == "completed", completed
    assert completed["data"]["remaining"] == 0


def test_patrol_closes_document_and_code_reference_work_at_the_cli(knowledge):
    raw_path = "docs-raw/specs/design.md"
    raw = write_text(knowledge, raw_path, "# Receive design\n\nUse the configured receive limit.\n")
    code_path = "main/driver/rx.c"
    unrelated_code_path = "main/driver/unreferenced.c"
    workspace = knowledge.parents[1]
    code = write_text(workspace, code_path, "int receive_limit(void)\n{\n    return 4;\n}\n")
    write_text(workspace, unrelated_code_path, "int unused(void) { return 1; }\n")
    config = knowledge / "config.yml"
    config.write_bytes(config.read_bytes().replace(b"modules: []", b"modules:\n- path: driver"))
    for path, identity in [(code_path, "code-rx"), (unrelated_code_path, "code-unused")]:
        status, registered = invoke(knowledge, "source", "register", request={
            "kind": "code", "path": path, "source_id": identity,
        })
        assert status == 0 and registered["phase"] == "registered", registered

    related_path, unrelated_path = "knowledge/receive.md", "knowledge/independent.md"
    related_body = "# Receive limit\n\nStatic observation: receive_limit returns 4.\n"
    unrelated_body = "# Independent card\n\nUse the configured receive limit.\n"
    document = patrol_task(knowledge, raw_path, "added")
    docs = [{"doc_id": document["source"]["doc_id"], "line_start": 1, "line_end": 3}]
    linked = {"id": "receive", "doc_ref": docs, "code_ref": [{
        "code_id": "code-rx", "line_start": 1, "line_end": 4, "symbol": "receive_limit",
    }]}
    independent = {"id": "independent", "doc_ref": docs, "code_ref": []}
    original_raw = raw.read_bytes()
    stage_patrol_cards(knowledge, document, {
        related_path: (linked, related_body), unrelated_path: (independent, unrelated_body),
    })
    publish_patrol_candidates(knowledge, ["receive", "independent"])
    assert_processed(knowledge, [raw_path])

    task = patrol_task(knowledge, code_path, "baseline_missing", code_review=True)
    assert [(card["id"], card["path"]) for card in task["affected_cards"]] == [("receive", related_path)]
    formal = {path: (knowledge / path).read_bytes() for path in (related_path, unrelated_path)}
    lock = knowledge / "governance/sources.lock.yaml"
    prior_lock = lock.read_bytes()
    changes = knowledge / ".build/changes.json"
    task_file = knowledge / ".build/task.json"
    original_task = task_file.read_bytes()
    unrelated_edit = {unrelated_path: (independent, unrelated_body + "Unrelated edit.\n")}
    for cards, deleted, expanded_task in [
        ({"knowledge/extra.md": ({**linked, "id": "extra"}, related_body)}, [], False),
        (unrelated_edit, [], False),
        ({}, [unrelated_path], False),
        (unrelated_edit, [], True),
    ]:
        stage_patrol_cards(knowledge, task, cards)
        if deleted:
            changes.write_text(json.dumps({"delete": deleted}), encoding="utf-8")
        if expanded_task:
            staged = json.loads(original_task)
            staged["affected_cards"].append({"id": "independent", "path": unrelated_path})
            task_file.write_text(json.dumps(staged), encoding="utf-8")
        # Attempt commit before invoking P4. Staged changes must stay private.
        status, rejected = invoke(knowledge, "ingest", "commit", request={"reason": "Synthetic scope test"})
        assert status != 0, rejected
        assert rejected["diagnostics"][0]["code"] == "MAINTENANCE_SCOPE", rejected
        status, rejected = invoke(knowledge, "ingest", "check")
        assert status != 0 and rejected["phase"] == "failed", rejected
        assert any(finding["code"] == "MAINTENANCE_SCOPE" for finding in rejected["data"]["findings"]), rejected
        assert lock.read_bytes() == prior_lock
        for path, content in formal.items():
            assert (knowledge / path).read_bytes() == content
        assert not (knowledge / "knowledge/extra.md").exists()
        for path in cards:
            (knowledge / ".build/cards" / path.removeprefix("knowledge/")).unlink()
        changes.unlink(missing_ok=True)
        if expanded_task:
            task_file.write_bytes(original_task)

    assert publish_selected(knowledge, task)["card_ids"] == []
    assert (knowledge / related_path).read_bytes() == formal[related_path]
    assert_patrol_drained(knowledge)

    old_code = code.read_bytes()
    invalid = {**linked, "code_ref": [{**linked["code_ref"][0], "line_start": 2}]}
    write_text(knowledge, related_path, card_text(invalid, related_body))
    task = patrol_task(knowledge, code_path, "reference_invalid", code_review=True)
    assert code.read_bytes() == old_code
    assert [card["id"] for card in task["affected_cards"]] == ["receive"]
    synthetic_plan(knowledge, task)
    status, rejected = invoke(knowledge, "ingest", "commit", request={"reason": "Attempt to accept stale citation"})
    assert status != 0 and rejected["diagnostics"][0]["code"] == "CODE_RANGE_CHANGED", rejected
    status, rejected = invoke(knowledge, "ingest", "check")
    assert status != 0 and rejected["phase"] == "failed", rejected
    assert any(finding["code"] == "CODE_RANGE_CHANGED" for finding in rejected["data"]["findings"]), rejected
    stage_patrol_cards(knowledge, task, {related_path: (linked, related_body)})
    publish_patrol_candidates(knowledge, ["receive"])
    assert_patrol_drained(knowledge)

    code.write_text("// Revised implementation\nint receive_limit(void)\n{\n    return 7;\n}\n", encoding="utf-8")
    task = patrol_task(knowledge, code_path, "modified", code_review=True)
    assert [card["id"] for card in task["affected_cards"]] == ["receive"]
    revised = {**linked, "code_ref": [{**linked["code_ref"][0], "line_start": 2, "line_end": 5}]}
    revised_body = related_body.replace("returns 4", "returns 7")
    stage_patrol_cards(knowledge, task, {related_path: (revised, revised_body)})
    publish_patrol_candidates(knowledge, ["receive"])
    assert_patrol_drained(knowledge)
    status, final_card = invoke(knowledge, "read", "receive")
    assert status == 0 and "returns 7" in final_card["data"]["body"], final_card
    assert final_card["data"]["code_ref"][0]["line_start"] == 2
    assert final_card["data"]["code_ref"][0]["line_end"] == 5
    assert (knowledge / unrelated_path).read_bytes() == formal[unrelated_path]
    assert raw.read_bytes() == original_raw
