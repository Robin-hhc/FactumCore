"""Merge/split run through installed dbox CLIs, exact evidence and P7 cleanup."""

import importlib.util
from pathlib import Path

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location(
    "dbox_decision_formats", Path(__file__).resolve().parents[2] / "support/stages/apply_formats.py"
)
FORMATS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FORMATS)
DBOX, json_bytes, no_private_path, sha = FORMATS.DBOX, FORMATS.json_bytes, FORMATS.no_private_path, FORMATS.sha
pipeline, release_runtime = FORMATS.pipeline, FORMATS.release_runtime


ALPHA = "Capture alpha marker requires an explicit alpha rule."
BETA = "Capture beta marker requires an explicit beta rule."
COMBINED = ALPHA + "\n" + BETA


def card_metadata(raw):
    return yaml.safe_load(raw.decode("utf-8-sig").split("---", 2)[1])


def authored_card(p, bundle, identity, text, locator):
    raw = p.card(identity, bundle, text)
    _, front, body = raw.decode("utf-8").split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["sources"][0]["locator"] = locator
    return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---" + body).encode()


@pytest.fixture
def decision_pipeline(pipeline, tmp_path):
    p = pipeline
    p.external = tmp_path / "decision external originals"
    p.external.mkdir()
    p.original_observations = []
    public_call = p.call

    def originals():
        return {path.relative_to(p.external).as_posix(): {
            "inode": path.stat().st_ino, "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns, "sha256": sha(path.read_bytes())}
            for path in p.external.rglob("*") if path.is_file()}

    def readonly_call(slug, request, action=None, expected=0):
        before = originals()
        try:
            return public_call(slug, request, action, expected)
        finally:
            after = originals()
            p.original_observations.append({"sequence": p.sequence, "skill": slug,
                "action": action, "before": before, "after": after})
            (tmp_path / "original-observations.json").write_bytes(json_bytes(p.original_observations))
            assert after == before, "Public CLI modified an external original"

    p.call = readonly_call
    p.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
    p.call("knowledge-source", {"operation_id": "configure", "path": str(p.external)}, "configure")
    return p


def run_batch(p, operation, cards, *, decision="create", replaces=(), mapping=None, before=None):
    prepared = p.call("knowledge-source", {"operation_id": operation, "source": DBOX}, "run")
    assert prepared["phase"] == "prepared"
    scan_ref = prepared["data"]["scan_ref"]
    material_ref = prepared["data"]["material_ref"]
    scan = p.record(scan_ref)
    assert scan["complete"] is True and scan["scope"] == [DBOX]
    assert len(scan["units"]) == 1
    unit = scan["units"][0]
    assert unit["path"] == DBOX + "/source.md"
    material = p.record(material_ref)
    bundle = p.record(material["bundle_ref"])
    assert {row["path"] for row in bundle["resources"]} == {unit["path"]}
    source_ref = {"source_id": unit["source_id"], "snapshot_id": bundle["snapshots"][0]["snapshot_id"]}
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
        "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "content",
        "reason": "Retire the exact old Claim with explicit replacement destinations"}
        for row in scan["current_context"].get("affected_claims", [])]
    if replaces:
        assert {row["card_id"] for row in maintenance} == set(replaces)
        assert unit["change"] == "changed"
    else:
        assert maintenance == [] and unit["change"] == "new"
    unit_ids = [unit["unit_id"]] + [row["unit_id"] for row in maintenance]
    all_ids = list(cards) + list(replaces)
    changes = [{"unit_ids": unit_ids, "card_id": identity, "claim_id": "c1", "action": "create",
        "before": None, "after": text, "conditions": "Universal synthetic source rule",
        "evidence": [source_ref], "preserved": "Exact source wording and native line locator",
        "reason": "Author this exact source-backed replacement Claim"}
        for identity, (text, _) in cards.items()]
    changes += [{"unit_ids": unit_ids, "card_id": identity, "claim_id": "c1", "action": "retire",
        "before": before[identity], "after": None, "conditions": "Retain the exact old Claim as historical",
        "evidence": [card_metadata((p.root / ("knowledge/rules/" + identity + ".md")).read_bytes())["sources"][0]],
        "preserved": "Original old evidence bytes remain recoverable",
        "reason": "The explicit Claim mapping names the replacement"} for identity in replaces]
    queries = [{"id": "current-replacement", "query": "capture", "purpose": "current",
        "required": list(cards), "forbidden": list(replaces),
        "expected_claim_ids": [identity + "#c1" for identity in cards]}]
    if replaces:
        queries.append({"id": "retained-old-claims", "query": "capture", "purpose": "historical",
            "required": list(replaces), "expected_claim_ids": [identity + "#c1" for identity in replaces]})
    semantic_ref = p.call("knowledge-change-plan", {"operation_id": operation,
        "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "fixture-author",
        "units": [{"unit_id": unit["unit_id"], "outcome": "content", "reason": "Read the exact external source"}],
        "maintenance_units": maintenance, "claim_changes": changes,
        "card_actions": [{"card_id": identity, "decision": decision, "author_id": "fixture-author",
            "unit_ids": unit_ids, "reason": "Explicit source-backed " + decision} for identity in all_ids],
        "target_queries": queries}, "plan")["data"]["semantic_plan_ref"]
    candidates = {identity: p.write(".build/candidates/" + operation + "/" + identity + ".md",
        authored_card(p, bundle, identity, text, locator)) for identity, (text, locator) in cards.items()}
    if decision == "create":
        decisions = [{"candidate_id": identity, "decision": "create", "reason": "Seed exact dbox evidence",
                      "card_inputs": [candidate]} for identity, candidate in candidates.items()]
    else:
        decisions = [{"candidate_id": operation, "decision": decision, "reason": "Explicit source-backed " + decision,
            "card_inputs": list(candidates.values()), "replaces": list(replaces), "claim_mapping": mapping}]
    view_ref = p.call("knowledge-view-materialize", {"operation_id": operation,
        "semantic_plan_ref": semantic_ref, "material_ref": material_ref, "decisions": decisions}, "run")["data"]["view_ref"]
    view = p.record(view_ref)
    assert {row["path"] for row in view["writes"] if row["path"].endswith(".md")
            and not row["path"].endswith("/index.md")} == {"knowledge/rules/" + identity + ".md" for identity in all_ids}
    _, review = p.review(operation, view_ref)
    assert review["status"] == "passed"
    record_ref = p.pending_record(operation, view_ref)
    pending = p.record(record_ref)
    assert pending["dispositions"][0]["action"] == decision
    applied = p.call("knowledge-apply", {"operation_id": operation, "view_ref": view_ref,
        "ingest_record_ref": record_ref}, "batch")
    assert applied["phase"] == "completed" and applied["data"]["batch_complete"] is True
    assert applied["data"]["published"] is True and applied["data"]["activated"] is True
    assert applied["data"]["cleanup"]["status"] == "done"
    assert not (p.root / view_ref).exists() and not (p.root / material_ref).exists()
    formal = yaml.safe_load((p.root / ("logs/ingest/" + operation + ".yaml")).read_bytes())
    assert formal["status"] == "applied" and formal["dispositions"][0]["action"] == decision
    publication = p.record(applied["data"]["publication_ref"])
    assert publication["dbox_execution_scope"] == [{"path": unit["path"],
        "sha256": sha((p.external / "source.md").read_bytes()), "bytes": (p.external / "source.md").stat().st_size}]
    for ref in applied["data"]["commit_files"]:
        assert "dbox.local.yml" not in ref
        no_private_path((p.root / ref).read_bytes(), p.external)
    return applied, scan


