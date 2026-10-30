"""Historical freshness through authored v3 inputs and public node calls."""

import hashlib
import json
import subprocess
import time

import pytest
import yaml


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def historical_batch(harness, definitions=None):
    """Author only candidates/review inputs; apply owns every formal asset."""
    def hashed(raw):
        return hashlib.sha256(raw).hexdigest()

    definitions = definitions or [("historical-card", "historical", None)]
    code = harness.base / "main/shared"
    code.mkdir(parents=True)
    original = b"int historical_example(void) { return 1; }\n"
    source = code / "file.c"
    source.write_bytes(original)
    config = {"schema_version": "2.0", "workspace_id": "historical-context",
              "knowledge_roots": {"wifi": harness.root.name}, "code_root": "main",
              "modules": [{"path": "shared", "chips": ["chip12"], "sides": ["host"]}]}
    config_path = harness.base / "config.yml"
    config_path.write_bytes(canonical(config))
    repo_id = "repo-" + hashed(b"main/shared")[:16]
    raw = b"# Source study\nKeep the captured example as bounded source knowledge.\n"
    harness.write("docs-raw/specs/history.md", raw)
    scan_ref = harness.run("source", {"operation_id": "seed"}, "scan")["data"]["scan_ref"]
    unit = harness.record(scan_ref)["units"][0]
    unit_id = unit["unit_id"]
    code_bundle_ref = harness.run("source", {"operation_id": "seed-code", "kind": "code",
        "repo_id": repo_id, "relative_path": "file.c", "source_id": "historical-code"}, action="capture")["data"]["bundle_ref"]
    code_bundle = harness.record(code_bundle_ref)
    code_snapshot = code_bundle["snapshots"][0]
    material_ref = harness.run("source", {"operation_id": "seed", "scan_ref": scan_ref,
        "code_bundle_refs": [{"bundle_ref": code_bundle_ref, "bundle_digest": code_bundle["digest"]}]},
        "prepare")["data"]["material_ref"]
    material = harness.record(material_ref)
    bundle = harness.record(material["bundle_ref"])
    raw_snapshot = next(s for s in bundle["snapshots"] if s["source_id"] == unit["source_id"])
    target = {"target_id": "chip12-host", "chip": "chip12", "side": "host",
              "build_profile": None, "features": [], "protocol_versions": [], "revision": None}
    cases = [{"id": identity, "query": "Synthetic", "purpose": "implementation" if usage == "current" else usage,
              "required": [identity], "context": target} for identity, usage, _ in definitions]
    semantic_ref = harness.run("change-plan", {
        "operation_id": "seed", "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "author",
        "units": [{"unit_id": unit_id, "outcome": "content", "reason": "Read the bounded source study"}],
        "claim_changes": [{"unit_ids": [unit_id], "card_id": identity, "claim_id": identity + "-claim",
            "action": "create", "before": None, "after": "Synthetic source example returns one",
            "conditions": "Explicitly scoped synthetic source study", "evidence": [raw_snapshot["snapshot_id"]],
            "preserved": "No previous card", "reason": "Source study supports this limited statement"}
            for identity, _, _ in definitions],
        "card_actions": [{"card_id": identity, "decision": "create", "author_id": "author",
            "unit_ids": [unit_id], "reason": "One bounded topic"} for identity, _, _ in definitions],
        "target_queries": cases}, "plan")["data"]["semantic_plan_ref"]
    context = {"schema_version": "2.0", "record_kind": "project_context", "operation_id": "seed",
        "rules_digest": harness.rules, "tool_identity": code_bundle["tool_identity"], "state": "context_loaded",
        "workspace_id": "historical-context", "workspace_root": str(harness.base), "knowledge_root": str(harness.root),
        "config_path": str(config_path), "config_digest": hashed(config_path.read_bytes()), "entries": [],
        "target": target if any(usage == "current" for _, usage, _ in definitions) else None, "build_evidence": None,
        "repos": {repo_id: {"repo_id": repo_id, "root": str(code), "kind": "export", "evidence_basis": "filesystem",
            "workspace_path": "main/shared", "head": None, "identity": None, "dirty": None,
            "files": {"file.c": hashed(original)}}}}
    context["digest"] = hashed(canonical(context))
    context_ref = harness.write(".build/operations/seed/source-context.json", canonical(context))
    decisions, claim_reviews = [], []
    for identity, usage, relation in definitions:
        _, header, body = harness.card(identity, {"snapshots": [raw_snapshot]}).decode().split("---", 2)
        meta = yaml.safe_load(header)
        if relation:
            meta["relations"] = [{"type": relation, "target_card_id": "historical-card",
                                  "target_claim_id": "historical-card-claim", "context_ids": []}]
        else:
            meta["review_mode"] = "code_gate"
            meta["sources"].append({"evidence_ref": "code", "source_id": code_snapshot["source_id"],
                "snapshot_id": code_snapshot["snapshot_id"], "locator": {"kind": "lines", "start": 1, "end": 1},
                "code_ref": {"kind": "function", "name": "historical_example", "scope": [],
                             "parameter_types": [], "role": "definition"}})
            meta["claims"][0].update(usage=usage, evidence_kind="implementation", source_refs=["e1", "code"],
                                    verification_requirements=["semantic-support"])
            if usage == "current":
                meta["scope"] = {"applicability": "constrained", "contexts": [{"context_id": "host",
                    "target_id": "chip12-host", "chip": "chip12", "side": "host", "build_profile": None,
                    "features_all": [], "features_none": [], "protocol_versions": [],
                    "revision_policy": "revalidate", "revision": None}]}
                meta["claims"][0]["context_ids"] = ["host"]
            claim_reviews.append({"card_id": identity, "claim_id": identity + "-claim", "status": "supported",
                "reason": "Read exact retained source and code; statement is limited to the declared use",
                "evidence": [{"source_id": ref["source_id"], "snapshot_id": ref["snapshot_id"],
                    "locator": ref["locator"], "sha256": next(s["sha256"] for s in bundle["snapshots"]
                        if s["snapshot_id"] == ref["snapshot_id"])} for ref in meta["sources"]]})
        candidate = harness.write(".build/candidates/" + identity + ".md",
                                  ("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---" + body).encode())
        decisions.append({"candidate_id": identity, "decision": "create", "reason": "Planned source study",
                          "card_inputs": [candidate]})
    produced = harness.run("view-materialize", {"operation_id": "seed", "v3_required": True,
        "semantic_plan_ref": semantic_ref, "bundle_ref": material["bundle_ref"], "context_ref": context_ref,
        "decisions": decisions})["data"]
    view_ref = produced["view_ref"]
    view = harness.record(view_ref)
    inputs = {"code_checkout": {"configuration": str(config_path), "config_digest": context["config_digest"],
                               "repos": {repo_id: {"root": str(code)}}}}

    report_ref = harness.write(".build/operations/seed/code-review.json", canonical({"schema_version": "2.0",
        "record_kind": "semantic_review", "payload": {"findings": [], "view_digest": view["digest"],
            "context_digest": context["digest"], "mode": "local", "issued_at": time.time(), "claims": claim_reviews}}))
    incoming = harness.write(".build/operations/seed/p5-review-input.json", canonical({
        "operation_id": "seed", "semantic_plan_ref": semantic_ref, "view_ref": view_ref,
        "reviewer_id": "synthetic-reviewer", "sampled_unit_ids": [unit_id], "unreviewed_unit_ids": [],
        "reason": "Synthetic reviewer declaration after reading exact old/current sources; no real host isolation claim",
        "findings": [], "inputs": inputs,
        "code_review": {"context_ref": context_ref, "semantic_report_ref": report_ref}}))
    lint_ref = ".build/operations/seed/p5-review.json"
    completed = subprocess.run([*harness.command("lint"),
        "--knowledge-root", str(harness.root), "--input", str(harness.root / incoming),
        "--output", str(harness.root / lint_ref), "--action", "review"], capture_output=True, check=False)
    assert completed.returncode == 0, (completed.stderr, harness.record(lint_ref))
    lint = harness.record(lint_ref)
    assert lint["status"] == "passed" and lint["scope"]["kind"] == "full"
    record_ref = harness.run("source", {"operation_id": "seed", "scan_ref": scan_ref,
        "semantic_plan_ref": semantic_ref, "view_ref": view_ref, "lint_ref": lint_ref,
        "disposition_preview_ref": produced["disposition_preview_ref"]}, "record")["data"]["ingest_record_ref"]
    applied = harness.run("apply", {"operation_id": "seed", "view_ref": view_ref, "ingest_record_ref": record_ref,
        "content_review_ref": lint["data"]["content_review_ref"], "lint_report_ref": lint_ref,
        "check_inputs": inputs}, "batch")
    assert applied["phase"] == "completed" and applied["data"]["activated"]
    return source, original, code_snapshot, raw


