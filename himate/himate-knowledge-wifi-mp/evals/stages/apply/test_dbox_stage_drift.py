"""Public P4/P6 reject adopted dbox drift without rescanning its whole tree."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


_spec = importlib.util.spec_from_file_location(
    "dbox_stage_journey", Path(__file__).resolve().parents[2] / "support/stages/apply_dbox_pipeline.py"
)
journey = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(journey)


def cli(pipeline, skill, action, request, *, expected=0, environment=None):
    """Run the installed public entry with the fixture's actual release lock."""
    pipeline.sequence += 1
    incoming = pipeline.base / f"stage-input-{pipeline.sequence}.json"
    outgoing = pipeline.base / f"stage-output-{pipeline.sequence}.json"
    incoming.write_bytes(journey.existing.P6.HELPER.canonical(request))
    process = subprocess.run(
        [sys.executable, str(pipeline.root / "knowledge.py"), skill, "--json",
         "--knowledge-root", str(pipeline.root), "--rules-digest", pipeline.rules,
         "--input", str(incoming), "--output", str(outgoing), "--action", action],
        capture_output=True, timeout=120, env=environment,
    )
    result = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
    assert process.returncode == expected, (result, process.stderr.decode(errors="replace"))
    return result


def formal_state(pipeline):
    """Include actual index pointers, published evidence and processing records."""
    return {path.relative_to(pipeline.root).as_posix(): path.read_bytes()
            for path in pipeline.root.rglob("*") if path.is_file()
            and path.relative_to(pipeline.root).parts[0] != ".build"}


def before_review(tmp_path):
    pipeline = journey.existing.MANUAL.ManualPipeline(tmp_path)
    source = tmp_path / "dbox"
    source.mkdir()
    (source / "manual.md").write_bytes(b"# Source\nCapture marker is a documented rule.\n")
    pipeline.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    pipeline.call("knowledge-source", {"operation_id": "configure", "path": str(source)}, "configure")
    operation = "dbox-stage-drift"
    prepared = pipeline.call("knowledge-source", {"operation_id": operation}, "run")["data"]
    bundle_ref = pipeline.record(prepared["material_ref"])["bundle_ref"]
    view_ref = pipeline.view(
        operation, bundle_ref, "dbox-rule", pipeline.card("dbox-rule", pipeline.record(bundle_ref)),
        scan_ref=prepared["scan_ref"], material_ref=prepared["material_ref"],
    )
    # Preserve the exact original public P3 request for a genuine reentry below.
    materialize_request = json.loads((pipeline.base / f"manual-in-{pipeline.sequence}.json").read_bytes())
    view = pipeline.record(view_ref)
    semantic = pipeline.record(view["semantic_plan_ref"])
    request = {"operation_id": operation, "view_ref": view_ref,
               "semantic_plan_ref": view["semantic_plan_ref"],
               "reviewer_id": "fixture-independent-reader", "independent_context": "fresh-fixture-context",
               "sampled_unit_ids": [row["unit_id"] for row in semantic["units"]],
               "unreviewed_unit_ids": [], "reason": "Synthetic reader reviewed the full source and authored view",
               "findings": []}
    return pipeline, source, request, materialize_request


def mutate(pipeline, source, fault):
    if fault == "bytes":
        (source / "manual.md").write_bytes(b"# Source\nThe adopted rule changed after drafting.\n")
        return
    replacement = pipeline.base / "same-bytes-new-root"
    replacement.mkdir()
    (replacement / "manual.md").write_bytes((source / "manual.md").read_bytes())
    pipeline.call("knowledge-source", {"operation_id": "relocate", "path": str(replacement)}, "configure")


def no_recursive_scan_environment(pipeline, source):
    """Observe actual filesystem enumeration, while allowing root readability checks."""
    probe = pipeline.base / "p5-enumeration-probe"
    probe.mkdir()
    trace = probe / "enumerations.json"
    (probe / "sitecustomize.py").write_text('''import atexit
import json
import os
from pathlib import Path
import sys

root = os.path.normcase(os.path.abspath(os.environ["HIMATE_TEST_DBOX_AUDIT_ROOT"]))
observed = []

def audit(event, args):
    if event != "os.scandir" or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
    if path == root or path.startswith(root + os.sep):
        relative = os.path.relpath(path, root)
        observed.append(relative)
        if relative != ".":
            raise RuntimeError("P5_RECURSIVELY_SCANNED_UNADOPTED_DBOX")

atexit.register(lambda: Path(os.environ["HIMATE_TEST_DBOX_AUDIT_TRACE"]).write_text(json.dumps(observed)))
sys.addaudithook(audit)
''', encoding="utf-8")
    return {**os.environ, "PYTHONPATH": str(probe), "HIMATE_TEST_DBOX_AUDIT_ROOT": str(source),
            "HIMATE_TEST_DBOX_AUDIT_TRACE": str(trace)}, trace


