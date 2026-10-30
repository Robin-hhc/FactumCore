"""Installed public CLIs exercise successive real dbox source lifecycles."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import pytest
import yaml

from support.releases import load_manual, select_release


ROOT = Path(__file__).resolve().parents[5]
SELECTION = select_release(ROOT, checkout=os.environ.get("HIMATE_DBOX_RELEASE_CHECKOUT"),
                           manifest_path=os.environ.get("HIMATE_DBOX_RELEASE_MANIFEST"))
RELEASE = SELECTION.root
MANUAL = load_manual(SELECTION, "dbox_incremental_manual")
PREFIX = "docs-raw/sources/dbox/"
PRIMARY = "中文 分组/manual.md"
SECONDARY = "other/second.md"
FIRST = "The capture marker requires version one."
SECOND = "The capture marker requires version two."


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Lifecycle(MANUAL.ManualPipeline):
    def __init__(self, base):
        super().__init__(base)
        self.external = base / "external documents"
        self.external.mkdir()
        self.external_roots = [self.external]
        self.trace = {"release_checkout": str(RELEASE), "rules_digest": self.rules,
                      "calls": [], "observations": []}
        release_manifest = os.environ.get("HIMATE_DBOX_RELEASE_MANIFEST")
        if release_manifest:
            self.trace.update(release_manifest=release_manifest,
                              release_manifest_sha256=sha(Path(release_manifest).read_bytes()))
        self.write("docs-raw/sources/.gitignore", b"/dbox.local.yml\n")
        self.call("knowledge-source", {"operation_id": "configure", "path": str(self.external)}, "configure")

    def originals(self):
        result = {f"root-{index}/" + path.relative_to(root).as_posix(): sha(path.read_bytes())
                  for index, root in enumerate(self.external_roots)
                  for path in root.rglob("*") if path.is_file()}
        moved = self.base / "moved-out.md"
        if moved.exists():
            result["moved-out.md"] = sha(moved.read_bytes())
        return result

    def save_trace(self):
        self.trace["call_count"] = len(self.trace["calls"])
        self.trace["total_cli_seconds"] = sum(row["seconds"] for row in self.trace["calls"])
        self.trace["stage_cli_seconds"] = {}
        for row in self.trace["calls"]:
            stage = row["skill"] + ":" + row["action"]
            self.trace["stage_cli_seconds"][stage] = self.trace["stage_cli_seconds"].get(stage, 0) + row["seconds"]
        (self.base / "lifecycle-evidence.json").write_text(
            json.dumps(self.trace, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def call(self, slug, request, action=None, expected=0):
        before = self.originals()
        started = time.perf_counter()
        try:
            result = super().call(slug, request, action, expected)
        finally:
            elapsed = time.perf_counter() - started
            after = self.originals()
            self.trace["calls"].append({"skill": slug, "action": action or "run",
                "operation_id": request.get("operation_id"), "seconds": elapsed,
                "request": f"manual-in-{self.sequence}.json", "response": f"manual-out-{self.sequence}.json",
                "expected_exit": expected, "original_sha_before": before, "original_sha_after": after})
            self.save_trace()
            assert before == after, "An ingestion/query CLI modified external originals"
        return result

    def put(self, relative, sentence):
        path = self.external / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = ("# Source\n" + sentence + "\n").encode()
        path.write_bytes(raw)
        return raw

    def scan(self, operation, source=None, action="scan"):
        request = {"operation_id": operation}
        if source is not None:
            request["source"] = PREFIX + source
        response = self.call("knowledge-source", request, action)
        scan = self.record(response["data"]["scan_ref"])
        self.trace["observations"].append({"operation_id": operation, "phase": response["phase"],
            "complete": scan["complete"], "scope": scan["scope"], "full_scan": scan["full_scan"],
            "units": scan["units"], "affected_claims": scan["current_context"].get("affected_claims", [])})
        self.save_trace()
        return response, scan


def metadata(raw):
    return yaml.safe_load(raw.decode("utf-8-sig").split("---", 2)[1])


def finish(pipeline, prepared, relative, identity, sentence, decision="create", before=None, batch_expected=0):
    """Author the exact Claim and disposition coverage, then really run P3--P7."""
    operation = pipeline.record(prepared["data"]["scan_ref"])["operation_id"]
    scan = pipeline.record(prepared["data"]["scan_ref"])
    material_ref = prepared["data"]["material_ref"]
    material = pipeline.record(material_ref)
    bundle = pipeline.record(material["bundle_ref"])
    unit = next(row for row in scan["units"] if row["path"] == PREFIX + relative)
    maintenance = [{"unit_id": "maintenance:" + card + "#" + claim, "card_id": card,
        "claim_id": claim, "outcome": "content", "reason": "Revise this exact affected Claim"}
        for card, claim in sorted({(row["card_id"], row["claim_id"])
                                  for row in scan["current_context"].get("affected_claims", [])})]
    assert all(row["card_id"] == identity for row in maintenance), maintenance
    adopted = [unit["unit_id"]] + [row["unit_id"] for row in maintenance]
    card_path = "knowledge/rules/" + identity + ".md"
    if decision == "deprecate":
        source = metadata((pipeline.root / card_path).read_bytes())["sources"][0]
        candidate_decision = {"candidate_id": identity, "decision": decision, "replaces": [identity],
                              "card_inputs": [], "reason": "Source was deliberately removed; retire current advice"}
        cases = [{"id": "retire-current", "query": identity.removesuffix("-rule"), "purpose": "current", "forbidden": [identity]},
                 {"id": "retain-history", "query": identity.removesuffix("-rule"), "purpose": "historical", "required": [identity],
                  "expected_claim_ids": [identity + "#c1"]}]
    else:
        snapshot = next(row for row in bundle["snapshots"] if row["source_id"] == unit["source_id"])
        source = {"source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"]}
        candidate = pipeline.write(f".build/candidates/{operation}/{identity}.md",
            pipeline.card(identity, {"snapshots": [snapshot]}, sentence))
        candidate_decision = {"candidate_id": identity, "decision": decision,
                              "card_inputs": [candidate], "reason": "Use the exact newly read source wording"}
        cases = [{"id": identity, "query": identity.removesuffix("-rule"), "purpose": "current", "required": [identity],
                  "expected_claim_ids": [identity + "#c1"]}]
    semantic = pipeline.call("knowledge-change-plan", {"operation_id": operation,
        "scan_ref": prepared["data"]["scan_ref"], "material_ref": material_ref, "author_id": "fixture-author",
        "units": [{"unit_id": row["unit_id"], "outcome": "content" if row == unit else "skip",
                   "reason": "Read the changed source" if row == unit else "Exact already published version is unchanged"}
                  for row in scan["units"]], "maintenance_units": maintenance,
        "claim_changes": [{"unit_ids": adopted, "card_id": identity, "claim_id": "c1",
            "action": "retire" if decision == "deprecate" else decision, "before": before,
            "after": None if decision == "deprecate" else sentence, "conditions": "Universal synthetic document rule",
            "evidence": [source], "preserved": "Retain source identity and exact old evidence",
            "reason": candidate_decision["reason"]}],
        "card_actions": [{"card_id": identity, "decision": decision, "author_id": "fixture-author",
                          "unit_ids": adopted, "reason": candidate_decision["reason"]}],
        "target_queries": cases}, "plan")["data"]["semantic_plan_ref"]
    view_ref = pipeline.call("knowledge-view-materialize", {"operation_id": operation,
        "semantic_plan_ref": semantic, "material_ref": material_ref,
        "decisions": [candidate_decision]}, "run")["data"]["view_ref"]
    view = pipeline.record(view_ref)
    # P1's proven, terminal unchanged scan-skips are outside P5's risk sample.
    # Review every adopted/affected unit; no content unit is left unreviewed.
    assert all(row == unit or (row["change"] == "unchanged"
                              and row["progress"] in {"completed", "skipped", "withdrawn"})
               for row in scan["units"])
    historical = {row["card_digest"]: str(pipeline.root / row["card_ref"])
                  for row in material.get("candidates", []) if row.get("card_ref")}
    report = pipeline.call("knowledge-lint", {"operation_id": operation, "view_ref": view_ref,
        "semantic_plan_ref": semantic, "reviewer_id": "fixture-independent-reader",
        "independent_context": "fresh-fixture-context", "sampled_unit_ids": adopted,
        "unreviewed_unit_ids": [], "reason": "Read every adopted/affected Claim and its exact original; P1 terminal scan-skips are retained",
        "findings": [], "inputs": {"historical_card_objects": historical}}, "review")
    assert report["status"] == "passed" and report["review"]["fixed_checks_executed"] is True
    record_ref = pipeline.pending_record(operation, view_ref)
    pending = pipeline.record(record_ref)
    assert pending["inventory"]["digest"] == pending["scan_digest"] == scan["digest"]
    assert pending["content_view_digest"] == view["digest"]
    if decision == "deprecate" and unit["change"] == "missing":
        withdrawal = next(row for row in pending["dispositions"] if row["unit_id"] == unit["unit_id"])
        assert withdrawal["action"] == "deprecate" and withdrawal["progress"] == "withdrawn"
        assert withdrawal["observed_fingerprint"] is None and withdrawal["adopted_fingerprint"] is None
    applied = pipeline.call("knowledge-apply", {"operation_id": operation, "view_ref": view_ref,
        "ingest_record_ref": record_ref}, "batch", expected=batch_expected)
    if batch_expected:
        return applied, source
    assert applied["data"]["batch_complete"] is True and applied["data"]["activated"] is True, applied
    assert pipeline.record("logs/ingest/" + operation + ".yaml")["status"] == "applied"
    pipeline.trace["observations"].append({"operation_id": operation, "publication": applied["data"],
                                           "source_ref": source, "view_digest": view["digest"]})
    pipeline.save_trace()
    return applied, source


def search_read(pipeline, operation, identity, purpose="current"):
    found = pipeline.call("knowledge-query", {"operation_id": operation, "query": identity.removesuffix("-rule"),
                                               "purpose": purpose}, "search")["data"]
    assert [row["card_id"] for row in found["matches"]] == [identity]
    read = pipeline.call("knowledge-query", {"operation_id": operation + "-read", "card_id": identity,
                                              "receipt_ref": found["receipt_ref"]}, "read")["data"]
    assert read["card_digest"] == found["matches"][0]["card_digest"]
    return found, read


def test_continuous_new_unchanged_update_add_remove_and_retire_dbox(tmp_path):
    p = Lifecycle(tmp_path)
    original = p.put(PRIMARY, FIRST)
    first, first_scan = p.scan("first", action="run")
    assert [row["change"] for row in first_scan["units"]] == ["new"]
    initial, old_source = finish(p, first, PRIMARY, "primary-rule", FIRST)
    old_record = (p.root / "logs/ingest/first.yaml").read_bytes()
    old_search, old_read = search_read(p, "old-historical", "primary-rule", "historical")
    assert old_read["source_links"][0]["evidence"]["sha256"] == sha(original)
    noop, observed = p.scan("no-change", action="run")
    assert noop["phase"] == "unchanged" and "material_ref" not in noop["data"]
    assert [row["change"] for row in observed["units"]] == ["unchanged"]

    changed = p.put(PRIMARY, SECOND)
    prepared, changed_scan = p.scan("changed", action="run")
    assert changed_scan["units"][0]["change"] == "changed"
    assert changed_scan["units"][0]["source_id"] == first_scan["units"][0]["source_id"]
    updated, new_source = finish(p, prepared, PRIMARY, "primary-rule", SECOND, "update", FIRST)
    assert old_source["source_id"] == new_source["source_id"]
    assert old_source["snapshot_id"] != new_source["snapshot_id"]
    assert initial["data"]["generation_ref"] != updated["data"]["generation_ref"]
    _, read = search_read(p, "new-current", "primary-rule")
    assert read["claims"][0]["text"].splitlines()[0] == SECOND
    assert FIRST not in read["claims"][0]["text"]
    assert read["source_links"][0]["evidence"]["sha256"] == sha(changed)
    retained = p.call("knowledge-query", {"operation_id": "old-read-after-update", "card_id": "primary-rule",
                                          "receipt_ref": old_search["receipt_ref"]}, "read")["data"]
    assert retained["claims"][0]["text"].splitlines()[0] == FIRST
    assert SECOND not in retained["claims"][0]["text"]
    assert retained["source_links"][0]["evidence"]["sha256"] == sha(original)
    assert retained["card_ref"] != read["card_ref"]
    assert (p.root / "logs/ingest/first.yaml").read_bytes() == old_record

    publish_addition(p)
    observe_removals_and_retire(p, SECOND)


def publish_addition(p):
    p.put(SECONDARY, "A second independent capture marker is documented.")
    added, addition_scan = p.scan("added", action="run")
    assert {row["path"]: row["change"] for row in addition_scan["units"]} == {
        PREFIX + PRIMARY: "unchanged", PREFIX + SECONDARY: "new"}
    assert added["data"]["actionable_unit_ids"] == [next(row["unit_id"] for row in addition_scan["units"]
                                                          if row["path"] == PREFIX + SECONDARY)]
    finish(p, added, SECONDARY, "secondary-rule", "A second independent capture marker is documented.")
    search_read(p, "secondary-current", "secondary-rule")
    assert p.scan("after-addition", action="run")[0]["phase"] == "unchanged"

def observe_removals_and_retire(p, sentence):
    primary = p.external / PRIMARY
    primary.unlink()
    _, deleted = p.scan("deleted")
    assert {row["path"]: row["change"] for row in deleted["units"]} == {
        PREFIX + PRIMARY: "missing", PREFIX + SECONDARY: "unchanged"}
    p.put(PRIMARY, sentence)
    renamed = primary.with_name("renamed.md")
    primary.rename(renamed)
    _, rename_scan = p.scan("renamed")
    rename_units = {row["path"]: row for row in rename_scan["units"]}
    assert rename_units[PREFIX + PRIMARY]["change"] == "missing"
    assert rename_units[PREFIX + "中文 分组/renamed.md"]["change"] == "new"
    assert rename_units[PREFIX + "中文 分组/renamed.md"]["source_id"] != rename_units[PREFIX + PRIMARY]["source_id"]
    renamed.rename(primary)
    moved = p.base / "moved-out.md"
    primary.rename(moved)
    _, moved_scan = p.scan("moved-out")
    assert next(row for row in moved_scan["units"] if row["path"] == PREFIX + PRIMARY)["change"] == "missing"
    assert all("moved-out" not in row["path"] for row in moved_scan["units"])
    moved.rename(primary)

    second = p.external / SECONDARY
    second_bytes = second.read_bytes()
    second.unlink()
    _, scoped = p.scan("limited", "中文 分组")
    assert scoped["full_scan"] is False and scoped["complete"] is True
    assert [(row["path"], row["change"]) for row in scoped["units"]] == [(PREFIX + PRIMARY, "unchanged")]
    second.write_bytes(second_bytes)
    (p.external / "empty").mkdir()
    empty, empty_scan = p.scan("empty-scope", "empty", action="run")
    assert empty["phase"] == "unchanged" and empty_scan["units"] == []

    primary.unlink()
    retirement, retirement_scan = p.scan("retired", action="run")
    assert next(row for row in retirement_scan["units"] if row["path"] == PREFIX + PRIMARY)["change"] == "missing"
    finish(p, retirement, PRIMARY, "primary-rule", sentence, "deprecate", sentence)
    assert metadata((p.root / "knowledge/rules/primary-rule.md").read_bytes())["lifecycle"] == "deprecated"
    query = p.call("knowledge-query", {"operation_id": "retired-current", "query": "primary"}, "search")
    assert query["data"]["matches"] == []
    search_read(p, "retired-history", "primary-rule", "historical")
    final, final_scan = p.scan("settled-retirement", action="run")
    assert next(row for row in final_scan["units"] if row["path"] == PREFIX + PRIMARY)["change"] == "unchanged"
    assert final["phase"] == "unchanged", final
    # Retirement must not hide missing or corrupted retained evidence.
    lock = yaml.safe_load((p.root / "governance/sources.lock.yaml").read_bytes())
    source = metadata((p.root / "knowledge/rules/primary-rule.md").read_bytes())["sources"][0]
    snapshot = next(row for row in lock["snapshots"] if row["snapshot_id"] == source["snapshot_id"])
    retained = p.root / snapshot["recovery"]["path"]
    exact_bytes = retained.read_bytes()
    for damage in ("missing", "corrupt"):
        if damage == "missing":
            retained.unlink()
        else:
            retained.write_bytes(b"Deliberately corrupted retained original.\n")
        inspected = p.call("knowledge-maintain", {"operation_id": "retired-evidence-" + damage}, "inspect-context")
        assert any(row["card_id"] == "primary-rule" and row["reason"] == "source_unavailable"
                   for row in inspected["data"]["affected_claims"]), inspected
        unresolved, _ = p.scan("retired-evidence-scan-" + damage, action="run")
        assert unresolved["phase"] != "unchanged"
        retained.write_bytes(exact_bytes)
    p.put(PRIMARY, sentence)
    returned, return_scan = p.scan("reappeared", action="run")
    restored = next(row for row in return_scan["units"] if row["path"] == PREFIX + PRIMARY)
    assert returned["phase"] == "prepared" and restored["change"] == "changed"
    assert restored["source_id"] == source["source_id"]
    assert metadata((p.root / "knowledge/rules/primary-rule.md").read_bytes())["lifecycle"] == "deprecated"
    primary.unlink()


def test_addition_deletion_rename_move_scoped_scan_and_retirement_without_prior_update(tmp_path):
    """Keep independent coverage when an earlier lifecycle update is blocked."""
    p = Lifecycle(tmp_path)
    p.put(PRIMARY, FIRST)
    first, _ = p.scan("first", action="run")
    finish(p, first, PRIMARY, "primary-rule", FIRST)
    publish_addition(p)
    observe_removals_and_retire(p, FIRST)


def test_empty_configured_dbox_is_complete_unchanged_without_processing_debt(tmp_path):
    p = Lifecycle(tmp_path)
    (p.external / "empty" / "nested").mkdir(parents=True)
    result, scan = p.scan("initial-empty", action="run")
    assert result["phase"] == "unchanged" and scan["complete"] is True and scan["units"] == []
    assert scan["current_context"]["affected_claims"] == []
    assert "material_ref" not in result["data"]
    assert not (p.root / "logs/ingest").exists()


@pytest.mark.parametrize("switch_root", [False, True])
def test_standalone_registered_dbox_change_checks_the_captured_root(tmp_path, switch_root):
    p = Lifecycle(tmp_path)
    p.put(PRIMARY, FIRST)
    first, _ = p.scan("first", action="run")
    _, source = finish(p, first, PRIMARY, "primary-rule", FIRST)
    current_bytes = p.put(PRIMARY, SECOND)
    captured = p.call("knowledge-source", {"operation_id": "standalone-capture", "source_path": PREFIX + PRIMARY,
        "source_id": source["source_id"]}, "capture")["data"]["bundle_ref"]
    snapshot = p.record(captured)["snapshots"][0]
    assert snapshot["snapshot_id"] != source["snapshot_id"] and snapshot["sha256"] == sha(current_bytes)
    event_root = p.root / "logs/events"
    before = {path.name: path.read_bytes() for path in event_root.glob("*.json")}
    if switch_root:
        replacement = tmp_path / "same bytes replacement"
        shutil.copytree(p.external, replacement)
        p.external_roots.append(replacement)
        p.call("knowledge-source", {"operation_id": "relocate", "path": str(replacement)}, "configure")
    result = p.call("knowledge-maintain", {"operation_id": "register", "bundle_ref": captured},
                    "register-source-change", expected=2 if switch_root else 0)
    if switch_root:
        assert result["diagnostics"][0]["code"] == "DBOX_BINDING_CHANGED"
        assert {path.name: path.read_bytes() for path in event_root.glob("*.json")} == before
    else:
        assert result["phase"] == "registered" and len(result["data"]["event_refs"]) == 1
        event = p.record(result["data"]["event_refs"][0])
        assert event["source_snapshot"]["snapshot_id"] == snapshot["snapshot_id"]
        assert event["source_snapshot"]["sha256"] == sha(current_bytes)
        assert event["change"]["old_snapshot_ids"] == [source["snapshot_id"]]


def test_same_release_committed_update_resumes_exact_refs_without_reapplying(tmp_path, monkeypatch):
    p = Lifecycle(tmp_path)
    p.put(PRIMARY, FIRST)
    first, _ = p.scan("first", action="run")
    finish(p, first, PRIMARY, "primary-rule", FIRST)
    p.put(PRIMARY, SECOND)
    prepared, _ = p.scan("changed", action="run")
    probe = tmp_path / "stop-before-event-publication"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import sys

def stop(frame, event, value):
    if (event == "call" and frame.f_code.co_name == "publish_changes"
            and frame.f_code.co_filename.replace("\\\\", "/").rsplit("/", 1)[-1] == "maintenance.py"):
        sys.setprofile(None)
        raise RuntimeError("SYNTHETIC_STOP_AFTER_COMMITTED_CONTENT")

sys.setprofile(stop)
''', encoding="utf-8")
    with monkeypatch.context() as isolated:
        isolated.setenv("PYTHONPATH", str(probe))
        failed, source = finish(p, prepared, PRIMARY, "primary-rule", SECOND, "update", FIRST, batch_expected=2)
    assert "SYNTHETIC_STOP_AFTER_COMMITTED_CONTENT" in failed["diagnostics"][0]["message"]
    request = json.loads((p.base / f"manual-in-{p.sequence}.json").read_bytes())
    journal = p.record(".build/operations/changed/transaction/journal.json")
    assert journal["status"] == "committed"
    result_digest = p.record(journal["result_ref"])["digest"]
    installed = {row["path"]: (p.root / row["path"]).read_bytes() for row in journal["entries"]}
    assert not (p.root / "logs/publications/changed/manifest.json").exists()
    assert not (p.root / "logs/ingest/changed.yaml").exists()
    resumed = p.call("knowledge-apply", request, "batch")
    assert resumed["data"]["batch_complete"] is True and resumed["data"]["activated"] is True
    assert {ref: (p.root / ref).read_bytes() for ref in installed} == installed
    manifest = p.record(resumed["data"]["publication_ref"])
    assert manifest["apply_result"]["digest"] == result_digest
    assert p.record("logs/ingest/changed.yaml")["status"] == "applied"
    events = [p.record(path.relative_to(p.root).as_posix()) for path in (p.root / "logs/events").glob("*.json")
              if path.name != "state.json"]
    assert len(events) == 1 and events[0]["change"]["new_snapshot_id"] == source["snapshot_id"]
    assert p.scan("resumed-steady", action="run")[0]["phase"] == "unchanged"


@pytest.mark.parametrize("mode", ["skip", "defer", "content_with_unwritten_card"])
def test_existing_card_references_survive_record_only_and_mixed_publications(tmp_path, mode):
    p = Lifecycle(tmp_path)
    p.put(PRIMARY, FIRST)
    first, _ = p.scan("first", action="run")
    finish(p, first, PRIMARY, "primary-rule", FIRST)
    primary_path = p.root / "knowledge/rules/primary-rule.md"
    primary_before = primary_path.read_bytes()
    existing_source = metadata(primary_before)["sources"][0]
    active = p.root / "artifacts/indexes/local/active.json"
    active_before = active.read_bytes()
    operation = "linked-" + mode.replace("_", "-")
    if mode == "content_with_unwritten_card":
        p.put(SECONDARY, "A second independent capture marker is documented.")
        prepared, scan = p.scan(operation, action="run")
    else:
        prepared = p.call("knowledge-source", {"operation_id": operation,
                         "candidate_card_ids": ["primary-rule"]}, "run")
        scan = p.record(prepared["data"]["scan_ref"])
    material_ref = prepared["data"]["material_ref"]
    material = p.record(material_ref)
    bundle = p.record(material["bundle_ref"])
    primary = next(row for row in scan["units"] if row["path"] == PREFIX + PRIMARY)
    outcome = "defer" if mode == "defer" else "skip"
    units = [{"unit_id": primary["unit_id"], "outcome": outcome, "kind": "substantive",
              "reason": "Preserve the published Claim; investigate the requested extension" if outcome == "defer"
                        else "Read the unchanged source and existing Claim; no new knowledge increment",
              "owner": "fixture-author", "next_step": "Investigate the extension" if outcome == "defer" else "No content rewrite"}]
    changes = [{"unit_ids": [primary["unit_id"]], "card_id": "primary-rule", "claim_id": "c1",
                "action": "preserve", "before": FIRST, "after": FIRST, "conditions": "Unchanged synthetic source",
                "evidence": [existing_source], "preserved": "Exact current card/Claim remains unchanged",
                "reason": "The existing assertion remains supported; this operation does not rewrite it"}]
    actions = [{"card_id": "primary-rule", "decision": "defer", "author_id": "fixture-author",
                "unit_ids": [primary["unit_id"]], "reason": "No card write is authorized by this disposition"}]
    decisions = [{"candidate_id": "primary-rule", "decision": "defer", "card_inputs": [],
                  "reason": "Retain the existing formal card without a content write"}]
    cases, sampled = [], [primary["unit_id"]] if mode == "defer" else []
    if mode == "content_with_unwritten_card":
        unit = next(row for row in scan["units"] if row["path"] == PREFIX + SECONDARY)
        snapshot = next(row for row in bundle["snapshots"] if row["source_id"] == unit["source_id"])
        candidate = p.write(f".build/candidates/{operation}/secondary-rule.md",
            p.card("secondary-rule", {"snapshots": [snapshot]}, "A second independent capture marker is documented."))
        units.append({"unit_id": unit["unit_id"], "outcome": "content", "reason": "Read the newly added independent source"})
        changes.append({"unit_ids": [unit["unit_id"]], "card_id": "secondary-rule", "claim_id": "c1", "action": "create",
            "before": None, "after": "A second independent capture marker is documented.", "conditions": "Synthetic document",
            "evidence": [snapshot["snapshot_id"]], "preserved": "Primary card remains untouched", "reason": "New independent rule"})
        actions.append({"card_id": "secondary-rule", "decision": "create", "author_id": "fixture-author",
                        "unit_ids": [unit["unit_id"]], "reason": "New independent rule"})
        decisions.append({"candidate_id": "secondary-rule", "decision": "create", "card_inputs": [candidate],
                          "reason": "Write only this newly authored secondary card"})
        cases = [{"id": "secondary", "query": "secondary", "purpose": "current", "required": ["secondary-rule"],
                  "expected_claim_ids": ["secondary-rule#c1"]}]
        sampled = [unit["unit_id"]]
    semantic = p.call("knowledge-change-plan", {"operation_id": operation, "scan_ref": prepared["data"]["scan_ref"],
        "material_ref": material_ref, "author_id": "fixture-author", "units": units, "claim_changes": changes,
        "card_actions": actions, "target_queries": cases}, "plan")["data"]["semantic_plan_ref"]
    view_ref = p.call("knowledge-view-materialize", {"operation_id": operation, "semantic_plan_ref": semantic,
        "material_ref": material_ref, "decisions": decisions}, "run")["data"]["view_ref"]
    view = p.record(view_ref)
    assert not any(row["path"] == "knowledge/rules/primary-rule.md" for row in view["writes"])
    assert view["batch_kind"] == ("content" if mode == "content_with_unwritten_card" else "record_only")
    reviewed = p.call("knowledge-lint", {"operation_id": operation, "semantic_plan_ref": semantic,
        "view_ref": view_ref, "reviewer_id": "fixture-independent-reader", "independent_context": "fresh-fixture-context",
        "sampled_unit_ids": sampled, "unreviewed_unit_ids": [], "findings": [],
        "reason": "Review all applicable authored outcomes; terminal unchanged scan-skips are explicit"}, "review")
    assert reviewed["status"] == "passed"
    record_ref = p.pending_record(operation, view_ref)
    record = p.record(record_ref)
    disposition = next(row for row in record["dispositions"] if row["unit_id"] == primary["unit_id"])
    assert disposition["action"] == outcome and disposition["card_refs"] == ["primary-rule"]
    assert disposition["claim_refs"] == ["primary-rule#c1"]
    assert disposition["progress"] == ("blocked" if mode == "defer" else "skipped")
    result = p.call("knowledge-apply", {"operation_id": operation, "view_ref": view_ref,
                    "ingest_record_ref": record_ref}, "batch")
    assert result["data"]["batch_complete"] is True
    assert primary_path.read_bytes() == primary_before
    if mode != "content_with_unwritten_card":
        assert active.read_bytes() == active_before and result["data"].get("activated") is not True
    formal = p.call("knowledge-lint", {"operation_id": "formal-after-" + mode}, "lint")
    assert formal["status"] == "passed"
    built = p.call("knowledge-apply", {"operation_id": "index-after-" + mode}, "index-build")["data"]
    verified = p.call("knowledge-apply", {"operation_id": "verify-after-" + mode,
                     "generation_ref": built["generation_ref"]}, "index-verify")
    assert verified["data"]["verified"] is True
    search_read(p, "query-after-" + mode, "primary-rule")
    fresh, inventory = p.scan("fresh-after-" + mode, action="run")
    observed = next(row for row in inventory["units"] if row["path"] == PREFIX + PRIMARY)
    assert observed["change"] == ("unfinished" if mode == "defer" else "unchanged")
    assert fresh["phase"] == ("prepared" if mode == "defer" else "unchanged")
