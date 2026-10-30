"""Combined public preparation, frozen retries and real post-publication no-ops.

Edited inventories below are explicitly synthetic fault inputs, never processing
or review success records. The true no-op oracle uses the real public P7 fixture.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


_flow_spec = importlib.util.spec_from_file_location(
    "source_run_supported_flow_fixture", Path(__file__).resolve().parents[2] / "support/stages/source_flow.py",
)
_flow_fixture = importlib.util.module_from_spec(_flow_spec)
_flow_spec.loader.exec_module(_flow_fixture)
planned_flow = _flow_fixture.planned_flow


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def scan(harness, operation, **request):
    response = harness.run("source", {"operation_id": operation, **request}, "scan")
    reference = response["data"]["scan_ref"]
    return reference, harness.record(reference)


def fault_inventory(harness, reference, inventory):
    """Seal only this test-owned fault observation; do not alter the rule lock."""
    value = copy.deepcopy(inventory)
    value.pop("digest")
    value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
    raw = canonical(value)
    harness.write(reference, raw)
    return raw


@pytest.mark.parametrize("action", [None, "run"], ids=["default", "explicit-run"])
def test_run_scans_and_prepares_exact_material_in_one_public_call(harness, action):
    source = "docs-raw/specs/source.md"
    original = b"# Source\nCombined entry material.\n"
    harness.write(source, original)
    response = harness.run("source", {"operation_id": "combined"}, action)
    assert response["phase"] == "prepared"
    data = response["data"]
    inventory = harness.record(data["scan_ref"])
    material = harness.record(data["material_ref"])
    bundle = harness.record(data["bundle_ref"])
    assert inventory["complete"] is True and inventory["full_scan"] is True
    assert [(row["path"], row["change"]) for row in inventory["units"]] == [(source, "new")]
    assert data["scan_digest"] == inventory["digest"]
    assert data["actionable_unit_ids"] == material["unit_ids"] == [inventory["units"][0]["unit_id"]]
    assert material["scan_ref"] == data["scan_ref"] and material["scan_digest"] == inventory["digest"]
    assert material["bundle_ref"] == data["bundle_ref"]
    assert material["bundle_digest"] == bundle["digest"]
    assert [row["path"] for row in bundle["resources"]] == [source]
    assert inventory["tool_identity"]["skill"] == material["tool_identity"]["skill"] == "hs-knowledge-source"
    assert (harness.root / source).read_bytes() == original
    assert not (harness.root / "knowledge").exists()
    assert not (harness.root / "logs/ingest").exists()


def test_default_run_is_unchanged_only_after_real_p7_completion(planned_flow):
    flow = planned_flow
    flow.produce()
    protected = flow.protected_bytes()
    response = flow.h.run("source", {"operation_id": "fresh-after-p7"})
    assert response["phase"] == "unchanged"
    data = response["data"]
    inventory = flow.h.record(data["scan_ref"])
    assert inventory["complete"] is True and inventory["current_context"]["complete"] is True
    assert [row["change"] for row in inventory["units"]] == ["unchanged"]
    assert data["actionable_unit_ids"] == [] and data["affected_claims"] == [] and data["context_gaps"] == []
    assert "material_ref" not in data and "bundle_ref" not in data
    assert not (flow.h.root / ".build/operations/fresh-after-p7/materials").exists()
    assert not (flow.h.root / ".build/operations/fresh-after-p7/sources").exists()
    assert not (flow.h.root / "logs/ingest/fresh-after-p7.yaml").exists()
    assert flow.protected_bytes() == protected


def test_explicit_candidate_revision_preserves_unchanged_source_units(planned_flow):
    flow = planned_flow
    flow.produce()
    response = flow.h.run("source", {"operation_id": "explicit-revision",
        "source": "docs-raw/specs/source.md", "candidate_card_ids": ["rule"]})
    assert response["phase"] == "prepared"
    inventory = flow.h.record(response["data"]["scan_ref"])
    material = flow.h.record(response["data"]["material_ref"])
    assert [(row["path"], row["change"]) for row in inventory["units"]] == [
        ("docs-raw/specs/source.md", "unchanged"),
    ]
    assert material["scan_ref"] == response["data"]["scan_ref"]
    assert material["unit_ids"] == [inventory["units"][0]["unit_id"]]
    assert material["units"] == inventory["units"]
    assert [row["card_id"] for row in material["candidates"]] == ["rule"]
    # A second explicit revision maps this card's real source identities. A new
    # unrelated original remains a scan fact but is outside this revision.
    unrelated = "docs-raw/specs/unrelated.md"
    flow.h.write(unrelated, b"# Unrelated new original\n")
    mapped = flow.h.run("source", {"operation_id": "mapped-revision", "candidate_card_ids": ["rule"]})
    assert mapped["phase"] == "prepared"
    mapped_scan = flow.h.record(mapped["data"]["scan_ref"])
    mapped_material = flow.h.record(mapped["data"]["material_ref"])
    assert {(row["path"], row["change"]) for row in mapped_scan["units"]} == {
        ("docs-raw/specs/source.md", "unchanged"), (unrelated, "new"),
    }
    original_unit = next(row for row in mapped_scan["units"] if row["path"] == "docs-raw/specs/source.md")
    assert mapped_material["unit_ids"] == [original_unit["unit_id"]]
    assert mapped_material["units"] == [original_unit]
    assert [row["card_id"] for row in mapped_material["candidates"]] == ["rule"]
    assert [row["path"] for row in flow.h.record(mapped_material["bundle_ref"])["resources"]] == [original_unit["path"]]


def test_unmatched_retained_candidate_requires_source_without_inventing_units(harness):
    # Retained evidence supports this synthetic pre-existing formal card; there
    # is deliberately no current raw file or formal processing inventory.
    _, bundle = harness.capture("retained", b"# Retained source\nHistorical material.\n")
    harness.publish_bundle(bundle)
    harness.write("governance/sources.lock.yaml", canonical({"schema_version": "2.0",
        "resources": bundle["resources"], "snapshots": bundle["snapshots"]}))
    harness.write("knowledge/rules/retained.md", harness.card("retained", bundle, lifecycle="stable"))
    (harness.root / "docs-raw/specs/source.md").unlink()
    response = harness.run("source", {"operation_id": "unmatched-revision", "candidate_card_ids": ["retained"]}, expected=3)
    assert response["diagnostics"][0]["code"] == "REVISION_SOURCE_REQUIRED"
    assert response["data"]["stopped_stage"] == "prepare"
    assert response["data"]["needs_explicit_source"] is True
    assert response["data"]["candidate_card_ids"] == ["retained"]
    inventory = harness.record(response["data"]["scan_ref"])
    assert inventory["units"] == []
    assert "material_ref" not in response["data"]
    assert not (harness.root / ".build/operations/unmatched-revision/materials").exists()


def test_saved_noop_inventory_cannot_assert_state_after_new_raw_arrives(harness):
    reference, inventory = scan(harness, "saved-noop")
    assert inventory["complete"] is True and inventory["units"] == []
    raw = (harness.root / reference).read_bytes()
    harness.write("docs-raw/specs/arrived.md", b"# Arrived after saved observation\n")
    response = harness.run("source", {"operation_id": "saved-noop"}, expected=3)
    assert response["diagnostics"][0]["code"] == "FRESH_OBSERVATION_REQUIRED"
    assert response["data"]["stopped_stage"] == "scan" and response["data"]["scan_ref"] == reference
    assert response["data"]["needs_scan"] is True
    assert "material_ref" not in response["data"]
    assert (harness.root / reference).read_bytes() == raw
    assert not (harness.root / ".build/operations/saved-noop/materials").exists()


@pytest.mark.parametrize("change", ["missing", "read_failed"])
def test_run_retains_unavailable_original_gaps_instead_of_noop(harness, change):
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic unavailable observation.\n")
    reference, inventory = scan(harness, "unavailable")
    unit = inventory["units"][0]
    unit.update(change=change, observed_fingerprint=None,
                read_error="SYNTHETIC_READ_FAILURE" if change == "read_failed" else None)
    inventory["complete"] = change != "read_failed"
    raw = fault_inventory(harness, reference, inventory)
    response = harness.run("source", {"operation_id": "unavailable"})
    assert response["phase"] == "prepared"
    assert response["data"]["complete"] is inventory["complete"]
    material = harness.record(response["data"]["material_ref"])
    assert material["unit_ids"] == [unit["unit_id"]]
    assert material["gaps"] == [{"unit_id": unit["unit_id"], "code": "CURRENT_ORIGINAL_UNAVAILABLE", "path": unit["path"]}]
    assert (harness.root / reference).read_bytes() == raw


@pytest.mark.parametrize("fault", [
    "incomplete_scan", "incomplete_context", "missing_context", "affected_claims", "context_gaps",
    "pending_event_ids", "pending_events",
])
def test_run_does_not_noop_for_incomplete_context_or_maintenance_debt(harness, fault):
    reference, inventory = scan(harness, "context-fault")
    assert inventory["units"] == []
    if fault == "incomplete_scan":
        inventory["complete"] = False
    elif fault == "incomplete_context":
        inventory["current_context"]["complete"] = False
    elif fault == "missing_context":
        inventory.pop("current_context")
    elif fault == "affected_claims":
        inventory["current_context"]["affected_claims"] = [{
            "card_id": "synthetic-absent-card", "claim_id": "claim", "reason": "synthetic_fault",
        }]
    elif fault == "context_gaps":
        inventory["current_context"]["gaps"] = [{"code": "SYNTHETIC_CONTEXT_GAP", "reason": "Fault observation"}]
    elif fault == "pending_event_ids":
        inventory["current_context"]["state"]["pending_event_ids"] = ["synthetic-pending-event"]
    else:
        inventory["current_context"]["state"]["pending_events"] = [{"event_id": "synthetic-pending-event"}]
    raw = fault_inventory(harness, reference, inventory)
    response = harness.run("source", {"operation_id": "context-fault"},
                           expected=2 if fault == "affected_claims" else 0)
    assert response["data"]["scan_ref"] == reference
    if fault == "affected_claims":
        # The deliberately absent target must reach preparation and retain its
        # original failure; a successful unchanged exit would hide this debt.
        assert response["diagnostics"][0]["code"] == "UNKNOWN_READING_CANDIDATE"
        assert response["data"]["stopped_stage"] == "prepare"
        assert "material_ref" not in response["data"]
    else:
        assert response["phase"] == "prepared"
        assert response["data"]["actionable_unit_ids"] == []
        material = harness.record(response["data"]["material_ref"])
        assert material["purpose"] == "source_materials" and material["scan_ref"] == reference
        assert response["data"]["affected_claims"] == inventory.get("current_context", {}).get("affected_claims", [])
        assert response["data"]["context_gaps"] == inventory.get("current_context", {}).get("gaps", [])
    assert (harness.root / reference).read_bytes() == raw


def test_run_preserves_scan_failure_and_reports_stopped_stage(harness):
    response = harness.run("source", {"operation_id": "bad-source", "source": "docs-raw/specs/missing.md"}, expected=2)
    assert response["diagnostics"][0]["code"] == "RAW_SCOPE_NOT_FOUND"
    assert response["data"]["stopped_stage"] == "scan"
    assert "scan_ref" not in response["data"] and "material_ref" not in response["data"]
    assert not (harness.root / ".build/operations/bad-source/source-inventory.json").exists()


def test_selected_raw_drift_preserves_fixed_scan_and_reports_prepare_stop(harness):
    harness.write("docs-raw/specs/selected.md", b"# Before\n")
    harness.write("docs-raw/specs/other.md", b"# Other\n")
    reference, inventory = scan(harness, "drift")
    raw = (harness.root / reference).read_bytes()
    selected = next(unit for unit in inventory["units"] if unit["path"].endswith("selected.md"))
    harness.write(selected["path"], b"# Changed after observation\n")
    response = harness.run("source", {"operation_id": "drift", "unit_ids": [selected["unit_id"]]}, expected=3)
    assert response["diagnostics"][0]["code"] == "SOURCE_CHANGED"
    assert response["data"]["stopped_stage"] == "prepare" and response["data"]["scan_ref"] == reference
    assert response["data"]["needs_scan"] is True and response["data"]["affected_scope"] == [selected["path"]]
    assert "material_ref" not in response["data"]
    assert (harness.root / reference).read_bytes() == raw


def test_prepare_io_stop_retries_same_inventory_without_scanning_new_raw(harness):
    source = "docs-raw/specs/original.md"
    harness.write(source, b"# Source\nFixed selected input.\n")
    reference, inventory = scan(harness, "retry-io")
    raw = (harness.root / reference).read_bytes()
    blocker = ".build/operations/retry-io/materials"
    harness.write(blocker, b"Test-owned IO blocker, not a material artifact.")
    stopped = harness.run("source", {"operation_id": "retry-io"}, expected=2)
    assert stopped["diagnostics"][0]["code"] == "INVALID_INPUT"
    assert stopped["data"]["stopped_stage"] == "prepare" and stopped["data"]["scan_ref"] == reference
    assert "material_ref" not in stopped["data"]
    assert (harness.root / reference).read_bytes() == raw
    assert list((harness.root / ".build/operations/retry-io/sources").rglob("capture.json"))
    (harness.root / blocker).unlink()
    harness.write("docs-raw/specs/added-after-stop.md", b"# Not in the frozen observation\n")
    resumed = harness.run("source", {"operation_id": "retry-io", "scan_ref": reference}, "run")
    assert resumed["phase"] == "prepared"
    material = harness.record(resumed["data"]["material_ref"])
    bundle = harness.record(resumed["data"]["bundle_ref"])
    assert material["scan_ref"] == reference and material["scan_digest"] == inventory["digest"]
    assert material["unit_ids"] == [inventory["units"][0]["unit_id"]]
    assert [row["path"] for row in bundle["resources"]] == [source]
    assert (harness.root / reference).read_bytes() == raw


def test_new_run_rejects_external_inventory_without_creating_own_scan(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\n")
    reference, _ = scan(harness, "external")
    raw = (harness.root / reference).read_bytes()
    response = harness.run("source", {"operation_id": "new-operation", "scan_ref": reference}, expected=2)
    assert response["diagnostics"][0]["code"] == "RUN_SCAN_REF_SCOPE"
    assert response["data"]["stopped_stage"] == "scan"
    assert "scan_ref" not in response["data"]
    assert not (harness.root / ".build/operations/new-operation/source-inventory.json").exists()
    assert (harness.root / reference).read_bytes() == raw


def test_same_operation_scope_change_cannot_replace_frozen_inventory(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\n")
    harness.write("docs-raw/conventions/other.md", b"# Other scope\n")
    reference, _ = scan(harness, "fixed-scope", source="docs-raw/specs")
    raw = (harness.root / reference).read_bytes()
    response = harness.run("source", {"operation_id": "fixed-scope", "source": "docs-raw/conventions"}, expected=2)
    assert response["diagnostics"][0]["code"] == "RUN_SCOPE_CHANGED"
    assert response["data"]["stopped_stage"] == "scan" and response["data"]["scan_ref"] == reference
    assert not (harness.root / ".build/operations/fixed-scope/materials").exists()
    assert (harness.root / reference).read_bytes() == raw


@pytest.mark.parametrize("action", ["run", "prepare"])
def test_public_inputs_reject_duplicate_frozen_unit_ids_before_preparing(harness, action):
    harness.write("docs-raw/specs/source.md", b"# Source\n")
    reference, inventory = scan(harness, "duplicate")
    inventory["units"].append(copy.deepcopy(inventory["units"][0]))
    raw = fault_inventory(harness, reference, inventory)
    response = harness.run("source", {"operation_id": "duplicate", "scan_ref": reference}, action, expected=2)
    assert response["diagnostics"][0]["code"] == "INVALID_SCAN"
    if action == "run":
        assert response["data"]["stopped_stage"] == "scan" and response["data"]["scan_ref"] == reference
    assert "material_ref" not in response["data"]
    assert not (harness.root / ".build/operations/duplicate/materials").exists()
    assert (harness.root / reference).read_bytes() == raw


def test_run_rejects_foreign_operation_in_own_slot_but_prepare_adopts_original(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\nForeign valid inventory.\n")
    original, inventory = scan(harness, "foreign")
    raw = (harness.root / original).read_bytes()
    own_slot = ".build/operations/receiver/source-inventory.json"
    harness.write(own_slot, raw)
    rejected = harness.run("source", {"operation_id": "receiver"}, expected=2)
    assert rejected["diagnostics"][0]["code"] == "RUN_SCAN_OPERATION_MISMATCH"
    assert rejected["data"]["stopped_stage"] == "scan" and rejected["data"]["scan_ref"] == own_slot
    assert "material_ref" not in rejected["data"]
    assert not (harness.root / ".build/operations/receiver/materials").exists()
    assert (harness.root / own_slot).read_bytes() == (harness.root / original).read_bytes() == raw
    adopted = harness.run("source", {"operation_id": "independent-adoption", "scan_ref": original}, "prepare")
    assert adopted["phase"] == "prepared"
    material = harness.record(adopted["data"]["material_ref"])
    assert material["scan_ref"] == original and material["scan_digest"] == inventory["digest"]
    assert material["origin_scan_operation_id"] == "foreign"
    assert material["unit_ids"] == [inventory["units"][0]["unit_id"]]
    assert (harness.root / own_slot).read_bytes() == (harness.root / original).read_bytes() == raw


def test_explicit_prepare_preserves_source_changed_for_old_rules_inventory(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\nObserved under prior rules.\n")
    reference, inventory = scan(harness, "old-rules")
    inventory["rules_digest"] = "1" * 64
    raw = fault_inventory(harness, reference, inventory)
    response = harness.run("source", {"operation_id": "current-rules", "scan_ref": reference}, "prepare", expected=3)
    assert response["diagnostics"][0]["code"] == "SOURCE_CHANGED"
    assert response["data"]["needs_scan"] is True
    assert response["data"]["affected_scope"] == ["governance/framework.lock.yaml"]
    assert "material_ref" not in response["data"]
    assert not (harness.root / ".build/operations/current-rules/materials").exists()
    assert (harness.root / reference).read_bytes() == raw


def test_default_source_runs_without_installed_skills(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\nStandalone combined entry.\n")
    assert not (harness.base / "installed").exists()
    incoming, outgoing = harness.base / "default-in.json", harness.base / "default-out.json"
    incoming.write_bytes(canonical({"operation_id": "standalone"}))
    process = subprocess.run([*harness.command("source"),
        "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(harness.root)],
        capture_output=True, check=False)
    response = json.loads(outgoing.read_bytes())
    assert process.returncode == 0, (response, process.stderr)
    assert response["phase"] == "prepared" and response["rules_digest"] == harness.rules
    assert not (harness.base / "installed").exists()
    inventory = harness.record(response["data"]["scan_ref"])
    material = harness.record(response["data"]["material_ref"])
    assert material["scan_ref"] == response["data"]["scan_ref"] and material["scan_digest"] == inventory["digest"]
    assert material["unit_ids"] == [inventory["units"][0]["unit_id"]]