def test_p5_checks_adopted_file_without_recursively_scanning_new_dbox_subtree(tmp_path):
    pipeline, source, request, _ = before_review(tmp_path)
    unadopted = source / "unselected" / "deep" / "new.md"
    unadopted.parent.mkdir(parents=True)
    unadopted.write_bytes(b"Unrelated new source outside the already adopted input set.\n")
    environment, trace = no_recursive_scan_environment(pipeline, source)
    before = formal_state(pipeline)
    report = cli(pipeline, "lint", "review", request, environment=environment)
    assert report["status"] == "passed" and report["review"]["fixed_checks_executed"] is True
    assert report["review"]["return_to"] == []
    observations = json.loads(trace.read_bytes())
    assert observations and set(observations) == {"."}
    assert formal_state(pipeline) == before
    assert not (pipeline.root / "logs/publications").exists()


@pytest.mark.parametrize("fault", ["bytes", "same_bytes_new_root"])
def test_p5_reports_adopted_dbox_drift_and_p4_requires_fresh_operation(tmp_path, fault):
    pipeline, source, request, materialize_request = before_review(tmp_path)
    view_before = (pipeline.root / request["view_ref"]).read_bytes()
    mutate(pipeline, source, fault)
    before = formal_state(pipeline)
    report = cli(pipeline, "lint", "review", request, expected=1)
    assert report["status"] == "failed" and report["complete"] is False
    assert any(row["code"] == "INPUT_CHANGED" for row in report["findings"])
    observed = next(row["input_observation"] for row in report["checks"] if "input_observation" in row)
    assert observed["unchanged"] is False
    assert any(row["group"] == "current_files" and row["path"] == "docs-raw/sources/dbox/manual.md"
               for row in observed["changes"])
    reentry = cli(pipeline, "view-materialize", "run", materialize_request, expected=2)
    assert reentry["diagnostics"][0]["code"] == "INPUT_CHANGED"
    assert "fresh operation" in reentry["diagnostics"][0]["message"]
    assert (pipeline.root / request["view_ref"]).read_bytes() == view_before
    assert formal_state(pipeline) == before
    assert not (pipeline.root / "logs/publications").exists()


@pytest.mark.parametrize("fault", ["bytes", "same_bytes_new_root"])
def test_p7_rejects_post_review_dbox_drift_before_formal_writes_or_activation(tmp_path, fault):
    pipeline, source, request = journey.pending(tmp_path)
    # Give the failed batch a real previously activated generation to preserve.
    built = pipeline.call("knowledge-apply", {"operation_id": "prior-index"}, "index-build")["data"]
    pipeline.call("knowledge-apply", {"operation_id": "prior-index", "generation_ref": built["generation_ref"],
                                      "expected_active": built["expected_active"]}, "index-activate")
    active = pipeline.root / "artifacts/indexes/local/active.json"
    active_before = active.read_bytes()
    view_before = (pipeline.root / request["view_ref"]).read_bytes()
    mutate(pipeline, source, fault)
    before = formal_state(pipeline)
    failed = cli(pipeline, "apply", "batch", request, expected=3)
    assert failed["status"] == "blocked"
    # The retained transaction boundary wraps the shared input diagnostic.
    assert failed["diagnostics"][0]["code"] == "awaiting_prerequisite"
    assert "batch input observation is unavailable: Batch inputs changed" in failed["diagnostics"][0]["message"]
    assert formal_state(pipeline) == before
    assert active.read_bytes() == active_before
    assert (pipeline.root / request["view_ref"]).read_bytes() == view_before
    assert not (pipeline.root / "knowledge/rules/dbox-rule.md").exists()
    assert not (pipeline.root / "logs/ingest/dbox-publication.yaml").exists()
    assert not (pipeline.root / "logs/publications/dbox-publication/manifest.json").exists()
    assert not (pipeline.root / ".build/operations/dbox-publication/transaction/journal.json").exists()