def test_completed_historical_code_drift_does_not_reopen_unchanged_raw(harness):
    source, original, old_snapshot, raw = historical_batch(harness, [
        ("historical-card", "historical", None), ("requires-card", "guidance", "requires"),
        ("derived-card", "guidance", "derived_from"), ("related-card", "guidance", "related_to")])
    before = harness.run("source", {"operation_id": "before-change"}, "scan")["data"]
    assert before["affected_claims"] == before["actionable_unit_ids"] == before["finalization_pending"] == []
    source.write_bytes(original.replace(b"1", b"2"))
    for attempt in range(2):
        result = harness.run("source", {"operation_id": "after-change-" + str(attempt)}, "scan")["data"]
        assert result["affected_claims"] == []
        assert result["actionable_unit_ids"] == result["finalization_pending"] == []
        assert harness.record(result["scan_ref"])["units"][0]["change"] == "unchanged"
    captured = harness.run("source", {"operation_id": "changed-code", "kind": "code",
        "repo_id": old_snapshot["code_identity"]["repo_id"], "relative_path": "file.c",
        "source_id": "historical-code"}, action="capture")["data"]["bundle_ref"]
    registered = harness.run("maintain", {"operation_id": "changed-code", "bundle_ref": captured},
                             "register-code-change")
    assert registered["data"]["blocked_claims"][0]["reason"] == "code_changed"
    state_path = harness.root / "logs/events/state.json"
    state_bytes = state_path.read_bytes()
    inspected = harness.run("maintain", {"operation_id": "inspect-registered"}, "inspect-context")["data"]
    assert inspected["affected_claims"] == []
    after_registration = harness.run("source", {"operation_id": "after-registration"}, "scan")["data"]
    assert after_registration["affected_claims"] == after_registration["actionable_unit_ids"] == []
    assert state_path.read_bytes() == state_bytes

    # Losing the retained original is a real historical/dependency gap. The
    # different current code may never substitute for those missing old bytes.
    old_object = harness.root / old_snapshot["recovery"]["path"]
    old_object.unlink()
    missing = harness.run("maintain", {"operation_id": "missing-history"}, "inspect-context")["data"]
    assert {row["card_id"] for row in missing["affected_claims"]} == {
        "historical-card", "requires-card", "derived-card"}
    assert any(row["card_id"] == "historical-card" and row["reason"] == "source_unavailable"
               for row in missing["affected_claims"])
    old_object.write_bytes(original)

    # Explicit semantic/applicability restrictions remain separate from byte
    # freshness. Seed only that isolated durable restriction, never card/index
    # bytes or a passed-step ticket; inspection must not modify the state.
    original_state = json.loads(state_bytes)
    for reason in ("semantic_mismatch", "applicability_unverified"):
        state = {**original_state, "blocked_claims": original_state["blocked_claims"] + [
            {"card_id": "historical-card", "claim_id": "historical-card-claim", "reason": reason}]}
        state.pop("digest")
        state["digest"] = hashlib.sha256(canonical(state)).hexdigest()
        state_path.write_bytes(canonical(state))
        restricted = harness.run("maintain", {"operation_id": reason}, "inspect-context")["data"]
        assert {row["card_id"] for row in restricted["affected_claims"]} == {
            "historical-card", "requires-card", "derived-card"}
        assert any(row["card_id"] == "historical-card" and row["reason"] == reason
                   for row in restricted["affected_claims"])
        assert state_path.read_bytes() == canonical(state)
    state_path.write_bytes(state_bytes)

    # A real raw upgrade remains a changed source inventory even when its old
    # historical interpretation and exact original remain available.
    changed_raw = raw + b"A later source version adds a separate observation.\n"
    harness.write("docs-raw/specs/history.md", changed_raw)
    captured = harness.run("source", {"operation_id": "raw-upgrade", "source_path": "docs-raw/specs/history.md",
        "source_id": harness.record(before["scan_ref"])["units"][0]["source_id"]}, action="capture")["data"]
    assert captured["event_refs"] == []
    assert len(captured["event_proposals"]) == 1
    assert state_path.read_bytes() == state_bytes  # P1 cannot publish a formal restriction.
    raw_changed = harness.run("source", {"operation_id": "raw-upgrade-scan"}, "scan")["data"]
    assert harness.record(raw_changed["scan_ref"])["units"][0]["change"] == "changed"
    assert raw_changed["actionable_unit_ids"]
    assert state_path.read_bytes() == state_bytes
    # The independent explicit maintain action retains its publishing contract.
    registered = harness.run("maintain", {"operation_id": "register-raw-upgrade",
        "bundle_ref": captured["bundle_ref"]}, "register-source-change")
    assert registered["data"]["event_refs"]
    assert any(block["reason"] == "source_changed" for block in harness.record("logs/events/state.json")["blocked_claims"])
    assert (harness.root / "docs-raw/specs/history.md").read_bytes() == changed_raw


