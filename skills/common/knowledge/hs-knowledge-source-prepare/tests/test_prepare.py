"""Independent public P2 contracts; synthetic inputs, no model or remote service."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


_code_spec = importlib.util.spec_from_file_location(
    "source_prepare_code_capture_fixture", Path(__file__).with_name("test_code_capture.py"),
)
_code_fixture = importlib.util.module_from_spec(_code_spec)
_code_spec.loader.exec_module(_code_fixture)
setup_code = _code_fixture.setup_code


def prepare(harness, request, expected=0):
    return harness.run("source-prepare", request, "prepare", expected)


def scan(harness, operation="batch"):
    response = harness.run("source-scan", {"operation_id": operation}, "scan")
    return response["data"]["scan_ref"], harness.record(response["data"]["scan_ref"])


def target(path, **extra):
    return {"source_path": path, **extra}


def test_prepare_does_not_publish_or_create_sibling_operations(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\nCurrent exact input.\n")
    def formal():
        return {p.relative_to(harness.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in harness.root.rglob("*") if p.is_file()
                and not p.relative_to(harness.root).as_posix().startswith(".build/")}
    before = formal()
    first = prepare(harness, {"operation_id": "first", "targets": [target("docs-raw/specs/source.md")]})
    assert formal() == before
    material = harness.record(first["data"]["material_ref"])
    assert all(row["bundle_ref"].startswith(".build/operations/first/sources/") for row in material["bundles"])
    assert {p.name for p in (harness.root / ".build/operations").iterdir()} == {"first"}
    second = prepare(harness, {"operation_id": "fresh", "targets": [target("docs-raw/specs/source.md")]})
    assert formal() == before
    assert all(row["owner_operation_id"] == "fresh"
               for row in harness.record(second["data"]["bundle_ref"])["staged_objects"])


def test_capture_rejects_formal_output_before_any_capture(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\n")
    incoming = harness.base / "unsafe-output.json"
    incoming.write_text(json.dumps({"operation_id": "stage-only", "source_path": "docs-raw/specs/source.md",
                                    "source_id": "source"}), encoding="utf-8")
    output = harness.root / "logs/unsafe-capture.json"
    result = subprocess.run([sys.executable, str(harness.packages / "hs-knowledge-source-prepare/scripts/cli.py"),
                             "--input", str(incoming), "--output", str(output), "--knowledge-root", str(harness.root),
                             "--rules-digest", harness.rules, "--action", "capture"], capture_output=True)
    assert result.returncode == 2
    assert not output.exists()
    assert not (harness.root / ".build/operations/stage-only").exists()


def test_default_prepare_works_with_only_its_installed_package(harness):
    harness.write("docs-raw/specs/source.md", b"# Exact original\nSynthetic facts.\n")
    installation = harness.base / "installed" / "hs-knowledge-source-prepare"
    shutil.copytree(harness.packages / "hs-knowledge-source-prepare", installation,
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    incoming, outgoing = harness.base / "independent-in.json", harness.base / "independent-out.json"
    incoming.write_text(json.dumps({"operation_id": "independent", "targets": [target("docs-raw/specs/source.md")]}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(installation / "scripts/cli.py"),
                             "--input", str(incoming), "--output", str(outgoing),
                             "--knowledge-root", str(harness.root)], capture_output=True, check=False)
    response = json.loads(outgoing.read_bytes())
    assert result.returncode == 0, response
    assert response["phase"] == "prepared"
    material = harness.record(response["data"]["material_ref"])
    assert material["purpose"] == "source_materials"
    assert "scan_ref" not in material and material["unit_ids"] == []
    assert material["targets"][0]["source_path"] == "docs-raw/specs/source.md"
    assert not (harness.root / ".build/operations/independent/source-inventory.json").exists()


def test_explicit_targets_do_not_extract_unrelated_raw(harness):
    harness.write("docs-raw/specs/source.md", b"# Selected\nReadable source.\n")
    untouched = b"\xff\x00Not a supported text original"
    harness.write("docs-raw/specs/unrelated.md", untouched)
    response = prepare(harness, {"operation_id": "selected", "targets": [target("docs-raw/specs/source.md")]})
    material = harness.record(response["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    assert [row["path"] for row in bundle["resources"]] == ["docs-raw/specs/source.md"]
    assert (harness.root / "docs-raw/specs/unrelated.md").read_bytes() == untouched
    assert [row["path"] for row in material["current_files"]] == ["docs-raw/specs/source.md"]


def test_fixed_scan_subset_does_not_recheck_other_units(harness):
    harness.write("docs-raw/specs/first.md", b"# First\n")
    harness.write("docs-raw/specs/other.md", b"# Other\n")
    reference, inventory = scan(harness)
    chosen = next(unit for unit in inventory["units"] if unit["path"].endswith("first.md"))
    harness.write("docs-raw/specs/other.md", b"\xff\x00Changed outside selected units")
    response = prepare(harness, {"operation_id": "batch", "scan_ref": reference, "unit_ids": [chosen["unit_id"]]})
    material = harness.record(response["data"]["material_ref"])
    assert material["unit_ids"] == [chosen["unit_id"]]
    assert [row["path"] for row in material["current_files"]] == [chosen["path"]]


def test_selected_scan_fingerprint_drift_requests_affected_p1_scope(harness):
    harness.write("docs-raw/specs/source.md", b"# Before\n")
    reference, _ = scan(harness)
    harness.write("docs-raw/specs/source.md", b"# After\n")
    response = prepare(harness, {"operation_id": "batch", "scan_ref": reference}, 3)
    assert any(error["code"] == "SOURCE_CHANGED" for error in response["diagnostics"])
    assert response["data"]["needs_scan"] is True
    assert response["data"]["affected_scope"] == ["docs-raw/specs/source.md"]


def test_supplement_is_a_new_version_and_preserves_original_targets(harness):
    harness.write("docs-raw/specs/first.md", b"# First\n")
    first = prepare(harness, {"operation_id": "supplement", "targets": [target("docs-raw/specs/first.md")]})
    original_ref = first["data"]["material_ref"]
    original_bytes = (harness.root / original_ref).read_bytes()
    harness.write("docs-raw/specs/second.md", b"# Second\n")
    # An unrelated unreadable original cannot turn a P5 supplement into P1.
    harness.write("docs-raw/specs/unrelated.md", b"\xff\x00")
    response = prepare(harness, {"operation_id": "supplement", "existing_material_ref": original_ref,
                                 "targets": [target("docs-raw/specs/second.md")]})
    material = harness.record(response["data"]["material_ref"])
    assert response["data"]["material_ref"] != original_ref
    assert material["previous_material_ref"] == original_ref
    assert material["previous_material_digest"] == first["data"]["material_digest"]
    assert (harness.root / original_ref).read_bytes() == original_bytes
    assert {row["source_path"] for row in material["targets"]} == {"docs-raw/specs/first.md", "docs-raw/specs/second.md"}
    assert {row["path"] for row in material["current_files"]} == {"docs-raw/specs/first.md", "docs-raw/specs/second.md"}
    assert not (harness.root / ".build/operations/supplement/source-inventory.json").exists()


def test_supplement_rejects_other_operation_and_keeps_original_bytes(harness):
    harness.write("docs-raw/specs/source.md", b"# Original\n")
    first = prepare(harness, {"operation_id": "first", "targets": [target("docs-raw/specs/source.md")]})
    ref = first["data"]["material_ref"]
    before = (harness.root / ref).read_bytes()
    response = prepare(harness, {"operation_id": "other", "existing_material_ref": ref, "targets": []}, 2)
    assert any(error["code"] == "OPERATION_MISMATCH" for error in response["diagnostics"])
    assert (harness.root / ref).read_bytes() == before
    assert not (harness.root / ".build/operations/other/materials").exists()


def test_supplement_cannot_replace_an_original_target_identity(harness):
    harness.write("docs-raw/specs/first.md", b"# First\n")
    harness.write("docs-raw/specs/second.md", b"# Second\n")
    first = prepare(harness, {"operation_id": "bound", "targets": [target("docs-raw/specs/first.md", target_id="chosen")]})
    response = prepare(harness, {"operation_id": "bound", "existing_material_ref": first["data"]["material_ref"],
                                 "targets": [target("docs-raw/specs/second.md", target_id="chosen")]}, 2)
    assert any(error["code"] == "MATERIAL_IDENTITY_CONFLICT" for error in response["diagnostics"])


def test_supplement_cannot_replace_original_scan(harness):
    harness.write("docs-raw/specs/source.md", b"# Source\n")
    first_scan, _ = scan(harness, "first-scan")
    first = prepare(harness, {"operation_id": "bound-scan", "scan_ref": first_scan})
    harness.write("docs-raw/specs/second.md", b"# Second\n")
    second_scan, _ = scan(harness, "second-scan")
    response = prepare(harness, {"operation_id": "bound-scan", "existing_material_ref": first["data"]["material_ref"],
                                 "scan_ref": second_scan}, 2)
    assert any(error["code"] == "MATERIAL_INPUT_MISMATCH" for error in response["diagnostics"])


def test_supplement_checks_only_adopted_sources_and_stops_their_drift(harness):
    harness.write("docs-raw/specs/source.md", b"# Before\n")
    first = prepare(harness, {"operation_id": "drift", "targets": [target("docs-raw/specs/source.md")]})
    original = (harness.root / first["data"]["material_ref"]).read_bytes()
    harness.write("docs-raw/specs/source.md", b"# After\n")
    response = prepare(harness, {"operation_id": "drift", "existing_material_ref": first["data"]["material_ref"], "targets": []}, 3)
    assert any(error["code"] == "SOURCE_CHANGED" for error in response["diagnostics"])
    assert response["data"]["needs_scan"] is True
    assert response["data"]["affected_scope"] == ["docs-raw/specs/source.md"]
    assert (harness.root / first["data"]["material_ref"]).read_bytes() == original


def test_prepare_reads_each_adopted_version_across_lifecycles(harness):
    _, first = harness.capture("first", b"# Source\nOld first version.\n")
    _, second = harness.capture("second", b"# Source\nOld second version.\n")
    harness.publish_bundle(first)
    harness.publish_bundle(second)
    harness.write("knowledge/rules/draft.md", harness.card("draft", first, lifecycle="draft"))
    harness.write("knowledge/rules/old.md", harness.card("old", second, lifecycle="deprecated"))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": first["resources"],
                                                               "snapshots": first["snapshots"] + second["snapshots"]}).encode())
    harness.write("docs-raw/specs/source.md", b"# Source\nCurrent third version.\n")
    response = prepare(harness, {"operation_id": "versions", "targets": [target("docs-raw/specs/source.md")]})
    material = harness.record(response["data"]["material_ref"])
    cards = {row["card_id"]: row for row in material["candidates"]}
    assert set(cards) == {"draft", "old"}
    assert "Old first version." in cards["draft"]["adopted_sources"][0]["text"]
    assert "Old second version." in cards["old"]["adopted_sources"][0]["text"]
    assert not material["gaps"]
    assert all(hashlib.sha256((harness.root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
               for item in material["adopted_objects"])


def test_adopted_formal_card_drift_prevents_supplement(harness):
    _, bundle = harness.capture("old")
    harness.write("knowledge/rules/chosen.md", harness.card("chosen", bundle))
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
                                                               "snapshots": bundle["snapshots"]}).encode())
    first = prepare(harness, {"operation_id": "cards", "candidate_card_ids": ["chosen"]})
    path = harness.root / "knowledge/rules/chosen.md"
    path.write_bytes(path.read_bytes() + b"\nExternal edit.\n")
    response = prepare(harness, {"operation_id": "cards", "existing_material_ref": first["data"]["material_ref"], "targets": []}, 3)
    assert any(error["code"] == "SOURCE_CHANGED" for error in response["diagnostics"])
    assert response["data"]["affected_scope"] == ["knowledge/rules/chosen.md"]


def test_material_preparation_does_not_repeat_profile_quality_checks(harness):
    _, bundle = harness.capture("old")
    full = harness.card("chosen", bundle)
    head = full.split(b"---\n", 2)[1]
    minimal_body = b"---\n" + head + b"---\n<a id=\"statement\"></a>\nSynthetic readable material.\n"
    harness.write("knowledge/rules/chosen.md", minimal_body)
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
                                                               "snapshots": bundle["snapshots"]}).encode())
    response = prepare(harness, {"operation_id": "read-only", "candidate_card_ids": ["chosen"]})
    assert [row["card_id"] for row in harness.record(response["data"]["material_ref"])["candidates"]] == ["chosen"]


def test_direct_code_target_binds_actual_code_and_config(harness):
    repo, context = setup_code(harness)
    response = prepare(harness, {"operation_id": "direct-code", "targets": [{"kind": "code", "repo_id": "code",
                                 "relative_path": "sample.c", "source_id": "explicit-code", "context_ref": context}]})
    material = harness.record(response["data"]["material_ref"])
    assert "scan_ref" not in material
    assert material["units"][0]["origin"] == "explicit_target"
    assert material["units"][0]["source_kind"] == "code"
    assert "change" not in material["units"][0]
    assert {row["kind"] for row in material["current_files"]} == {"code", "config"}
    assert next(row for row in material["current_files"] if row["kind"] == "code")["path"] == (repo / "sample.c").as_posix()
    assert material["current_code"][0]["current_source_matches"] is True
    assert material["context_ref"] == context
    assert material["context_digest"] == harness.record(context)["digest"]
    assert harness.record(material["bundle_ref"])["context_digest"] == material["context_digest"]


def test_code_config_drift_cannot_reuse_old_material(harness):
    setup_code(harness)
    first = prepare(harness, {"operation_id": "config-drift", "targets": [{"kind": "code", "repo_id": "code",
                             "relative_path": "sample.c", "source_id": "explicit-code"}]})
    config_path = harness.root.parent / "config.yml"
    config_path.write_bytes(config_path.read_bytes() + b"\n# Same files, changed adopted configuration\n")
    response = prepare(harness, {"operation_id": "config-drift", "existing_material_ref": first["data"]["material_ref"], "targets": []}, 3)
    assert response["data"]["needs_scan"] is True
    assert any(error["code"] == "SOURCE_CHANGED" for error in response["diagnostics"])
    config_path.write_bytes(b"modules: [invalid YAML\n")
    invalid = prepare(harness, {"operation_id": "config-drift", "existing_material_ref": first["data"]["material_ref"], "targets": []}, 3)
    assert invalid["data"]["needs_scan"] is True
    assert any(error["code"] == "SOURCE_CHANGED" for error in invalid["diagnostics"])


def test_changed_registered_raw_only_freezes_event_proposal(harness):
    _, old = harness.capture("old", b"# Old source\n")
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": old["resources"],
                                                               "snapshots": old["snapshots"]}).encode())
    formal_lock = (harness.root / "governance/sources.lock.yaml").read_bytes()
    harness.write("docs-raw/specs/source.md", b"# New source\n")
    response = harness.run("source-prepare", {"operation_id": "new", "source_path": "docs-raw/specs/source.md", "source_id": "synthetic"}, "capture")
    assert response["data"]["event_refs"] == []
    assert len(response["data"]["event_proposals"]) == 1
    proposal = response["data"]["event_proposals"][0]
    assert proposal["old_snapshot_ids"] == [old["snapshots"][0]["snapshot_id"]]
    assert proposal["source_lock_digest"] == hashlib.sha256(formal_lock).hexdigest()
    assert not (harness.root / "logs/events").exists()
    assert (harness.root / "governance/sources.lock.yaml").read_bytes() == formal_lock


def test_code_capture_does_not_register_code_change_implicitly(harness):
    repo, _ = setup_code(harness)
    request = {"operation_id": "code-old", "kind": "code", "repo_id": "code", "relative_path": "sample.c", "source_id": "code"}
    first = harness.run("source-prepare", request, "capture")
    old = harness.record(first["data"]["bundle_ref"])
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": old["resources"],
                                                               "snapshots": old["snapshots"]}).encode())
    (repo / "sample.c").write_bytes(b"int synthetic(void) { return 99; }\n")
    second = harness.run("source-prepare", {**request, "operation_id": "code-new"}, "capture")
    assert second["data"]["event_refs"] == []
    assert not (harness.root / "logs/events").exists()


def test_full_material_digest_paths_support_long_operation_paths(harness):
    def read_record(reference):
        selected = harness.root / reference
        if os.name == "nt":
            selected = Path("\\\\?\\" + str(selected.absolute()))
        return json.loads(selected.read_bytes())

    harness.write("docs-raw/specs/source.md", b"# Source\nLong-path fixture.\n")
    response = prepare(harness, {"operation_id": "long-" + "x" * 85, "targets": [target("docs-raw/specs/source.md")]})
    ref = response["data"]["material_ref"]
    assert len(ref.split("/")[-2]) == 64
    path = harness.root / ref
    if os.name == "nt":
        assert len(str(path)) > 260
        path = Path("\\\\?\\" + str(path.absolute()))
    material = json.loads(path.read_bytes())
    assert material["digest"] == response["data"]["material_digest"]
    assert material["units"][0]["origin"] == "explicit_target"
    child = read_record(material["bundles"][0]["bundle_ref"])
    assert len(child["operation_id"]) <= 96
    second = prepare(harness, {"operation_id": "long-" + "x" * 84 + "y", "targets": [target("docs-raw/specs/source.md")]})
    second_material = read_record(second["data"]["material_ref"])
    second_child = read_record(second_material["bundles"][0]["bundle_ref"])
    assert second_child["operation_id"] != child["operation_id"]
