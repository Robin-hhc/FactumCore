"""P5 candidate queries use the real qualifier/ranker on a checked private DB."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("candidate_query_support", DOMAIN / "evals/support/contracts.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)


@pytest.fixture
def fixture(tmp_path):
    runtime = SUPPORT.module("runtime")
    records = SUPPORT.module("records")
    validation = SUPPORT.module("validation")
    modules = {name: SUPPORT.module(name) for name in (
        "knowledge", "indexing", "query_runtime", "index_runtime", "staging", "maintenance",
    )}
    modules.update(runtime=runtime, records=records, validation=validation)
    rules = {"rules_digest": "0" * 64,
             "schemas": {"record": json.loads((DOMAIN / "governance/schemas/records.schema.json").read_bytes())}}
    root = tmp_path / "knowledge"
    root.mkdir()
    ctx = runtime.OperationContext(root, {"operation_id": "preview"}, modules=modules,
        rules=rules, tool={"skill": "hs-knowledge-lint", "package_digest": "0" * 64,
                          "requirements_digest": "0" * 64, "runtime": "fixture"}, rules_digest=rules["rules_digest"])
    original = b"Capture marker is a documented rule.\n"
    original_path = root / "docs-raw/specs/original.md"
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(original)
    source = {"source_id": "source", "snapshot_id": "snapshot", "evidence_ref": "entry",
              "locator": {"kind": "lines", "start": 1, "end": 1}}
    metadata = {"schema_version": "2.0", "id": "rule", "profile": "rule", "title": "Capture marker",
        "summary": "Documented capture marker rule", "lifecycle": "stable", "review_mode": "manual_document",
        "scope": {"applicability": "universal", "contexts": []}, "aliases": [], "sources": [source],
        "claims": [{"id": "claim", "text_ref": "#claim", "evidence_kind": "design", "source_refs": ["entry"],
                    "context_ids": [], "usage": "current", "verification_requirements": []}], "relations": []}
    raw = ("---\n" + json.dumps(metadata) + "\n---\n# Capture marker\n<a id=\"claim\"></a>\nDocumented capture marker.\n").encode()
    card = modules["knowledge"].decode_card(raw, "knowledge/rules/rule.md", rules)
    lock = {"resources": [{"source_id": "source", "kind": "raw", "path": "docs-raw/specs/original.md"}],
            "snapshots": []}
    def resolve(context, reference, bundle=None):
        assert bundle is not None and bundle["resources"] == lock["resources"]
        return {"source_ref": reference, "source_kind": "raw", "resource": lock["resources"][0],
                "snapshot_digest": "1" * 64, "sha256": runtime.sha(original),
                "original_ref": "docs-raw/specs/original.md", "locator": reference["locator"],
                "current_source_sha256": runtime.sha(original), "current_source_matches": True}
    modules["source_operations"] = SimpleNamespace(resolve_source=resolve)
    modules["source_resources"] = SimpleNamespace(read_source_lock=lambda root: pytest.fail("Read old formal lock"))
    view = {"operation_id": "preview", "digest": "2" * 64, "staged_objects": [], "publication_plan": {"event_proposals": []}}
    return ctx, card, lock, view


@pytest.mark.parametrize("purpose,passed", [("implementation", False), ("current", True), ("guidance", True)])
def test_candidate_executes_real_scope_and_claim_assertions(fixture, tmp_path, purpose, passed):
    ctx, card, lock, view = fixture
    candidate = SUPPORT.module("candidate_queries")
    cases = [{"id": "capture", "query": "Capture marker", "purpose": purpose,
              "required": ["rule"], "expected_claim_ids": ["rule#claim"]}]
    temporary = ctx.root / ctx.base / "lint-index"
    temporary.mkdir(parents=True)
    with ctx.modules["indexing"].checked_database([card], ctx.rules, temporary) as (db, observed):
        result = candidate.run(ctx, view, {"rule": card}, lock,
            {card["path"]: card["raw"]}, db, observed, cases,
            state={"validity_epoch": 0, "blocked_claims": []})
    assert result["passed"] is passed
    assert result["status"] == ("passed" if passed else "failed")
    outcome = result["outcomes"][0]
    assert outcome["purpose"] == purpose
    assert outcome["actual_claim_ids"] == (["rule#claim"] if passed else [])
    assert not (ctx.root / "artifacts").exists()


def test_candidate_observation_cannot_be_supplied_by_json(fixture):
    ctx, _, _, _ = fixture
    with pytest.raises(ctx.modules["runtime"].NodeError) as error:
        ctx.modules["query_runtime"].search(ctx, {"query": "Capture marker", "evaluation": True},
                                          candidate={"passed": True})
    assert error.value.code == "INVALID_CANDIDATE_QUERY"


def evaluate(fixture, cases, *, metadata=None, body=None):
    ctx, card, lock, view = fixture
    if metadata is not None or body is not None:
        card = ctx.modules["knowledge"].decode_card(
            ("---\n" + json.dumps(metadata or card["metadata"]) + "\n---\n" + (body or card["body"])).encode(),
            card["path"], ctx.rules)
    temporary = ctx.root / ctx.base / "lint-index"
    temporary.mkdir(parents=True)
    with ctx.modules["indexing"].checked_database([card], ctx.rules, temporary) as (db, observed):
        return SUPPORT.module("candidate_queries").run(ctx, view, {"rule": card}, lock,
            {card["path"]: card["raw"]}, db, observed, cases,
            state={"validity_epoch": 0, "blocked_claims": []})


@pytest.mark.parametrize("change,purpose,context,passed", [
    ("guidance", "current", {}, False),
    ("guidance", "guidance", {}, True),
    ("unknown", "current", {}, False),
    ("unknown", "guidance", {}, True),
    ("constrained", "current", {"target_id": "target-a"}, True),
    ("constrained", "current", {"target_id": "target-b"}, False),
])
def test_candidate_uses_claim_usage_scope_and_actual_query_context(fixture, change, purpose, context, passed):
    _, card, _, _ = fixture
    metadata = card["metadata"]
    if change == "guidance":
        metadata["claims"][0]["usage"] = "guidance"
    elif change == "unknown":
        metadata["scope"] = {"applicability": "unknown", "contexts": []}
    else:
        metadata["scope"] = {"applicability": "constrained", "contexts": [
            {"context_id": "target", "target_id": "target-a"}]}
        metadata["claims"][0]["context_ids"] = ["target"]
    result = evaluate(fixture, [{"id": "scope", "query": "Capture marker", "purpose": purpose,
                                "context": context, "required": ["rule"]}], metadata=metadata)
    assert result["passed"] is passed


@pytest.mark.parametrize("change", ["keyword", "order", "forbidden", "claim", "forbidden_claim"])
def test_candidate_checks_lexical_hit_and_every_frozen_assertion(fixture, change):
    case = {"id": "assertion", "query": "Capture marker", "purpose": "current", "required": ["rule"]}
    case.update({"keyword": {"query": "absentuniqueidentifier"}, "order": {"expected_order": []},
                 "forbidden": {"forbidden": ["rule"]}, "claim": {"expected_claim_ids": ["rule#absent"]},
                 "forbidden_claim": {"forbidden_claim_ids": ["rule#claim"]}}[change])
    result = evaluate(fixture, [case])
    assert result["status"] == "failed" and result["passed"] is False


def test_candidate_accepts_intentional_empty_implementation_result(fixture):
    result = evaluate(fixture, [{"id": "exclude-design", "query": "Capture marker", "purpose": "implementation",
                                "expected_order": [], "forbidden": ["rule"]}])
    assert result["passed"] and result["outcomes"][0]["actual"] == []


def test_candidate_negative_query_does_not_treat_missing_source_as_success(fixture):
    ctx, _, _, _ = fixture
    def missing(*args):
        raise FileNotFoundError("Exact source payload is absent")
    ctx.modules["source_operations"].resolve_source = missing
    result = evaluate(fixture, [{"id": "exclude", "query": "Capture marker", "purpose": "current",
                                "expected_order": [], "forbidden": ["rule"]}])
    assert result["status"] == "incomplete" and not result["passed"]


@pytest.mark.parametrize("expected,passed", [("implementation", True), ("claim", False)])
def test_mixed_card_requires_the_expected_qualified_claim(fixture, expected, passed):
    _, card, _, _ = fixture
    metadata = card["metadata"]
    metadata["claims"].append({**metadata["claims"][0], "id": "implementation", "text_ref": "#implementation",
                               "evidence_kind": "implementation"})
    body = card["body"] + '\n<a id="implementation"></a>\nCapture marker implementation details.\n'
    result = evaluate(fixture, [{"id": "mixed", "query": "Capture marker", "purpose": "implementation",
                                "required": ["rule"], "expected_claim_ids": ["rule#" + expected]}],
                      metadata=metadata, body=body)
    assert result["passed"] is passed
    assert result["outcomes"][0]["actual_claim_ids"] == ["rule#implementation"]


@pytest.mark.parametrize("damage", ["database", "card", "formal_read"])
def test_private_observation_rejects_changed_bytes_and_formal_use(fixture, damage):
    ctx, card, lock, view = fixture
    candidate = SUPPORT.module("candidate_queries")
    temporary = ctx.root / ctx.base / "lint-index"
    temporary.mkdir(parents=True)
    with ctx.modules["indexing"].checked_database([card], ctx.rules, temporary) as (db, observed):
        inputs = candidate._prepare(ctx, view, {"rule": card}, lock, {card["path"]: card["raw"]},
                                    db, observed, {"validity_epoch": 0, "blocked_claims": []}, {})
        payload = {"query": "Capture marker", "purpose": "current", "generation_ref": inputs.generation_ref,
                   "evaluation": damage != "formal_read"}
        if damage == "database":
            inputs.database.write_bytes(b"damaged database")
        elif damage == "card":
            (ctx.root / inputs.manifest["documents"]["rule"]["blob_ref"]).write_bytes(b"damaged card")
        if damage == "card":
            result = ctx.modules["query_runtime"].search(ctx, payload, candidate=inputs)
            assert not result["matches"]
            assert result["gaps"][0]["code"] == "CARD_NOT_QUALIFIED"
        else:
            with pytest.raises(ctx.modules["runtime"].NodeError) as error:
                ctx.modules["query_runtime"].search(ctx, payload, candidate=inputs)
            assert error.value.code in {"CANDIDATE_QUERY_CHANGED", "INVALID_CANDIDATE_QUERY"}


def test_private_preview_handles_native_windows_long_paths(fixture):
    ctx, card, lock, view = fixture
    temporary = ctx.root / ctx.base / "lint-index" / ("deep" * 26)
    Path(ctx.modules["runtime"].native_path(temporary)).mkdir(parents=True)
    with ctx.modules["indexing"].checked_database([card], ctx.rules, temporary) as (db, observed):
        result = SUPPORT.module("candidate_queries").run(ctx, view, {"rule": card}, lock,
            {card["path"]: card["raw"]}, db, observed,
            [{"id": "capture", "query": "Capture marker", "required": ["rule"]}],
            state={"validity_epoch": 0, "blocked_claims": []})
    assert result["passed"], result


def test_formal_maintenance_change_during_preview_is_incomplete(fixture):
    ctx, _, _, _ = fixture
    previous = ctx.modules["source_operations"].resolve_source
    changed = False
    def changing(*args):
        nonlocal changed
        result = previous(*args)
        if not changed:
            state = ctx.modules["records"].seal({"schema_version": "2.0", "record_kind": "maintenance_state",
                "validity_epoch": 1, "blocked_claims": []})
            ctx.modules["runtime"].write_bytes(ctx.root, "logs/events/state.json",
                ctx.modules["runtime"].canonical(state), immutable=False)
            changed = True
        return result
    ctx.modules["source_operations"].resolve_source = changing
    result = evaluate(fixture, [{"id": "capture", "query": "Capture marker", "required": ["rule"]}])
    assert result["status"] == "incomplete" and not result["passed"]
    assert result["error"]["code"] == "VALIDITY_CHANGED"


def test_read_losing_one_claim_source_is_incomplete_with_its_gap(fixture, monkeypatch):
    ctx, card, _, _ = fixture
    metadata = card["metadata"]
    metadata["sources"].append({**metadata["sources"][0], "evidence_ref": "second", "snapshot_id": "second"})
    metadata["claims"].append({**metadata["claims"][0], "id": "second", "text_ref": "#second",
                               "source_refs": ["second"]})
    original_search = ctx.modules["query_runtime"].search
    original_resolve = ctx.modules["source_operations"].resolve_source
    reading = False

    def search(*args, **kwargs):
        nonlocal reading
        result = original_search(*args, **kwargs)
        assert result["matches"][0]["claim_ids"] == ["claim", "second"]
        reading = True
        return result

    def resolve(context, reference, bundle=None):
        if reading and reference["evidence_ref"] == "second":
            raise FileNotFoundError("Second Claim source became unavailable before same-generation read")
        return original_resolve(context, reference, bundle)

    monkeypatch.setattr(ctx.modules["query_runtime"], "search", search)
    monkeypatch.setattr(ctx.modules["source_operations"], "resolve_source", resolve)
    result = evaluate(fixture, [{"id": "both", "query": "Capture marker", "required": ["rule"],
                                "expected_claim_ids": ["rule#claim", "rule#second"]}], metadata=metadata,
                      body=card["body"] + '\n<a id="second"></a>\nCapture marker second rule.\n')
    assert result["status"] == "incomplete" and not result["passed"]
    outcome = result["outcomes"][0]
    assert outcome["status"] == "incomplete" and not outcome["passed"]
    assert any(gap["code"] == "SOURCE_NOT_CURRENT" and gap["claim_id"] == "second"
               for gap in outcome["gaps"])


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_query_report_retains_each_incomplete_case(fixture, monkeypatch, reverse):
    ctx, _, _, _ = fixture
    checks = SUPPORT.module("checks")
    outcomes = [{"case_id": "semantic", "purpose": "implementation", "status": "failed", "passed": False,
                 "expected": {"required": ["rule"]}, "actual": [], "actual_claim_ids": [], "gaps": []},
                {"case_id": "missing", "purpose": "current", "status": "incomplete", "passed": False,
                 "expected": {"required": ["rule"]}, "actual": [], "actual_claim_ids": [],
                 "gaps": [{"code": "SOURCE_NOT_CURRENT", "card_id": "rule", "claim_id": "second"}]}]
    if reverse:
        outcomes.reverse()
    monkeypatch.setattr(SUPPORT.module("candidate_queries"), "run", lambda *args, **kwargs: {
        "status": "failed", "passed": False, "outcomes": outcomes})
    candidate = ctx.modules["records"].seal({"schema_version": "2.0", "operation_id": ctx.operation})
    report = checks.run({"mode": "candidate", "root": ctx.root, "files": {}, "candidate": candidate},
                        {**ctx.rules, "knowledge_root": ctx.root}, query_context=ctx)
    assert all(item["code"].startswith("TARGET_QUERY_") for item in report["findings"]), report
    assert report["status"] == "failed" and report["exit_code"] == 1
    assert report["complete"] is False
    assert {(finding["code"], finding["case_id"]) for finding in report["findings"]} == {
        ("TARGET_QUERY_EXPECTATION_FAILED", "semantic"), ("TARGET_QUERY_INPUT_UNAVAILABLE", "missing")}
    semantic = next(item for item in report["findings"] if item["case_id"] == "semantic")
    assert semantic["return_to"] == "P2"
    unavailable = next(item for item in report["findings"] if item["case_id"] == "missing")
    expected_gap = next(item["gaps"] for item in outcomes if item["case_id"] == "missing")
    assert unavailable["purpose"] == "current" and unavailable["gaps"] == expected_gap
    assert "return_to" not in unavailable
    checks.validate_report(report)
    review = SUPPORT.runtime_module("stages.lint.review")
    review.finish(report, {"validation": ctx.modules["validation"], "checks": checks})
    assert report["complete"] is False
    checks.validate_report(report)