@pytest.mark.parametrize("historical_first", [True, False], ids=["historical-first", "current-first"])
@pytest.mark.parametrize("change", ["body", "symbol"])
def test_same_source_freshness_distinguishes_current_and_guidance_navigation(harness, historical_first, change):
    definitions = ([("a-history", "historical", None), ("b-current", "current", None), ("c-guidance", "guidance", None)]
                   if historical_first else
                   [("a-current", "current", None), ("b-guidance", "guidance", None), ("z-history", "historical", None)])
    source, original, old_snapshot, raw = historical_batch(harness, definitions)
    source.write_bytes(original.replace(b"1", b"2") if change == "body"
                       else original.replace(b"historical_example", b"renamed_example"))
    expected = {identity for identity, usage, _ in definitions
                if usage == "current" or (usage == "guidance" and change == "symbol")}
    observed = harness.run("maintain", {"operation_id": "mixed-live-drift"}, "inspect-context")["data"]
    assert {row["card_id"] for row in observed["affected_claims"]} == expected
    guidance = next(row for row in observed["code_navigation"]
                    if row["card_id"] == next(identity for identity, usage, _ in definitions if usage == "guidance"))
    assert guidance["code_navigation"]["status"] == ("resolved" if change == "body" else "missing")
    assert guidance["current_source_matches"] is False
    new_bundle = harness.run("source", {"operation_id": "mixed-new-code", "kind": "code",
        "repo_id": old_snapshot["code_identity"]["repo_id"], "relative_path": "file.c",
        "source_id": "historical-code"}, action="capture")["data"]["bundle_ref"]
    harness.run("maintain", {"operation_id": "mixed-new-code", "bundle_ref": new_bundle}, "register-code-change")
    state_before = (harness.root / "logs/events/state.json").read_bytes()
    registered = harness.run("maintain", {"operation_id": "mixed-registered-drift"}, "inspect-context")["data"]
    assert {row["card_id"] for row in registered["affected_claims"]} == expected
    assert {row["card_id"] for row in registered["affected_claims"] if row["reason"] == "code_changed"} == expected
    assert (harness.root / "logs/events/state.json").read_bytes() == state_before
    assert (harness.root / "docs-raw/specs/history.md").read_bytes() == raw
