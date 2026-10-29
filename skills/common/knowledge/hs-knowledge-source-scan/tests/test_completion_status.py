"""Public CLI recovery facts; synthetic sources never imply semantic acceptance."""

import pytest

import importlib.util
from pathlib import Path


_flow_spec = importlib.util.spec_from_file_location(
    "source_scan_completion_flow_fixture", Path(__file__).with_name("test_supported_workflow.py"),
)
_flow_fixture = importlib.util.module_from_spec(_flow_spec)
_flow_spec.loader.exec_module(_flow_fixture)
planned_flow = _flow_fixture.planned_flow


def applied_batch(harness, *, fault_after=None, with_record=True):
    operation = "batch"
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic evidence.\n")
    scanned = harness.run("source-scan", {"operation_id": operation}, "scan")["data"]
    scan = harness.record(scanned["scan_ref"])
    unit = scan["units"][0]
    bundle_ref = harness.run("source-prepare", {"operation_id": operation,
        "source_path": unit["path"], "source_id": unit["source_id"]}, action="capture")["data"]["bundle_ref"]
    candidate = harness.write(".build/candidates/new.md", harness.card("new", harness.record(bundle_ref)))
    produced = harness.run("view-materialize", {"operation_id": operation, "bundle_ref": bundle_ref,
        "decisions": [{"candidate_id": "new", "decision": "create", "reason": "Synthetic recovery fixture",
                       "card_inputs": [candidate]}]})["data"]
    view = produced["view_ref"]
    record = harness.run("source-scan", {
        "operation_id": operation, "scan_ref": scanned["scan_ref"], "view_ref": view,
        "dispositions": [{"unit_id": unit["unit_id"], "action": "create", "reason": "Synthetic recovery fixture",
                          "observed_fingerprint": unit["observed_fingerprint"],
                          "adopted_fingerprint": unit["observed_fingerprint"], "progress": "completed",
                          "card_refs": ["new"], "claim_refs": ["new#new-claim"]}],
    }, "record")["data"]["ingest_record_ref"] if with_record else None
    harness.run("apply", {"operation_id": operation, "view_ref": view,
                          **({"ingest_record_ref": record} if with_record else {}),
                          **({"fault_after": fault_after} if fault_after is not None else {})},
                expected=3 if fault_after is not None else 0)
    return view


def operation_status(harness, *, global_history=False):
    request = {"operation_id": "status"}
    if not global_history:
        request["target_operation_id"] = "batch"
    return next(row for row in harness.run("source-scan", request, "status")["data"]["operations"]
                if row["operation_id"] == "batch")


def test_ordinary_scan_does_not_discover_legacy_index_tail(harness):
    applied_batch(harness)
    response = harness.run("source-scan", {"operation_id": "reopened"}, "scan")["data"]
    assert response["actionable_unit_ids"] == []
    assert response["finalization_pending"] == []
    assert response["execution_history"] == {"status": "not_inspected"}
    status = operation_status(harness)
    assert {row["stage"] for row in status["facts"]} >= {"plan", "view", "apply"}
    assert status["stage_status"]["content_review"] == "unknown"
    assert status["completion"]["status"] == "unknown"
    assert status["completion"]["next_action"] == "inspect_finalization"
    assert operation_status(harness, global_history=True)["completion"]["next_action"] == "rebuild_index"


def test_ordinary_scan_never_reads_independent_apply_tail(harness):
    applied_batch(harness, with_record=False)
    assert not (harness.root / "logs/ingest/batch.yaml").exists()
    response = harness.run("source-scan", {"operation_id": "reopened"}, "scan")["data"]
    assert response["finalization_pending"] == []
    assert response["execution_history"] == {"status": "not_inspected"}
    harness.write("docs-raw/troubleshooting/other.md", b"Unrelated source\n")
    narrow = harness.run("source-scan", {"operation_id": "narrow", "source": "docs-raw/troubleshooting"}, "scan")["data"]
    assert narrow["finalization_pending"] == []
    # Later external/current content must not trigger activation of the old view.
    card = harness.root / "knowledge/rules/new.md"
    card.write_bytes(card.read_bytes().replace(b"Synthetic fixture statement.", b"A later current statement."))
    historical = harness.run("source-scan", {"operation_id": "after-new-content"}, "scan")["data"]
    assert historical["finalization_pending"] == []
    assert historical["historical_finalization_unknown"] == []


