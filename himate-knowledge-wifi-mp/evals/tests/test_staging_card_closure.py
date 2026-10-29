"""Real P2/P4 algorithms retain necessary old cards, not reading candidates."""

import importlib.util
import base64
import json
from pathlib import Path

import pytest
import yaml


spec = importlib.util.spec_from_file_location("card_closure_boundary", Path(__file__).with_name("test_staging_source_boundary.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
production = fixture.helper.module("production")
snapshots = fixture.helper.module("input_snapshot")
runtime = fixture.runtime


def card(identity, snapshot, *, text=None):
    metadata = {"schema_version": "2.0", "id": identity, "profile": "rule", "title": identity,
        "summary": "Synthetic closure evidence", "lifecycle": "stable", "review_mode": "manual_document",
        "owner": "fixture", "scope": {"applicability": "unknown", "contexts": []}, "aliases": [],
        "sources": [{"evidence_ref": "source", "source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"],
                     "locator": {"kind": "lines", "start": 1, "end": 1}}],
        "claims": [{"id": "statement", "text_ref": "#statement", "evidence_kind": "design",
                    "source_refs": ["source"], "context_ids": [], "usage": "guidance", "verification_requirements": []}],
        "relations": []}
    return ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n<a id=\"statement\"></a>\n" + (text or identity) + "\n").encode()


def context(root, operation="batch", **request):
    ctx = fixture.make_context(root, operation, **request)
    ctx.args.rules_digest = runtime.sha((root / "governance/framework.lock.yaml").read_bytes())
    return ctx


def setup(tmp_path):
    fixture.write(tmp_path, "governance/framework.lock.yaml", b"explicit synthetic rules identity\n")
    fixture.write(tmp_path, "docs-raw/specs/source.md", b"# Fixed original\n")
    captured, _ = fixture.operations.capture(context(tmp_path, "seed", source_path="docs-raw/specs/source.md", source_id="source"))
    bundle = json.loads((tmp_path / captured["bundle_ref"]).read_bytes())
    fixture.write(tmp_path, "governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0",
        "resources": bundle["resources"], "snapshots": bundle["snapshots"]}).encode())
    old = {identity: card(identity, bundle["snapshots"][0]) for identity in ("changed", "reading")}
    for identity, raw in old.items():
        fixture.write(tmp_path, "knowledge/rules/" + identity + ".md", raw)
    prepared, _ = fixture.materials.prepare(context(tmp_path, targets=[{"source_path": "docs-raw/specs/source.md", "source_id": "source"}],
                                                        candidate_card_ids=["changed", "reading"]))
    material = json.loads((tmp_path / prepared["material_ref"]).read_bytes())
    return bundle["snapshots"][0], old, prepared, material


@pytest.mark.parametrize("action,expected", [("create", set()), ("update", {"changed"}),
    ("related", {"reading"}), ("deprecate", {"changed"}), ("unchanged_write", set()), ("explicit_history", {"reading"})])
def test_only_lost_versions_or_explicit_history_enter_card_publication(tmp_path, action, expected):
    snapshot, old, prepared, material = setup(tmp_path)
    selected = "changed" if action in {"update", "unchanged_write"} else "new"
    raw = old[selected] if action == "unchanged_write" else card(selected, snapshot, text="Authored revision")
    draft = ".build/operations/batch/draft.md"
    fixture.write(tmp_path, draft, raw)
    decision = {"candidate_id": selected, "decision": "update" if action in {"update", "unchanged_write"} else "create",
                "reason": "Actual authored scope", "card_inputs": [draft]}
    if action == "related":
        related = ".build/operations/batch/related.md"
        fixture.write(tmp_path, related, card("reading", snapshot, text="Explicit related edit"))
        decision["related_card_inputs"] = [related]
    if action == "deprecate":
        decision.update(decision="deprecate", card_inputs=[], replaces=["changed"])
    request = {"material_ref": prepared["material_ref"], "decisions": [decision]}
    if action == "explicit_history":
        # Absolute inside-K job input is normalized by capture_inputs; its hash
        # still denotes a card, not a generic object during publication.
        historical = ".build/operations/batch/explicit-history.md"
        fixture.write(tmp_path, historical, old["reading"])
        request["check_inputs"] = {"historical_card_objects": {runtime.sha(old["reading"]): str(tmp_path / historical)}}
    before = fixture.formal(tmp_path)
    ctx = context(tmp_path, **request)
    output, _ = production.assemble(ctx)
    view = json.loads((tmp_path / output["view_ref"]).read_bytes())
    assert fixture.formal(tmp_path) == before
    card_entries = [row for row in view["staged_objects"] if row["final_ref"].startswith("logs/evidence/published/cards/")]
    assert {row["sha256"] for row in card_entries} == {runtime.sha(old[identity]) for identity in expected}
    assert all(row["final_ref"] == "logs/evidence/published/cards/" + row["sha256"] + ".md" for row in card_entries)
    # Required source recovery/extraction/locator entries survive the card filter.
    source_entries = {row["final_ref"] for row in view["staged_objects"] if row["kind"] != "card"}
    material_bundle = json.loads((tmp_path / material["bundle_ref"]).read_bytes())
    assert {row["final_ref"] for row in material_bundle["staged_objects"] if row["kind"] != "card"} <= source_entries
    read_candidate = next(row for row in material["candidates"] if row["card_id"] == "reading")
    assert read_candidate["card_ref"] in view["input_snapshot"]["adopted_objects"]
    # Unchanged candidate stage remains a prewrite drift obligation.
    candidate_path = tmp_path / read_candidate["card_ref"]
    candidate_path.write_bytes(candidate_path.read_bytes() + b"\nUnexpected drift\n")
    observed = snapshots.compare_inputs(ctx, view["input_snapshot"])
    assert not observed["unchanged"]
    assert any(row.get("path") == read_candidate["card_ref"] for row in observed["changes"])


def test_published_input_projection_does_not_require_unmodified_candidate_copy(tmp_path):
    snapshot, _, prepared, material = setup(tmp_path)
    draft = ".build/operations/batch/draft.md"
    fixture.write(tmp_path, draft, card("new", snapshot, text="A new independent card"))
    output, _ = production.assemble(context(tmp_path, material_ref=prepared["material_ref"], decisions=[{
        "candidate_id": "new", "decision": "create", "reason": "New authored card", "card_inputs": [draft]}]))
    view = json.loads((tmp_path / output["view_ref"]).read_bytes())
    # Install only the explicit payload bytes to exercise the postwrite
    # projection. This is not a P7/transaction/index acceptance claim.
    for row in view["writes"]:
        fixture.write(tmp_path, row["path"], base64.b64decode(row["bytes_b64"], validate=True))
    for row in view["staged_objects"]:
        fixture.write(tmp_path, row["final_ref"], (tmp_path / row["stage_ref"]).read_bytes())
    consumer = context(tmp_path)
    published = snapshots.published_inputs(consumer, view["input_snapshot"], staged_objects=view["staged_objects"])
    assert not published["business_records"]
    assert all(not entry.get("path", key).startswith(".build/")
               for key, entry in published["adopted_objects"].items())
    for row in material["candidates"]:
        (tmp_path / row["card_ref"]).unlink()
    (tmp_path / prepared["material_ref"]).unlink()
    (tmp_path / material["bundle_ref"]).unlink()
    assert snapshots.compare_inputs(consumer, published, stage="postwrite")["unchanged"]
