"""The merged preparation node uses the real source run, then P3 through P7."""

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "source_node_pipeline", Path(__file__).parents[1] / "pipeline_harness.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def test_combined_source_node_completes_real_six_node_public_chain(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    source = pipeline.write("docs-raw/specs/source.md", b"# Source\nCapture marker is a documented rule.\n")
    calls = []
    actual = pipeline.call

    def call(skill, request, action=None, expected=0):
        calls.append((skill, action))
        return actual(skill, request, action, expected)

    pipeline.call = call
    prepared = pipeline.call("knowledge-source", {"operation_id": "combined", "source": source}, "run")
    assert prepared["phase"] == "prepared"
    data = prepared["data"]
    material = pipeline.record(data["material_ref"])
    scan = pipeline.record(data["scan_ref"])
    assert material["scan_ref"] == data["scan_ref"]
    assert material["scan_digest"] == scan["digest"]
    bundle = pipeline.record(material["bundle_ref"])
    view = pipeline.view("combined", material["bundle_ref"], "combined-rule",
        pipeline.card("combined-rule", bundle), scan_ref=data["scan_ref"], material_ref=data["material_ref"])
    pipeline.review("combined", view)
    record = pipeline.pending_record("combined", view)
    result = pipeline.call("knowledge-apply", {"operation_id": "combined", "view_ref": view,
        "ingest_record_ref": record}, "batch")
    assert result["phase"] == "completed"
    assert result["data"]["batch_complete"] is True
    assert result["data"]["activated"] is True
    assert calls == [("knowledge-source", "run"), ("knowledge-change-plan", "plan"),
        ("knowledge-view-materialize", "run"), ("knowledge-lint", "review"),
        ("knowledge-source", "record"), ("knowledge-apply", "batch")]
    assert len(FIXTURE.PUBLIC_SKILLS) == 8
    assert not (pipeline.skills / "hs-knowledge-source-scan").exists()
    assert not (pipeline.skills / "hs-knowledge-source-prepare").exists()
    hit = pipeline.call("knowledge-query", {"operation_id": "read-combined", "query": "combined rule"}, "search")["data"]
    assert [row["card_id"] for row in hit["matches"]] == ["combined-rule"]
    read = pipeline.call("knowledge-query", {"operation_id": "read-combined-body",
        "receipt_ref": hit["receipt_ref"], "card_id": "combined-rule"}, "read")["data"]
    assert read["generation_ref"] == hit["generation_ref"]
    assert read["claims"][0]["id"] == "c1"


def test_combined_source_node_noop_stops_without_material_or_processing_record(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    result = pipeline.call("knowledge-source", {"operation_id": "empty"}, "run")
    assert result["phase"] == "unchanged"
    assert not result["data"].get("material_ref")
    assert not list((pipeline.root / ".build/operations/empty").glob("materials/*/material.json"))
    assert not list((pipeline.root / "logs/ingest").glob("*.yaml"))
    assert not (pipeline.root / "artifacts/indexes/local/active.json").exists()
