"""Adversarial public-contract coverage for evidence governance publication."""

import copy
import hashlib
import json
import importlib.util
from pathlib import Path

import pytest
import yaml

_support_spec = importlib.util.spec_from_file_location(
    "_code_evidence_lifecycle_support", Path(__file__).with_name("test_code_evidence_lifecycle.py"))
_support = importlib.util.module_from_spec(_support_spec)
_support_spec.loader.exec_module(_support)
card, confirm, fixture, parsed = (_support.card, _support.confirm, _support.fixture, _support.parsed)
from contracts import module, write_plan


def _rewrite(root, reference_updates=None, *, path="knowledge/waiting.md", identity=None):
    current = module("cards_v3").parse_card((root / path).read_bytes(), path)
    metadata = copy.deepcopy(current["metadata"])
    if reference_updates is not None:
        metadata["code_ref"] = reference_updates
    if identity is not None:
        metadata["id"] = identity
    raw = ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
           + "---\n" + current["body"]).encode("utf-8")
    (root / path).write_bytes(raw)
    return raw


def _function_reference(symbol, start, end, source="code-wait"):
    return {"code_id": source, "line_start": start, "line_end": end, "symbol": symbol}


def _two_sources(tmp_path):
    root, first = fixture(tmp_path)
    second = first.with_name("retry.c")
    second.write_bytes(b"int retry_limit(void) {\n    return 3;\n}\n")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("code", "code/wifi/retry.c", source_id="code-retry")
    _rewrite(root, [_function_reference("wait_reply", 1, 3),
                    _function_reference("retry_limit", 1, 3, "code-retry")])
    confirm(root)
    return root, first, second


def _mechanical(tmp_path):
    root, source = fixture(tmp_path)
    confirm(root)
    source.write_bytes(b"// inserted header\n" + source.read_bytes())
    result, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "mechanical_prepared", result
    return root, source, json.loads((root / ".build/task.json").read_bytes())


def _forge_mechanical_digest(root, task):
    """An attacker knows the digest format; content restrictions must still hold."""
    sha = lambda value: hashlib.sha256(value).hexdigest()
    locations = {entry["id"]: entry["path"] for entry in task["affected_cards"]}
    drafts = []
    for path in (root / ".build/cards").rglob("*.md"):
        value = module("cards_v3").parse_card(path.read_bytes(), "candidate.md")
        drafts.append((value["id"], locations[value["id"]], sha(value["raw"])))
    payload = {"input": task, "plan_sha256": sha((root / ".build/plan.md").read_bytes()),
               "cards": sorted(drafts), "deleted": []}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {"mode": "mechanical", "sha256": sha(encoded)}


def _prepare_ingest(root):
    ingest = module("ingest")
    result, phase = ingest.scan(root, {"source": "doc-design", "reprocess": True})
    assert phase == "prepared", result
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    (root / ".build/cards/waiting.md").write_bytes(card("Reviewed replacement body."))
    checked, phase = ingest.check(root, {})
    assert phase == "passed", checked
    return ingest


def test_one_card_with_relocated_and_changed_references_requires_semantic_lane(tmp_path):
    root, source = fixture(tmp_path)
    source.write_bytes(source.read_bytes() + b"\nint retry_limit(void) {\n    return 3;\n}\n")
    _rewrite(root, [_function_reference("wait_reply", 1, 3),
                    _function_reference("retry_limit", 5, 7)])
    confirm(root)
    before = (root / "knowledge/waiting.md").read_bytes()
    source.write_bytes(b"// inserted\n" + source.read_bytes().replace(b"return 3", b"return 8"))
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    assert {entry["status"] for entry in task["evidence_states"]["waiting"]} == {"relocated", "changed"}
    assert not (root / ".build/maintenance-mechanical-check.json").exists()
    assert (root / "knowledge/waiting.md").read_bytes() == before


