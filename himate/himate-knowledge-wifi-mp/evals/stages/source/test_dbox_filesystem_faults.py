"""Public source CLI checks against real native permissions and links."""

import json
import os
from pathlib import Path
import threading
import time

import pytest
import yaml

from support.releases import load_manual, select_release


SELECTION = select_release(Path(__file__).resolve().parents[5],
                           checkout=os.environ.get("HIMATE_DBOX_RELEASE_CHECKOUT"),
                           manifest_path=os.environ.get("HIMATE_DBOX_RELEASE_MANIFEST"))
RELEASE = SELECTION.root
MANUAL = load_manual(SELECTION, "dbox_filesystem_manual")
DBOX = "docs-raw/sources/dbox"


class ObservedPipeline(MANUAL.ManualPipeline):
    def __init__(self, base):
        super().__init__(base)
        self.audit = []

    def call(self, slug, request, action=None, expected=0):
        started = time.monotonic()
        try:
            return super().call(slug, request, action, expected)
        finally:
            output = self.base / f"manual-out-{self.sequence}.json"
            self.audit.append({"skill": slug, "action": action, "operation_id": request.get("operation_id"),
                               "seconds": round(time.monotonic() - started, 6),
                               "response": json.loads(output.read_bytes()) if output.exists() else None})
            (self.base / "filesystem-evidence.json").write_text(json.dumps(self.audit, indent=2), encoding="utf-8")


def configured(tmp_path):
    pipeline = ObservedPipeline(tmp_path)
    external = tmp_path / "external documents"
    external.mkdir()
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(external)}, "configure")
    return pipeline, external


def publish_one(pipeline, external, relative="source.md"):
    original = b"# Source\nCapture marker is a documented rule.\n"
    source = external / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(original)
    prepared = pipeline.call("knowledge-source", {"operation_id": "seed"}, "run")
    material = pipeline.record(prepared["data"]["material_ref"])
    bundle_ref = material["bundle_ref"]
    view = pipeline.view("seed", bundle_ref, "filesystem-rule",
                         pipeline.card("filesystem-rule", pipeline.record(bundle_ref)),
                         scan_ref=prepared["data"]["scan_ref"], material_ref=prepared["data"]["material_ref"])
    pipeline.review("seed", view)
    record = pipeline.pending_record("seed", view)
    result = pipeline.call("knowledge-apply", {"operation_id": "seed", "view_ref": view,
                                               "ingest_record_ref": record}, "batch")
    assert result["data"]["batch_complete"] is True
    assert source.read_bytes() == original
    return source, original


def native_nonroot():
    if os.name != "posix" or os.geteuid() == 0:
        pytest.skip("Requires real POSIX permissions under a non-root user")


def test_configure_unreadable_root_preserves_existing_local_bytes(tmp_path):
    native_nonroot()
    pipeline, _ = configured(tmp_path)
    local = pipeline.root / "docs-raw/sources/dbox.local.yml"
    before = local.read_bytes()
    denied = tmp_path / "denied root"
    denied.mkdir()
    denied.chmod(0)
    try:
        with pytest.raises(PermissionError):
            with os.scandir(denied):
                pass
        response = pipeline.call("knowledge-source", {"operation_id": "unreadable", "path": str(denied)},
                                 "configure", expected=2)
        assert response["diagnostics"][0]["code"] == "DBOX_ROOT_UNAVAILABLE"
        assert local.read_bytes() == before
    finally:
        denied.chmod(0o700)


def test_disconnected_permissions_do_not_turn_published_documents_into_missing(tmp_path):
    native_nonroot()
    pipeline, external = configured(tmp_path)
    source, original = publish_one(pipeline, external)
    external.chmod(0)
    try:
        with pytest.raises(PermissionError):
            source.read_bytes()
        response = pipeline.call("knowledge-source", {"operation_id": "denied-scan"}, "scan")
        inventory = pipeline.record(response["data"]["scan_ref"])
        assert inventory["complete"] is False
        assert inventory["dbox_root_error"]["code"] == "DBOX_ROOT_UNAVAILABLE"
        assert not any(unit["change"] == "missing" for unit in inventory["units"])
        blocked = pipeline.call("knowledge-source", {"operation_id": "denied-run"}, "run", expected=3)
        assert blocked["data"]["stopped_stage"] == "scan"
    finally:
        external.chmod(0o700)
    assert source.read_bytes() == original
    fresh = pipeline.call("knowledge-source", {"operation_id": "restored"}, "run")
    assert fresh["phase"] == "unchanged"


