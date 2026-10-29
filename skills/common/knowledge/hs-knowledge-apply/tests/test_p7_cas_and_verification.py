"""Real CLI CAS/activation-history failures and actual SQLite verification counts."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

_actions_spec = importlib.util.spec_from_file_location("p7_cas_public_actions", Path(__file__).with_name("test_p7_actions.py"))
_actions = importlib.util.module_from_spec(_actions_spec)
_actions_spec.loader.exec_module(_actions)
HELPER, PublicP7, ROOT = _actions.HELPER, _actions.PublicP7, _actions.ROOT


PROBE = r'''import atexit, json, os, sys, tempfile
calls = []
def profile(frame, event, arg):
    if event != "call":
        return
    source = frame.f_code.co_filename.replace("\\", "/")
    if "/governance/contracts/" not in source:
        return
    name, filename = frame.f_code.co_name, source.rsplit("/", 1)[-1]
    if (filename, name) in {("indexing.py", "verify_database"), ("checks.py", "run"),
                            ("query_runtime.py", "search"), ("index_runtime.py", "verify_generation")}:
        calls.append({"module": filename, "name": name, "path": str(frame.f_locals.get("path", ""))})
    stop = os.environ.get("HIMATE_P7_STOP")
    if ((stop == "before_build" and filename == "index_runtime.py" and name == "execute"
         and frame.f_locals["ctx"].args.action == "build")
        or (stop == "before_activation" and filename == "ingest_execution.py" and name == "_activation_observation")):
        raise RuntimeError("SYNTHETIC_" + stop)
def save():
    descriptor, _ = tempfile.mkstemp(prefix=str(os.getpid()) + "-", suffix=".json",
                                     dir=os.environ["HIMATE_P7_TRACE"])
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"argv": sys.argv, "calls": calls}, stream)
atexit.register(save)
sys.setprofile(profile)
'''


def probe_environment(base, stop=None):
    probe, trace = base / "probe", base / "trace"
    probe.mkdir()
    trace.mkdir()
    (probe / "sitecustomize.py").write_text(PROBE, encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(probe), "HIMATE_P7_TRACE": str(trace)}
    if stop:
        environment["HIMATE_P7_STOP"] = stop
    return environment, trace


def test_probe_preserves_distinct_trace_files_when_process_id_is_reused(tmp_path):
    environment, trace = probe_environment(tmp_path)
    environment.pop("HIMATE_P7_STOP", None)
    command = "import os; os.getpid = lambda: 71384"
    saved = {}
    for marker in ("first", "second"):
        process = subprocess.run([sys.executable, "-c", command, marker], env=environment,
                                 capture_output=True, text=True, check=False)
        assert process.returncode == 0, process.stderr
        assert "Traceback" not in process.stderr, process.stderr
        if marker == "first":
            saved = {path: path.read_bytes() for path in trace.glob("*.json")}
            assert len(saved) == 1
    files = list(trace.glob("*.json"))
    assert len(files) == 2
    assert all(path.name.startswith("71384-") for path in files)
    assert all(path.read_bytes() == raw for path, raw in saved.items())
    runs = [json.loads(path.read_bytes()) for path in files]
    assert {tuple(run["argv"]) for run in runs} == {("-c", "first"), ("-c", "second")}
    assert all(run["calls"] == [] for run in runs)


def active(trial):
    return trial.record("artifacts/indexes/local/active.json")


def build(trial, operation):
    return trial.call("index-build", {"operation_id": operation})["data"]


def activate(trial, built, operation):
    return trial.call("index-activate", {"operation_id": operation,
        "generation_ref": built["generation_ref"], "expected_active": built["expected_active"]})


def test_generation_cas_cannot_be_rebased_to_a_new_active_pointer(tmp_path):
    trial = PublicP7(tmp_path)
    activate(trial, build(trial, "a"), "activate-a")
    first = build(trial, "first")
    activate(trial, build(trial, "second"), "activate-second")
    pointer = active(trial)
    denied = trial.call("index-activate", {"operation_id": "rebase", "generation_ref": first["generation_ref"],
        "expected_active": pointer["digest"]}, expected=3)
    assert denied["diagnostics"][0]["code"] == "ACTIVE_CHANGED"
    assert active(trial) == pointer


@pytest.mark.parametrize("replace_baseline", [True, False])
def test_regression_rejects_rebased_or_stale_activation_before_running_cases(tmp_path, replace_baseline):
    trial = PublicP7(tmp_path)
    first = build(trial, "first")
    activate(trial, build(trial, "second"), "activate-second")
    pointer = active(trial)
    denied = trial.call("regression", {"operation_id": "denied", "generation_ref": first["generation_ref"],
        "expected_active": pointer["digest"] if replace_baseline else first["expected_active"],
        "cases": [{"id": "empty", "query": "anything", "expected_order": []}]}, expected=3)
    assert denied["diagnostics"][0]["code"] == "ACTIVE_CHANGED"
    assert not (trial.root / ".build/operations/denied").exists()
    assert active(trial) == pointer


def test_verify_only_retains_the_report_baseline_after_a_later_generation_is_active(tmp_path):
    trial = PublicP7(tmp_path)
    first = build(trial, "first")
    report = trial.call("regression", {"operation_id": "original", "generation_ref": first["generation_ref"],
        "expected_active": first["expected_active"], "cases": [{"id": "empty", "query": "anything", "expected_order": []}]})
    activate(trial, build(trial, "later"), "activate-later")
    pointer = active(trial)
    verified = trial.call("regression-verify", {"operation_id": "recheck", "report_ref": report["data"]["report_ref"]})
    assert verified["phase"] == "verified" and verified["data"]["activated"] is False
    original = trial.record(report["data"]["report_ref"])
    assert original["expected_active"] is None and active(trial) == pointer
    denied = trial.call("regression-verify", {"operation_id": "rebase", "report_ref": report["data"]["report_ref"],
        "expected_active": pointer["digest"]}, expected=2)
    assert denied["diagnostics"][0]["code"] == "REGRESSION_INPUT_CHANGED"


@pytest.mark.parametrize("sealed_pointer", [False, True])
def test_forged_observation_and_unrooted_history_cannot_complete_an_unactivated_batch(tmp_path, sealed_pointer):
    trial = PublicP7(tmp_path)
    request = trial.content()
    environment, _ = probe_environment(tmp_path, "before_activation")
    stopped = trial.call("batch", request, expected=2, environment=environment)
    assert "SYNTHETIC_before_activation" in stopped["diagnostics"][0]["message"]
    built = trial.record(".build/operations/batch/batch-build.json")
    manifest = trial.record(built["generation_ref"])
    activate(trial, build(trial, "other"), "activate-other")
    current = active(trial)
    context = trial.context("batch")
    pointer = {"generation_ref": built["generation_ref"], "manifest_digest": manifest["digest"], "digest": "invented"}
    if sealed_pointer:
        pointer = context.seal({**{key: value for key, value in pointer.items() if key != "digest"},
            "generation_id": manifest["generation_id"], "channel": "local", "previous_active_digest": None}, "index_manifest")
        trial.write("artifacts/indexes/local/activations/" + pointer["digest"] + ".json", HELPER.canonical(pointer))
    forged = context.seal({"purpose": "index_activation_observation", "generation_ref": built["generation_ref"],
        "manifest_digest": manifest["digest"], "expected_active": built["expected_active"],
        "active_digest": pointer["digest"], "active_pointer": pointer}, "artifact_manifest")
    trial.write(".build/operations/batch/activation/forged.json", HELPER.canonical(forged))
    denied = trial.call("batch", request, expected=3)
    assert denied["diagnostics"][0]["code"] == "ACTIVE_CHANGED"
    assert active(trial) == current
    assert not (trial.root / ".build/operations/batch/batch-complete.json").exists()


def test_actual_activation_history_preserves_old_completion_after_a_later_active_generation(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    first = trial.call("batch", request)
    first_pointer = active(trial)
    (trial.root / ".build/operations/batch/batch-complete.json").unlink()
    for path in (trial.root / ".build/operations/batch/activation").glob("*.json"):
        path.unlink()
    activate(trial, build(trial, "later"), "activate-later")
    current = active(trial)
    assert current["previous_active_digest"] == first_pointer["digest"]
    resumed = trial.call("batch", request)
    assert resumed["phase"] == "completed" and resumed["data"]["generation_ref"] == first["data"]["generation_ref"]
    assert active(trial) == current
    assert trial.call("batch", request)["data"] == resumed["data"]


def test_self_sealed_completion_cannot_claim_a_generation_was_activated(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    environment, _ = probe_environment(tmp_path, "before_activation")
    trial.call("batch", request, expected=2, environment=environment)
    built = trial.record(".build/operations/batch/batch-build.json")
    completion = trial.context("batch").seal({"purpose": "batch_completion",
        "view_digest": trial.record(request["view_ref"])["digest"], "phase": "completed",
        "data": {"apply_result_ref": built["apply_result_ref"], "generation_ref": built["generation_ref"],
                 "report_ref": next((trial.root / ".build/operations/batch/regression").glob("*.json")).relative_to(trial.root).as_posix(),
                 "batch_complete": True, "activated": True}}, "artifact_manifest")
    trial.write(".build/operations/batch/batch-complete.json", HELPER.canonical(completion))
    denied = trial.call("batch", request, expected=3)
    assert denied["diagnostics"][0]["code"] == "BATCH_COMPLETION_CHANGED"
    assert not (trial.root / "artifacts/indexes/local/active.json").exists()


@pytest.mark.parametrize("replace_report", [False, True])
def test_resealed_build_and_completion_cannot_relabel_a_real_old_active_generation_as_this_batch(tmp_path, replace_report):
    trial = PublicP7(tmp_path)
    old = trial.call("batch", trial.content(operation="old"))
    pointer = active(trial)
    request = trial.content(operation="new")
    environment, _ = probe_environment(tmp_path, "before_activation")
    trial.call("batch", request, expected=2, environment=environment)
    context = trial.context("new")
    ref = ".build/operations/new/batch-build.json"
    built = trial.record(ref)
    original_report = next((trial.root / ".build/operations/new/regression").glob("*.json"))
    report_ref = original_report.relative_to(trial.root).as_posix()
    built["generation_ref"] = old["data"]["generation_ref"]
    built["expected_active"] = trial.record(built["generation_ref"])["expected_active"]
    trial.write(ref, HELPER.canonical(trial.modules["records"].seal(built)))
    if replace_report:
        report = trial.record(report_ref)
        report.update(generation_ref=built["generation_ref"], expected_active=built["expected_active"])
        report_ref = ".build/operations/new/regression/forged.json"
        trial.write(report_ref, HELPER.canonical(trial.modules["records"].seal(report)))
    completion = context.seal({"purpose": "batch_completion", "view_digest": trial.record(request["view_ref"])["digest"],
        "phase": "completed", "data": {"apply_result_ref": built["apply_result_ref"],
        "generation_ref": built["generation_ref"], "report_ref": report_ref,
        "batch_complete": True, "activated": True}}, "artifact_manifest")
    trial.write(".build/operations/new/batch-complete.json", HELPER.canonical(completion))
    denied = trial.call("batch", request, expected=3 if replace_report else 2)
    assert denied["diagnostics"][0]["code"] == ("BATCH_COMPLETION_CHANGED" if replace_report else "REGRESSION_BINDING_CHANGED")
    assert active(trial) == pointer
    assert trial.record(".build/operations/new/transaction/journal.json")["status"] == "committed"


@pytest.mark.parametrize("damage", ["missing_report", "changed_cases"])
def test_completed_batch_rejects_missing_actual_report_or_replaced_frozen_cases(tmp_path, damage):
    trial = PublicP7(tmp_path)
    request = trial.content()
    complete = trial.call("batch", request)
    pointer = active(trial)
    report_ref = complete["data"]["report_ref"]
    if damage == "missing_report":
        (trial.root / report_ref).unlink()
    else:
        report = trial.record(report_ref)
        report["cases"][0]["query"] = "replacement query"
        report["cases_digest"] = trial.modules["runtime"].digest(report["cases"])
        trial.write(report_ref, HELPER.canonical(trial.modules["records"].seal(report)))
    denied = trial.call("batch", request, expected=2)
    assert denied["status"] == "error"
    if damage == "changed_cases":
        assert denied["diagnostics"][0]["code"] == "REGRESSION_BINDING_CHANGED"
    assert active(trial) == pointer


def test_retry_omitting_an_explicit_intent_baseline_cannot_capture_a_later_active_pointer(tmp_path):
    trial = PublicP7(tmp_path)
    request = trial.content()
    environment, _ = probe_environment(tmp_path, "before_build")
    stopped = trial.call("batch", {**request, "expected_active": None}, expected=2, environment=environment)
    assert "SYNTHETIC_before_build" in stopped["diagnostics"][0]["message"]
    assert trial.record(".build/operations/batch/transaction/journal.json")["status"] == "committed"
    assert not (trial.root / ".build/operations/batch/batch-build.json").exists()
    activate(trial, build(trial, "other"), "activate-other")
    current = active(trial)
    denied = trial.call("batch", request, expected=3)
    assert denied["diagnostics"][0]["code"] == "ACTIVE_CHANGED"
    assert trial.record(".build/operations/batch/batch-intent.json")["requested_expected_active"] is None
    assert not (trial.root / ".build/operations/batch/batch-build.json").exists()
    assert len(list((trial.root / ".build/operations").glob("*/transaction/journal.json"))) == 1
    assert active(trial) == current


def test_real_p5_temporary_and_p7_actual_database_each_receive_one_full_verification(tmp_path, monkeypatch):
    environment, trace = probe_environment(tmp_path)
    for name in ("PYTHONPATH", "HIMATE_P7_TRACE"):
        monkeypatch.setenv(name, environment[name])
    spec = importlib.util.spec_from_file_location("counted_public_document_flow",
        ROOT / "himate-knowledge-wifi-mp/evals/tests/test_post_ingest_correction.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    workspace = tmp_path / "flow"
    workspace.mkdir()
    harness = fixture.frozen_harness(workspace)
    harness.write("docs-raw/specs/source.md", b"# Source\nSynthetic fixture statement for test readers.\n")
    result = fixture.complete_document_operation(harness, "counted", "create", "Synthetic fixture statement.")
    runs = [json.loads(path.read_bytes()) for path in trace.glob("*.json")]

    def count(run):
        return [row for row in run["calls"] if (row["module"], row["name"]) == ("indexing.py", "verify_database")]

    p5 = [run for run in runs if "review" in run["argv"]]
    p7 = [run for run in runs if "batch" in run["argv"]]
    assert len(p5) == len(p7) == 1
    assert len(count(p5[0])) == len(count(p7[0])) == 1
    assert "index-tmp" in count(p7[0])[0]["path"]
    manifest = harness.record(result["generation_ref"])
    assert HELPER.sha((harness.root / manifest["database_ref"]).read_bytes()) == manifest["database_digest"]
    assert manifest["index_verification"]["complete"] and manifest["index_verification"]["documents"] == 1
    prior = set(trace.glob("*.json"))
    harness.run("apply", {"operation_id": "independent", "generation_ref": result["generation_ref"],
        "verified_database": {"passed": True}, "passed": True}, "index-verify")
    later = [json.loads(path.read_bytes()) for path in set(trace.glob("*.json")) - prior]
    assert len(later) == 1 and len(count(later[0])) == 1


def test_database_observation_rejects_serialized_or_changed_bytes_and_rules(tmp_path):
    trial = PublicP7(tmp_path)
    indexing = trial.modules["indexing"]
    path = tmp_path / "verified.sqlite"
    observed = indexing.build_database([], trial.rules_digest, path, verified=True)
    assert indexing.reuse_database([], trial.rules_digest, path, observed)["complete"]
    for token, rules in (({"passed": True}, trial.rules_digest), (observed, "f" * 64)):
        with pytest.raises(ValueError, match="observation|bytes|rows"):
            indexing.reuse_database([], rules, path, token)
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="observation|bytes|rows"):
        indexing.reuse_database([], trial.rules_digest, path, observed)