def test_unaffected_card_sharing_source_is_not_selected_for_semantic_work(tmp_path):
    root, source = fixture(tmp_path)
    source.write_bytes(source.read_bytes() + b"\nint retry_limit(void) {\n    return 3;\n}\n")
    other = root / "knowledge/unaffected.md"
    other.write_bytes(card(references=[_function_reference("retry_limit", 5, 7)]))
    _rewrite(root, path="knowledge/unaffected.md", identity="unaffected")
    confirm(root)
    other_before = other.read_bytes()
    source.write_bytes(source.read_bytes().replace(b"return 5", b"return 8"))
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    assert [entry["id"] for entry in task["affected_cards"]] == ["waiting"]
    assert set(task["evidence_states"]) == {"waiting"}
    assert other.read_bytes() == other_before


def test_other_source_change_on_same_card_prevents_mechanical_lane(tmp_path):
    root, first, second = _two_sources(tmp_path)
    first.write_bytes(b"// inserted\n" + first.read_bytes())
    second.write_bytes(second.read_bytes().replace(b"return 3", b"return 7"))
    task, phase = module("ingest").maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    assert set(task["code_inputs"]) == {"code-wait", "code-retry"}
    states = {entry["source_id"]: entry["status"] for entry in task["evidence_states"]["waiting"]}
    assert states == {"code-wait": "relocated", "code-retry": "changed"}
    assert (root / task["code_inputs"]["code-retry"]["original_ref"]).read_bytes() == second.read_bytes()


def test_parallel_second_source_edit_after_review_blocks_publication(tmp_path):
    root, first, second = _two_sources(tmp_path)
    first.write_bytes(first.read_bytes().replace(b"return 5", b"return 8"))
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    write_plan(root, [])
    checked, phase = ingest.maintenance_check(root, {})
    assert phase == "passed", checked
    original = (root / "knowledge/waiting.md").read_bytes()
    second.write_bytes(second.read_bytes().replace(b"return 3", b"return 9"))
    with pytest.raises(ingest.ContractError, match="SOURCE_CHANGED|CODE_EVIDENCE_CHANGED"):
        ingest.maintenance_commit(root, {"reason": "The card had been reviewed before the parallel source change."})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_review_confirms_all_actually_checked_sources_on_one_card(tmp_path):
    root, first, second = _two_sources(tmp_path)
    before = [reference["evidence_version"] for reference in parsed(root)["code_ref"]]
    first.write_bytes(first.read_bytes().replace(b"return 5", b"return 8"))
    second.write_bytes(second.read_bytes().replace(b"return 3", b"return 7"))
    confirm(root)
    after = [reference["evidence_version"] for reference in parsed(root)["code_ref"]]
    assert all(old != new for old, new in zip(before, after))
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}


@pytest.mark.parametrize("tamper", ["missing", "digest", "review-marker-only", "mode", "inputs"])
def test_mechanical_publication_requires_its_own_fixed_proof(tmp_path, tamper):
    root, _, task = _mechanical(tmp_path)
    ingest = module("ingest")
    original = (root / "knowledge/waiting.md").read_bytes()
    marker = root / ".build/maintenance-mechanical-check.json"
    assert json.loads(marker.read_bytes()) == _forge_mechanical_digest(root, task)
    if tamper == "missing":
        marker.unlink()
    elif tamper == "digest":
        marker.write_text(json.dumps({"mode": "mechanical", "sha256": "0" * 64}))
    elif tamper == "review-marker-only":
        (root / ".build/maintenance-review-check.json").write_bytes(marker.read_bytes())
        marker.unlink()
    else:
        task["mode"] = "semantic" if tamper == "mode" else task["mode"]
        if tamper == "inputs":
            task["code_inputs"] = {}
        (root / ".build/task.json").write_text(json.dumps(task), encoding="utf-8")
    with pytest.raises(ingest.ContractError, match="MECHANICAL|MAINTENANCE"):
        ingest.maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


