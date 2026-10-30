"""Public local-directory source behavior using test-owned originals only."""

import hashlib
import json
import os
import subprocess

import pytest
import yaml


DBOX = "docs-raw/sources/dbox"
LOCAL = "docs-raw/sources/dbox.local.yml"


@pytest.fixture
def dbox(harness):
    (harness.root / LOCAL).unlink()
    external = harness.base / "external documents"
    external.mkdir()
    harness.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    return harness, external


def test_configure_saves_one_directory_and_checks_without_rewriting(dbox):
    harness, external = dbox
    result = harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    assert result["phase"] == "configured"
    config = (harness.root / LOCAL).read_bytes()
    assert yaml.safe_load(config) == {"schema_version": "1.0", "path": str(external)}
    checked = harness.run("source", {"operation_id": "check-config"}, "configure")
    assert checked["phase"] == "configured"
    assert (harness.root / LOCAL).read_bytes() == config
    assert not list((harness.root / "logs").glob("**/*")) if (harness.root / "logs").exists() else True


def test_dbox_scan_capture_and_exact_recovery_without_current_directory(dbox):
    harness, external = dbox
    child = external / "设计" / "nested file.md"
    child.parent.mkdir()
    original = b"# External document\nExact original evidence.\n"
    child.write_bytes(original)
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    scanned = harness.run("source", {"operation_id": "scan"}, "scan")
    inventory = harness.record(scanned["data"]["scan_ref"])
    logical = DBOX + "/设计/nested file.md"
    assert inventory["complete"] is True
    assert inventory["scope"][-1] == DBOX
    assert [(unit["path"], unit["change"]) for unit in inventory["units"]] == [(logical, "new")]
    assert set(inventory["dbox_binding"]) == {"config_sha256", "root_token"}
    assert str(external) not in json.dumps(inventory, ensure_ascii=False)
    captured = harness.run("source", {"operation_id": "capture", "source_path": logical, "source_id": "dbox-test"}, "capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    assert bundle["resources"][0]["path"] == logical
    assert bundle["dbox_binding"] == inventory["dbox_binding"]
    reference = {"source_id": "dbox-test", "snapshot_id": bundle["snapshots"][0]["snapshot_id"],
                 "locator": {"kind": "lines", "start": 1, "end": 2}}
    resolved = harness.run("source", {"operation_id": "resolve-current", "bundle_ref": captured["data"]["bundle_ref"], "source_ref": reference}, "resolve-source")
    assert resolved["data"]["current_source_matches"] is True
    assert resolved["data"]["current_source_binding"] == inventory["dbox_binding"]
    (harness.root / LOCAL).unlink()
    historical = harness.run("source", {"operation_id": "resolve-old", "bundle_ref": captured["data"]["bundle_ref"], "source_ref": reference}, "resolve-source")
    assert historical["data"]["current_source_matches"] is None
    assert historical["data"]["current_source_observation"]["code"] == "DBOX_CONFIG_REQUIRED"
    assert historical["data"]["text"] == original.decode()


def test_default_run_stops_for_missing_dbox_but_explicit_old_raw_does_not(dbox):
    harness, _ = dbox
    failed = harness.run("source", {"operation_id": "missing-dbox"}, expected=3)
    assert failed["diagnostics"][0]["code"] == "DBOX_CONFIG_REQUIRED"
    assert failed["data"]["stopped_stage"] == "scan"
    inventory = harness.record(failed["data"]["scan_ref"])
    assert inventory["complete"] is False
    harness.write("docs-raw/specs/.gitkeep", b"")
    old = harness.run("source", {"operation_id": "old-scope", "source": "docs-raw/specs"}, "scan")
    assert harness.record(old["data"]["scan_ref"])["complete"] is True


def test_run_material_and_retry_preserve_original_directory_binding(dbox):
    harness, external = dbox
    (external / "source.md").write_bytes(b"# External\nOriginal.\n")
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    prepared = harness.run("source", {"operation_id": "run"})
    material = harness.record(prepared["data"]["material_ref"])
    scan = harness.record(prepared["data"]["scan_ref"])
    assert material["dbox_binding"] == scan["dbox_binding"]
    assert material["current_files"] == [{"kind": "external_raw", "path": DBOX + "/source.md",
                                          "sha256": hashlib.sha256(b"# External\nOriginal.\n").hexdigest(),
                                          "bytes": len(b"# External\nOriginal.\n"), "dbox_binding": scan["dbox_binding"]}]
    frozen = (harness.root / prepared["data"]["scan_ref"]).read_bytes()
    other = harness.base / "other location"
    other.mkdir()
    (other / "source.md").write_bytes((external / "source.md").read_bytes())
    harness.run("source", {"operation_id": "reconfigure", "path": str(other)}, "configure")
    rejected = harness.run("source", {"operation_id": "run"}, expected=3)
    assert rejected["diagnostics"][0]["code"] == "DBOX_BINDING_CHANGED"
    assert (harness.root / prepared["data"]["scan_ref"]).read_bytes() == frozen


def test_explicit_prepare_without_scan_cannot_rebind_old_material(dbox):
    harness, external = dbox
    (external / "source.md").write_bytes(b"# Exact old source\n")
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    prepared = harness.run("source", {"operation_id": "explicit", "targets": [{"source_path": DBOX + "/source.md"}]}, "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    assert "scan_ref" not in material and material["dbox_binding"]
    other = harness.base / "other root"
    other.mkdir()
    (other / "source.md").write_bytes((external / "source.md").read_bytes())
    harness.run("source", {"operation_id": "reconfigure", "path": str(other)}, "configure")
    rejected = harness.run("source", {"operation_id": "explicit", "existing_material_ref": prepared["data"]["material_ref"]}, "prepare", expected=3)
    assert rejected["diagnostics"][0]["code"] in {"DBOX_BINDING_CHANGED", "SOURCE_CHANGED"}


@pytest.mark.parametrize("raw", [
    b"schema_version: '1.0'\npath: relative\n",
    b"schema_version: 1.0\npath: /example\n",
    b"schema_version: '1.0'\npath: /example\nextra: true\n",
    b"schema_version: '1.0'\npath: /first\npath: /second\n",
    b"schema_version: '1.0'\npath: [\n",
    b"schema_version: '1.0'\npath: null\n",
])
def test_invalid_configuration_stops_without_rewriting(dbox, raw):
    harness, _ = dbox
    harness.write(LOCAL, raw)
    result = harness.run("source", {"operation_id": "invalid-config"}, "configure", expected=2)
    assert result["diagnostics"][0]["code"] == "DBOX_CONFIG_INVALID"
    assert (harness.root / LOCAL).read_bytes() == raw


def test_failed_configure_does_not_replace_valid_configuration(dbox):
    harness, external = dbox
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    frozen = (harness.root / LOCAL).read_bytes()
    result = harness.run("source", {"operation_id": "wrong-path", "path": str(external / "absent")}, "configure", expected=2)
    assert result["diagnostics"][0]["code"] == "DBOX_ROOT_UNAVAILABLE"
    assert (harness.root / LOCAL).read_bytes() == frozen
    unsafe = harness.run("source", {"operation_id": "self-scan", "path": str(harness.root)}, "configure", expected=2)
    assert unsafe["diagnostics"][0]["code"] == "DBOX_PATH_UNSAFE"
    assert (harness.root / LOCAL).read_bytes() == frozen


@pytest.mark.parametrize("protection", ["ignored", "tracked", "not_ignored"])
def test_configure_respects_actual_git_protection(dbox, protection):
    harness, external = dbox
    subprocess.run(["git", "init", "--quiet", str(harness.root)], check=True, capture_output=True)
    if protection == "not_ignored":
        (harness.root / "docs-raw/sources/.gitignore").unlink()
    elif protection == "tracked":
        harness.write(LOCAL, b"private existing contents\n")
        subprocess.run(["git", "-C", str(harness.root), "add", "-f", "--", LOCAL], check=True, capture_output=True)
    before = (harness.root / LOCAL).read_bytes() if (harness.root / LOCAL).exists() else None
    result = harness.run("source", {"operation_id": "git-configure", "path": str(external)}, "configure",
                         expected=0 if protection == "ignored" else 3)
    assert result["data"]["git_protection"]["status"] == protection
    if protection != "ignored":
        assert ((harness.root / LOCAL).read_bytes() if (harness.root / LOCAL).exists() else None) == before


def test_configured_root_replacement_is_detected_even_with_identical_bytes(dbox):
    harness, external = dbox
    (external / "source.md").write_bytes(b"# Original\n")
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    scan = harness.run("source", {"operation_id": "replacement"}, "scan")
    external.rename(external.with_name("old directory"))
    external.mkdir()
    (external / "source.md").write_bytes(b"# Original\n")
    result = harness.run("source", {"operation_id": "replacement", "scan_ref": scan["data"]["scan_ref"]}, expected=3)
    assert result["diagnostics"][0]["code"] == "DBOX_BINDING_CHANGED"


def test_dbox_attachments_can_use_parent_inside_the_same_root(dbox):
    harness, external = dbox
    (external / "folder").mkdir()
    (external / "folder/source.md").write_bytes(b"# Source\n![Image](../image.png)\n")
    (external / "image.png").write_bytes(b"opaque attachment")
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    captured = harness.run("source", {"operation_id": "attachments", "source_id": "attached",
                                      "source_path": DBOX + "/folder/source.md", "attachments": [DBOX + "/image.png"]}, "capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    assert [row["kind"] for row in bundle["resources"]] == ["raw", "attachment"]
    assert all(str(external) not in json.dumps(row) for row in bundle["resources"])
    (external / "folder/source.md").write_bytes(b"# Source\n[Escape](../../outside.md)\n")
    escaped = harness.run("source", {"operation_id": "escape", "source_id": "attached",
                                     "source_path": DBOX + "/folder/source.md"}, "capture", expected=2)
    assert escaped["diagnostics"][0]["code"] == "UNSAFE_ATTACHMENT"


def test_nested_links_are_not_followed(dbox):
    harness, external = dbox
    target = harness.base / "other tree"
    target.mkdir()
    (target / "secret.md").write_bytes(b"Must not be observed\n")
    link = external / "linked"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    response = harness.run("source", {"operation_id": "linked-tree"}, "scan")
    inventory = harness.record(response["data"]["scan_ref"])
    assert inventory["complete"] is False
    assert [(row["path"], row["read_error"]) for row in inventory["units"]] == [(DBOX + "/linked", "LINKED_PATH")]
    assert "secret.md" not in json.dumps(inventory)


def test_new_dbox_inventory_cannot_drop_its_binding(dbox):
    harness, external = dbox
    (external / "source.md").write_bytes(b"# Bound\n")
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    scanned = harness.run("source", {"operation_id": "missing-binding"}, "scan")
    path = harness.root / scanned["data"]["scan_ref"]
    inventory = json.loads(path.read_bytes())
    del inventory["dbox_binding"]
    inventory.pop("digest")
    inventory["digest"] = hashlib.sha256(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    rejected = harness.run("source", {"operation_id": "missing-binding"}, expected=2)
    assert rejected["diagnostics"][0]["code"] == "DBOX_BINDING_REQUIRED"


@pytest.mark.parametrize("relative", ["bad\nname.md", "folder/../source.md", "folder//source.md", "CON.md"])
def test_capture_rejects_nonportable_or_aliased_dbox_paths(dbox, relative):
    harness, external = dbox
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    result = harness.run("source", {"operation_id": "unsafe-name", "source_id": "unsafe", "source_path": DBOX + "/" + relative}, "capture", expected=2)
    assert result["diagnostics"][0]["code"] == "DBOX_PATH_UNSAFE"


def test_configure_cannot_hide_tracked_private_config_with_inherited_git_index(dbox, monkeypatch):
    harness, external = dbox
    subprocess.run(["git", "init", "--quiet", str(harness.root)], check=True, capture_output=True)
    original = b"Tracked private configuration must not be overwritten\n"
    harness.write(LOCAL, original)
    subprocess.run(["git", "-C", str(harness.root), "add", "-f", "--", LOCAL], check=True, capture_output=True)
    hidden_index = harness.base / "empty-test-index"
    environment = dict(os.environ, GIT_INDEX_FILE=str(hidden_index))
    subprocess.run(["git", "-C", str(harness.root), "read-tree", "--empty"],
                   env=environment, check=True, capture_output=True)
    monkeypatch.setenv("GIT_INDEX_FILE", str(hidden_index))
    result = harness.run("source", {"operation_id": "hostile-git-index", "path": str(external)}, "configure", expected=3)
    assert result["diagnostics"][0]["code"] == "DBOX_CONFIG_UNPROTECTED"
    assert result["data"]["git_protection"]["status"] == "tracked"
    assert (harness.root / LOCAL).read_bytes() == original


def test_registered_dbox_current_fallback_reports_the_actual_original_path(dbox):
    harness, external = dbox
    original = b"# Recover from explicit configured directory\n"
    child = external / "source.md"
    child.write_bytes(original)
    harness.run("source", {"operation_id": "configure", "path": str(external)}, "configure")
    captured = harness.run("source", {"operation_id": "fallback", "source_id": "registered-dbox",
                                      "source_path": DBOX + "/source.md"}, "capture")
    bundle = harness.record(captured["data"]["bundle_ref"])
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
                                                                 "snapshots": bundle["snapshots"]}, sort_keys=False).encode())
    snapshot = bundle["snapshots"][0]
    harness.bundle_path(bundle, snapshot["recovery"]["path"]).unlink()
    result = harness.run("source", {"operation_id": "read-fallback", "bundle_ref": captured["data"]["bundle_ref"],
                                   "source_ref": {"source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"],
                                                  "locator": {"kind": "lines", "start": 1, "end": 1}}}, "resolve-source")
    assert result["data"]["original_ref"] == str(child)
    assert result["data"]["current_source_matches"] is True
    assert result["data"]["text"] == original.decode()
    assert bundle["resources"][0]["path"] == DBOX + "/source.md"
