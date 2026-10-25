"""Public source scanning and material preparation over synthetic originals."""

import hashlib
import json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def hashed(data):
    return hashlib.sha256(data).hexdigest()


def test_default_scan_discovers_five_raw_classes_without_source_argument(harness):
    harness.write("docs-raw/specs/new.md", b"# Synthetic source\n")
    harness.write("docs-raw/chips/chip.md", b"# Synthetic chip\n")
    harness.write("sources/outside.md", b"Not an accepted raw source")
    result = harness.run("source-scan", {"operation_id": "scan-one"}, "scan")
    scan = harness.record(result["data"]["scan_ref"])
    assert result["phase"] == "scanned"
    assert scan["full_scan"] is True and scan["complete"] is True
    assert [(u["path"], u["change"]) for u in scan["units"]] == [
        ("docs-raw/chips/chip.md", "new"), ("docs-raw/specs/new.md", "new")
    ]
    assert all(u["progress"] is None for u in scan["units"])
    assert not (harness.root / "logs/ingest").exists()


def test_prepare_reads_all_card_states_and_each_adopted_version(harness):
    import yaml

    _, first = harness.capture("first", b"# Source\nOld first version.\n")
    _, second = harness.capture("second", b"# Source\nOld second version.\n")
    harness.write("knowledge/rules/draft.md", harness.card("draft", first, lifecycle="draft"))
    harness.write("knowledge/rules/old.md", harness.card("old", second, lifecycle="deprecated"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({
        "schema_version": "2.0", "resources": first["resources"],
        "snapshots": first["snapshots"] + second["snapshots"],
    }).encode())
    harness.write("docs-raw/specs/source.md", b"# Source\nCurrent third version.\n")
    scanned = harness.run("source-scan", {"operation_id": "batch"}, "scan")
    prepared = harness.run("source-scan", {
        "operation_id": "batch", "scan_ref": scanned["data"]["scan_ref"],
    }, "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    candidates = {c["card_id"]: c for c in material["candidates"]}
    assert set(candidates) == {"draft", "old"}
    assert candidates["draft"]["adopted_sources"][0]["snapshot_id"] == first["snapshots"][0]["snapshot_id"]
    assert candidates["old"]["adopted_sources"][0]["snapshot_id"] == second["snapshots"][0]["snapshot_id"]
    assert "Old first version." in candidates["draft"]["adopted_sources"][0]["text"]
    assert "Old second version." in candidates["old"]["adopted_sources"][0]["text"]
    assert not material["gaps"]


def test_record_only_defer_is_portable_and_remains_unfinished(harness):
    harness.write("docs-raw/specs/new.md", b"# Incomplete original\n")
    scanned = harness.run("source-scan", {"operation_id": "waiting"}, "scan")
    scan = harness.record(scanned["data"]["scan_ref"])
    unit = scan["units"][0]
    result = harness.run("source-scan", {
        "operation_id": "waiting", "scan_ref": scanned["data"]["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "defer", "reason": "Missing authoritative scope",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None,
                          "progress": "blocked", "card_refs": [], "claim_refs": []}],
    }, "record")
    record = harness.record(result["data"]["record_ref"])
    assert record["batch_kind"] == "record_only"
    assert record["inventory"]["digest"] == scan["digest"]
    assert record["content_view_digest"] is None
    assert not (harness.root / "logs/ingest").exists()
    assert not (harness.root / "knowledge").exists()
    # P7 owns the formal write. A portable unresolved record cannot suppress work.
    harness.write(record["target_path"], (harness.root / result["data"]["record_ref"]).read_bytes())
    later = harness.run("source-scan", {"operation_id": "later"}, "scan")
    assert harness.record(later["data"]["scan_ref"])["units"][0]["change"] == "unfinished"


def test_status_reports_actual_saved_stages_without_advancing_work(harness):
    harness.write("docs-raw/specs/pending.md", b"# Pending\n")
    harness.run("source-scan", {"operation_id": "pending"}, "scan")
    before = sorted(p.relative_to(harness.root).as_posix() for p in harness.root.rglob("*") if p.is_file())
    response = harness.run("source-scan", {"operation_id": "status-report", "target_operation_id": "pending"}, "status")
    assert response["phase"] == "status"
    assert response["data"]["operations"][0]["operation_id"] == "pending"
    assert response["data"]["operations"][0]["facts"][0]["stage"] == "scan"
    assert response["data"]["operations"][0]["git_submission"] == "not_verified"
    assert sorted(p.relative_to(harness.root).as_posix() for p in harness.root.rglob("*") if p.is_file()) == before


def persist_skip(harness, operation, source=None):
    request = {"operation_id": operation}
    if source:
        request["source"] = source
    result = harness.run("source-scan", request, "scan")
    scan = harness.record(result["data"]["scan_ref"])
    dispositions = [{"unit_id": u["unit_id"], "action": "skip", "kind": "substantive", "reason": "Fully read; no knowledge increment",
                     "observed_fingerprint": u["observed_fingerprint"], "adopted_fingerprint": None,
                     "progress": "skipped", "card_refs": [], "claim_refs": []} for u in scan["units"]]
    response = harness.run("source-scan", {"operation_id": operation, "scan_ref": result["data"]["scan_ref"],
                           "dispositions": dispositions, "skip_sample": {"independent": True, "reviewer": "separate-reviewer", "reason": "Synthetic full risk sample",
                           "sampled_unit_ids": [u["unit_id"] for u in scan["units"]], "unreviewed_unit_ids": []}}, "record")
    record = harness.record(response["data"]["record_ref"])
    # Fixture P7 formalization: preserve disposition facts, add real stage fact.
    record["status"] = "recorded"
    record["progress"] = {"apply": {"status": "recorded", "operation_id": operation, "view_digest": None}}
    record.pop("digest")
    record["digest"] = hashed(canonical(record))
    harness.write(record["target_path"], canonical(record))
    return scan


def test_incremental_history_keeps_out_of_scope_files_after_narrow_scan(harness):
    harness.write("docs-raw/specs/a.md", b"A\n")
    harness.write("docs-raw/specs/b.md", b"B\n")
    persist_skip(harness, "full")
    harness.write("docs-raw/specs/a.md", b"A changed\n")
    persist_skip(harness, "narrow", "docs-raw/specs/a.md")
    (harness.root / "docs-raw/specs/b.md").unlink()
    response = harness.run("source-scan", {"operation_id": "again"}, "scan")
    units = {u["path"]: u for u in harness.record(response["data"]["scan_ref"])["units"]}
    assert units["docs-raw/specs/a.md"]["change"] == "unchanged"
    assert units["docs-raw/specs/b.md"]["change"] == "missing"


def test_limited_scan_never_infers_deletion_outside_selected_scope(harness):
    harness.write("docs-raw/specs/a.md", b"A\n")
    harness.write("docs-raw/chips/b.md", b"B\n")
    persist_skip(harness, "full")
    (harness.root / "docs-raw/chips/b.md").unlink()
    response = harness.run("source-scan", {"operation_id": "only-a", "source": "docs-raw/specs"}, "scan")
    scan = harness.record(response["data"]["scan_ref"])
    assert scan["full_scan"] is False
    assert [u["path"] for u in scan["units"]] == ["docs-raw/specs/a.md"]


def test_record_rejects_omitted_unit_and_unreviewed_substantive_skip(harness):
    harness.write("docs-raw/specs/a.md", b"A\n")
    response = harness.run("source-scan", {"operation_id": "batch"}, "scan")
    scan = harness.record(response["data"]["scan_ref"])
    bad = harness.run("source-scan", {"operation_id": "batch", "scan_ref": response["data"]["scan_ref"], "dispositions": []}, "record", expected=2)
    assert bad["diagnostics"][0]["code"] == "UNIT_COVERAGE_INVALID"
    unit = scan["units"][0]
    bad = harness.run("source-scan", {"operation_id": "batch", "scan_ref": response["data"]["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "skip", "reason": "No new knowledge",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None,
                          "progress": "skipped", "card_refs": [], "claim_refs": []}]}, "record", expected=2)
    assert bad["diagnostics"][0]["code"] == "SKIP_SAMPLE_REQUIRED"