def test_cross_operation_regression_activation_and_repeated_noop_stay_complete(harness):
    view = applied_batch(harness)
    built = harness.run("apply", {"operation_id": "index-other"}, action='index-build')["data"]
    own_index = next(row for row in harness.run("source-scan", {"operation_id": "status"}, "status")["data"]["operations"] if row["operation_id"] == "index-other")
    assert "index" in {row["stage"] for row in own_index["facts"]}
    assert own_index["completion"]["status"] == "unknown"
    assert own_index["completion"]["next_action"] == "inspect_finalization"
    assert operation_status(harness)["completion"]["status"] == "unknown"
    before_query = operation_status(harness, global_history=True)
    assert before_query["completion"]["next_action"] == "resume_queries"
    checked = harness.run("apply", {
        "operation_id": "query-other", "view_ref": view, "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "find-new", "query": "Synthetic", "purpose": "guidance", "required": ["new"]}],
    }, action='regression')["data"]
    assert checked["activated"]
    own_query = next(row for row in harness.run("source-scan", {"operation_id": "status"}, "status")["data"]["operations"] if row["operation_id"] == "query-other")
    assert {row["stage"] for row in own_query["facts"]} >= {"regression", "activation"}
    assert own_query["completion"]["status"] == "unknown"
    after_query = operation_status(harness, global_history=True)
    assert after_query["completion"]["status"] == "complete"
    assert after_query["completion"]["index_health"] == "not_examined"
    assert {row["stage"] for row in after_query["facts"]} >= {"index", "regression", "activation"}
    records_before = sorted((harness.root / "logs/ingest").glob("*"))
    for attempt in range(3):
        scanned = harness.run("source-scan", {"operation_id": "noop-" + str(attempt)}, "scan")["data"]
        assert scanned["actionable_unit_ids"] == []
        assert scanned["finalization_pending"] == []
    assert sorted((harness.root / "logs/ingest").glob("*")) == records_before
    # A later active generation must not erase the earlier observed activation.
    later = harness.run("apply", {"operation_id": "later-generation"}, action='index-build')["data"]
    harness.run("apply", {"operation_id": "later-activation", "generation_ref": later["generation_ref"],
                                "expected_active": later["expected_active"]}, 'index-activate')
    assert operation_status(harness, global_history=True)["completion"]["status"] == "complete"


