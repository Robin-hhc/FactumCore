"""Real public CLI patrol mechanisms over synthetic local materials only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


SPEC = importlib.util.spec_from_file_location("patrol_audit_fixture", Path(__file__).resolve().parents[2] / "support/stages/maintain_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
ROOT = Path(__file__).resolve().parents[5]
PIPE_SPEC = importlib.util.spec_from_file_location("patrol_manual_fixture", ROOT / "himate/himate-knowledge-wifi-mp/evals/support/manual.py")
MANUAL = importlib.util.module_from_spec(PIPE_SPEC)
PIPE_SPEC.loader.exec_module(MANUAL)


def repin(trial):
    """Only the isolated fixture lock changes; the development lock stays owned by integration."""
    lock_path = trial.root / "governance/framework.lock.yaml"
    value = yaml.safe_load(lock_path.read_bytes())
    for path in sorted((trial.root / "governance/contracts").glob("*.py")):
        key = "contracts/" + path.name
        value["files"][key] = {"path": "governance/" + key, "sha256": AUDIT.hashed(path.read_bytes())}
    for row in value["files"].values():
        row["sha256"] = AUDIT.hashed((trial.root / row["path"]).read_bytes())
    lock_path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    trial.rules = AUDIT.hashed(lock_path.read_bytes())


def configure_empty(trial):
    workspace = trial.root.parent
    (workspace / "main").mkdir(exist_ok=True)
    (workspace / "config.yml").write_bytes(AUDIT.canonical({"schema_version": "2.0", "workspace_id": "patrol-empty",
        "knowledge_roots": {"wifi": trial.root.name}, "code_root": "main", "modules": []}))


@pytest.fixture
def patrol_harness(harness):
    repin(harness)
    configure_empty(harness)
    return harness


def call(trial, request, action, expected=0):
    if hasattr(trial, "run"):
        return trial.run("maintain", request, action, expected)
    return trial.call("knowledge-maintain", request, action, expected)


def source_call(trial, request, action):
    if hasattr(trial, "run"):
        return trial.run("source", request, action)
    return trial.call("knowledge-source", request, action)


def fixed_plan(trial, operation="patrol"):
    result = call(trial, {"operation_id": operation}, "patrol-plan")
    return result, trial.record(result["data"]["plan_ref"])


def test_empty_index_rebuild_then_noop_has_a_real_successful_baseline(patrol_harness):
    p = patrol_harness
    result, plan = fixed_plan(p)
    assert result["phase"] == "needs_index"
    assert not (p.root / ".build/runtime/patrol-state.json").exists()
    indexed = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-reindex")
    assert indexed["phase"] == "indexed" and indexed["data"]["passed"] is True
    retry = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-reindex")
    assert retry["phase"] == "indexed" and retry["data"]["activated"] is True
    completed = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert completed["phase"] == "completed", completed
    assert (p.root / result["data"]["plan_ref"]).exists()
    again, observed = fixed_plan(p, "next")
    assert again["phase"] == "unchanged" and observed["force_full"] is False
    assert observed["counts"]["code_files_checked"] == 0
    assert call(p, {"operation_id": "next", "plan_ref": again["data"]["plan_ref"]}, "patrol-complete")["phase"] == "completed"


def test_same_operation_reentry_checks_new_raw_instead_of_trusting_saved_plan(patrol_harness):
    p = patrol_harness
    result, saved = fixed_plan(p)
    before = (p.root / result["data"]["plan_ref"]).read_bytes()
    assert fixed_plan(p)[1] == saved
    p.write("docs-raw/specs/new.md", b"# New original\n")
    changed = call(p, {"operation_id": "patrol"}, "patrol-plan", expected=3)
    assert changed["diagnostics"][0]["code"] == "PATROL_INPUT_CHANGED", changed
    assert (p.root / result["data"]["plan_ref"]).read_bytes() == before
    assert not (p.root / ".build/runtime/patrol-state.json").exists()


def test_two_ready_plans_cannot_overwrite_a_concurrent_successful_baseline(patrol_harness):
    p = patrol_harness
    first, _ = fixed_plan(p, "one")
    second, _ = fixed_plan(p, "two")
    call(p, {"operation_id": "one", "plan_ref": first["data"]["plan_ref"]}, "patrol-reindex")
    assert call(p, {"operation_id": "one", "plan_ref": first["data"]["plan_ref"]}, "patrol-complete")["phase"] == "completed"
    baseline = (p.root / ".build/runtime/patrol-state.json").read_bytes()
    stale = call(p, {"operation_id": "two", "plan_ref": second["data"]["plan_ref"]}, "patrol-complete")
    assert stale["phase"] == "pending"
    assert stale["data"]["reasons"][0]["code"] == "PATROL_BASELINE_CHANGED"
    assert (p.root / ".build/runtime/patrol-state.json").read_bytes() == baseline


def test_repository_recheck_gap_cannot_advance_a_ready_plan(patrol_harness, monkeypatch):
    p = patrol_harness
    result, _ = fixed_plan(p)
    request = {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}
    call(p, request, "patrol-reindex")
    ctx = AUDIT.operation_context(p, request, "patrol-complete")
    git = AUDIT.public_module("patrol_git")
    original = git.observe_repositories

    def unavailable(*args, **kwargs):
        observed = original(*args, **kwargs)
        return {**observed, "gaps": [{"code": "PATROL_GIT_UNAVAILABLE", "reason": "synthetic observation failure"}], "complete": False}

    monkeypatch.setattr(git, "observe_repositories", unavailable)
    data, phase = AUDIT.public_module("patrol").execute(ctx)
    assert phase == "pending"
    assert data["reasons"][0]["code"] == "PATROL_GIT_RECHECK_UNAVAILABLE"
    assert not (p.root / ".build/runtime/patrol-state.json").exists()


@pytest.mark.parametrize("change", ["insert", "body", "delete", "rename-symbol", "ambiguous", "move", "crlf"])
def test_direct_code_cases_are_classified_without_rewriting_old_locators(harness, change):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("current", "guidance", "historical"))
    if change == "insert":
        source.write_bytes(b"// inserted\n\n" + raw)
    elif change == "body":
        source.write_bytes(raw.replace(b"1", b"2"))
    elif change == "crlf":
        source.write_bytes(raw.replace(b"\n", b"\r\n"))
    elif change == "delete":
        source.unlink()
    elif change == "move":
        source.rename(source.with_name("moved.c"))
    elif change == "rename-symbol":
        source.write_bytes(raw.replace(b"selected_fixture", b"other_fixture"))
    else:
        source.write_bytes(raw + raw)
    protected = AUDIT.protected_bytes(harness)
    result, plan = fixed_plan(harness)
    assert result["phase"] == "needs_ingest", result
    effects = {row["claims"][0]["usage"]: row["effect"] for row in plan["references"]}
    assert effects["current"] == "current_reference_needs_review"
    assert effects["historical"] == "historical_reference"
    resolved = change in {"insert", "body", "crlf"}
    assert effects["guidance"] == ("guidance_navigation_resolved" if resolved else "guidance_navigation_needs_review")
    assert plan["source_request"]["unit_ids"] == []
    assert "audit-current" in plan["source_request"]["candidate_card_ids"]
    assert "audit-historical" not in plan["source_request"]["candidate_card_ids"]
    if change == "insert":
        row = next(row for row in plan["references"] if row["claims"][0]["usage"] == "guidance")
        assert row["old_locator"] == {"kind": "lines", "start": 1, "end": 1}
        assert row["code_navigation"]["range"]["start_line"] == 3
    material = source_call(harness, result["data"]["source_request"], "prepare")
    assert material["phase"] == "prepared", material
    prepared = harness.record(material["data"]["material_ref"])
    assert "audit-current" in {row["card_id"] for row in prepared["candidates"]}
    assert {path: value for path, value in AUDIT.protected_bytes(harness).items()
            if "logs/patrol/" not in path.replace("\\", "/")} == protected
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


def test_changed_partially_parsed_symbol_is_handed_to_ingest_without_claiming_absence(harness):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance",), source_bytes=
        b"int selected_fixture(void) { return 1; }\nint broken(int value { return 0; }\n")
    source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    before = AUDIT.protected_bytes(harness)
    result, planned = fixed_plan(harness)
    assert result["phase"] == "needs_ingest", result
    assert planned["complete"] is True and planned["gaps"] == []
    row, = planned["references"]
    assert row["code_navigation"]["status"] == "unavailable"
    assert row["code_navigation"]["partial_parse"] is True
    assert row["code_navigation"]["matches"] == []
    assert row["gaps"] == [{"code": "CODE_SYMBOL_UNAVAILABLE", "reason":
        "Source contains uncertain syntax for this symbol; uniqueness or absence cannot be established"}]
    assert row["effect"] == "guidance_navigation_needs_review"
    assert planned["candidate_card_ids"] == ["audit-guidance"]
    target, = planned["source_request"]["targets"]
    assert target["relative_path"] == "file.c"
    assert target["expected_fingerprint"] == AUDIT.hashed(source.read_bytes())
    scan = harness.record(planned["scan_ref"])
    assert scan["current_context"]["affected_claims"][0]["reason"] == "code_navigation_unavailable"
    prepared = source_call(harness, result["data"]["source_request"], "prepare")
    material = harness.record(prepared["data"]["material_ref"])
    assert material["current_code"] and len(material["candidates"]) == 1
    assert {path: value for path, value in AUDIT.protected_bytes(harness).items()
            if "logs/patrol/" not in path.replace("\\", "/")} == before
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


@pytest.mark.parametrize("fault", ["unreadable", "old-evidence", "unauthorized"])
def test_partial_parser_handoff_never_hides_material_or_authorization_failures(harness, fault):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance",), source_bytes=
        b"int selected_fixture(void) { return 1; }\nint broken(int value { return 0; }\n")
    source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    if fault == "unreadable":
        source.unlink()
        source.mkdir()
    elif fault == "old-evidence":
        lock = yaml.safe_load((harness.root / "governance/sources.lock.yaml").read_bytes())
        recovery = lock["snapshots"][0]["recovery"]
        (harness.root / recovery.get("reference", recovery.get("path"))).unlink()
    else:
        configuration = harness.base / "config.yml"
        value = yaml.safe_load(configuration.read_bytes())
        value["modules"] = []
        configuration.write_text(yaml.safe_dump(value), encoding="utf-8")
    result, planned = fixed_plan(harness)
    assert result["phase"] == "blocked", result
    assert planned["complete"] is False and planned["gaps"]
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


@pytest.mark.parametrize("binding", ["sha256", "config_digest"])
def test_partial_parser_handoff_requires_the_same_current_file_and_configuration(harness, monkeypatch, binding):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance",), source_bytes=
        b"int selected_fixture(void) { return 1; }\nint broken(int value { return 0; }\n")
    source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    context = AUDIT.operation_context(harness, {"operation_id": "binding-drift"}, "patrol-plan")
    resources = AUDIT.public_module("source_resources")
    original = resources.resolve_code_navigation

    def other_binding(*args, **kwargs):
        return {**original(*args, **kwargs), binding: "0" * 64}

    monkeypatch.setattr(resources, "resolve_code_navigation", other_binding)
    data, phase = AUDIT.public_module("patrol").execute(context)
    assert phase == "blocked" and data["complete"] is False
    assert any(row["code"] == "CODE_SYMBOL_UNAVAILABLE" for row in data["gaps"])
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


def pipeline(tmp_path):
    p = MANUAL.ManualPipeline(tmp_path)
    repin(p)
    configure_empty(p)
    return p


def publish_plan(p, result, card_id="patrol-card"):
    op = result["data"]["source_request"]["operation_id"]
    prepared = p.call("knowledge-source", result["data"]["source_request"], "prepare")
    material_ref = prepared["data"]["material_ref"]
    bundle_ref = p.record(material_ref)["bundle_ref"]
    scan_ref = result["data"]["scan_ref"]
    view = p.view(op, bundle_ref, card_id, p.card(card_id, p.record(bundle_ref)),
                  scan_ref=scan_ref, material_ref=material_ref,
                  queries=[{"id": "patrol-published", "query": "capture", "required": [card_id]}])
    p.review(op, view)
    record = p.call("knowledge-source", {"operation_id": op, "scan_ref": scan_ref, "view_ref": view,
        "disposition_preview_ref": p.record(view)["disposition_preview_ref"]}, "record")["data"]["ingest_record_ref"]
    applied = p.call("knowledge-apply", {"operation_id": op, "view_ref": view, "ingest_record_ref": record}, "batch")
    return applied


def test_real_p1_p7_publication_cleanup_and_patrol_completion_roundtrip(tmp_path):
    p = pipeline(tmp_path)
    p.write("docs-raw/specs/rule.md", b"# Source\nCapture marker is a documented rule.\n")
    result, _ = fixed_plan(p)
    assert result["phase"] == "needs_ingest"
    applied = publish_plan(p, result)
    assert applied["data"]["batch_complete"] is True
    completed = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"],
        "completion_ref": applied["data"]["completion_ref"]}, "patrol-complete")
    assert completed["phase"] == "completed", completed
    assert (p.root / result["data"]["plan_ref"]).is_file()
    assert (p.root / result["data"]["scan_ref"]).is_file()
    following, plan = fixed_plan(p, "next")
    assert following["phase"] == "unchanged", following
    assert plan["required_units"] == [] and plan["candidate_card_ids"] == []


def test_new_raw_and_repair_candidate_raw_are_an_explicit_union(tmp_path):
    p = pipeline(tmp_path)
    old_raw = "docs-raw/specs/rule.md"
    p.write(old_raw, b"# Source\nCapture marker is a documented rule.\n")
    first, _ = fixed_plan(p, "initial")
    publish_plan(p, first)
    # Existing card is a repair candidate even though its original bytes did
    # not change. A new raw must still be included in the same handoff.
    state = {"schema_version": "2.0", "record_kind": "maintenance_state", "operation_id": "restriction",
        "rules_digest": p.rules, "tool_identity": p.record(first["data"]["plan_ref"])["tool_identity"],
        "validity_epoch": 1, "knowledge_apply_watermark": None, "observed_sources": {}, "processed_event_ids": [],
        "pending_event_ids": [], "pending_events": [], "impact_scan_watermark": None,
        "blocked_claims": [{"card_id": "patrol-card", "claim_id": "c1", "reason": "pending_review"}]}
    records = AUDIT.public_module("records")
    p.write("logs/events/state.json", AUDIT.canonical(records.seal(state)))
    p.write("docs-raw/specs/new.md", b"# New\nNew material.\n")
    result, plan = fixed_plan(p, "repair")
    assert result["phase"] == "needs_ingest", result
    assert {row["path"] for row in plan["required_units"]} == {old_raw, "docs-raw/specs/new.md"}
    prepared = p.call("knowledge-source", result["data"]["source_request"], "prepare")
    material = p.record(prepared["data"]["material_ref"])
    assert {row["path"] for row in material["units"]} >= {old_raw, "docs-raw/specs/new.md"}
    assert [row["card_id"] for row in material["candidates"]] == ["patrol-card"]


def test_actual_p7_cleanup_failure_blocks_next_round_and_requires_exact_resume(tmp_path, monkeypatch):
    p = pipeline(tmp_path)
    p.write("docs-raw/specs/rule.md", b"# Source\nCapture marker is a documented rule.\n")
    result, _ = fixed_plan(p)
    probe = p.base / "cleanup-probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text(
        "from pathlib import Path\noriginal = Path.unlink\n"
        "def denied(path, *args, **kwargs):\n"
        "    if path.as_posix().endswith('/.build/operations/patrol/final-view.json'):\n"
        "        raise PermissionError('synthetic cleanup failure')\n"
        "    return original(path, *args, **kwargs)\n"
        "Path.unlink = denied\n", encoding="utf-8")
    with monkeypatch.context() as environment:
        environment.setenv("PYTHONPATH", str(probe))
        applied = publish_plan(p, result)
    assert applied["data"]["published"] is True and applied["data"]["batch_complete"] is False, applied
    following, plan = fixed_plan(p, "next")
    assert following["phase"] == "blocked", following
    assert plan["pending_publications"][0]["resume_request"] == {"operation_id": "patrol"}
    assert call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")["phase"] == "pending"
    assert not (p.root / ".build/runtime/patrol-state.json").exists()
    resumed = p.call("knowledge-apply", {"operation_id": "patrol"}, "batch")
    assert resumed["data"]["batch_complete"] is True
    finished = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished


def test_missing_real_p7_and_new_raw_drift_never_advance_baseline(patrol_harness):
    p = patrol_harness
    p.write("docs-raw/specs/new.md", b"# Original\n")
    result, _ = fixed_plan(p)
    incomplete = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"],
        "passed": True, "batch_complete": True}, "patrol-complete")
    assert incomplete["phase"] == "pending"
    assert not (p.root / ".build/runtime/patrol-state.json").exists()
    p.write("docs-raw/specs/new.md", b"# Changed\n")
    assert call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")["phase"] == "pending"
    assert not (p.root / ".build/runtime/patrol-state.json").exists()


def without_parser(trial, request, action, *, expect_parser=False):
    """Observe the real target CLI without relying on blocked site customization."""
    probe = trial.base / "parser-probe" / action
    probe.mkdir(parents=True)
    marker = probe / "called"
    parser_path = (trial.root / "governance/contracts/code_symbols.py").resolve()
    # This trusted test shim profiles the verified contract in a new process.
    # Execute this fixture's own entry point: dispatching from the development
    # root would spawn another interpreter and lose this process-local probe.
    shim = probe / "run_with_parser_probe.py"
    shim.write_text(
        "import runpy\nimport sys\nfrom pathlib import Path\n"
        "entry, target, marker, *arguments = sys.argv[1:]\n"
        "target = Path(target).resolve()\n"
        "def profile(frame, event, arg):\n"
        "    if event == 'call' and frame.f_code.co_name == '_parse':\n"
        "        if Path(frame.f_code.co_filename).resolve() == target:\n"
        "            Path(marker).write_text(str(target), encoding='utf-8')\n"
        "            raise RuntimeError('synthetic parser probe')\n"
        "sys.argv = [entry, *arguments]\n"
        "sys.setprofile(profile)\n"
        "try:\n"
        "    runpy.run_path(entry, run_name='__main__')\n"
        "finally:\n"
        "    sys.setprofile(None)\n", encoding="utf-8")
    incoming, outgoing = probe / "in.json", probe / "out.json"
    incoming.write_bytes(AUDIT.canonical(request))
    process = subprocess.run([sys.executable, "-X", "utf8", str(shim),
        str(trial.root / "knowledge.py"), str(parser_path), str(marker), "maintain", "--json",
        "--knowledge-root", str(trial.root), "--rules-digest", trial.rules,
        "--input", str(incoming), "--output", str(outgoing), "--action", action],
        capture_output=True)
    (probe / "stdout.log").write_bytes(process.stdout)
    (probe / "stderr.log").write_bytes(process.stderr)
    result = json.loads(outgoing.read_bytes() if outgoing.exists() else process.stdout)
    if expect_parser:
        assert marker.exists(), "fresh code did not reach the instrumented parser"
        assert marker.read_text(encoding="utf-8") == str(parser_path)
        assert process.returncode != 0 or result.get("phase") != "unchanged", result
    else:
        assert process.returncode == 0, result
        assert not marker.exists(), "unchanged patrol unexpectedly invoked Tree-sitter"
    return result


@pytest.mark.parametrize("git_dirty", [False, True])
def test_successful_baseline_skips_parser_for_unchanged_or_same_dirty_bytes(harness, git_dirty):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance", "historical"))
    if git_dirty:
        for args in (["init"], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "add", "file.c"],
                     ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture"]):
            result = subprocess.run(["git", "-C", str(source.parent), *args], capture_output=True)
            assert result.returncode == 0, result.stderr
        source.write_bytes(raw + b"// still dirty after successful patrol\n")
    first, _ = fixed_plan(harness, "initial")
    assert first["phase"] == "needs_index", first
    call(harness, {"operation_id": "initial", "plan_ref": first["data"]["plan_ref"]}, "patrol-reindex")
    done = call(harness, {"operation_id": "initial", "plan_ref": first["data"]["plan_ref"]}, "patrol-complete")
    assert done["phase"] == "completed", done
    second = without_parser(harness, {"operation_id": "second"}, "patrol-plan")
    assert second["phase"] == "unchanged", second
    assert second["data"]["counts"]["code_files_deep_checked"] == 0
    finished = without_parser(harness, {"operation_id": "second", "plan_ref": second["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished


def test_parser_probe_reaches_fresh_code_without_a_successful_baseline(harness):
    repin(harness)
    AUDIT.code_fixture(harness, ("guidance", "historical"))
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()
    result = without_parser(harness, {"operation_id": "fresh"}, "patrol-plan", expect_parser=True)
    assert result.get("phase") != "unchanged", result
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


def test_persisted_freshness_exception_stays_valid_in_following_round(harness):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance", "historical"))
    source.write_bytes(b"// shifted\n" + raw)
    ctx = AUDIT.operation_context(harness, {"operation_id": "event"}, "status")
    state = ctx.modules["maintenance"].state(ctx)
    state["blocked_claims"] = [{"card_id": "audit-" + usage, "claim_id": "audit-" + usage + "-claim",
                                "reason": "source_changed", "source_id": "selected-code"}
                               for usage in ("guidance", "historical")]
    ctx.save("logs/events/state.json", ctx.seal(state, "maintenance_state"))
    durable = (harness.root / "logs/events/state.json").read_bytes()
    result, _ = fixed_plan(harness, "initial")
    assert result["phase"] == "needs_index", result
    call(harness, {"operation_id": "initial", "plan_ref": result["data"]["plan_ref"]}, "patrol-reindex")
    finished = call(harness, {"operation_id": "initial", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished
    next_round, plan = fixed_plan(harness, "following")
    assert next_round["phase"] == "unchanged", next_round
    assert plan["candidate_card_ids"] == []
    assert (harness.root / "logs/events/state.json").read_bytes() == durable


def test_unchanged_code_with_missing_code_ref_is_a_repair_candidate(harness):
    repin(harness)
    AUDIT.code_fixture(harness, ("guidance",))
    path = harness.root / "knowledge/rules/audit-guidance.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(header)
    del metadata["sources"][0]["code_ref"]
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
    result, plan = fixed_plan(harness)
    assert result["phase"] == "needs_ingest", result
    assert plan["candidate_card_ids"] == ["audit-guidance"]
    assert plan["structural_findings"][0]["code"] == "CODE_REF_REQUIRED"


@pytest.mark.parametrize("partial_parse", [False, True])
def test_metadata_only_broken_reference_cannot_be_hidden_by_real_record_only_skip(harness, partial_parse):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance",), source_bytes=
        b"int still_fixture(void) { return 1; }\nint selected_fixture(void) { return 2; }\n"
        + (b"int broken(int value { return 0; }\n" if partial_parse else b""))
    path = harness.root / "knowledge/rules/audit-guidance.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(header)
    extra = json.loads(json.dumps(metadata["sources"][0]))
    extra["evidence_ref"] = "metadata-only"
    extra["locator"] = {"kind": "lines", "start": 2, "end": 2}
    metadata["sources"][0]["code_ref"]["name"] = "still_fixture"
    metadata["sources"].append(extra)
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body, encoding="utf-8")
    source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    result, planned = fixed_plan(harness)
    assert result["phase"] == "needs_ingest", result
    assert planned["candidate_card_ids"] == ["audit-guidance"]
    scan = harness.record(result["data"]["scan_ref"])
    assert scan["units"] == [] and scan["current_context"]["affected_claims"]
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                    "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "skip",
                    "reason": "Synthetic author deliberately leaves metadata unchanged"}
                   for row in scan["current_context"]["affected_claims"]]
    record = harness.run("source", {"operation_id": "patrol", "scan_ref": result["data"]["scan_ref"],
        "dispositions": [], "maintenance_dispositions": maintenance}, "record")
    applied = harness.run("apply", {"operation_id": "patrol", "ingest_record_ref": record["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True
    complete = call(harness, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert complete["phase"] == "pending", complete
    assert complete["data"]["reasons"][0]["code"] == "PATROL_REFERENCE_PENDING"
    assert not (harness.root / ".build/runtime/patrol-state.json").exists()


@pytest.mark.parametrize("retire", [False, True])
@pytest.mark.parametrize("partial_parse", [False, True])
def test_pure_code_symbol_repair_runs_real_p3_p7_and_completes(harness, retire, partial_parse):
    repin(harness)
    source, raw, _, checkout = AUDIT.code_fixture(harness, ("guidance",), source_bytes=
        b"int selected_fixture(void) { return 1; }\n"
        + (b"int broken(int value { return 0; }\n" if partial_parse else b""))
    # This scenario repairs guidance navigation, with no current implementation
    # Claim or build/runtime assertion. Preserve its document-review contract.
    initial_path = harness.root / "knowledge/rules/audit-guidance.md"
    _, initial_header, initial_body = initial_path.read_text(encoding="utf-8").split("---", 2)
    initial_metadata = yaml.safe_load(initial_header)
    initial_metadata["review_mode"] = "manual_document"
    initial_path.write_text("---\n" + yaml.safe_dump(initial_metadata, sort_keys=False) + "---" + initial_body, encoding="utf-8")
    if retire:
        source.unlink()
    else:
        source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    result, planned = fixed_plan(harness)
    assert result["phase"] == "needs_ingest", result
    if partial_parse and not retire:
        unresolved, = planned["references"]
        assert unresolved["code_navigation"]["status"] == "unavailable"
        assert unresolved["code_navigation"]["partial_parse"] is True
        # The fixed checker used by P4 still rejects the old live reference;
        # allowing material handoff does not turn uncertain navigation into pass.
        fixed = harness.record(AUDIT.lint_report(harness, checkout))
        assert any(row["code"] == "CODE_SYMBOL_UNAVAILABLE" for row in fixed["findings"])
        assert fixed["complete"] is False
    scan_ref = result["data"]["scan_ref"]
    scan = harness.record(scan_ref)
    assert scan["units"] == []
    assert bool(planned["source_request"]["targets"]) is not retire
    prepared = harness.run("source", result["data"]["source_request"], "prepare")
    material_ref = prepared["data"]["material_ref"]
    material = harness.record(material_ref)
    bundle = harness.record(material["bundle_ref"])
    if not retire:
        assert material["current_code"] and material["units"][0]["origin"] == "explicit_target"
    card_id, claim_id = "audit-guidance", "audit-guidance-claim"
    path = harness.root / "knowledge/rules/audit-guidance.md"
    _, header, body = path.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(header)
    if not retire:
        metadata["sources"][0]["snapshot_id"] = bundle["snapshots"][0]["snapshot_id"]
        metadata["sources"][0]["code_ref"]["name"] = "renamed_fixture"
    candidate = harness.write(".build/candidates/repaired.md", ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode())
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                    "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "content",
                    "reason": "Read exact renamed implementation and preserve guidance"}
                   for row in scan["current_context"]["affected_claims"]]
    unit_ids = sorted({row["unit_id"] for row in maintenance})
    queries = [{"id": "find-code", "query": card_id, "purpose": "historical", "required": [card_id],
                "context": {"target_id": "chip12-host", "chip": "chip12", "side": "host"}}]
    authored = harness.run("change-plan", {"operation_id": "patrol", "scan_ref": scan_ref,
        "material_ref": material_ref, "author_id": "synthetic-author", "units": [], "maintenance_units": maintenance,
        "claim_changes": [{"unit_ids": unit_ids, "card_id": card_id, "claim_id": claim_id, "action": "retire" if retire else "update",
            "before": "Synthetic guidance with the old function navigation", "after": "Same guidance with verified renamed navigation",
            "conditions": "Existing declared host scope", "evidence": [{"source": metadata["sources"][0]["snapshot_id"], "locator": "line 1"}],
            "preserved": "Guidance text and historical old evidence remain recoverable", "reason": "Explicit symbol rename review"}],
        "card_actions": [{"card_id": card_id, "decision": "deprecate" if retire else "update", "author_id": "synthetic-author", "unit_ids": unit_ids,
                          "reason": "Fix the exact declared function identity"}], "target_queries": queries}, "plan")
    semantic = authored["data"]["semantic_plan_ref"]
    viewed = harness.run("view-materialize", {"operation_id": "patrol", "semantic_plan_ref": semantic,
        "material_ref": material_ref, "decisions": [{"candidate_id": card_id, "decision": "deprecate" if retire else "update",
        "reason": "Explicit fixture repair", "card_inputs": [] if retire else [candidate],
        **({"replaces": [card_id], "retired_claim_ids": [claim_id]} if retire else {})}]})
    view_ref = viewed["data"]["view_ref"]
    view = harness.record(view_ref)
    historical = {row["card_digest"]: str(harness.root / row["card_ref"]) for row in material["candidates"]}
    harness.run("lint", {"operation_id": "patrol", "view_ref": view_ref, "semantic_plan_ref": semantic,
        "reviewer_id": "synthetic-independent-reader", "independent_context": "fresh-code-repair-context",
        "sampled_unit_ids": unit_ids, "unreviewed_unit_ids": [], "findings": [],
        "reason": "Independent synthetic reader reviewed exact current implementation and guidance",
        "inputs": {"historical_card_objects": historical}}, "review")
    recorded = harness.run("source", {"operation_id": "patrol", "view_ref": view_ref,
        "disposition_preview_ref": view["disposition_preview_ref"]}, "record")
    record = harness.record(recorded["data"]["record_ref"])
    assert record["inventory"]["units"] == [] and record["maintenance_dispositions"]
    applied = harness.run("apply", {"operation_id": "patrol", "view_ref": view_ref,
        "ingest_record_ref": recorded["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True, applied
    finished = call(harness, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished
    if retire:
        assert fixed_plan(harness, "after-retirement")[0]["phase"] == "unchanged"
        baseline = (harness.root / ".build/runtime/patrol-state.json").read_bytes()
        lock = yaml.safe_load((harness.root / "governance/sources.lock.yaml").read_bytes())
        recovery = lock["snapshots"][0]["recovery"]
        (harness.root / recovery.get("reference", recovery.get("path"))).unlink()
        lost, _ = fixed_plan(harness, "old-evidence-lost")
        assert lost["phase"] == "blocked", lost
        pending = call(harness, {"operation_id": "old-evidence-lost", "plan_ref": lost["data"]["plan_ref"]}, "patrol-complete")
        assert pending["phase"] == "pending", pending
        assert (harness.root / ".build/runtime/patrol-state.json").read_bytes() == baseline


def test_published_code_only_defer_survives_byte_reversion_until_explicit_descendant_resolution(harness):
    repin(harness)
    source, raw, _, _ = AUDIT.code_fixture(harness, ("guidance",))
    source.write_bytes(raw.replace(b"selected_fixture", b"renamed_fixture"))
    initial, _ = fixed_plan(harness, "deferred")
    scan = harness.record(initial["data"]["scan_ref"])
    maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                    "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "defer",
                    "reason": "An independent judgment is still required"}
                   for row in scan["current_context"]["affected_claims"]]
    recorded = harness.run("source", {"operation_id": "deferred", "scan_ref": initial["data"]["scan_ref"],
        "dispositions": [], "maintenance_dispositions": maintenance}, "record")
    applied = harness.run("apply", {"operation_id": "deferred", "ingest_record_ref": recorded["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True
    refused = call(harness, {"operation_id": "deferred", "plan_ref": initial["data"]["plan_ref"]}, "patrol-complete")
    assert refused["phase"] == "pending" and refused["data"]["reasons"][0]["code"] == "PATROL_MAINTENANCE_PENDING"
    source.write_bytes(raw)
    next_round, plan = fixed_plan(harness, "resolved")
    assert next_round["phase"] == "needs_ingest", next_round
    assert plan["candidate_card_ids"] == ["audit-guidance"]
    next_scan = harness.record(next_round["data"]["scan_ref"])
    assert any(row["reason"] == "shared_pending_review" for row in next_scan["current_context"]["affected_claims"])
    resolution = [{**row, "outcome": "skip", "reason": "Read the reverted exact implementation; old navigation is valid"}
                  for row in maintenance]
    recorded = harness.run("source", {"operation_id": "resolved", "scan_ref": next_round["data"]["scan_ref"],
        "dispositions": [], "maintenance_dispositions": resolution}, "record")
    applied = harness.run("apply", {"operation_id": "resolved", "ingest_record_ref": recorded["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True
    finished = call(harness, {"operation_id": "resolved", "plan_ref": next_round["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished
    assert fixed_plan(harness, "clean")[0]["phase"] == "unchanged"


def test_real_record_only_all_skip_builds_missing_index_in_same_completion(patrol_harness):
    p = patrol_harness
    p.write("docs-raw/specs/low-value.md", b"# Deliberately skipped synthetic document\n")
    result, planned = fixed_plan(p)
    unit = planned["required_units"][0]
    recorded = p.run("source", {"operation_id": "patrol", "scan_ref": result["data"]["scan_ref"],
        "dispositions": [{"unit_id": unit["unit_id"], "action": "skip", "progress": "skipped",
            "reason": "Explicitly reviewed and excluded low-value synthetic input", "observed_fingerprint": unit["observed_fingerprint"],
            "adopted_fingerprint": None, "card_refs": [], "claim_refs": []}]}, "record")
    applied = p.run("apply", {"operation_id": "patrol", "ingest_record_ref": recorded["data"]["record_ref"]}, "batch")
    assert applied["data"]["batch_complete"] is True
    assert not (p.root / "artifacts/indexes/local/active.json").exists()
    finished = call(p, {"operation_id": "patrol", "plan_ref": result["data"]["plan_ref"]}, "patrol-complete")
    assert finished["phase"] == "completed", finished
    assert (p.root / "artifacts/indexes/local/active.json").exists()
    assert fixed_plan(p, "next")[0]["phase"] == "unchanged"


def test_unregistered_conflict_is_scoped_out_but_registered_and_io_gaps_block():
    patrol = AUDIT.public_module("patrol")
    registered = {"repo": {"used.c"}}
    unrelated = {"code": "PATROL_GIT_UNMERGED", "repo_id": "repo", "path": "unused.c", "reason": "conflict"}
    relevant = {**unrelated, "path": "used.c"}
    io_gap = {"code": "PATROL_GIT_UNAVAILABLE", "reason": "cannot read index"}
    assert patrol._repository_gaps({"complete": False, "gaps": [unrelated]}, registered) == []
    assert patrol._repository_gaps({"complete": False, "gaps": [unrelated, relevant, io_gap]}, registered) == [relevant, io_gap]