def test_prepare_expands_explicit_dependencies_but_not_related_links(harness):
    import yaml
    _, seed = harness.capture("seed-old")
    harness.write("docs-raw/specs/other.md", b"# Independent source\nUnrelated facts.\n")
    response = harness.run("source-capture", {"operation_id": "other-old", "source_id": "other", "source_path": "docs-raw/specs/other.md"})
    other = harness.record(response["data"]["bundle_ref"])
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": seed["resources"] + other["resources"],
        "snapshots": seed["snapshots"] + other["snapshots"]}).encode())
    harness.write("knowledge/rules/seed.md", harness.card("seed", seed))
    for identity, kind in (("requires-card", "requires"), ("derived-card", "derived_from"), ("related-card", "related_to")):
        harness.write("knowledge/rules/" + identity + ".md", harness.card(identity, other, relation=[{
            "type": kind, "target_card_id": "seed", "target_claim_id": "seed-claim", "context_ids": []}]))
    scanned = harness.run("source-scan", {"operation_id": "batch", "source": "docs-raw/specs/source.md"}, "scan")
    prepared = harness.run("source-scan", {"operation_id": "batch", "scan_ref": scanned["data"]["scan_ref"]}, "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    assert {c["card_id"] for c in material["candidates"]} == {"seed", "requires-card", "derived-card"}
    assert all((harness.root / source["original_ref"]).is_file() for candidate in material["candidates"] for source in candidate["adopted_sources"])
    assert all("recovery" in source for candidate in material["candidates"] for source in candidate["adopted_sources"])


def test_scan_rejects_external_source_scope(harness):
    harness.write("sources/outside.md", b"Outside allowed raw roots")
    response = harness.run("source-scan", {"operation_id": "invalid", "source": "sources/outside.md"}, "scan", expected=2)
    assert response["diagnostics"][0]["code"] == "RAW_SCOPE_REQUIRED"
    assert not (harness.root / ".build/operations/invalid").exists()


def test_pending_formal_record_does_not_prove_completed_processing(harness):
    harness.write("docs-raw/specs/a.md", b"A\n")
    persist_skip(harness, "not-applied")
    record = harness.record("logs/ingest/not-applied.yaml")
    record["status"], record["progress"] = "pending", {}
    record.pop("digest")
    record["digest"] = hashed(canonical(record))
    harness.write("logs/ingest/not-applied.yaml", canonical(record))
    response = harness.run("source-scan", {"operation_id": "retry"}, "scan")
    assert harness.record(response["data"]["scan_ref"])["units"][0]["change"] == "unfinished"


def test_scan_accepts_valid_object_progress_from_shared_processing_record(harness):
    harness.write("docs-raw/specs/a.md", b"A\n")
    persist_skip(harness, "object-progress")
    record = harness.record("logs/ingest/object-progress.yaml")
    record["dispositions"][0]["progress"] = {"status": "skipped"}
    record.pop("digest")
    record["digest"] = hashed(canonical(record))
    harness.write("logs/ingest/object-progress.yaml", canonical(record))
    result = harness.run("source-scan", {"operation_id": "later-object"}, "scan")
    assert harness.record(result["data"]["scan_ref"])["units"][0]["change"] == "unchanged"


def test_prepare_includes_explicit_current_code_evidence_without_fake_raw_units(harness):
    import importlib.util
    helper = harness.packages / "hs-knowledge-source-capture/tests/test_code_capture.py"
    spec = importlib.util.spec_from_file_location("source_scan_code_fixture", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo, context_ref = module.setup_code(harness)
    current = b"int synthetic(void) { return 7; }\n"
    (repo / "sample.c").write_bytes(current)
    captured = harness.run("source-capture", {"operation_id": "code-current", "kind": "code", "repo_id": "code",
        "relative_path": "sample.c", "source_id": "synthetic-code", "context_ref": context_ref})
    code = harness.record(captured["data"]["bundle_ref"])
    scanned = harness.run("source-scan", {"operation_id": "code-batch"}, "scan")
    assert harness.record(scanned["data"]["scan_ref"])["units"] == []
    prepared = harness.run("source-scan", {"operation_id": "code-batch", "scan_ref": scanned["data"]["scan_ref"],
        "code_bundle_refs": [{"bundle_ref": captured["data"]["bundle_ref"], "bundle_digest": code["digest"]}]}, "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    combined = harness.record(material["bundle_ref"])
    assert [r["kind"] for r in combined["resources"]] == ["code"]
    assert (harness.root / material["current_code"][0]["original_ref"]).read_bytes() == current
    assert material["current_code"][0]["current_source_matches"] is True
    (repo / "sample.c").write_bytes(b"int synthetic(void) { return 8; }\n")
    later = harness.run("source-scan", {"operation_id": "stale-code-batch"}, "scan")
    rejected = harness.run("source-scan", {"operation_id": "stale-code-batch", "scan_ref": later["data"]["scan_ref"],
        "code_bundle_refs": [{"bundle_ref": captured["data"]["bundle_ref"], "bundle_digest": code["digest"]}]}, "prepare", expected=3)
    assert rejected["diagnostics"][0]["code"] == "CURRENT_CODE_REQUIRED"


def test_record_preserves_maintenance_defer_without_inventing_raw_units(harness):
    scanned = harness.run("source-scan", {"operation_id": "maintenance"}, "scan")
    scan = harness.record(scanned["data"]["scan_ref"])
    scan["current_context"]["affected_claims"] = [{"card_id": "code-card", "claim_id": "claim", "reason": "code_changed"}]
    scan.pop("digest")
    scan["digest"] = hashed(canonical(scan))
    harness.write(scanned["data"]["scan_ref"], canonical(scan))
    unit = {"unit_id": "maintenance:code-card#claim", "card_id": "code-card", "claim_id": "claim", "outcome": "defer", "reason": "Actual build evidence missing"}
    plan = {"schema_version": "2.0", "record_kind": "semantic_plan", "operation_id": "maintenance", "rules_digest": harness.rules,
        "tool_identity": scan["tool_identity"],
        "scan_ref": scanned["data"]["scan_ref"], "scan_digest": scan["digest"], "material_ref": ".build/operations/maintenance/material.json",
        "units": [], "card_actions": [], "target_queries": [], "maintenance_units": [unit]}
    plan["digest"] = hashed(canonical(plan))
    plan_ref = harness.write(".build/operations/maintenance/semantic-plan.json", canonical(plan))
    result = harness.run("source-scan", {"operation_id": "maintenance", "scan_ref": scanned["data"]["scan_ref"],
        "semantic_plan_ref": plan_ref, "dispositions": []}, "record")
    record = harness.record(result["data"]["record_ref"])
    assert record["dispositions"] == []
    assert record["maintenance_dispositions"] == [unit]
    assert record["pending"][0]["unit_id"] == unit["unit_id"]


def existing_card_record(harness, card_id, claim_id, *, expected=0):
    import yaml
    _, bundle = harness.capture("existing-source")
    harness.write("knowledge/rules/existing.md", harness.card("existing", bundle, lifecycle="stable"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"], "snapshots": bundle["snapshots"]}).encode())
    scanned = harness.run("source-scan", {"operation_id": "associated-record"}, "scan")
    unit = harness.record(scanned["data"]["scan_ref"])["units"][0]
    return harness.run("source-scan", {"operation_id": "associated-record", "scan_ref": scanned["data"]["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "defer", "reason": "Related existing knowledge awaits further review",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None, "progress": "blocked",
                          "card_refs": [card_id], "claim_refs": [{"card_id": card_id, "claim_id": claim_id}]}]}, "record", expected=expected)


def test_record_only_can_reference_existing_formal_card_without_writing_it(harness):
    result = existing_card_record(harness, "existing", "existing-claim")
    record = harness.record(result["data"]["record_ref"])
    assert record["batch_kind"] == "record_only" and record["content_view_digest"] is None
    assert record["dispositions"][0]["card_refs"] == ["existing"]
    assert record["dispositions"][0]["progress"] == "blocked"
    assert not (harness.root / "logs/ingest").exists()


def test_record_only_rejects_nonexistent_card_reference(harness):
    result = existing_card_record(harness, "invented", "invented-claim", expected=2)
    assert result["diagnostics"][0]["code"] == "DANGLING_CARD_RECORD"
    assert not (harness.root / ".build/operations/associated-record/ingest-record.yaml").exists()


def test_record_only_rejects_nonexistent_claim_on_existing_card(harness):
    result = existing_card_record(harness, "existing", "invented-claim", expected=2)
    assert result["diagnostics"][0]["code"] == "DANGLING_CLAIM_RECORD"


def test_record_only_reference_does_not_adopt_a_build_draft(harness):
    harness.write(".build/candidates/failed.md", b"Unreviewed failed candidate; not formal knowledge")
    result = existing_card_record(harness, ".build/candidates/failed.md", "candidate-claim", expected=2)
    assert result["diagnostics"][0]["code"] == "DANGLING_CARD_RECORD"
