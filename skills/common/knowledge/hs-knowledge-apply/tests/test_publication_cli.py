"""New publication CLI behavior with exact authored synthetic business bytes."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


SPEC = importlib.util.spec_from_file_location("publication_public_p7", Path(__file__).with_name("test_p7_actions.py"))
P7 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P7)
MANUAL_SPEC = importlib.util.spec_from_file_location("publication_manual_skills",
    P7.HELPER.ROOT / "himate-knowledge-wifi-mp/evals/tests/test_manual_skills.py")
MANUAL = importlib.util.module_from_spec(MANUAL_SPEC)
MANUAL_SPEC.loader.exec_module(MANUAL)


def manual_pending(tmp_path):
    """Use real P1--P6 public entries, including authored plan and P5 review."""
    pipeline = MANUAL.ManualPipeline(tmp_path)
    operation = "manual-publication"
    pipeline.write("docs-raw/specs/manual.md", b"# Source\nCapture marker is a documented rule.\n")
    scan = pipeline.call("knowledge-source-scan", {"operation_id": operation}, "scan")["data"]["scan_ref"]
    material = pipeline.call("knowledge-source-prepare", {"operation_id": operation, "scan_ref": scan}, "prepare")["data"]["material_ref"]
    bundle_ref = pipeline.record(material)["bundle_ref"]
    view = pipeline.view(operation, bundle_ref, "manual-rule", pipeline.card("manual-rule", pipeline.record(bundle_ref)),
                         scan_ref=scan, material_ref=material)
    pipeline.review(operation, view)
    record = pipeline.call("knowledge-source-scan", {"operation_id": operation, "scan_ref": scan, "view_ref": view,
        "disposition_preview_ref": pipeline.record(view)["disposition_preview_ref"]}, "record")["data"]["ingest_record_ref"]
    return pipeline, {"operation_id": operation, "view_ref": view, "ingest_record_ref": record}


def publication_content(trial, operation="batch"):
    request = trial.content(operation, legacy_objects=False)
    ctx = trial.context(operation)
    view = trial.record(request["view_ref"])
    bundle = trial.record(".build/operations/" + operation + "-raw/capture.json")
    view.update(staged_objects=bundle.get("staged_objects", []), event_proposals=bundle.get("event_proposals", []),
                owned_files=ctx.owned_files())
    publication = P7.HELPER.load_contract("publication")
    view["publication_plan"] = publication.prepare_plan(ctx, view)
    view["content_digest"] = view["publication_plan"]["content_digest"]
    view = ctx.modules["records"].seal(view)
    raw = P7.HELPER.canonical(view)
    trial.write(request["view_ref"], raw)
    ctx.register_owned(request["view_ref"], raw)
    return request


def test_publication_batch_cleans_owned_draft_and_reentry_uses_formal_result(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    result = trial.call("batch", request)
    assert result["data"]["published"] is True and result["data"]["batch_complete"] is True, result
    assert not (trial.root / request["view_ref"]).exists()
    assert not (trial.root / ".build/operations/batch/transaction/journal.json").exists()
    assert not (trial.root / ".build/operations/batch/transaction/apply-result.json").exists()
    assert (trial.root / "logs/publications/batch/manifest.json").is_file()
    assert (trial.root / "logs/publications/batch/completion.json").is_file()
    before = {path.relative_to(trial.root).as_posix(): path.read_bytes()
              for path in (trial.root / "knowledge").rglob("*.md")}
    again = trial.call("batch", {"operation_id": "batch"})
    assert again["data"]["batch_complete"] is True
    assert before == {path.relative_to(trial.root).as_posix(): path.read_bytes()
                      for path in (trial.root / "knowledge").rglob("*.md")}
    ready = trial.call("prepare-submission", {"operation_id": "batch",
        "publication_ref": result["data"]["publication_ref"]})
    assert "logs/publications/batch/manifest.json" in ready["data"]["commit_files"]
    assert not any(ref.startswith(".build/") for ref in ready["data"]["commit_files"])


def test_publication_cleanup_failure_retries_without_rebuilding_index(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''from pathlib import Path
original = Path.unlink
def denied(path, *args, **kwargs):
    if path.as_posix().endswith("/.build/operations/batch/view.json"):
        raise PermissionError("synthetic exact owned-file cleanup failure")
    return original(path, *args, **kwargs)
Path.unlink = denied
''', encoding="utf-8")
    failed = trial.call("batch", request, environment={**os.environ, "PYTHONPATH": str(probe)})
    assert failed["data"]["published"] is True and failed["data"]["batch_complete"] is False
    assert failed["data"]["cleanup"]["status"] == "cleanup_pending"
    pointer = trial.record("artifacts/indexes/local/active.json")
    generation_files = {path.relative_to(trial.root).as_posix(): path.read_bytes()
                        for path in (trial.root / "artifacts/indexes").rglob("*") if path.is_file()}
    retried = trial.call("batch", {"operation_id": "batch"})
    assert retried["data"]["batch_complete"] is True
    assert trial.record("artifacts/indexes/local/active.json") == pointer
    assert generation_files == {path.relative_to(trial.root).as_posix(): path.read_bytes()
                               for path in (trial.root / "artifacts/indexes").rglob("*") if path.is_file()}


def test_actual_git_submission_verification_after_publication_cleanup(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    trial.git("init", "-b", "main")
    trial.git("add", "governance", "knowledge/index.md", "docs-raw")
    trial.git("commit", "-m", "Isolated publication baseline")
    result = trial.call("batch", request)
    ready = trial.call("prepare-submission", {"operation_id": "batch",
        "publication_ref": result["data"]["publication_ref"]})
    trial.git("add", "--", *ready["data"]["commit_files"])
    trial.git("commit", "-m", "Exact synthetic publication")
    commit = trial.git("rev-parse", "HEAD")
    verified = trial.call("verify-submission", {"operation_id": "batch",
        "publication_ref": result["data"]["publication_ref"], "commit_sha": commit})
    assert verified["phase"] == "submitted" and verified["data"]["commit_sha"] == commit
    assert not (trial.root / request["view_ref"]).exists()


def test_record_only_publishes_debt_then_cleans_owned_proposal(tmp_path):
    trial = P7.PublicP7(tmp_path)
    ctx = trial.context("facts")
    inventory = ctx.seal({"scope": ["docs-raw/specs"], "full_scan": False, "complete": True, "units": [{
        "unit_id": "one", "source_id": "raw", "path": "docs-raw/specs/a.md", "observed_fingerprint": "a" * 64,
        "previous_fingerprint": None, "change": "new", "progress": None, "read_error": None}]}, "source_inventory")
    record = ctx.seal({"record_id": "facts", "target_path": "logs/ingest/facts.yaml", "batch_kind": "record_only",
        "status": "pending", "progress": {}, "scan_ref": ctx.base + "/inventory.json", "scan_digest": inventory["digest"],
        "inventory": inventory, "dispositions": [{"unit_id": "one", "action": "defer", "reason": "Synthetic missing required material",
        "observed_fingerprint": "a" * 64, "adopted_fingerprint": None, "progress": "blocked", "card_refs": [], "claim_refs": []}]}, "ingest_record")
    reference = ctx.save(ctx.base + "/record.json", record)
    response = trial.call("batch", {"operation_id": "facts", "ingest_record_ref": reference})
    assert response["phase"] == "recorded" and response["data"]["batch_complete"] is True
    saved = trial.record("logs/ingest/facts.yaml")
    assert saved["status"] == "recorded" and saved["dispositions"][0]["progress"] == "blocked"
    assert not (trial.root / reference).exists() and not (trial.root / "artifacts/indexes/local/active.json").exists()


def test_content_publication_with_no_new_event_proposal_rechecks_mechanical_block(tmp_path):
    trial = P7.PublicP7(tmp_path)
    ctx = trial.context("batch")
    state = trial.modules["maintenance"].state(ctx)
    state.update(validity_epoch=1, blocked_claims=[{
        "card_id": "batch-card", "claim_id": "c1", "source_id": "raw", "reason": "source_changed"}])
    ctx.save("logs/events/state.json", ctx.seal(state, "maintenance_state"))
    request = publication_content(trial)
    assert trial.record(request["view_ref"])["event_proposals"] == []
    result = trial.call("batch", request)
    assert result["data"]["batch_complete"] is True
    assert trial.record("logs/events/state.json")["blocked_claims"] == []


def test_legacy_run_keeps_formal_record_semantics_with_new_staged_view(tmp_path):
    pipeline, request = manual_pending(tmp_path)
    assert pipeline.record(request["view_ref"])["publication_plan"]
    result = pipeline.call("knowledge-apply", request, "run")
    assert result["phase"] == "committed"
    record = pipeline.record("logs/ingest/" + request["operation_id"] + ".yaml")
    assert record["status"] == "applied" and record["progress"]["apply"]["status"] == "applied"
    journal = pipeline.record(".build/operations/" + request["operation_id"] + "/transaction/journal.json")
    assert "publication_protocol" not in journal


def test_formal_closure_rejection_precedes_processing_success(tmp_path, monkeypatch):
    pipeline, request = manual_pending(tmp_path)
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import sys
def reject(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "published_inputs" and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/input_snapshot.py"):
        raise RuntimeError("SYNTHETIC_FORMAL_CLOSURE_REJECTED")
sys.setprofile(reject)
''', encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setenv("PYTHONPATH", str(probe))
        result = pipeline.call("knowledge-apply", request, "batch", expected=2)
    assert "SYNTHETIC_FORMAL_CLOSURE_REJECTED" in result["diagnostics"][0]["message"]
    assert not (pipeline.root / ("logs/ingest/" + request["operation_id"] + ".yaml")).exists()
    assert not (pipeline.root / ("logs/publications/" + request["operation_id"] + "/manifest.json")).exists()


def test_p6_replacement_after_content_commit_cannot_publish_success(tmp_path, monkeypatch):
    pipeline, request = manual_pending(tmp_path)
    frozen = pipeline.record(request["ingest_record_ref"])["digest"]
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import json, sys
fired = False
def replace_pending(frame, event, arg):
    global fired
    if not fired and event == "call" and frame.f_code.co_name == "published_inputs" and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/input_snapshot.py"):
        fired = True
        ctx = frame.f_locals["ctx"]
        path = ctx.root / ctx.request["ingest_record_ref"]
        record = json.loads(path.read_bytes())
        record["dispositions"][0]["reason"] = "unreviewed replacement after content commit"
        path.write_bytes(ctx.modules["runtime"].canonical(ctx.modules["records"].seal(record)))
sys.setprofile(replace_pending)
''', encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setenv("PYTHONPATH", str(probe))
        result = pipeline.call("knowledge-apply", request, "batch", expected=2)
    assert pipeline.record(request["ingest_record_ref"])["digest"] != frozen
    assert "Pending record changed" in result["diagnostics"][0]["message"]
    assert not (pipeline.root / ("logs/ingest/" + request["operation_id"] + ".yaml")).exists()
    assert not (pipeline.root / ("logs/publications/" + request["operation_id"] + "/manifest.json")).exists()


def test_historical_verify_result_rejects_another_real_publication(tmp_path):
    trial = P7.PublicP7(tmp_path)
    first = trial.call("batch", publication_content(trial))["data"]
    second = trial.call("batch", publication_content(trial, "other"))["data"]
    correct = trial.call("verify-result", {"operation_id": "batch", "purpose": "historical",
        "publication_ref": first["publication_ref"]})
    assert correct["data"]["content_digest"] == first["content_digest"]
    wrong = trial.call("verify-result", {"operation_id": "batch", "purpose": "historical",
        "publication_ref": second["publication_ref"]}, expected=2)
    assert "operation" in wrong["diagnostics"][0]["message"].lower()


def test_first_null_baseline_survives_manifest_failure_and_retry_omission(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import sys
def reject(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "published_inputs" and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/input_snapshot.py"):
        raise RuntimeError("SYNTHETIC_STOP_BEFORE_MANIFEST")
sys.setprofile(reject)
''', encoding="utf-8")
    trial.call("batch", {**request, "expected_active": None}, expected=2,
               environment={**os.environ, "PYTHONPATH": str(probe)})
    assert not (trial.root / "logs/publications/batch/manifest.json").exists()
    built = trial.call("index-build", {"operation_id": "later-build"})["data"]
    trial.call("index-activate", {"operation_id": "later-activate", "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"]})
    pointer = trial.record("artifacts/indexes/local/active.json")
    denied = trial.call("batch", request, expected=3)
    assert denied["diagnostics"][0]["code"] == "ACTIVE_CHANGED"
    assert trial.record("artifacts/indexes/local/active.json") == pointer
    assert trial.record("logs/publications/batch/manifest.json")["index_inputs"]["expected_active"] is None


def test_unactivated_publication_cannot_complete_by_resealing_only_completion(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text('''import sys
def reject(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "_activation_observation" and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/ingest_execution.py"):
        raise RuntimeError("SYNTHETIC_BEFORE_ACTIVATION")
sys.setprofile(reject)
''', encoding="utf-8")
    trial.call("batch", request, expected=2, environment={**os.environ, "PYTHONPATH": str(probe)})
    manifest = trial.record("logs/publications/batch/manifest.json")
    ctx = trial.context("batch")
    forged = ctx.seal({"purpose": "knowledge_publication_completion", "protocol_version": "1.0",
        "publication_ref": "logs/publications/batch/manifest.json", "publication_digest": manifest["digest"],
        "content_digest": manifest["content_digest"], "published": True, "batch_complete": True, "phase": "completed",
        "data": {"activated": True}, "retrieval": {"complete": True},
        "cleanup": {"status": "done", "owned": [], "deleted": [], "retained": [], "failed": []}}, "artifact_manifest")
    trial.write("logs/publications/batch/completion.json", P7.HELPER.canonical(forged))
    denied = trial.call("batch", {"operation_id": "batch"}, expected=2)
    assert denied["diagnostics"][0]["code"] == "PUBLICATION_COMPLETION_CHANGED"
    assert not (trial.root / "artifacts/indexes/local/active.json").exists()


@pytest.mark.parametrize("damage", ["missing_report", "inline_regression"])
def test_completed_publication_requires_unchanged_formal_retrieval_facts(tmp_path, damage):
    trial = P7.PublicP7(tmp_path)
    result = trial.call("batch", publication_content(trial))["data"]
    if damage == "missing_report":
        (trial.root / result["report_ref"]).unlink()
    else:
        completion = trial.record(result["completion_ref"])
        completion["retrieval"]["regression"]["cases"][0]["query"] = "replacement query"
        trial.write(result["completion_ref"], P7.HELPER.canonical(trial.modules["records"].seal(completion)))
    denied = trial.call("batch", {"operation_id": "batch"}, expected=2)
    assert denied["status"] == "error"


def test_historical_completion_survives_rules_identity_and_local_index_changes(tmp_path):
    trial = P7.PublicP7(tmp_path)
    result = trial.call("batch", publication_content(trial))["data"]
    publication = P7.HELPER.load_contract("publication")
    ctx = trial.context("reader")
    ctx.args.rules_digest = "f" * 64
    shutil.rmtree(trial.root / "artifacts")
    completion = publication.read_completion(ctx, operation_id="batch")
    assert completion["batch_complete"] is True
    assert trial.call("batch", {"operation_id": "batch"})["data"] == result


def test_rules_upgrade_keeps_historical_verification_without_current_eligibility(tmp_path):
    trial = P7.PublicP7(tmp_path)
    result = trial.call("batch", publication_content(trial))["data"]
    contract = trial.root / "governance/contracts/indexing.py"
    contract.write_bytes(contract.read_bytes() + b"\n# Synthetic infrastructure-only rules upgrade.\n")
    lock_path = trial.root / "governance/framework.lock.yaml"
    lock = yaml.safe_load(lock_path.read_bytes())
    lock["files"]["contracts/indexing.py"]["sha256"] = P7.HELPER.sha(contract.read_bytes())
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    refused = trial.call("verify-result", {"operation_id": "batch", "publication_ref": result["publication_ref"]}, expected=2)
    assert refused["diagnostics"][0]["code"] == "STALE_RULES"
    historical = trial.call("verify-result", {"operation_id": "batch", "publication_ref": result["publication_ref"],
        "purpose": "historical"})["data"]
    assert historical["result_verified"] is True and historical["eligible_files"] == []
    assert historical["historical_files"] == [{"path": "knowledge/rules/batch-card.md",
        "sha256": P7.HELPER.sha((trial.root / "knowledge/rules/batch-card.md").read_bytes())}]


def run_transport(trial, request, output, *, incoming=None):
    incoming = incoming or (trial.base / "transport-input.json")
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_bytes(P7.HELPER.canonical(request))
    return subprocess.run([sys.executable, str(P7.ROOT / "skills/common/knowledge/hs-knowledge-apply/scripts/cli.py"),
        "--action", "batch", "--knowledge-root", str(trial.root), "--input", str(incoming), "--output", str(output)],
        capture_output=True, timeout=120)


@pytest.mark.parametrize("destination", ["logs/events/response.json", ".build/operations/another/response.json", "artifacts/response.json"])
def test_batch_transport_rejects_other_knowledge_paths_before_business_write(tmp_path, destination):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    output = trial.root / destination
    result = run_transport(trial, request, output)
    assert result.returncode == 2
    assert not output.exists()
    assert not (trial.root / "knowledge/rules/batch-card.md").exists()


def test_batch_own_transport_request_is_cleaned_but_final_envelope_does_not_recreate_ledger(tmp_path):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    incoming = trial.root / ".build/operations/batch/request.json"
    outgoing = trial.root / ".build/operations/batch/final.json"
    result = run_transport(trial, request, outgoing, incoming=incoming)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(outgoing.read_bytes())["data"]["batch_complete"] is True
    assert not incoming.exists()
    assert not (trial.root / ".build/operations/batch/owned-files.json").exists()


@pytest.mark.parametrize("slot", ["transaction/journal.json", "transaction/nested/response.json",
    "owned-files.json", "batch-intent.json", "batch-build.json", "batch-complete.json", "view.json",
    "final-view.json", "plan.json", "disposition-preview.json", "view-summary.json", "revision.json"])
def test_batch_response_cannot_recreate_reserved_protocol_slots(tmp_path, slot):
    trial = P7.PublicP7(tmp_path)
    request = publication_content(trial)
    output = trial.root / ".build/operations/batch" / slot
    previous = output.read_bytes() if output.exists() else None
    result = run_transport(trial, request, output)
    assert result.returncode == 2
    assert (output.read_bytes() if output.exists() else None) == previous
    assert not (trial.root / "knowledge/rules/batch-card.md").exists()


def test_actual_source_defer_state_is_submitted_and_survives_git_clone(tmp_path):
    trial = P7.PublicP7(tmp_path)
    initial = publication_content(trial)
    trial.git("init", "-b", "main")
    trial.git("add", "governance", "knowledge/index.md", "docs-raw")
    trial.git("commit", "-m", "Initial synthetic source")
    first = trial.call("batch", initial)["data"]
    ready = trial.call("prepare-submission", {"operation_id": "batch", "publication_ref": first["publication_ref"]})["data"]
    trial.git("add", "--", *ready["commit_files"])
    trial.git("commit", "-m", "Initial exact publication")
    previous = (trial.root / "docs-raw/specs/raw.md").read_bytes()
    changed = b"Capture marker changed; the existing card requires review.\n"
    trial.write("docs-raw/specs/raw.md", changed)
    trial.git("add", "docs-raw/specs/raw.md")
    trial.git("commit", "-m", "Actual source update before deferred processing")
    captured = trial.call("capture", {"operation_id": "deferred-source", "source_id": "raw",
        "source_path": "docs-raw/specs/raw.md"}, skill="hs-knowledge-source-prepare")["data"]
    bundle = trial.record(captured["bundle_ref"])
    assert bundle["event_proposals"]
    lock = yaml.safe_load((trial.root / "governance/sources.lock.yaml").read_bytes())
    snapshots = {row["snapshot_id"]: row for row in lock["snapshots"]}
    snapshots.update({row["snapshot_id"]: row for row in bundle["snapshots"]})
    lock["snapshots"] = list(snapshots.values())
    ctx = trial.context("deferred")
    adopted = trial.modules["input_snapshot"].capture_inputs(ctx, bundle=bundle, material={
        "current_files": [{"path": "docs-raw/specs/raw.md", "sha256": P7.HELPER.sha(changed)}]})
    view_ref = trial.view("deferred", {"governance/sources.lock.yaml": yaml.safe_dump(lock, sort_keys=False).encode()},
        snapshots=bundle["snapshots"], snapshot=adopted)
    view = trial.record(view_ref)
    view.update(staged_objects=bundle["staged_objects"], event_proposals=bundle["event_proposals"],
        owned_files=ctx.owned_files(), target_queries=[{"id": "debt", "query": "capture marker", "forbidden": ["batch-card"]}])
    publication = P7.HELPER.load_contract("publication")
    view["publication_plan"] = publication.prepare_plan(ctx, view)
    view["content_digest"] = view["publication_plan"]["content_digest"]
    view = ctx.modules["records"].seal(view)
    raw = P7.HELPER.canonical(view)
    trial.write(view_ref, raw)
    ctx.register_owned(view_ref, raw)
    inventory = ctx.seal({"scope": ["docs-raw/specs"], "full_scan": False, "complete": True, "units": [{
        "unit_id": "changed", "source_id": "raw", "path": "docs-raw/specs/raw.md", "observed_fingerprint": P7.HELPER.sha(changed),
        "previous_fingerprint": P7.HELPER.sha(previous), "change": "changed", "progress": None, "read_error": None}]}, "source_inventory")
    scan_ref = ctx.save(ctx.base + "/inventory.json", inventory)
    record = ctx.seal({"record_id": "deferred", "target_path": "logs/ingest/deferred.yaml", "batch_kind": "content",
        "status": "pending", "progress": {}, "scan_ref": scan_ref, "scan_digest": inventory["digest"], "inventory": inventory,
        "content_view_digest": view["digest"], "dispositions": [{"unit_id": "changed", "action": "defer",
        "reason": "Read the real changed source; defer updating its old Claim", "observed_fingerprint": P7.HELPER.sha(changed),
        "adopted_fingerprint": None, "progress": "blocked", "card_refs": [], "claim_refs": []}]}, "ingest_record")
    record_ref = ctx.save(ctx.base + "/record.json", record)
    result = trial.call("batch", {"operation_id": "deferred", "view_ref": view_ref, "ingest_record_ref": record_ref})["data"]
    state = trial.record("logs/events/state.json")
    assert state["blocked_claims"] and state["validity_epoch"] > 0
    handoff = trial.call("prepare-submission", {"operation_id": "deferred", "publication_ref": result["publication_ref"]})["data"]
    assert "logs/events/state.json" in handoff["commit_files"]
    trial.git("add", "--", *handoff["commit_files"])
    trial.git("commit", "-m", "Deferred source state in formal closure")
    commit = trial.git("rev-parse", "HEAD")
    assert trial.call("verify-submission", {"operation_id": "deferred", "publication_ref": result["publication_ref"],
        "commit_sha": commit})["phase"] == "submitted"
    clone = tmp_path / "consumer"
    trial.git("clone", "--no-hardlinks", str(trial.root), str(clone))
    assert json.loads((clone / "logs/events/state.json").read_bytes()) == state
    assert not (clone / ".build").exists()
    consumer = P7.PublicP7.__new__(P7.PublicP7)
    consumer.base, consumer.root, consumer.calls = tmp_path / "consumer-io", clone, 0
    consumer.base.mkdir()
    built = consumer.call("index-build", {"operation_id": "consumer-build"})["data"]
    tested = consumer.call("regression", {"operation_id": "consumer-test", "generation_ref": built["generation_ref"],
        "expected_active": built["expected_active"], "cases": [{"id": "debt", "query": "capture marker", "forbidden": ["batch-card"]}]})
    assert tested["data"]["passed"] is True