@pytest.mark.parametrize("orphan_history", [False, True], ids=["no-control-plane", "unrooted-history"])
def test_self_sealed_activation_observation_without_real_active_chain_is_not_complete(harness, orphan_history):
    import hashlib
    import json

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    view_ref = applied_batch(harness)
    view = harness.record(view_ref)
    built = harness.run("apply", {"operation_id": "real-build"}, "index-build")["data"]
    manifest = harness.record(built["generation_ref"])

    def sealed(kind, operation, payload):
        value = {"schema_version": "2.0", "record_kind": kind, "operation_id": operation,
                 "rules_digest": harness.rules, "tool_identity": manifest["tool_identity"], **payload}
        value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
        return value

    cases = [{"id": "find-new", "query": "Synthetic", "purpose": "guidance", "required": ["new"]}]
    # Declare assertions, then use public regression-verify to execute actual
    # queries/read-back without activation. This is not a synthetic passed report.
    declared = sealed("query_regression", "declared-cases", {
        "generation_ref": built["generation_ref"], "expected_active": built["expected_active"],
        "view_ref": view_ref, "view_digest": view["digest"], "cases": cases,
        "cases_digest": hashlib.sha256(canonical(cases)).hexdigest(), "outcomes": [],
        "passed": False, "index_verified": False})
    report_ref = harness.write(".build/operations/declared-cases/report.json", canonical(declared))
    verified = harness.run("apply", {"operation_id": "actual-queries", "report_ref": report_ref}, "regression-verify")["data"]
    assert verified["passed"] is True and verified["activated"] is False
    assert harness.record(verified["report_ref"])["index_verified"] is True
    control_plane = harness.root / "artifacts/indexes/local"
    assert not (control_plane / "active.json").exists()
    assert not any(control_plane.glob("activations/*.json"))
    assert operation_status(harness, global_history=True)["completion"]["status"] == "pending"

    pointer = sealed("index_manifest", "forged-pointer", {
        "channel": "local", "generation_id": manifest["generation_id"],
        "generation_ref": built["generation_ref"], "manifest_digest": manifest["digest"],
        "previous_active_digest": built["expected_active"]})
    observation = sealed("artifact_manifest", "forged-observation", {
        "purpose": "index_activation_observation", "generation_ref": built["generation_ref"],
        "manifest_digest": manifest["digest"], "expected_active": built["expected_active"],
        "active_digest": pointer["digest"], "active_pointer": pointer})
    harness.write(".build/operations/forged-observation/activation/" + observation["digest"] + ".json", canonical(observation))
    if orphan_history:
        # A prepared history object that is not reachable from active.json
        # supplies no activation fact, even though every local digest is valid.
        harness.write("artifacts/indexes/local/activations/" + pointer["digest"] + ".json", canonical(pointer))
    # Explicitly inspect the legacy cross-operation query/activation chain;
    # a targeted status intentionally does not discover independent old work.
    completion = operation_status(harness, global_history=True)["completion"]
    assert completion["status"] in {"pending", "unknown"}
    scanned = harness.run("source-scan", {"operation_id": "after-forged-observation"}, "scan")["data"]
    assert scanned["actionable_unit_ids"] == []
    assert scanned["finalization_pending"] == []
    assert scanned["execution_history"] == {"status": "not_inspected"}
    assert not (control_plane / "active.json").exists()