@pytest.mark.parametrize("decision", ["merge", "split"])
def test_dbox_merge_or_split_publishes_mapped_claims_and_preserves_old_evidence(decision_pipeline, tmp_path, decision):
    p = decision_pipeline
    old_cards = {"old-alpha": (ALPHA, {"kind": "lines", "start": 2, "end": 2}),
                 "old-beta": (BETA, {"kind": "lines", "start": 3, "end": 3})} if decision == "merge" else {
                     "old-combined": (COMBINED, {"kind": "lines", "start": 2, "end": 3})}
    original = ("# Source\n" + COMBINED + "\n").encode()
    child = p.external / "source.md"
    child.write_bytes(original)
    initial, seed_scan = run_batch(p, "seed-" + decision, old_cards)
    old_record = (p.root / ("logs/ingest/seed-" + decision + ".yaml")).read_bytes()
    old_sources = {identity: card_metadata((p.root / ("knowledge/rules/" + identity + ".md")).read_bytes())["sources"][0]
                   for identity in old_cards}
    current = original + b"Explicit source clarification preserves both rules.\n"
    child.write_bytes(current)
    if decision == "merge":
        cards = {"merged-rule": (COMBINED, {"kind": "lines", "start": 2, "end": 3})}
        mapping = {identity + "#c1": ["merged-rule#c1"] for identity in old_cards}
    else:
        cards = {"part-alpha": (ALPHA, {"kind": "lines", "start": 2, "end": 2}),
                 "part-beta": (BETA, {"kind": "lines", "start": 3, "end": 3})}
        mapping = {"old-combined#c1": ["part-alpha#c1", "part-beta#c1"]}
    applied, changed_scan = run_batch(p, "actual-" + decision, cards, decision=decision,
        replaces=list(old_cards), mapping=mapping, before={identity: text for identity, (text, _) in old_cards.items()})
    assert seed_scan["units"][0]["source_id"] == changed_scan["units"][0]["source_id"]
    assert initial["data"]["generation_ref"] != applied["data"]["generation_ref"]
    assert (p.root / ("logs/ingest/seed-" + decision + ".yaml")).read_bytes() == old_record
    assert p.call("knowledge-lint", {})["status"] == "passed"
    found = p.call("knowledge-query", {"operation_id": "current-" + decision,
        "query": "capture", "purpose": "current"}, "search")["data"]
    assert {row["card_id"] for row in found["matches"]} == set(cards)
    assert found["generation_ref"] == applied["data"]["generation_ref"]
    for hit in found["matches"]:
        read = p.call("knowledge-query", {"operation_id": "read-" + hit["card_id"],
            "card_id": hit["card_id"], "receipt_ref": found["receipt_ref"]}, "read")["data"]
        assert read["card_digest"] == hit["card_digest"] and read["generation_ref"] == found["generation_ref"]
        assert read["claims"][0]["text"].split("\n\n", 1)[0] == cards[hit["card_id"]][0]
        assert read["source_links"][0]["evidence"]["sha256"] == sha(current)
        assert read["source_links"][0]["evidence"]["locator"] == cards[hit["card_id"]][1]
        assert read["source_links"][0]["current"]["path"] == str(child)
    for identity, source_ref in old_sources.items():
        metadata = card_metadata((p.root / ("knowledge/rules/" + identity + ".md")).read_bytes())
        assert metadata["lifecycle"] == "deprecated"
        assert set(metadata["replacement"]) == set(cards)
        resolved = p.call("knowledge-source", {"operation_id": "resolve-" + identity,
            "source_ref": source_ref}, "resolve-source")["data"]
        assert resolved["sha256"] == sha(original)
        assert old_cards[identity][0] in resolved["text"]
    fresh = p.call("knowledge-source", {"operation_id": "fresh-" + decision, "source": DBOX}, "scan")
    final_scan = p.record(fresh["data"]["scan_ref"])
    assert final_scan["complete"] is True and len(final_scan["units"]) == 1
    final_unit = final_scan["units"][0]
    assert final_unit["change"] == "unchanged" and final_unit["progress"] == "completed"
    assert final_unit["observed_fingerprint"] == sha(current) and fresh["data"]["actionable_unit_ids"] == []
    assert child.read_bytes() == current
    (tmp_path / "case-evidence.json").write_bytes(json_bytes({"release": p.release_identity,
        "decision": decision, "logical_path": DBOX + "/source.md", "initial_sha256": sha(original),
        "current_sha256": sha(current), "claim_mapping": mapping, "old_cards": list(old_cards), "new_cards": list(cards),
        "seed_publication": initial["data"]["publication_ref"], "publication": applied["data"]["publication_ref"],
        "generation_ref": found["generation_ref"], "fresh_scan_ref": fresh["data"]["scan_ref"],
        "cli_calls": len(p.audit), "cli_seconds": sum(row["seconds"] for row in p.audit)}))
