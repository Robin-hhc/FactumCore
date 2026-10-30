"""Current source restrictions can be rebuilt without registering a local event."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("context_pipeline", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/pipeline.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_inspect_detects_unregistered_source_change_without_mutating_state(tmp_path):
    pipeline = fixture.Pipeline(tmp_path)
    bundle_ref, bundle = pipeline.capture("first", b"# Rule\nOriginal statement.\n")
    view = pipeline.view("first", bundle_ref, "inspect-rule", pipeline.card("inspect-rule", bundle))
    pipeline.apply("first", view)
    before = {path.relative_to(pipeline.root).as_posix(): path.read_bytes()
              for prefix in ("knowledge", "logs/events")
              for path in (pipeline.root / prefix).rglob("*") if path.is_file()}
    pipeline.write("docs-raw/specs/raw-source.md", b"# Rule\nA changed statement.\n")
    result = pipeline.call("knowledge-maintain", {"operation_id": "inspect"}, "inspect-context")["data"]
    assert result["complete"] is True
    assert {item["card_id"] for item in result["affected_claims"]} == {"inspect-rule"}
    assert any(item["reason"] == "source_changed" for item in result["affected_claims"])
    after = {path.relative_to(pipeline.root).as_posix(): path.read_bytes()
             for prefix in ("knowledge", "logs/events")
             for path in (pipeline.root / prefix).rglob("*") if path.is_file()}
    assert before == after