@pytest.mark.parametrize("completion_kind", ["legacy", "batch"])
def test_real_independent_activation_without_regression_binding_rejects_forged_completion(planned_flow, completion_kind):
    import hashlib
    import json

    harness = planned_flow.h

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    if completion_kind == "batch":
        # Stop before indexing/query execution with a real IO blocker. The
        # independently built/activated generation below has no P7 regression.
        planned_flow.produce("applied")
        operation, view_ref = planned_flow.operation, planned_flow.state["view_ref"]
    else:
        operation, view_ref = "batch", applied_batch(harness)
    view = harness.record(view_ref)
    journal = harness.record(f".build/operations/{operation}/transaction/journal.json")
    applied = harness.record(journal["result_ref"])
    built = harness.run("apply", {"operation_id": "independent-index"}, "index-build")["data"]
    activated = harness.run("apply", {"operation_id": "independent-activation",
        "generation_ref": built["generation_ref"], "expected_active": built["expected_active"]}, "index-activate")["data"]
    manifest = harness.record(built["generation_ref"])
    pointer = harness.record("artifacts/indexes/local/active.json")
    assert activated["activated"] is True
    assert "execution_binding" not in pointer
    assert not list((harness.root / ".build/operations").glob("*/regression/*.json"))

    def sealed(kind, payload):
        value = {"schema_version": "2.0", "record_kind": kind, "operation_id": operation,
                 "rules_digest": harness.rules, "tool_identity": manifest["tool_identity"], **payload}
        value["digest"] = hashlib.sha256(canonical(value)).hexdigest()
        return value

    # These intentionally forged JSON claims are structurally valid and bind
    # the exact view/cases/apply bytes. They cannot give an independent real
    # activation a regression execution it never observed.
    cases = view.get("target_queries") or [
        {"id": "find-new", "query": "Synthetic", "purpose": "guidance", "required": ["new"]}]
    report = sealed("query_regression", {
        "generation_ref": built["generation_ref"], "expected_active": built["expected_active"],
        "view_ref": view_ref, "view_digest": view["digest"],
        "apply_result_ref": journal["result_ref"], "apply_result_digest": applied["digest"],
        "cases": cases, "cases_digest": hashlib.sha256(canonical(cases)).hexdigest(),
        "outcomes": [{"case_id": case["id"], "passed": True, "actual": case["required"],
                      "same_generation_reads": []} for case in cases],
        "passed": True, "index_verified": True})
    report_ref = harness.write(f".build/operations/{operation}/regression/" + report["digest"] + ".json", canonical(report))
    observation = sealed("artifact_manifest", {
        "purpose": "index_activation_observation", "generation_ref": built["generation_ref"],
        "manifest_digest": manifest["digest"], "expected_active": built["expected_active"],
        "active_digest": pointer["digest"], "active_pointer": pointer})
    observation_ref = harness.write(f".build/operations/{operation}/activation/" + observation["digest"] + ".json", canonical(observation))
    if completion_kind == "batch":
        stage = sealed("artifact_manifest", {"purpose": "batch_index", "view_digest": view["digest"],
            "apply_result_ref": journal["result_ref"], "apply_result_digest": applied["digest"],
            "generation_ref": built["generation_ref"], "expected_active": built["expected_active"]})
        harness.write(f".build/operations/{operation}/batch-build.json", canonical(stage))
        complete = sealed("artifact_manifest", {"purpose": "batch_completion", "view_digest": view["digest"],
            "phase": "completed", "data": {"batch_complete": True, "transaction_status": "committed",
                "apply_result_ref": journal["result_ref"], "apply_result_digest": applied["digest"],
                "generation_ref": built["generation_ref"], "expected_active": built["expected_active"],
                "activated": True, "report_ref": report_ref, "activation_observation_ref": observation_ref}})
        harness.write(f".build/operations/{operation}/batch-complete.json", canonical(complete))
    statuses = harness.run("source-scan", {"operation_id": "forgery-status"}, "status")["data"]["operations"]
    status = next(row for row in statuses if row["operation_id"] == operation)
    assert status["completion"]["status"] in {"pending", "unknown"}
    if completion_kind == "batch":
        formal = harness.run("source-scan", {"operation_id": "formal-forgery-status",
            "target_operation_id": operation}, "status")["data"]["operations"][0]
        assert formal["completion"]["published"] is True
        assert formal["completion"]["batch_complete"] is False
    scanned = harness.run("source-scan", {"operation_id": "after-forged-regression"}, "scan")["data"]
    assert scanned["actionable_unit_ids"] == []
    assert scanned["finalization_pending"] == []
    assert scanned["execution_history"] == {"status": "not_inspected"}
    assert harness.record("artifacts/indexes/local/active.json") == pointer


def test_unbound_or_irrelevant_regression_is_not_batch_completion(harness):
    view = applied_batch(harness)
    built = harness.run("apply", {"operation_id": "unrelated-index"}, action='index-build')["data"]
    checked = harness.run("apply", {
        "operation_id": "irrelevant-query", "view_ref": view, "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"],
        "cases": [{"id": "irrelevant", "query": "No such card", "forbidden": ["nonexistent-card"]}],
    }, action='regression')["data"]
    assert checked["activated"]
    status = operation_status(harness)
    assert status["completion"]["status"] != "complete"
    assert status["completion"]["next_action"] == "inspect_finalization"
    assert status["stage_status"]["regression"] == "unknown"


@pytest.mark.parametrize("source", ["docs-raw/specs/typo.md", "docs-raw/troubleshooting/not-there"])
def test_missing_explicit_scope_without_history_is_an_error(harness, source):
    result = harness.run("source-scan", {"operation_id": "typo", "source": source}, "scan", expected=2)
    assert result["diagnostics"][0]["code"] == "RAW_SCOPE_NOT_FOUND"
    assert not (harness.root / ".build/operations/typo/source-inventory.json").exists()


def test_default_empty_raw_scope_is_valid_and_status_is_readonly(harness):
    result = harness.run("source-scan", {"operation_id": "empty"}, "scan")["data"]
    assert result["complete"] and result["actionable_unit_ids"] == []
    before = {p.relative_to(harness.root).as_posix(): p.read_bytes() for p in harness.root.rglob("*") if p.is_file()}
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "empty"}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "not_applicable"
    assert {p.relative_to(harness.root).as_posix(): p.read_bytes() for p in harness.root.rglob("*") if p.is_file()} == before


