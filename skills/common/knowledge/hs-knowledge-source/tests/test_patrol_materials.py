"""Synthetic patrol material contracts; no business originals or Git-MM calls."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import yaml
import pytest


def context_for(harness, operation, **request):
    path = harness.packages / "hs-knowledge-source/scripts/support.py"
    spec = importlib.util.spec_from_file_location("patrol_material_public_support", path)
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    args = SimpleNamespace(knowledge_root=str(harness.root), rules_digest=harness.rules,
                           action="scan", catalog=str(harness.catalog))
    return support.Context(args, {"operation_id": operation, **request}, path.parents[1])


def inventory(harness, operation):
    response = harness.run("source", {"operation_id": operation}, "scan")
    return response["data"]["scan_ref"], harness.record(response["data"]["scan_ref"])


def test_patrol_keeps_bad_document_debt_while_preparing_readable_units(harness):
    bad, good = "docs-raw/specs/bad.md", "docs-raw/specs/good.md"
    harness.write(bad, b"\xff\x00Invalid Markdown encoding")
    harness.write(good, b"# Readable\nKeep this material.\n")
    scan_ref, scan = inventory(harness, "mixed-originals")
    response = harness.run("source", {
        "operation_id": "mixed-originals", "scan_ref": scan_ref,
        "unit_ids": [row["unit_id"] for row in scan["units"]],
        "tolerate_source_errors": True,
    }, "prepare")
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    bad_unit = next(row["unit_id"] for row in scan["units"] if row["path"] == bad)
    assert {row["path"] for row in bundle["resources"]} == {good}
    assert {row["path"] for row in material["units"]} == {bad, good}
    assert material["unit_ids"] == sorted(row["unit_id"] for row in scan["units"])
    assert any(row["unit_id"] == bad_unit and row["path"] == bad
               and row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE" for row in material["gaps"])
    assert {row["path"] for row in material["current_files"]} == {good}
    assert (harness.root / bad).read_bytes() == b"\xff\x00Invalid Markdown encoding"


@pytest.mark.parametrize("replacement", [b"# Changed after observation\n", b"\xff\x00Changed into unreadable source"])
def test_patrol_tolerance_does_not_swallow_fixed_inventory_drift(harness, replacement):
    path = "docs-raw/specs/source.md"
    harness.write(path, b"# Observed\n")
    scan_ref, _ = inventory(harness, "changed-original")
    harness.write(path, replacement)
    response = harness.run("source", {
        "operation_id": "changed-original", "scan_ref": scan_ref,
        "tolerate_source_errors": True,
    }, "prepare", 3)
    assert response["data"]["needs_scan"] is True
    assert response["data"]["affected_scope"] == [path]
    assert "SOURCE_CHANGED" in {row["code"] for row in response["diagnostics"]}
    assert not (harness.root / ".build/operations/changed-original/materials").exists()


def test_scoped_context_retains_limits_and_inventory_coverage(harness):
    bundles = []
    for identity in ("selected", "unselected"):
        path = "docs-raw/specs/" + identity + ".md"
        harness.write(path, b"# Original\nSynthetic evidence.\n")
        captured = harness.run("source", {"operation_id": "seed-" + identity,
            "source_path": path, "source_id": identity}, "capture")
        bundle = harness.record(captured["data"]["bundle_ref"])
        harness.publish_bundle(bundle)
        harness.write("knowledge/rules/" + identity + ".md", harness.card(identity, bundle))
        bundles.append(bundle)
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0",
        "resources": [row for bundle in bundles for row in bundle["resources"]],
        "snapshots": [row for bundle in bundles for row in bundle["snapshots"]]}, sort_keys=False).encode())
    harness.write("docs-raw/specs/selected.md", b"# Changed\n")
    (harness.root / "docs-raw/specs/unselected.md").unlink()
    context = context_for(harness, "partial")
    observed, phase = context.modules["maintenance"].inspect_context(context, source_ids={"selected"})
    assert phase == "inspected" and observed["complete"] is True
    assert {row["card_id"] for row in observed["affected_claims"]} == {"selected"}
    assert observed["coverage"] == {"scope": "selected_sources", "source_ids": ["selected"],
                                    "all_sources_checked": False}
    scanned, _ = context.modules["source_inventory"].scan(context, current_context=observed)
    fixed = harness.record(scanned["scan_ref"])
    assert fixed["current_context"] == observed
    assert fixed["full_scan"] is True  # all raw paths; source-reference coverage stays separate.
    # This internal override cannot be injected through a public JSON request.
    normal = harness.run("source", {"operation_id": "full", "current_context": observed}, "scan")
    full = harness.record(normal["data"]["scan_ref"])["current_context"]
    assert {row["card_id"] for row in full["affected_claims"]} == {"selected", "unselected"}
    assert full["coverage"]["all_sources_checked"] is True
    harness.write("knowledge/rules/dependent.md", harness.card("dependent", bundles[0],
        relation=[{"type": "requires", "target_card_id": "unselected", "context_ids": []}]))
    state = context.modules["maintenance"].state(context)
    state["blocked_claims"] = [{"card_id": "unselected", "claim_id": "*", "reason": "semantic_debt"}]
    context.save("logs/events/state.json", context.seal(state, "maintenance_state"))
    restricted, _ = context.modules["maintenance"].inspect_context(context, source_ids=set())
    assert {(row["card_id"], row["reason"]) for row in restricted["affected_claims"]} == {
        ("unselected", "semantic_debt"), ("dependent", "dependency_not_qualified")}


def test_patrol_collects_local_markdown_attachments(harness):
    primary, attachment = "docs-raw/specs/source.md", "docs-raw/specs/image asset.png"
    original = b'# Source\n![local](<image%20asset.png>)\n![remote](https://invalid.example/a.png)\n'
    harness.write(primary, original)
    harness.write(attachment, b"synthetic opaque attachment")
    scan_ref, scan = inventory(harness, "attachments")
    unit = next(row for row in scan["units"] if row["path"] == primary)
    response = harness.run("source", {"operation_id": "attachments", "scan_ref": scan_ref,
        "unit_ids": [unit["unit_id"]], "collect_local_attachments": True,
        "tolerate_source_errors": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    assert {row["path"] for row in bundle["resources"]} == {primary, attachment}
    assert {row["kind"] for row in bundle["resources"]} == {"raw", "attachment"}
    assert {row["path"] for row in material["current_files"]} == {primary, attachment}
    assert any("not fetched" in row.get("reason", "") for row in material["gaps"])
    assert (harness.root / primary).read_bytes() == original


@pytest.mark.parametrize("suffix,bad_bytes", [(".pdf", b"not a PDF"), (".docx", b"not a ZIP document")])
def test_patrol_retains_corrupt_binary_document_debt(harness, suffix, bad_bytes):
    bad, good = "docs-raw/specs/bad" + suffix, "docs-raw/specs/good.md"
    harness.write(bad, bad_bytes)
    harness.write(good, b"# Readable\n")
    scan_ref, _ = inventory(harness, "binary")
    response = harness.run("source", {"operation_id": "binary", "scan_ref": scan_ref,
        "tolerate_source_errors": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    assert {row["path"] for row in bundle["resources"]} == {good}
    assert any(row["path"] == bad and row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE"
               for row in material["gaps"])


@pytest.mark.parametrize("reference", ["absent.png", "../../../../outside.md", "https://invalid.example/a.png"])
def test_patrol_attachment_gaps_are_local_and_do_not_block_other_units(harness, reference):
    bad, good = "docs-raw/specs/linked.md", "docs-raw/specs/good.md"
    harness.write(bad, ("# Linked\n![asset](" + reference + ")\n").encode())
    harness.write(good, b"# Readable\n")
    scan_ref, _ = inventory(harness, "linked")
    response = harness.run("source", {"operation_id": "linked", "scan_ref": scan_ref,
        "collect_local_attachments": True, "tolerate_source_errors": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    if reference.startswith("https:"):
        assert {row["path"] for row in bundle["resources"]} == {bad, good}
        assert any("not fetched" in row.get("reason", "") for row in material["gaps"])
    else:
        assert {row["path"] for row in bundle["resources"]} == {good}
        assert any(row["path"] == bad and row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE"
                   for row in material["gaps"])


def test_explicit_patrol_units_include_new_raw_and_candidate_source(harness):
    spec = importlib.util.spec_from_file_location("patrol_supported_ingest_fixture", Path(__file__).with_name("test_supported_workflow.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    flow = fixture.planned_flow.__wrapped__(harness)
    flow.produce()
    harness.write("docs-raw/specs/new.md", b"# New source\n")
    scan_ref, scan = inventory(harness, "union")
    assert {(row["path"], row["change"]) for row in scan["units"]} == {
        ("docs-raw/specs/source.md", "unchanged"), ("docs-raw/specs/new.md", "new")}
    response = harness.run("source", {"operation_id": "union", "scan_ref": scan_ref,
        "unit_ids": [row["unit_id"] for row in scan["units"]], "candidate_card_ids": ["rule"],
        "tolerate_source_errors": True, "collect_local_attachments": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    assert {row["path"] for row in bundle["resources"]} == {"docs-raw/specs/source.md", "docs-raw/specs/new.md"}
    assert [row["card_id"] for row in material["candidates"]] == ["rule"]
    assert set(material["unit_ids"]) == {row["unit_id"] for row in scan["units"]}


def test_patrol_can_prepare_explicit_current_code_without_raw(harness):
    spec = importlib.util.spec_from_file_location("patrol_code_capture_fixture", Path(__file__).with_name("test_code_capture.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    repo, _ = fixture.setup_code(harness)
    raw = (repo / "sample.c").read_bytes()
    response = harness.run("source", {"operation_id": "code-only", "targets": [{"kind": "code",
        "repo_id": "code", "relative_path": "sample.c", "expected_fingerprint": hashlib.sha256(raw).hexdigest()}],
        "tolerate_source_errors": True, "collect_local_attachments": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    assert material["unit_ids"] == []
    assert len(material["units"]) == 1 and material["units"][0]["source_kind"] == "code"
    assert len(material["current_code"]) == 1 and material["current_code"][0]["current_source_matches"] is True
    assert {row["kind"] for row in material["current_files"]} == {"code", "config"}


def test_regular_prepare_still_rejects_unreadable_primary(harness):
    harness.write("docs-raw/specs/bad.md", b"\xff\x00Unreadable")
    response = harness.run("source", {"operation_id": "strict",
        "targets": [{"source_path": "docs-raw/specs/bad.md"}]}, "prepare", 2)
    assert "material_ref" not in response["data"]


def test_patrol_rejects_changed_code_before_decode_or_capture(harness):
    spec = importlib.util.spec_from_file_location("patrol_code_drift_fixture", Path(__file__).with_name("test_code_capture.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    repo, _ = fixture.setup_code(harness)
    expected = hashlib.sha256((repo / "sample.c").read_bytes()).hexdigest()
    (repo / "sample.c").write_bytes(b"\xff\x00changed code")
    response = harness.run("source", {"operation_id": "code-drift", "targets": [{"kind": "code",
        "repo_id": "code", "relative_path": "sample.c", "text_encoding": "utf-8",
        "expected_fingerprint": expected}], "tolerate_source_errors": True}, "prepare", 3)
    assert response["data"]["needs_scan"] is True
    assert response["data"]["affected_scope"] == ["sample.c"]
    assert "SOURCE_CHANGED" in {row["code"] for row in response["diagnostics"]}


def test_patrol_keeps_failed_explicit_target_observation(harness):
    path = "docs-raw/specs/bad.md"
    harness.write(path, b"\xff\x00Unreadable")
    response = harness.run("source", {"operation_id": "target-gap", "targets": [{
        "target_id": "broken-original", "source_path": path}], "tolerate_source_errors": True}, "prepare")
    material = harness.record(response["data"]["material_ref"])
    assert len(material["units"]) == 1
    assert material["units"][0]["target_id"] == "broken-original"
    assert material["units"][0]["path"] == path
    assert material["units"][0]["status"] == "unavailable"
    assert any(row["target_id"] == "broken-original" for row in material["gaps"])


@pytest.mark.parametrize("mode", ["scan", "target"])
def test_patrol_supplement_resolves_only_recaptured_attachment_gap(harness, mode):
    path = "docs-raw/specs/source.md"
    harness.write(path, b"# Linked\n![asset](missing.png)\n")
    scan_ref, _ = inventory(harness, "supplement")
    request = {"operation_id": "supplement", **({"scan_ref": scan_ref} if mode == "scan" else {
        "targets": [{"target_id": "linked", "source_path": path}]}),
               "collect_local_attachments": True, "tolerate_source_errors": True}
    first = harness.run("source", request, "prepare")
    previous_ref = first["data"]["material_ref"]
    previous_bytes = (harness.root / previous_ref).read_bytes()
    assert any(row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE" for row in first["data"]["gaps"])
    harness.write("docs-raw/specs/missing.png", b"opaque attachment")
    second = harness.run("source", {**request, "existing_material_ref": previous_ref}, "prepare")
    material = harness.record(second["data"]["material_ref"])
    assert material["previous_material_ref"] == previous_ref
    assert not any(row["code"] == "CURRENT_ORIGINAL_UNAVAILABLE" for row in material["gaps"])
    assert {row["path"] for row in harness.record(material["bundle_ref"])["resources"]} == {
        path, "docs-raw/specs/missing.png"}
    assert (harness.root / previous_ref).read_bytes() == previous_bytes


def publish_record_only(harness, operation, scan_ref, scan, *, progress="skipped", action=None):
    dispositions = [{"unit_id": row["unit_id"], "action": action or ("skip" if progress in {"skipped", "withdrawn"} else "defer"),
        "reason": "Explicit synthetic source disposition", "observed_fingerprint": row["observed_fingerprint"],
        "adopted_fingerprint": None, "progress": progress, "card_refs": [], "claim_refs": []}
        for row in scan["units"]]
    record = harness.run("source", {"operation_id": operation, "scan_ref": scan_ref,
        "dispositions": dispositions}, "record")
    applied = harness.run("apply", {"operation_id": operation,
        "ingest_record_ref": record["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True
    return harness.record("logs/ingest/" + operation + ".yaml")


@pytest.mark.parametrize("mode", ["delete", "rename"])
@pytest.mark.parametrize("progress", ["skipped", "withdrawn"])
def test_terminal_deleted_raw_is_unchanged_until_it_reappears(harness, mode, progress):
    old, new = "docs-raw/specs/old.md", "docs-raw/specs/new.md"
    original = b"# Original\nStable raw identity.\n"
    harness.write(old, original)
    initial_ref, initial = inventory(harness, "initial")
    publish_record_only(harness, "initial", initial_ref, initial)
    original_id = initial["units"][0]["source_id"]
    if mode == "rename":
        (harness.root / old).rename(harness.root / new)
    else:
        (harness.root / old).unlink()
    deleted_ref, deleted = inventory(harness, "deleted")
    old_unit = next(row for row in deleted["units"] if row["path"] == old)
    assert old_unit["change"] == "missing" and old_unit["source_id"] == original_id
    if mode == "rename":
        new_unit = next(row for row in deleted["units"] if row["path"] == new)
        assert new_unit["change"] == "new" and new_unit["source_id"] != original_id
    formal = publish_record_only(harness, "deleted", deleted_ref, deleted, progress=progress)
    saved = (harness.root / formal["target_path"]).read_bytes()
    _, fresh = inventory(harness, "fresh")
    assert all(row["change"] == "unchanged" for row in fresh["units"])
    assert next(row for row in fresh["units"] if row["path"] == old)["observed_fingerprint"] is None
    harness.write(old, original)
    _, reappeared = inventory(harness, "reappeared")
    restored = next(row for row in reappeared["units"] if row["path"] == old)
    assert restored["change"] == "changed" and restored["source_id"] == original_id
    assert (harness.root / formal["target_path"]).read_bytes() == saved


def test_unresolved_deleted_raw_remains_missing_after_real_record_only_apply(harness):
    path = "docs-raw/specs/source.md"
    harness.write(path, b"# Original\n")
    initial_ref, initial = inventory(harness, "initial")
    publish_record_only(harness, "initial", initial_ref, initial)
    (harness.root / path).unlink()
    deleted_ref, deleted = inventory(harness, "deleted")
    publish_record_only(harness, "deleted", deleted_ref, deleted, progress="blocked")
    _, fresh = inventory(harness, "fresh")
    assert fresh["units"][0]["change"] == "missing"


@pytest.mark.parametrize("action", ["defer", "failed", "uncovered"])
@pytest.mark.parametrize("progress", ["skipped", "withdrawn"])
def test_unresolved_action_cannot_hide_behind_published_terminal_progress(harness, action, progress):
    path = "docs-raw/specs/source.md"
    harness.write(path, b"# Original\nUnresolved author decision.\n")
    scan_ref, scan = inventory(harness, "debt")
    # The public legacy record API permits this contradictory combination.
    # Read-time governance must retain the actual unresolved action, including
    # old formal records; tightening new requests cannot repair that history.
    formal = publish_record_only(harness, "debt", scan_ref, scan, progress=progress, action=action)
    assert formal["status"] == "recorded"
    assert formal["dispositions"][0]["action"] == action
    assert formal["dispositions"][0]["progress"] == progress
    original_record = (harness.root / formal["target_path"]).read_bytes()
    _, fresh = inventory(harness, "fresh")
    assert fresh["units"][0]["change"] == "unfinished"
    assert fresh["units"][0]["progress"] != "completed"
    assert (harness.root / formal["target_path"]).read_bytes() == original_record