@pytest.mark.parametrize("tamper", ["body", "doc_ref", "version", "lifecycle", "line_range"])
def test_recomputed_mechanical_digest_cannot_authorize_semantic_or_wrong_location_edits(tmp_path, tamper):
    root, _, task = _mechanical(tmp_path)
    draft = root / ".build/cards/waiting.md"
    value = module("cards_v3").parse_card(draft.read_bytes(), "knowledge/waiting.md")
    metadata, body = copy.deepcopy(value["metadata"]), value["body"]
    if tamper == "body":
        body += "Unreviewed extra conclusion.\n"
    elif tamper == "doc_ref":
        metadata["doc_ref"][0]["line_end"] = 2
    elif tamper == "version":
        metadata["code_ref"][0]["evidence_version"] = "forged-but-nonempty"
    elif tamper == "lifecycle":
        metadata["lifecycle"] = "deprecated"
    else:
        metadata["code_ref"][0].update(line_start=1, line_end=3)
    draft.write_bytes(("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
                       + "---\n" + body).encode("utf-8"))
    (root / ".build/maintenance-mechanical-check.json").write_text(
        json.dumps(_forge_mechanical_digest(root, task)), encoding="utf-8")
    original = (root / "knowledge/waiting.md").read_bytes()
    with pytest.raises(module("ingest").ContractError, match="MECHANICAL_SCOPE"):
        module("ingest").maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_semantic_task_cannot_be_relabelled_as_mechanical(tmp_path):
    root, source = fixture(tmp_path)
    confirm(root)
    source.write_bytes(source.read_bytes().replace(b"return 5", b"return 8"))
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    original = (root / "knowledge/waiting.md").read_bytes()
    task = json.loads((root / ".build/task.json").read_bytes())
    task["mode"] = "mechanical"
    task["mechanical_check_ref"] = ".build/maintenance-mechanical-check.json"
    (root / ".build/task.json").write_text(json.dumps(task))
    write_plan(root, [])
    (root / task["mechanical_check_ref"]).write_text(json.dumps(_forge_mechanical_digest(root, task)))
    with pytest.raises(ingest.ContractError, match="MAINTENANCE_TASK_CHANGED"):
        ingest.maintenance_commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_missing_p4_code_receipt_cannot_bypass_source_change_protection(tmp_path):
    root, source = fixture(tmp_path)
    ingest = _prepare_ingest(root)
    original = (root / "knowledge/waiting.md").read_bytes()
    (root / ".build/code-evidence-check.json").unlink()
    source.write_bytes(source.read_bytes().replace(b"return 5", b"return 8"))
    with pytest.raises(ingest.ContractError, match="CODE_EVIDENCE_NOT_CHECKED|CODE_EVIDENCE_CHANGED|SOURCE_CHANGED"):
        ingest.commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_p4_receipt_cannot_omit_the_candidate_code_evidence_coverage(tmp_path):
    root, _ = fixture(tmp_path)
    ingest = _prepare_ingest(root)
    original = (root / "knowledge/waiting.md").read_bytes()
    path = root / ".build/code-evidence-check.json"
    receipt = json.loads(path.read_bytes())
    receipt.update(sources={}, versions={})
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ingest.ContractError, match="CODE_EVIDENCE_NOT_CHECKED|CODE_EVIDENCE_COVERAGE"):
        ingest.commit(root, {})
    assert (root / "knowledge/waiting.md").read_bytes() == original


def test_deleted_current_source_cannot_be_confirmed_by_zero_change_reason(tmp_path):
    root, source = fixture(tmp_path)
    confirm(root)
    original = (root / "knowledge/waiting.md").read_bytes()
    source.unlink()
    ingest = module("ingest")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared" and task["mode"] == "semantic", task
    write_plan(root, [])
    checked, phase = ingest.maintenance_check(root, {})
    assert phase == "failed", checked
    assert any(item["code"] == "SOURCE_INPUT_UNAVAILABLE" for item in checked["findings"])
    with pytest.raises(ingest.ContractError, match="SOURCE_INPUT_UNAVAILABLE"):
        ingest.maintenance_commit(root, {"reason": "A reason alone cannot resolve a missing current reference."})
    assert (root / "knowledge/waiting.md").read_bytes() == original
    assert module("library").patrol(root, "plan", {})[1] == "needs_maintenance"