def test_portable_formal_only_history_is_visible_without_private_tail_requirement(harness):
    # Explicit legacy apply-run compatibility: a formal ingest record alone
    # does not assert the new P7 publication/retrieval/cleanup completion.
    applied_batch(harness)
    # Model a consuming clone that retains shared records and current knowledge.
    import shutil
    shutil.rmtree(harness.root / ".build")
    if (harness.root / "logs/operations").exists():
        shutil.rmtree(harness.root / "logs/operations")
    scanned = harness.run("source-scan", {"operation_id": "consumer"}, "scan")["data"]
    assert scanned["actionable_unit_ids"] == [] and scanned["finalization_pending"] == []
    statuses = harness.run("source-scan", {"operation_id": "status"}, "status")["data"]["operations"]
    imported = next(row for row in statuses if row["operation_id"] == "batch")
    assert "record_formal" in {row["stage"] for row in imported["facts"]}
    assert imported["completion"]["status"] == "unknown"
    assert imported["completion"]["next_action"] == "check_local_index"


def test_published_history_needs_no_producer_stage_or_local_index(planned_flow):
    import shutil

    flow = planned_flow
    flow.produce()
    harness = flow.h
    protected = flow.protected_bytes()
    root = harness.root.resolve(strict=True)
    for name in (".build", "artifacts"):
        target = harness.root / name
        if target.exists():
            assert target.resolve(strict=True).parent == root
            shutil.rmtree(target)
    status = harness.run("source-scan", {"operation_id": "portable-status",
        "target_operation_id": flow.operation}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert status["completion"]["batch_complete"] is True
    assert status["completion"]["index_health"] == "not_examined"
    assert {row["stage"] for row in status["facts"]} == {"publication", "publication_completion"}
    scanned = harness.run("source-scan", {"operation_id": "portable-fresh"}, "scan")["data"]
    assert scanned["actionable_unit_ids"] == scanned["finalization_pending"] == []
    assert scanned["execution_history"] == {"status": "not_inspected"}
    assert flow.protected_bytes() == protected


def test_missing_explicit_scope_preserves_registered_deletion(harness):
    source = "docs-raw/specs/tracked.md"
    harness.write(source, b"Tracked source\n")
    scanned = harness.run("source-scan", {"operation_id": "tracked"}, "scan")["data"]
    unit = harness.record(scanned["scan_ref"])["units"][0]
    proposed = harness.run("source-scan", {"operation_id": "tracked", "scan_ref": scanned["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "defer", "reason": "Needs authoritative context",
                          "observed_fingerprint": unit["observed_fingerprint"], "adopted_fingerprint": None,
                          "progress": "blocked", "card_refs": [], "claim_refs": []}]}, "record")["data"]
    harness.run("apply", {"operation_id": "tracked", "ingest_record_ref": proposed["ingest_record_ref"]})
    (harness.root / source).unlink()
    repeated = harness.run("source-scan", {"operation_id": "deleted", "source": source}, "scan")["data"]
    assert harness.record(repeated["scan_ref"])["units"][0]["change"] == "missing"


def test_rolled_back_transaction_is_terminal_and_never_resumed(harness):
    import json

    harness.write(".isolated-knowledge-fixture", b"HIMATE_SYNTHETIC_FIXTURE_V2")
    catalog = json.loads(harness.catalog.read_bytes())
    catalog["test_fixture_root"] = str(harness.root)
    harness.catalog.write_text(json.dumps(catalog), encoding="utf-8")
    applied_batch(harness, fault_after=1)
    assert operation_status(harness)["completion"]["next_action"] == "recover_transaction"
    harness.run("apply", {"operation_id": "batch"}, "rollback")
    status = operation_status(harness)
    assert status["completion"]["scope"] == "rolled_back"
    assert status["completion"]["status"] == "not_applicable"
    assert status["completion"]["next_action"] == "prepare_material"
    assert next(row for row in status["facts"] if row["stage"] == "transaction")["status"] == "rolled_back"


