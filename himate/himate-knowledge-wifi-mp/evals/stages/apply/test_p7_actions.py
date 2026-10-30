"""Behavioral cases; shared synthetic materials live under evals/support."""

from support.stages.apply_p7 import (
    HELPER,
    PublicP7,
    base64,
    pytest,
)


def test_public_batch_complete_reentry_and_independent_query(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    completed = trial.call("batch", request)
    data = completed["data"]
    assert completed["phase"] == "completed" and data["batch_complete"] and data["activated"]
    journal = trial.record(".build/operations/batch/transaction/journal.json")
    assert journal["status"] == "committed" and journal["verification_tier"] == "transaction_bytes_only"
    assert journal["execution_checks"] == "safety_only"
    assert set(data["commit_files"]) == {"knowledge/rules/batch-card.md", "governance/sources.lock.yaml"}
    assert trial.call("batch", request)["data"] == data
    searched = trial.call("search", {"operation_id": "daily", "query": "capture marker"}, skill="hs-knowledge-query")
    assert searched["data"]["matches"][0]["card_id"] == "batch-card"
    assert searched["data"]["generation_ref"] == data["generation_ref"]


def test_batch_does_not_repeat_p5_quality_and_old_run_json_cannot_disable_it(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content(omitted_heading=True)
    before = set((trial.root / "knowledge").rglob("*.md"))
    old = trial.call("run", {**request, "safety_only": True}, expected=2)
    assert old["status"] == "error" and set((trial.root / "knowledge").rglob("*.md")) == before
    result = trial.call("batch", request)
    assert result["data"]["batch_complete"]
    assert trial.record(".build/operations/batch/transaction/apply-result.json")["verification_tier"] == "transaction_bytes_only"


def test_batch_input_drift_blocks_before_any_target_write(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    original_lock = (trial.root / "governance/sources.lock.yaml").read_bytes()
    trial.write("docs-raw/specs/raw.md", b"Changed selected original.\n")
    blocked = trial.call("batch", request, expected=3)
    assert blocked["status"] == "blocked"
    assert not (trial.root / "knowledge/rules/batch-card.md").exists()
    assert (trial.root / "governance/sources.lock.yaml").read_bytes() == original_lock
    assert not (trial.root / ".build/operations/batch/transaction/journal.json").exists()


def test_partial_batch_can_be_inspected_and_resumed_without_new_transaction(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    catalog = tmp_path / "fixture-catalog.json"
    catalog.write_bytes(HELPER.canonical({"test_fixture_root": str(trial.root.resolve())}))
    trial.call("batch", {**request, "fault_after": 1}, expected=3, catalog=catalog)
    inspected = trial.call("inspect", {"operation_id": "batch"})
    assert inspected["data"]["transaction_status"] == "recovery_required"
    resumed = trial.call("batch", request)
    assert resumed["phase"] == "completed" and resumed["data"]["activated"]
    assert len(list((trial.root / ".build/operations").glob("*/transaction/journal.json"))) == 1


def test_batch_failed_frozen_query_keeps_local_commit_and_active_pointer(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    view = trial.record(request["view_ref"])
    view["target_queries"][0]["required"] = ["absent-card"]
    view = trial.modules["records"].seal(view)
    trial.write(request["view_ref"], HELPER.canonical(view))
    response = trial.call("batch", request)
    assert response["phase"] == "needs_revision" and not response["data"]["activated"]
    assert response["data"]["transaction_status"] == "committed"
    assert not (trial.root / "artifacts/indexes/local/active.json").exists()
    assert (trial.root / "knowledge/rules/batch-card.md").exists()


def test_resealed_committed_journal_cannot_replace_the_candidates_write_bytes(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    view = trial.record(request["view_ref"])
    view["target_queries"][0]["required"] = ["absent-card"]
    trial.write(request["view_ref"], HELPER.canonical(trial.modules["records"].seal(view)))
    assert trial.call("batch", request)["phase"] == "needs_revision"
    ref = ".build/operations/batch/transaction/journal.json"
    journal = trial.record(ref)
    changed = b"forged installed bytes\n"
    row = next(entry for entry in journal["entries"] if entry["path"] == "knowledge/rules/batch-card.md")
    row["new_digest"], row["bytes_b64"] = HELPER.sha(changed), base64.b64encode(changed).decode()
    trial.write(row["path"], changed)
    trial.write(ref, HELPER.canonical(trial.modules["records"].seal(journal)))
    denied = trial.call("batch", request, expected=2)
    assert denied["diagnostics"][0]["code"] == "JOURNAL_VIEW_MISMATCH"
    assert not (trial.root / "artifacts/indexes/local/active.json").exists()


def test_invalid_index_channel_is_rejected_before_local_application(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    denied = trial.call("batch", {**request, "channel": "unknown"}, expected=2)
    assert denied["diagnostics"][0]["code"] == "INVALID_CHANNEL"
    assert not (trial.root / ".build/operations/batch/transaction/journal.json").exists()


def test_new_batch_accepts_the_shared_operation_id_contract(tmp_path):
    trial = PublicP7(tmp_path)
    response = trial.call("batch", trial.content(operation="batch.v2"))
    assert response["phase"] == "completed" and response["data"]["batch_complete"]


@pytest.mark.parametrize("cases", [[], [{"id": "no-assertion", "query": "anything"}]])
def test_independent_regression_rejects_missing_behavior_without_activation(tmp_path, cases):
    trial = PublicP7(tmp_path)
    built = trial.call("index-build", {"operation_id": "index"})["data"]
    rejected = trial.call("regression", {"operation_id": "regression", "generation_ref": built["generation_ref"],
                         "expected_active": built["expected_active"], "cases": cases}, expected=2)
    assert rejected["status"] == "error"
    assert not (trial.root / "artifacts/indexes/local/active.json").exists()


def test_independent_empty_expected_order_and_verify_do_not_require_producer_history(tmp_path):
    trial = PublicP7(tmp_path)
    built = trial.call("index-build", {"operation_id": "index"})["data"]
    checked = trial.call("regression", {"operation_id": "regression", "generation_ref": built["generation_ref"],
                         "expected_active": built["expected_active"],
                         "cases": [{"id": "empty", "query": "anything", "expected_order": []}]})
    pointer = (trial.root / "artifacts/indexes/local/active.json").read_bytes()
    verified = trial.call("regression-verify", {"operation_id": "recheck", "report_ref": checked["data"]["report_ref"]})
    assert verified["phase"] == "verified" and not verified["data"]["activated"]
    assert (trial.root / "artifacts/indexes/local/active.json").read_bytes() == pointer
    assert not list((trial.root / ".build/operations").glob("*/transaction/journal.json"))


def test_submission_verifies_actual_git_blobs_deletion_and_exact_changed_scope(tmp_path):
    trial = PublicP7(tmp_path)
    trial.write("knowledge/selected.md", b"old selected\n")
    trial.write("knowledge/deleted.md", b"old deletion\n")
    trial.git("init", "-q")
    trial.git("add", "--", "knowledge/selected.md", "knowledge/deleted.md")
    trial.git("commit", "-qm", "baseline")
    view_ref = trial.view("submit", {"knowledge/selected.md": b"new exact bytes\n"}, deletes=["knowledge/deleted.md"])
    trial.write("knowledge/selected.md", b"new exact bytes\n")
    (trial.root / "knowledge/deleted.md").unlink()
    request = {"operation_id": "submit", "view_ref": view_ref}
    ready = trial.call("prepare-submission", request)
    assert set(ready["data"]["commit_files"]) == {"knowledge/selected.md", "knowledge/deleted.md"}
    trial.git("add", "--", "knowledge/selected.md", "knowledge/deleted.md")
    trial.git("commit", "-qm", "scoped batch")
    commit = trial.git("rev-parse", "HEAD")
    submitted = trial.call("verify-submission", {**request, "commit_sha": commit})
    assert submitted["phase"] == "submitted" and submitted["data"]["commit_sha"] == commit
    trial.write("outside.txt", b"unrelated\n")
    trial.git("add", "--", "outside.txt")
    trial.git("commit", "-qm", "outside scope")
    rejected = trial.call("verify-submission", {**request, "commit_sha": trial.git("rev-parse", "HEAD")}, expected=2)
    assert rejected["status"] == "error"


def test_submission_rejects_changed_selected_bytes_without_an_apply_ticket(tmp_path):
    trial = PublicP7(tmp_path)
    view_ref = trial.view("submit", {"knowledge/selected.md": b"selected exact bytes\n"})
    trial.write("knowledge/selected.md", b"different current bytes\n")
    denied = trial.call("prepare-submission", {"operation_id": "submit", "view_ref": view_ref}, expected=3)
    assert denied["status"] == "blocked" and denied["phase"] != "submitted"


def test_submission_agent_record_alone_cannot_claim_published(tmp_path):
    trial = PublicP7(tmp_path)
    context = trial.context("submit")
    reference = "logs/operations/submit/apply-result.json"
    context.save(reference, context.seal({"status": "committed", "view_ref": None,
        "view_digest": "a" * 64, "writes": [], "deletes": [],
        "verification_tier": "agent_record"}, "apply_result"))
    denied = trial.call("prepare-submission", {"operation_id": "submit", "apply_result_ref": reference}, expected=3)
    assert denied["status"] == "blocked" and denied["phase"] != "submitted"
    assert not (trial.root / ".build/operations/submit/publish-handoff.json").exists()


def test_manual_inspect_preserves_earlier_records_and_ignores_workflow_metadata(tmp_path):
    trial = PublicP7(tmp_path)
    operation = "operation-" + "x" * 70
    request = trial.content(operation=operation)
    catalog = tmp_path / "fixture-catalog.json"
    catalog.write_bytes(HELPER.canonical({"test_fixture_root": str(trial.root.resolve())}))
    trial.call("batch", {**request, "fault_after": 1}, expected=3, catalog=catalog)
    original_ref = ".build/operations/" + operation + "/recover-inspect-standalone-request.json"
    trial.write(original_ref, b"earlier manual attempt\n")
    result = trial.call("inspect", {"operation_id": operation, "workflow": "owned by harness"})
    assert result["data"]["transaction_status"] == "recovery_required"
    assert (trial.root / original_ref).read_bytes() == b"earlier manual attempt\n"
    assert not (trial.root / "logs/workflows").exists()
    assert not list((trial.root / ".build/operations").glob("*/calls/*"))


def test_recovery_without_actual_transaction_facts_cannot_report_success(tmp_path):
    trial = PublicP7(tmp_path)
    denied = trial.call("resume", {"operation_id": "absent"}, expected=3)
    assert denied["status"] == "blocked"
    assert not (trial.root / ".build/operations/absent/transaction/apply-result.json").exists()


def test_claimed_commit_sha_without_a_real_object_cannot_report_submission(tmp_path):
    trial = PublicP7(tmp_path)
    view_ref = trial.view("submit", {"knowledge/selected.md": b"selected exact bytes\n"})
    trial.write("knowledge/selected.md", b"selected exact bytes\n")
    trial.git("init", "-q")
    trial.git("add", "--", "knowledge/selected.md")
    trial.git("commit", "-qm", "fixture baseline")
    denied = trial.call("verify-submission", {"operation_id": "submit", "view_ref": view_ref,
                        "commit_sha": "f" * 40}, expected=3)
    assert denied["status"] == "blocked" and denied["phase"] != "submitted"


def test_record_only_batch_preserves_failure_debt_and_skips_index(tmp_path):
    trial = PublicP7(tmp_path)
    ctx = trial.context("facts")
    scan = ctx.seal({"scope": ["docs-raw/specs"], "full_scan": True, "complete": False,
                     "units": [{"unit_id": "u1", "path": "docs-raw/specs/missing.md", "source_id": "source",
                                "observed_fingerprint": None, "previous_fingerprint": None, "change": "added",
                                "read_error": "unreadable", "progress": "blocked"}]}, "source_inventory")
    record = ctx.seal({"record_id": "facts", "target_path": "logs/ingest/facts.yaml", "batch_kind": "record_only",
                      "scan_ref": ctx.base + "/scan.json", "scan_digest": scan["digest"], "inventory": scan,
                      "progress": {}, "dispositions": [{"unit_id": "u1", "action": "failed", "reason": "unreadable",
                          "observed_fingerprint": None, "adopted_fingerprint": None, "progress": "blocked",
                          "card_refs": [], "claim_refs": []}]}, "ingest_record")
    reference = ctx.base + "/record.json"
    ctx.save(reference, record)
    result = trial.call("batch", {"operation_id": "facts", "ingest_record_ref": reference})
    assert result["phase"] == "recorded" and result["data"]["batch_complete"]
    assert set(result["data"]["commit_files"]) == {"logs/ingest/facts.yaml",
        "logs/publications/facts/apply-result.json", "logs/publications/facts/manifest.json",
        "logs/publications/facts/completion.json"}
    assert not (trial.root / "artifacts/indexes").exists()
    saved = trial.record("logs/ingest/facts.yaml")
    assert saved["dispositions"][0]["progress"] == "blocked"
    assert saved["progress"]["apply"]["status"] == "recorded"
