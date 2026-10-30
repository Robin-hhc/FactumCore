"""Actual configured module paths select code without a discovery stage."""

import hashlib

import pytest
import yaml


def module_workspace(harness):
    workspace = harness.root.parent
    config = {
        "schema_version": "2.0", "workspace_id": "module-selection",
        "knowledge_roots": {"wifi": harness.root.name}, "code_root": "main",
        "modules": [{"path": "wifi/host", "sides": ["host"]}],
    }
    (workspace / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (workspace / "AGENTS.md").write_text("Synthetic project entry.\n", encoding="utf-8")
    code = workspace / "main/wifi/host"
    code.mkdir(parents=True)
    (code / "first.c").write_bytes(b"int first(void) { return 1; }\n")
    (code / "unselected.c").write_bytes(b"\x00not interpreted")
    return code


def test_prepare_uses_actual_module_path_and_generates_selected_code_context(harness):
    code = module_workspace(harness)
    result = harness.run("source", {"operation_id": "module-code", "targets": [
        {"kind": "code", "module_path": "wifi/host", "relative_path": "first.c"},
    ]}, "prepare")
    assert result["phase"] == "prepared"
    material = harness.record(result["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    context = harness.record(result["data"]["context_ref"])
    repo_id = bundle["resources"][0]["repo_id"]
    assert context["repos"][repo_id]["files"] == {
        "first.c": hashlib.sha256((code / "first.c").read_bytes()).hexdigest(),
    }
    assert material["targets"][0]["repo_id"] == repo_id
    assert "module_path" not in material["targets"][0]
    assert not (harness.root / ".build/project-context").exists()
    assert not (harness.root / "knowledge").exists()


def prepared_bundle(harness, operation, target):
    result = harness.run("source", {"operation_id": operation, "targets": [
        {"kind": "code", "relative_path": "first.c", **target},
    ]}, "prepare")
    return result, harness.record(result["data"]["bundle_ref"])


def test_module_and_repo_selectors_keep_the_same_source_snapshot_and_target_identity(harness):
    module_workspace(harness)
    first, by_module = prepared_bundle(harness, "by-module", {"module_path": "wifi/host"})
    repo_id = by_module["resources"][0]["repo_id"]
    second, by_repo = prepared_bundle(harness, "by-repo", {"repo_id": repo_id})
    assert by_module["resources"] == by_repo["resources"]
    assert by_module["snapshots"] == by_repo["snapshots"]
    assert harness.record(first["data"]["material_ref"])["targets"] == harness.record(second["data"]["material_ref"])["targets"]
    original = (harness.root / first["data"]["material_ref"]).read_bytes()
    same = harness.run("source", {"operation_id": "by-module", "targets": [
        {"kind": "code", "repo_id": repo_id, "module_path": "wifi/host", "relative_path": "first.c"},
    ]}, "prepare")
    assert same["data"]["material_ref"] == first["data"]["material_ref"]
    assert (harness.root / first["data"]["material_ref"]).read_bytes() == original


def test_direct_capture_accepts_the_same_module_selector(harness):
    module_workspace(harness)
    _, by_module = prepared_bundle(harness, "discover-selected", {"module_path": "wifi/host"})
    repo_id = by_module["resources"][0]["repo_id"]
    request = {"kind": "code", "relative_path": "first.c", "source_id": "explicit-code"}
    first = harness.run("source", {"operation_id": "capture-module", **request, "module_path": "wifi/host"}, "capture")
    second = harness.run("source", {"operation_id": "capture-repo", **request, "repo_id": repo_id}, "capture")
    assert harness.record(first["data"]["bundle_ref"])["resources"] == harness.record(second["data"]["bundle_ref"])["resources"]
    assert harness.record(first["data"]["bundle_ref"])["snapshots"] == harness.record(second["data"]["bundle_ref"])["snapshots"]


@pytest.mark.parametrize("selector", [None, "main/wifi/host", "../wifi/host", "wifi/missing", 7])
def test_module_selection_requires_an_actual_configured_module(harness, selector):
    module_workspace(harness)
    result = harness.run("source", {"operation_id": "invalid-module", "targets": [
        {"kind": "code", "module_path": selector, "relative_path": "first.c"},
    ]}, "prepare", expected=3)
    assert result["diagnostics"][0]["code"] in {"CODE_MODULE_UNKNOWN", "CODE_AUTHORIZATION_REQUIRED"}
    assert not (harness.root / ".build/operations/invalid-module/materials").exists()


def test_conflicting_explicit_repo_and_module_are_rejected(harness):
    module_workspace(harness)
    _, first = prepared_bundle(harness, "configured-repo", {"module_path": "wifi/host"})
    repo_id = first["resources"][0]["repo_id"]
    path = harness.root.parent / "config.yml"
    config = yaml.safe_load(path.read_bytes())
    config["modules"].append({"path": "wifi/device", "sides": ["device"]})
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    other = harness.root.parent / "main/wifi/device"
    other.mkdir()
    (other / "first.c").write_bytes(b"int other(void) { return 2; }\n")
    result = harness.run("source", {"operation_id": "conflicting-selection", "targets": [
        {"kind": "code", "repo_id": repo_id, "module_path": "wifi/device", "relative_path": "first.c"},
    ]}, "prepare", expected=3)
    assert result["diagnostics"][0]["code"] == "CODE_MODULE_MISMATCH"
    assert not (harness.root / ".build/operations/conflicting-selection/materials").exists()


def test_module_selector_does_not_bypass_nested_module_authorization(harness):
    code = module_workspace(harness)
    path = harness.root.parent / "config.yml"
    config = yaml.safe_load(path.read_bytes())
    config["modules"].append({"path": "wifi/host/private", "sides": ["device"]})
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    (code / "private").mkdir()
    (code / "private/secret.c").write_bytes(b"int private(void) { return 3; }\n")
    result = harness.run("source", {"operation_id": "nested-boundary", "targets": [
        {"kind": "code", "module_path": "wifi/host", "relative_path": "private/secret.c"},
    ]}, "prepare", expected=3)
    assert result["diagnostics"][0]["code"] == "CODE_MODULE_UNKNOWN"
    assert not (harness.root / ".build/operations/nested-boundary/materials").exists()


def test_empty_module_mapping_does_not_authorize_existing_code(harness):
    module_workspace(harness)
    path = harness.root.parent / "config.yml"
    config = yaml.safe_load(path.read_bytes())
    config["modules"] = []
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    result = harness.run("source", {"operation_id": "empty-modules", "targets": [
        {"kind": "code", "module_path": "wifi/host", "relative_path": "first.c"},
    ]}, "prepare", expected=3)
    assert result["diagnostics"][0]["code"] == "CODE_MODULE_UNKNOWN"
    assert not (harness.root / ".build/operations/empty-modules/materials").exists()


def test_document_can_be_supplemented_from_config_without_explore(harness):
    code = module_workspace(harness)
    original = b"# Design\nThe first function returns one.\n"
    harness.write("docs-raw/specs/design.md", original)
    first = harness.run("source", {"operation_id": "design-module", "targets": [
        {"source_path": "docs-raw/specs/design.md"},
    ]}, "prepare")
    material_ref = first["data"]["material_ref"]
    original_material = (harness.root / material_ref).read_bytes()
    assert harness.record(material_ref)["context_ref"] is None
    result = harness.run("source", {"operation_id": "design-module", "existing_material_ref": material_ref, "targets": [
        {"kind": "code", "module_path": "wifi/host", "relative_path": "first.c"},
    ]}, "prepare")
    material = harness.record(result["data"]["material_ref"])
    bundle = harness.record(material["bundle_ref"])
    context = harness.record(material["context_ref"])
    assert {row["kind"] for row in bundle["resources"]} == {"raw", "code"}
    assert next(iter(context["repos"].values()))["files"] == {
        "first.c": hashlib.sha256((code / "first.c").read_bytes()).hexdigest(),
    }
    assert (harness.root / material_ref).read_bytes() == original_material
    assert (harness.root / "docs-raw/specs/design.md").read_bytes() == original
    assert not (harness.root / ".build/project-context").exists()