def test_empty_raw_inventory_with_maintenance_debt_is_not_a_noop(harness):
    import hashlib
    import json

    scanned = harness.run("source-scan", {"operation_id": "maintenance-only"}, "scan")["data"]
    inventory = harness.record(scanned["scan_ref"])
    inventory["current_context"]["affected_claims"] = [{"card_id": "code-card", "claim_id": "c1", "reason": "rules_changed"}]
    inventory.pop("digest")
    inventory["digest"] = hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(scanned["scan_ref"], json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode())
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": "maintenance-only"}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] != "not_applicable"


def test_cleaned_batch_status_uses_formal_completion_and_frozen_queries_cannot_be_replaced(planned_flow):
    import hashlib
    import json
    flow = planned_flow
    flow.produce()
    harness, operation = flow.h, flow.operation
    status = harness.run("source-scan", {"operation_id": "status", "target_operation_id": operation}, "status")["data"]["operations"][0]
    assert status["completion"]["status"] == "complete"
    assert {row["stage"] for row in status["facts"]} == {"publication", "publication_completion"}
    assert not (harness.root / flow.state["view_ref"]).exists()
    completion_ref = status["completion"]["completion_ref"]
    completion = harness.record(completion_ref)
    original_ref = completion["data"]["report_ref"]
    # A real successful alternate query still cannot replace frozen batch cases.
    original = harness.record(original_ref)
    cases = [{"id": "other-query", "query": "fixture", "purpose": "guidance", "required": ["rule"]}]
    alternate = harness.run("apply", {"operation_id": "alternate-query", "report_ref": original_ref,
        "cases": cases}, "regression-verify", expected=2)
    assert alternate["diagnostics"][0]["code"] == "REGRESSION_INPUT_CHANGED"
    assert completion["retrieval"]["regression"]["cases"] == original["cases"]
    # A broken selected formal binding remains a gap, even with other passing
    # independent results or old private summaries on this machine.
    completion["publication_digest"] = "0" * 64
    completion.pop("digest")
    completion["digest"] = hashlib.sha256(json.dumps(completion, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(completion_ref, json.dumps(completion).encode())
    rejected = harness.run("source-scan", {"operation_id": "status", "target_operation_id": operation}, "status")["data"]["operations"][0]
    assert rejected["completion"]["status"] != "complete"
    assert rejected["completion"]["next_action"] == "inspect_finalization"


@pytest.mark.parametrize("raw", [b"[]", b"null", b"{broken", b'{"record_kind":"ingest_record"}'])
def test_status_reports_bad_formal_history_without_hiding_other_operations(harness, raw):
    harness.write("docs-raw/specs/source.md", b"Known pending input\n")
    harness.run("source-scan", {"operation_id": "known"}, "scan")
    harness.write("logs/ingest/broken.yaml", raw)
    response = harness.run("source-scan", {"operation_id": "status"}, "status")["data"]
    known = next(row for row in response["operations"] if row["operation_id"] == "known")
    assert known["facts"][0]["stage"] == "scan"
    assert known["completion"]["status"] != "complete"
    assert response["complete"] is False
    assert response["catalog_gaps"][0]["ref"] == "logs/ingest/broken.yaml"


def test_missing_original_cas_baseline_is_unknown_and_never_reconstructed(harness):
    import hashlib
    import json

    applied_batch(harness)
    built = harness.run("apply", {"operation_id": "legacy-index"}, action='index-build')["data"]
    manifest = harness.record(built["generation_ref"])
    manifest.pop("expected_active")
    manifest.pop("digest")
    manifest["digest"] = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    harness.write(built["generation_ref"], json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    completion = operation_status(harness)["completion"]
    assert completion["status"] == "unknown"
    assert completion["next_action"] == "inspect_finalization"
    assert "expected_active" not in completion


def test_unreadable_local_journal_requires_inspection_not_clone_readiness(harness):
    applied_batch(harness)
    harness.write(".build/operations/batch/transaction/journal.json", b"[]")
    status = operation_status(harness)
    assert status["completion"]["status"] == "unknown"
    assert status["completion"]["next_action"] == "recover_transaction"
    assert any(gap["stage"] == "transaction" for gap in status["gaps"])
