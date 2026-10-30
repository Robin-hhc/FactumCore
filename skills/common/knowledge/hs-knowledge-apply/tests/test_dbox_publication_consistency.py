"""A publication's execution fields must agree with its frozen content basis.

The public CLIs operate only on synthetic data and installed frozen packages.
R7 intentionally fails the protection assertions, retaining its real unsafe
responses on disk; the exact same tests must pass against the repaired reader.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


_spec = importlib.util.spec_from_file_location(
    "_dbox_consistency_portable", Path(__file__).with_name("test_dbox_portable_recovery.py")
)
PORTABLE = importlib.util.module_from_spec(_spec)
_previous_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    _spec.loader.exec_module(PORTABLE)
finally:
    sys.dont_write_bytecode = _previous_bytecode


def read(path):
    absolute = str(path.absolute())
    if os.name == "nt" and not absolute.startswith("\\\\?\\"):
        absolute = "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
    return Path(absolute).read_bytes()


def files_under(root):
    return {path.relative_to(root).as_posix(): read(path)
            for path in root.rglob("*") if path.is_file()}


def stop_before_build(base):
    """Stop the actual public batch after publication, before its index build."""
    probe = base / "stop-before-build"
    probe.mkdir()
    marker = probe / "called.txt"
    program = '''from pathlib import Path
import sys
def profile(frame, event, value):
    if (event == "call" and frame.f_code.co_name == "execute"
            and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/index_runtime.py")
            and frame.f_locals["ctx"].args.action == "build"):
        Path(MARKER).write_text("published before build", encoding="utf-8")
        sys.setprofile(None)
        raise RuntimeError("SYNTHETIC_CONSISTENCY_STOP_BEFORE_BUILD")
sys.setprofile(profile)
'''.replace("MARKER", repr(str(marker)))
    (probe / "sitecustomize.py").write_text(program, encoding="utf-8")
    return {**os.environ, "PYTHONPATH": str(probe)}, marker


def observe(pipeline, action, request):
    """Capture an unsafe old result before asserting the repaired contract."""
    pipeline.sequence += 1
    incoming = pipeline.base / f"consistency-in-{pipeline.sequence}.json"
    outgoing = pipeline.base / f"consistency-out-{pipeline.sequence}.json"
    incoming.write_bytes(PORTABLE.canonical(request))
    started = time.perf_counter()
    process = subprocess.run([sys.executable, "-X", "utf8",
        str(pipeline.skills / "hs-knowledge-apply/scripts/cli.py"),
        "--knowledge-root", str(pipeline.root), "--input", str(incoming),
        "--output", str(outgoing), "--action", action], capture_output=True, timeout=180)
    response = json.loads(read(outgoing)) if outgoing.exists() else {}
    observation = {"action": action, "returncode": process.returncode,
        "seconds": time.perf_counter() - started, "response": response,
        "stderr": process.stderr.decode(errors="replace")}
    with (pipeline.base / "consistency-cli-observations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(observation, ensure_ascii=False) + "\n")
    return observation


@pytest.mark.parametrize("damage", ["batch-kind", "deletes"])
def test_execution_fields_cannot_skip_or_replace_content_finalization(tmp_path, damage):
    pipeline, external, relative, original, _, _, _, request = PORTABLE.pending(tmp_path / "p")
    baseline = pipeline.call("knowledge-apply", {"operation_id": "old-index"}, "index-build")["data"]
    pipeline.call("knowledge-apply", {"operation_id": "old-active",
        "generation_ref": baseline["generation_ref"], "expected_active": baseline["expected_active"]}, "index-activate")
    active = pipeline.root / "artifacts/indexes/local/active.json"
    old_active = read(active)
    old_pointer = json.loads(old_active)
    environment, marker = stop_before_build(tmp_path)
    stopped = pipeline.call("knowledge-apply", request, "batch", expected=2, environment=environment)
    assert marker.read_text(encoding="utf-8") == "published before build"
    assert "SYNTHETIC_CONSISTENCY_STOP_BEFORE_BUILD" in json.dumps(stopped)
    operation = request["operation_id"]
    publication = pipeline.root / f"logs/publications/{operation}/manifest.json"
    completion = pipeline.root / f"logs/publications/{operation}/completion.json"
    build_ref = pipeline.root / f".build/operations/{operation}/batch-build.json"
    view = pipeline.root / request["view_ref"]
    original_manifest_bytes = read(publication)
    original_manifest = json.loads(original_manifest_bytes)
    assert original_manifest["batch_kind"] == original_manifest["content_basis"]["batch_kind"] == "content"
    assert original_manifest["published_view"]["batch_kind"] == "content"
    assert original_manifest["deletes"] == original_manifest["content_basis"]["deletes"] == []
    assert not build_ref.exists() and not completion.exists() and view.exists()
    assert read(active) == old_active
    formal = {row["path"]: read(pipeline.root / row["path"]) for row in original_manifest["files"]}
    stage = pipeline.root / f".build/operations/{operation}"
    stage_before = files_under(stage)
    assert request["view_ref"].split(f".build/operations/{operation}/", 1)[1] in stage_before
    generations_before = {path.parent.name for path in (pipeline.root / "artifacts/indexes/local").glob("gen-*/manifest.json")}
    damaged = copy.deepcopy(original_manifest)
    if damage == "batch-kind":
        damaged["batch_kind"] = "record_only"
    else:
        damaged["deletes"] = [{"path": "knowledge/rules/not-deleted.md", "expected_old_digest": None}]
    damaged["digest"] = PORTABLE.sha(PORTABLE.canonical({key: value for key, value in damaged.items() if key != "digest"}))
    damaged_bytes = PORTABLE.canonical(damaged)
    publication.write_bytes(damaged_bytes)
    (pipeline.base / "consistency-original-manifest.json").write_bytes(original_manifest_bytes)
    reader = observe(pipeline, "verify-result", {"operation_id": operation,
        "publication_ref": publication.relative_to(pipeline.root).as_posix(), "purpose": "historical"})
    resumed = observe(pipeline, "batch", {"operation_id": operation})
    stage_after = files_under(stage)
    generations_after = {path.parent.name for path in (pipeline.root / "artifacts/indexes/local").glob("gen-*/manifest.json")}
    saved_completion = json.loads(read(completion)) if completion.exists() else None
    facts = {"damage": damage, "release_checkout": str(PORTABLE.RELEASE),
        "reader": reader, "batch": resumed, "published_on_disk": json.loads(read(publication))["published"],
        "completion": saved_completion, "build_exists": build_ref.exists(),
        "generations_before": sorted(generations_before), "generations_after": sorted(generations_after),
        "old_active_sha256": PORTABLE.sha(old_active), "active_after_sha256": PORTABLE.sha(read(active)),
        "original_source_unchanged": read(external / relative) == original,
        "formal_contents_unchanged": all(read(pipeline.root / path) == raw for path, raw in formal.items()),
        "view_exists": view.exists(), "stage_removed": sorted(set(stage_before) - set(stage_after)),
        "stage_changed": sorted(path for path in set(stage_before) & set(stage_after)
                                if stage_before[path] != stage_after[path])}
    evidence = pipeline.base / "consistency-observation.json"
    evidence.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    # These fail against R7 after its unsafe outcome has been captured above.
    for observation in (reader, resumed):
        assert observation["returncode"] == 2, facts
        assert any(row["code"] == "INVALID_PUBLICATION"
                   for row in observation["response"].get("diagnostics", [])), facts
    assert facts["published_on_disk"] is True
    assert saved_completion is None and resumed["response"].get("data", {}).get("batch_complete") is not True
    assert not build_ref.exists() and generations_after == generations_before
    assert read(active) == old_active and view.exists()
    assert stage_after == stage_before
    assert read(publication) == damaged_bytes
    assert facts["original_source_unchanged"] and facts["formal_contents_unchanged"]
    publication.write_bytes(original_manifest_bytes)
    status = pipeline.call("knowledge-source", {"operation_id": "restored-status",
        "target_operation_id": operation}, "status")["data"]["operations"][0]
    assert status["completion"]["published"] is True and status["completion"]["batch_complete"] is False
    completed = pipeline.call("knowledge-apply", {"operation_id": operation}, "batch")["data"]
    assert completed["published"] is True and completed["batch_complete"] is True and completed["activated"] is True
    assert completed["cleanup"]["status"] == "done" and not view.exists()
    pointer = pipeline.record("artifacts/indexes/local/active.json")
    assert pointer["generation_ref"] == completed["generation_ref"] != baseline["generation_ref"]
    assert pointer["previous_active_digest"] == old_pointer["digest"]
    assert read(publication) == original_manifest_bytes
    assert read(external / relative) == original
    assert all(read(pipeline.root / path) == raw for path, raw in formal.items())
    found = PORTABLE.search(pipeline, "restored-current", "current")
    hit = PORTABLE.one_match(found)
    assert found["generation_ref"] == completed["generation_ref"]
    read_card = pipeline.call("knowledge-query", {"operation_id": "restored-read",
        "receipt_ref": found["receipt_ref"], "card_id": hit["card_id"]}, "read")["data"]
    assert read_card["card_digest"] == PORTABLE.sha(formal["knowledge/rules/portable-dbox-rule.md"])
    assert read_card["generation_ref"] == completed["generation_ref"]
    facts.update(restored_status=status["completion"], restored_batch_complete=completed["batch_complete"],
                 restored_generation=completed["generation_ref"], restored_retrieval_complete=True)
    evidence.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("damage", ["cases", "cas"])
def test_original_batch_intent_rejects_replaced_queries_or_activation_baseline(tmp_path, damage):
    pipeline, external, relative, original, _, _, _, request = PORTABLE.pending(tmp_path / "p")
    baseline = pipeline.call("knowledge-apply", {"operation_id": "old-index"}, "index-build")["data"]
    pipeline.call("knowledge-apply", {"operation_id": "old-active",
        "generation_ref": baseline["generation_ref"], "expected_active": baseline["expected_active"]}, "index-activate")
    active = pipeline.root / "artifacts/indexes/local/active.json"
    original_active_bytes = read(active)
    original_pointer = json.loads(original_active_bytes)
    environment, marker = stop_before_build(tmp_path)
    stopped = pipeline.call("knowledge-apply", request, "batch", expected=2, environment=environment)
    assert marker.read_text(encoding="utf-8") == "published before build"
    assert "SYNTHETIC_CONSISTENCY_STOP_BEFORE_BUILD" in json.dumps(stopped)
    operation = request["operation_id"]
    publication = pipeline.root / f"logs/publications/{operation}/manifest.json"
    completion = pipeline.root / f"logs/publications/{operation}/completion.json"
    stage = pipeline.root / f".build/operations/{operation}"
    intent_path = stage / "batch-intent.json"
    original_intent_bytes = read(intent_path)
    intent = json.loads(original_intent_bytes)
    original_manifest_bytes = read(publication)
    manifest = json.loads(original_manifest_bytes)
    original_cases = copy.deepcopy(manifest["published_view"]["target_queries"])
    assert intent["cases"] == original_cases and len(original_cases) == 1
    assert intent["expected_active"] == manifest["index_inputs"]["expected_active"] == original_pointer["digest"]
    formal = {row["path"]: read(pipeline.root / row["path"]) for row in manifest["files"]}
    view = pipeline.root / request["view_ref"]
    assert not completion.exists() and view.exists()
    competitor = None
    if damage == "cases":
        manifest["published_view"]["target_queries"][0].update(id="replaced-query", query="portable")
        assert manifest["published_view"]["target_queries"] != intent["cases"]
        manifest["published_view_digest"] = PORTABLE.sha(PORTABLE.canonical(manifest["published_view"]))
    else:
        # Create a real competing generation and activate it via the public CAS.
        # Its pointer is never fabricated or edited by this test.
        competing = pipeline.call("knowledge-apply", {"operation_id": "competitor-build"}, "index-build")["data"]
        assert competing["expected_active"] == original_pointer["digest"]
        activated = pipeline.call("knowledge-apply", {"operation_id": "competitor-activate",
            "generation_ref": competing["generation_ref"], "expected_active": competing["expected_active"]}, "index-activate")
        assert activated["data"]["activated"] is True
        competitor = json.loads(read(active))
        assert competitor["generation_ref"] == competing["generation_ref"]
        assert competitor["previous_active_digest"] == original_pointer["digest"]
        assert competitor["digest"] != intent["expected_active"]
        manifest["index_inputs"]["expected_active"] = competitor["digest"]
    assert read(intent_path) == original_intent_bytes
    active_before_retry = read(active)
    stage_before = files_under(stage)
    generations_before = {path.parent.name for path in (pipeline.root / "artifacts/indexes/local").glob("gen-*/manifest.json")}
    manifest["digest"] = PORTABLE.sha(PORTABLE.canonical({key: value for key, value in manifest.items() if key != "digest"}))
    mutated_bytes = PORTABLE.canonical(manifest)
    publication.write_bytes(mutated_bytes)
    (pipeline.base / "intent-original-manifest.json").write_bytes(original_manifest_bytes)
    (pipeline.base / "intent-original-record.json").write_bytes(original_intent_bytes)
    attempted = observe(pipeline, "batch", {"operation_id": operation})
    stage_after = files_under(stage)
    generations_after = {path.parent.name for path in (pipeline.root / "artifacts/indexes/local").glob("gen-*/manifest.json")}
    saved_completion = json.loads(read(completion)) if completion.exists() else None
    facts = {"damage": damage, "release_checkout": str(PORTABLE.RELEASE), "batch": attempted,
        "original_cases": original_cases, "mutated_cases": manifest["published_view"]["target_queries"],
        "original_expected_active": intent["expected_active"],
        "mutated_expected_active": manifest["index_inputs"]["expected_active"],
        "competitor_pointer": competitor, "completion": saved_completion,
        "executed_cases": (saved_completion or {}).get("retrieval", {}).get("regression", {}).get("cases"),
        "completed_expected_active": (saved_completion or {}).get("retrieval", {}).get("expected_active"),
        "active_before_sha256": PORTABLE.sha(active_before_retry),
        "active_after_sha256": PORTABLE.sha(read(active)),
        "generations_before": sorted(generations_before), "generations_after": sorted(generations_after),
        "source_unchanged": read(external / relative) == original,
        "formal_contents_unchanged": all(read(pipeline.root / path) == raw for path, raw in formal.items()),
        "stage_removed": sorted(set(stage_before) - set(stage_after)),
        "stage_changed": sorted(path for path in set(stage_before) & set(stage_after)
                                if stage_before[path] != stage_after[path]),
        "view_exists": view.exists(), "original_intent_preserved_before_attempt": True}
    evidence = pipeline.base / "intent-observation.json"
    evidence.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    # R8 fails here only after actual changed queries/CAS execution is recorded.
    assert attempted["returncode"] == 2, facts
    assert any(row["code"] == "BATCH_INPUT_CHANGED"
               for row in attempted["response"].get("diagnostics", [])), facts
    assert saved_completion is None and view.exists()
    assert read(active) == active_before_retry and generations_after == generations_before
    assert stage_after == stage_before and read(intent_path) == original_intent_bytes
    assert read(publication) == mutated_bytes
    assert facts["source_unchanged"] and facts["formal_contents_unchanged"]
    publication.write_bytes(original_manifest_bytes)
    if damage == "cases":
        resumed = pipeline.call("knowledge-apply", {"operation_id": operation}, "batch")["data"]
        assert resumed["published"] is True and resumed["batch_complete"] is True
        assert resumed["activated"] is True and resumed["cleanup"]["status"] == "done" and not view.exists()
        saved = json.loads(read(completion))
        assert saved["retrieval"]["regression"]["cases"] == original_cases
        assert saved["retrieval"]["expected_active"] == original_pointer["digest"]
        pointer = json.loads(read(active))
        assert pointer["generation_ref"] == resumed["generation_ref"]
        assert pointer["previous_active_digest"] == original_pointer["digest"]
        found = PORTABLE.search(pipeline, "restored-original-cases", "current")
        hit = PORTABLE.one_match(found)
        read_card = pipeline.call("knowledge-query", {"operation_id": "restored-original-read",
            "receipt_ref": found["receipt_ref"], "card_id": hit["card_id"]}, "read")["data"]
        assert found["generation_ref"] == read_card["generation_ref"] == resumed["generation_ref"]
        facts.update(restored_batch_complete=True, restored_cases=saved["retrieval"]["regression"]["cases"])
    else:
        # The original baseline remains binding: restoring metadata cannot erase
        # the genuine independent activation that won the CAS in the meantime.
        rejected = observe(pipeline, "batch", {"operation_id": operation})
        facts["restored_baseline_attempt"] = rejected
        evidence.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        assert rejected["returncode"] == 3 and rejected["response"]["phase"] == "awaiting", rejected
        assert any(row["code"] == "ACTIVE_CHANGED"
                   for row in rejected["response"].get("diagnostics", [])), rejected
        assert read(active) == active_before_retry
        assert files_under(stage) == stage_before and read(intent_path) == original_intent_bytes
        assert not completion.exists() and view.exists()
        facts.update(restored_baseline_attempt=rejected, restored_batch_complete=False,
                     restored_competitor_still_active=json.loads(read(active)) == competitor)
    status = pipeline.call("knowledge-source", {"operation_id": "restored-intent-status",
        "target_operation_id": operation}, "status")["data"]["operations"][0]
    assert status["completion"]["published"] is True
    assert status["completion"]["batch_complete"] is (damage == "cases")
    assert read(publication) == original_manifest_bytes
    assert read(external / relative) == original
    assert all(read(pipeline.root / path) == raw for path, raw in formal.items())
    facts["restored_status"] = status["completion"]
    evidence.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