def test_registered_historical_reference_does_not_follow_current_source_edits(tmp_path):
    root, source = fixture(tmp_path)
    confirm(root)
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    relative = "artifacts/evidence/objects/" + digest + ".bin"
    retained = root / relative
    retained.parent.mkdir(parents=True)
    retained.write_bytes(content)
    lock = root / "governance/sources.lock.yaml"
    registry = yaml.safe_load(lock.read_bytes())
    registry["snapshots"].append({"snapshot_id": "retained-code", "source_id": "code-wait",
                                  "sha256": digest, "bytes": len(content),
                                  "recovery": {"method": "evidence_object", "path": relative}})
    lock.write_text(yaml.safe_dump(registry), encoding="utf-8")
    references = copy.deepcopy(parsed(root)["code_ref"])
    references[0]["snapshot_id"] = "retained-code"
    before = _rewrite(root, references)
    source.write_bytes(b"// moved current implementation\n" + content.replace(b"return 5", b"return 9"))
    assert module("library").patrol(root, "plan", {})[1] in {"unchanged", "needs_reindex"}
    assert module("ingest").maintenance_prepare(root, {"source": "code-wait"})[1] == "unchanged"
    checked, phase = module("ingest").check(root, {"formal": True})
    assert phase == "passed", checked
    assert (root / "knowledge/waiting.md").read_bytes() == before


def test_unregistered_legacy_snapshot_label_cannot_hide_current_code_change(tmp_path):
    root, source = fixture(tmp_path)
    confirm(root)
    references = copy.deepcopy(parsed(root)["code_ref"])
    references[0]["snapshot_id"] = "legacy-version-label"
    before = _rewrite(root, references)
    source.write_bytes(source.read_bytes().replace(b"return 5", b"return 9"))
    selected, phase = module("library").patrol(root, "plan", {})
    assert phase == "needs_maintenance", selected
    assert (root / "knowledge/waiting.md").read_bytes() == before


def test_observe_reuses_one_decode_and_symbol_parse_per_source_operation(tmp_path, monkeypatch):
    root, _ = fixture(tmp_path)
    confirm(root)
    raw = (root / "knowledge/waiting.md").read_bytes()
    for index in range(24):
        (root / f"knowledge/copy-{index}.md").write_bytes(
            raw.replace(b"id: waiting\n", f"id: copy-{index}\n".encode(), 1))
    resources, symbols = module("source_resources"), module("code_symbols")
    extract, parse = resources.extract_code_text, symbols._parse
    counts = {"extract": 0, "parse": 0}
    def counted_extract(*args, **kwargs):
        counts["extract"] += 1
        return extract(*args, **kwargs)
    def counted_parse(*args, **kwargs):
        counts["parse"] += 1
        return parse(*args, **kwargs)
    monkeypatch.setattr(resources, "extract_code_text", counted_extract)
    monkeypatch.setattr(symbols, "_parse", counted_parse)
    with module("catalog").Catalog(root) as catalog:
        cards = catalog.all_cards()
        for operation in range(1, 3):
            states, _ = module("evidence_review").observe(root, catalog, cards)
            assert sum(len(rows) for rows in states.values()) == 25
            assert {item["status"] for rows in states.values() for item in rows} == {"fresh"}
            assert counts == {"extract": operation, "parse": operation}


