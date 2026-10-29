"""Every actual P1-P6 public call leaves the formal tree unchanged."""

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("phase_boundary_manual", Path(__file__).with_name("test_manual_skills.py"))
MANUAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANUAL)


def formal(root):
    return {path.relative_to(root).as_posix(): MANUAL.FIXTURE.sha(path.read_bytes())
            for path in root.rglob("*") if path.is_file()
            and path.relative_to(root).parts[0] != ".build"}


def test_seven_stage_public_pipeline_publishes_only_in_p7(tmp_path):
    p = MANUAL.ManualPipeline(tmp_path)
    p.write("docs-raw/specs/phases.md", b"# Source\nCapture is explicitly documented.\n")
    baseline = formal(p.root)
    original = p.call
    calls = []

    def staged_call(slug, request, action=None, expected=0):
        response = original(slug, request, action, expected)
        assert formal(p.root) == baseline, (slug, action)
        calls.append((slug, action))
        return response

    p.call = staged_call
    scan_ref = p.call("knowledge-source-scan", {"operation_id": "phases"}, "scan")["data"]["scan_ref"]
    prepared = p.call("knowledge-source-prepare", {"operation_id": "phases", "scan_ref": scan_ref}, "prepare")
    material_ref = prepared["data"]["material_ref"]
    bundle_ref = p.record(material_ref)["bundle_ref"]
    view_ref = p.view("phases", bundle_ref, "phase-rule", p.card("phase-rule", p.record(bundle_ref)),
        scan_ref=scan_ref, material_ref=material_ref,
        queries=[{"id": "rule", "query": "capture", "required": ["phase-rule"]}])
    p.review("phases", view_ref)
    record_ref = p.pending_record("phases", view_ref)
    assert {slug for slug, _ in calls} >= {"knowledge-source-scan", "knowledge-source-prepare",
        "knowledge-change-plan", "knowledge-view-materialize", "knowledge-lint"}
    assert ("knowledge-source-scan", "record") in calls
    # A new process/operation after P6 still derives work solely from formal state.
    fresh = p.call("knowledge-source-scan", {"operation_id": "fresh-before-p7"}, "scan")
    assert p.record(fresh["data"]["scan_ref"])["units"][0]["change"] == "new"
    p.call = original
    result = p.call("knowledge-apply", {"operation_id": "phases", "view_ref": view_ref,
        "ingest_record_ref": record_ref}, "batch")["data"]
    assert result["published"] is True and result["batch_complete"] is True
    assert (p.root / "knowledge/rules/phase-rule.md").is_file()
    assert (p.root / "logs/ingest/phases.yaml").is_file()
    assert not (p.root / view_ref).exists()