@pytest.mark.parametrize("denial", ["file", "subtree"])
def test_real_subtree_or_file_denial_keeps_scan_incomplete_without_deletions(tmp_path, denial):
    native_nonroot()
    pipeline, external = configured(tmp_path)
    source, original = publish_one(pipeline, external, "private/source.md")
    target = source if denial == "file" else source.parent
    mode = target.stat().st_mode & 0o777
    target.chmod(0)
    try:
        with pytest.raises(PermissionError):
            source.read_bytes()
        response = pipeline.call("knowledge-source", {"operation_id": "incomplete"}, "scan")
        inventory = pipeline.record(response["data"]["scan_ref"])
        assert inventory["complete"] is False
        assert not any(unit["change"] == "missing" for unit in inventory["units"])
        affected = [unit for unit in inventory["units"] if unit["path"] == DBOX + "/private/source.md"]
        assert affected and affected[0]["change"] in {"read_failed", "unfinished"}
    finally:
        target.chmod(mode)
    assert source.read_bytes() == original
    fresh = pipeline.call("knowledge-source", {"operation_id": "restored"}, "run")
    assert fresh["phase"] == "unchanged"


@pytest.mark.parametrize("kind", ["file", "directory", "cycle"])
def test_native_links_and_loops_are_rejected_without_foreign_fingerprints(tmp_path, kind):
    if os.name != "posix":
        pytest.skip("Native-link matrix runs on the Linux filesystem")
    pipeline, external = configured(tmp_path)
    foreign = tmp_path / "foreign directory"
    foreign.mkdir()
    secret = foreign / "outside.md"
    secret.write_bytes(b"# Outside\nThis must never become an observed dbox original.\n")
    link = external / "linked"
    link.symlink_to(secret if kind == "file" else external if kind == "cycle" else foreign,
                    target_is_directory=kind != "file")
    lock_path = pipeline.root / "governance/sources.lock.yaml"
    before_lock = lock_path.read_bytes()
    response = pipeline.call("knowledge-source", {"operation_id": "linked"}, "scan")
    inventory = pipeline.record(response["data"]["scan_ref"])
    assert inventory["complete"] is False
    assert [(unit["path"], unit["change"]) for unit in inventory["units"]] == [(DBOX + "/linked", "read_failed")]
    assert inventory["units"][0]["observed_fingerprint"] is None
    assert lock_path.read_bytes() == before_lock


@pytest.mark.parametrize("change", ["configuration", "adopted-bytes", "root-identity"])
def test_real_change_during_prepare_preserves_the_original_inventory(tmp_path, monkeypatch, change):
    pipeline, external = configured(tmp_path)
    original = b"# Source\nCapture marker is a documented rule.\n"
    source = external / "source.md"
    source.write_bytes(original)
    scanned = pipeline.call("knowledge-source", {"operation_id": "prepare-race"}, "scan")
    scan_ref = scanned["data"]["scan_ref"]
    inventory = (pipeline.root / scan_ref).read_bytes()
    lock_path = pipeline.root / "governance/sources.lock.yaml"
    before_lock = lock_path.read_bytes()
    probe = tmp_path / "actual prepare timing"
    probe.mkdir()
    ready, release = probe / "ready", probe / "release"
    script = r'''import sys, time
from pathlib import Path

def profile(frame, event, value):
    filename = frame.f_code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]
    if event == "call" and filename == "source_operations.py" and frame.f_code.co_name == "raw_member":
        sys.setprofile(None)
        Path(READY).write_bytes(b"ready")
        deadline = time.monotonic() + 30
        while not Path(RELEASE).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("SYNTHETIC_PREPARE_CHANGE_TIMEOUT")
            time.sleep(0.01)

sys.setprofile(profile)
'''
    (probe / "sitecustomize.py").write_text(
        script.replace("READY", repr(str(ready))).replace("RELEASE", repr(str(release))), encoding="utf-8")
    finished, errors = threading.Event(), []

    def writer():
        try:
            deadline = time.monotonic() + 25
            while not ready.exists():
                if finished.is_set():
                    raise AssertionError("Prepare did not reach its actual raw read")
                if time.monotonic() >= deadline:
                    raise AssertionError("Prepare timing marker was not observed")
                time.sleep(0.01)
            if change == "adopted-bytes":
                source.write_bytes(b"# Source\nChanged marker replaces the adopted bytes.\n")
            elif change == "root-identity":
                external.rename(tmp_path / "old root retained")
                external.mkdir()
                source.write_bytes(original)
            else:
                replacement = tmp_path / "another configured root"
                replacement.mkdir()
                (replacement / "source.md").write_bytes(original)
                (pipeline.root / "docs-raw/sources/dbox.local.yml").write_text(yaml.safe_dump({
                    "schema_version": "1.0", "path": str(replacement),
                }), encoding="utf-8")
        except BaseException as error:
            errors.append(error)
        finally:
            release.touch()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        with monkeypatch.context() as environment:
            environment.setenv("PYTHONPATH", str(probe))
            response = pipeline.call("knowledge-source", {"operation_id": "prepare-race", "scan_ref": scan_ref},
                                     "prepare", expected=3)
    finally:
        finished.set()
        release.touch()
        thread.join(timeout=30)
    assert not thread.is_alive() and not errors, errors
    assert ready.read_bytes() == b"ready"
    assert (pipeline.root / scan_ref).read_bytes() == inventory
    assert any(row["code"] in {"DBOX_BINDING_CHANGED", "SOURCE_CHANGED"} for row in response["diagnostics"])
    assert lock_path.read_bytes() == before_lock