def test_record_reuses_decoded_source_and_capture_cache_within_one_check(tmp_path, monkeypatch):
    root, code = fixture(tmp_path)
    resources, evidence, versions = module("source_resources"), module("evidence_review"), module("code_evidence")
    extract, capture = resources.extract_code_text, versions.capture
    extractions, caches = [], []
    def counted_extract(*args, **kwargs):
        extractions.append(args[0])
        return extract(*args, **kwargs)
    def checked_capture(*args, **kwargs):
        assert isinstance(kwargs.get("cache"), dict)
        caches.append(kwargs["cache"])
        return capture(*args, **kwargs)
    monkeypatch.setattr(resources, "extract_code_text", counted_extract)
    monkeypatch.setattr(versions, "capture", checked_capture)
    with module("catalog").Catalog(root) as catalog:
        source = catalog.get_file("code-wait")
    content, context = code.read_bytes(), {}
    for _ in range(5):
        for line in range(1, 4):
            evidence.record(context, source, {"code_id": "code-wait", "line_start": line, "line_end": line}, content)
    assert len(extractions) == 1
    assert len(context["code_versions"]) == 3
    assert all(cache is caches[0] for cache in caches)
    evidence.record({}, source, _function_reference("wait_reply", 1, 3), content)
    assert len(extractions) == 2 and caches[-1] is not caches[0]
    with pytest.raises(evidence.ContractError, match="CODE_EVIDENCE_CHANGED"):
        evidence.record(context, source, _function_reference("wait_reply", 1, 3),
                        content.replace(b"return 5", b"return 8"))
    assert len(extractions) == 2


@pytest.mark.parametrize("replacement", [False, True])
def test_semantic_reference_stamping_preserves_same_batch_retry_after_index_failure(tmp_path, monkeypatch, replacement):
    root, source = fixture(tmp_path)
    previous_version = confirm(root)
    source.write_bytes(source.read_bytes().replace(b"return 5", b"return 8"))
    ingest, library = module("ingest"), module("library")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    write_plan(root, [("waiting", "knowledge/waiting.md")] if replacement else [])
    if replacement:
        (root / ".build/cards/waiting.md").write_bytes(card("A reviewed corrected explanation."))
    assert ingest.maintenance_check(root, {})[1] == "passed"
    original_build = library.build_search
    def interrupted(*args, **kwargs):
        raise OSError("Synthetic index failure after reference stamping")
    monkeypatch.setattr(library, "build_search", interrupted)
    with pytest.raises(OSError, match="Synthetic index failure"):
        ingest.maintenance_commit(root, {"reason": "Actual current code and the card were reviewed."})
    published = (root / "knowledge/waiting.md").read_bytes()
    assert parsed(root)["code_ref"][0]["evidence_version"] != previous_version
    monkeypatch.setattr(library, "build_search", original_build)
    result, phase = ingest.maintenance_commit(root, {"reason": "Retry the same independently reviewed batch."})
    assert phase == "completed", result
    assert (root / "knowledge/waiting.md").read_bytes() == published
    assert not (root / ".build/task.json").exists()


def test_retry_can_remove_trigger_reference_and_stamp_another_reviewed_source(tmp_path, monkeypatch):
    root, first, second = _two_sources(tmp_path)
    first.write_bytes(first.read_bytes().replace(b"return 5", b"return 8"))
    second.write_bytes(second.read_bytes().replace(b"return 3", b"return 7"))
    ingest, library = module("ingest"), module("library")
    task, phase = ingest.maintenance_prepare(root, {"source": "code-wait"})
    assert phase == "prepared", task
    write_plan(root, [("waiting", "knowledge/waiting.md")])
    current = parsed(root)
    retained = [reference for reference in current["code_ref"] if reference["code_id"] == "code-retry"]
    (root / ".build/cards/waiting.md").write_bytes(card("Only the retained code still supports this card.", references=retained))
    assert ingest.maintenance_check(root, {})[1] == "passed"
    original_build = library.build_search
    def interrupted(*args, **kwargs):
        raise OSError("Synthetic index failure after dropping obsolete association")
    monkeypatch.setattr(library, "build_search", interrupted)
    with pytest.raises(OSError, match="Synthetic index failure"):
        ingest.maintenance_commit(root, {})
    published = (root / "knowledge/waiting.md").read_bytes()
    assert [reference["code_id"] for reference in parsed(root)["code_ref"]] == ["code-retry"]
    monkeypatch.setattr(library, "build_search", original_build)
    result, phase = ingest.maintenance_commit(root, {})
    assert phase == "completed", result
    assert (root / "knowledge/waiting.md").read_bytes() == published
