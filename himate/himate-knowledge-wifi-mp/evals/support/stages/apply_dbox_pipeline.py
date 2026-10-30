"""The published dbox journey and real interruption/recovery boundaries."""

import json
import copy as copy
import os
import importlib.util
from pathlib import Path
import re
import subprocess
import sys

import pytest as pytest

_spec = importlib.util.spec_from_file_location("dbox_pipeline_cases", Path(__file__).with_name("apply_publication_cli.py"))
existing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(existing)


def pending(tmp_path):
    pipeline = existing.MANUAL.ManualPipeline(tmp_path)
    source = tmp_path / "dbox"
    source.mkdir()
    (source / "manual.md").write_bytes(b"# Source\nCapture marker is a documented rule.\n")
    pipeline.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(source)}, "configure")
    operation = "dbox-publication"
    prepared = pipeline.call("knowledge-source", {"operation_id": operation}, "run")
    assert prepared["phase"] == "prepared", prepared
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    bundle_ref = pipeline.record(material_ref)["bundle_ref"]
    view = pipeline.view(operation, bundle_ref, "dbox-rule", pipeline.card("dbox-rule", pipeline.record(bundle_ref)),
                         scan_ref=scan_ref, material_ref=material_ref)
    pipeline.review(operation, view)
    record = pipeline.pending_record(operation, view)
    return pipeline, source, {"operation_id": operation, "view_ref": view, "ingest_record_ref": record}


def batch(pipeline, request, *, environment=None, expected=0, action="batch"):
    pipeline.sequence += 1
    incoming = pipeline.base / f"batch-input-{pipeline.sequence}.json"
    outgoing = pipeline.base / f"batch-output-{pipeline.sequence}.json"
    incoming.write_bytes(existing.P6.HELPER.canonical(request))
    process = subprocess.run([sys.executable, str(pipeline.root / "knowledge.py"), "apply", "--json",
        "--knowledge-root", str(pipeline.root), "--input", str(incoming), "--output", str(outgoing),
        "--action", action], capture_output=True, env=environment, timeout=120)
    result = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
    assert process.returncode == expected, (result, process.stderr.decode(errors="replace"))
    return result


def stop_environment(base, stop):
    probe = base / ("probe-" + stop)
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import sys
def profile(frame, event, value):
    if event != "call":
        return
    name = frame.f_code.co_name
    filename = frame.f_code.co_filename.replace("\\\\", "/").rsplit("/", 1)[-1]
    before_build = filename == "index_runtime.py" and name == "execute" and frame.f_locals["ctx"].args.action == "build"
    before_activation = filename == "ingest_execution.py" and name == "_activation_observation"
    if (STOP == "build" and before_build) or (STOP == "activate" and before_activation):
        sys.setprofile(None)
        raise RuntimeError("SYNTHETIC_DBOX_STOP")
sys.setprofile(profile)
'''.replace("STOP", repr(stop)), encoding="utf-8")
    return {**os.environ, "PYTHONPATH": str(probe)}


def resume_environment(base, *, cleanup_only=False):
    """A real CLI retry must not replay already completed business stages."""
    probe = base / "probe-resume"
    probe.mkdir()
    marker = probe / "loaded.txt"
    script = r'''from pathlib import Path
import sys
Path(MARKER).write_text("loaded", encoding="utf-8")
forbidden = {("transaction.py", "execute")}
if CLEANUP_ONLY:
    forbidden.update({("index_runtime.py", "execute"), ("index_runtime.py", "verify_generation"),
                      ("query_regression.py", "execute"), ("source_inventory.py", "scan"),
                      ("source_resources.py", "dbox_root"), ("source_resources.py", "read_dbox")})
def profile(frame, event, value):
    if event == "call":
        filename = frame.f_code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]
        if (filename, frame.f_code.co_name) in forbidden:
            raise RuntimeError("SYNTHETIC_REPLAY_OF_COMPLETED_WORK:" + filename + ":" + frame.f_code.co_name)
sys.setprofile(profile)
'''
    (probe / "sitecustomize.py").write_text(
        script.replace("MARKER", repr(str(marker))).replace("CLEANUP_ONLY", repr(cleanup_only)), encoding="utf-8")
    return {**os.environ, "PYTHONPATH": str(probe)}, marker


def assert_no_private_directory(raw, source):
    """JSON-escaped Windows paths and native/POSIX separators share one form."""
    private = re.sub(r"[\\/]+", "/", str(source)).casefold()
    published = re.sub(r"[\\/]+", "/", raw.decode("utf-8", errors="replace")).casefold()
    assert private not in published, "Published bytes contain the private source directory"
