"""Actual public P7 CLIs over isolated raw/card bytes and local Git objects."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[5]
HELPER_SPEC = importlib.util.spec_from_file_location("p7_action_helpers", Path(__file__).with_name("p7_test_helpers.py"))
HELPER = importlib.util.module_from_spec(HELPER_SPEC)
HELPER_SPEC.loader.exec_module(HELPER)


class PublicP7:
    def __init__(self, base):
        self.base, self.root = base, base / "k"
        self.root.mkdir()
        shutil.copytree(ROOT / "himate-knowledge-wifi-mp/governance", self.root / "governance",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.write("knowledge/index.md", b"# Knowledge\n")
        self.write(".isolated-knowledge-fixture", b"HIMATE_SYNTHETIC_FIXTURE_V2")
        self.rules_digest = HELPER.sha((self.root / "governance/framework.lock.yaml").read_bytes())
        self.calls = 0
        names = ("validation", "records", "knowledge", "source_resources", "indexing", "checks", "runtime",
                 "input_snapshot", "source_operations", "source_materials", "index_runtime", "query_runtime",
                 "query_regression", "submission", "ingest_execution", "maintenance")
        self.modules = {name: HELPER.load_contract(name) for name in names}
        self.rules = self.modules["validation"].load_rules(self.root, self.rules_digest)
        self.tool = {"skill": "hs-fixture", "package_digest": "0" * 64,
                     "requirements_digest": "0" * 64, "runtime": "fixture"}

    def write(self, ref, raw):
        target = self.root / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return ref

    def record(self, ref):
        return json.loads((self.root / ref).read_bytes())

    def context(self, operation):
        return self.modules["runtime"].OperationContext(self.root, {"operation_id": operation},
                modules=self.modules, rules=self.rules, tool=self.tool, rules_digest=self.rules_digest)

    def call(self, action, request, expected=0, skill="hs-knowledge-apply", catalog=None, environment=None):
        self.calls += 1
        incoming, outgoing = self.base / (str(self.calls) + ".in.json"), self.base / (str(self.calls) + ".out.json")
        incoming.write_bytes(HELPER.canonical(request))
        command = [sys.executable, str(ROOT / "skills/common/knowledge" / skill / "scripts/cli.py"),
                   "--input", str(incoming), "--output", str(outgoing), "--knowledge-root", str(self.root)]
        if action:
            command += ["--action", action]
        if catalog:
            command += ["--catalog", str(catalog)]
        completed = subprocess.run(command, capture_output=True, timeout=90, env=environment)
        response = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
        assert completed.returncode == expected, (response, completed.stderr.decode(errors="replace"))
        assert response.get("digest") == HELPER.sha(HELPER.canonical({key: value for key, value in response.items() if key != "digest"}))
        return response

    def content(self, operation="batch", *, omitted_heading=False):
        original = b"Capture marker is an explicit synthetic rule.\nSecond line.\n"
        self.write("docs-raw/specs/raw.md", original)
        captured = self.call("capture", {"operation_id": operation + "-raw", "source_id": "raw",
                             "source_path": "docs-raw/specs/raw.md"}, skill="hs-knowledge-source-prepare")
        bundle = self.record(captured["data"]["bundle_ref"])
        snapshot = bundle["snapshots"][0]
        template = (self.root / "governance/templates/rule.md").read_text(encoding="utf-8")
        for key, value in {"card_id": "batch-card", "title": "Batch card", "summary": "Capture marker",
                           "owner": "fixture", "evidence_ref": "e1", "source_id": "raw",
                           "snapshot_id": snapshot["snapshot_id"], "claim_id": "c1",
                           "claim_text": "Capture marker is an explicit synthetic rule."}.items():
            template = template.replace("{{" + key + "}}", value)
        _, front, body = template.split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["lifecycle"] = "stable"
        metadata["scope"] = {"applicability": "universal", "contexts": []}
        metadata["claims"][0]["usage"] = "current"
        metadata["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 2}
        if omitted_heading:
            body = "\n".join(line for line in body.splitlines() if not line.startswith("## "))
        card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
        lock = yaml.safe_dump({"schema_version": "2.0", "resources": bundle["resources"],
                               "snapshots": bundle["snapshots"]}, sort_keys=False).encode()
        ctx = self.context(operation)
        inputs = self.modules["input_snapshot"].capture_inputs(ctx, bundle=bundle, material={
            "current_files": [{"path": "docs-raw/specs/raw.md", "sha256": HELPER.sha(original)}]})
        view_ref = self.view(operation, {"knowledge/rules/batch-card.md": card,
                                         "governance/sources.lock.yaml": lock}, snapshots=bundle["snapshots"],
                             snapshot=inputs)
        return {"operation_id": operation, "view_ref": view_ref}

    def view(self, operation, writes, *, deletes=(), snapshots=(), snapshot=None):
        ctx = self.context(operation)
        entries = [{"path": ref, "bytes_b64": base64.b64encode(raw).decode(), "final_digest": HELPER.sha(raw),
                    "expected_old_digest": HELPER.sha((self.root / ref).read_bytes()) if (self.root / ref).exists() else None}
                   for ref, raw in writes.items()]
        removals = [{"path": ref, "expected_old_digest": HELPER.sha((self.root / ref).read_bytes())} for ref in deletes]
        view = ctx.seal({"review_mode": "manual_document", "batch_kind": "content", "writes": entries,
            "deletes": removals, "source_refs": list(snapshots),
            "baseline_digest": HELPER.sha(HELPER.canonical({"files": {
                row["path"]: row["expected_old_digest"] for row in entries + removals}})),
            "plan_ref": ctx.base + "/plan.json", "plan_digest": "0" * 64,
            "input_snapshot": snapshot or self.modules["input_snapshot"].capture_inputs(ctx),
            "target_queries": [{"id": "marker", "query": "capture marker", "required": ["batch-card"]}]}, "final_view")
        reference = ctx.base + "/view.json"
        ctx.save(reference, view)
        return reference

    def git(self, *arguments):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")
        command = ["git", "-C", str(self.root), "-c", "core.hooksPath=" + os.devnull,
                   "-c", "commit.gpgsign=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                   *arguments]
        result = subprocess.run(command, capture_output=True, env=environment, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout.decode("utf-8").strip()


def test_public_batch_complete_reentry_and_independent_query(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    completed = trial.call("batch", request)
    data = completed["data"]
    assert completed["phase"] == "completed" and data["batch_complete"] and data["activated"]
    journal = trial.record("logs/operations/batch/journal.json")
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
    assert trial.record("logs/operations/batch/apply-result.json")["verification_tier"] == "transaction_bytes_only"


def test_batch_input_drift_blocks_before_any_target_write(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    original_lock = (trial.root / "governance/sources.lock.yaml").read_bytes()
    trial.write("docs-raw/specs/raw.md", b"Changed selected original.\n")
    blocked = trial.call("batch", request, expected=3)
    assert blocked["status"] == "blocked"
    assert not (trial.root / "knowledge/rules/batch-card.md").exists()
    assert (trial.root / "governance/sources.lock.yaml").read_bytes() == original_lock
    assert not (trial.root / "logs/operations/batch/journal.json").exists()


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
    assert len(list((trial.root / "logs/operations").glob("*/journal.json"))) == 1


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
    ref = "logs/operations/batch/journal.json"
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
    assert not (trial.root / "logs/operations/batch/journal.json").exists()


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
    assert not (trial.root / "logs/operations").exists() or not list((trial.root / "logs/operations").glob("*/journal.json"))


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
    assert not (trial.root / "logs/operations/absent/apply-result.json").exists()


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
    assert result["data"]["commit_files"] == ["logs/ingest/facts.yaml"]
    assert not (trial.root / "artifacts/indexes").exists()
    saved = trial.record("logs/ingest/facts.yaml")
    assert saved["dispositions"][0]["progress"] == "blocked"
    assert saved["progress"]["apply"]["status"] == "recorded"
