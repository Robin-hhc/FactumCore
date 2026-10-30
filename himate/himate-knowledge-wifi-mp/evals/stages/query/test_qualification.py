"""Same-generation qualification and source/relationship rejection boundaries."""

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_node():
    public = Path(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py"
    spec = importlib.util.spec_from_file_location("qualification_contract_fixture", public)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    # Tests replace a real qualification collaborator; reload to isolate each case.
    return importlib.reload(fixture.module("query_runtime")), fixture.module("runtime")


def card(identity, dependency=None, *, review_mode="manual_document"):
    source = {
        "source_id": identity,
        "snapshot_id": identity + "-snapshot",
        "locator": {"kind": "lines", "start": 1, "end": 1},
    }
    relation = (
        []
        if not dependency
        else [
            {"type": dependency[0], "target_card_id": dependency[1], "context_ids": []}
        ]
    )
    return {
        "metadata": {
            "id": identity,
            "title": identity,
            "summary": identity,
            "lifecycle": "stable",
            "review_mode": review_mode,
            "relations": relation,
            "scope": {"applicability": "universal", "contexts": []},
        },
        "claims": [
            {
                "id": "c1",
                "text": identity,
                "usage": "current",
                "evidence_kind": "implementation",
                "scope": {"applicability": "universal", "contexts": []},
                "source_records": [source],
            }
        ],
    }


def fixture_context(tmp_path, cards, *, stale=None, code_sources=()):
    node, support = load_node()
    stale = set(stale or [])
    # These unit tests isolate eligibility/source decisions. The real module/Target
    # mapping check is covered through actual contracts in test_live_code_scope.
    node.validate_live_code_claim = lambda *args: None
    documents, qualifications, calls = {}, {}, []
    for identity, value in cards.items():
        ref = f"artifacts/indexes/local/g/cards/{identity}.md"
        path = tmp_path / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(identity.encode())
        value.update(
            path=f"knowledge/rules/{identity}.md", sha256=support.sha(identity.encode())
        )
        documents[identity] = {
            "path": value["path"],
            "sha256": value["sha256"],
            "blob_ref": ref,
        }
        qualifications[identity] = {
            "operation_id": "apply-" + identity,
            "apply_result_ref": f"logs/operations/apply-{identity}/apply-result.json",
            "current_code_proof_ref": "logs/operations/apply-"
            + identity
            + "/fresh-check.json",
        }
    manifest = {"documents": documents, "qualifications": qualifications}

    def scope(claim, context, purpose):
        conditions = claim.get("scope", {}).get("contexts", [])
        return not conditions or any(
            all(
                context.get(k) == v
                for k, v in row.items()
                if k in {"side", "target_id"}
            )
            for row in conditions
        )

    modules = {
        "indexing": SimpleNamespace(
            read_document=lambda raw, path, rules, **binding: cards[raw.decode()]
        ),
        "knowledge": SimpleNamespace(
            parse_card=lambda raw, path, rules: cards[raw.decode()], match_scope=scope
        ),
        "source_resources": SimpleNamespace(
            read_source_lock=lambda root: {
                "resources": [
                    {
                        "source_id": identity,
                        "kind": "code" if identity in code_sources else "raw",
                    }
                    for identity in cards
                ]
            }
        ),
    }

    def resolve_source(context, source, bundle=None):
        calls.append(("resolve_source", source))
        return {"source_ref": source, "snapshot_digest": source["snapshot_id"],
                "current_source_matches": source["source_id"] not in stale}

    modules["source_operations"] = SimpleNamespace(resolve_source=resolve_source)
    ctx = SimpleNamespace(root=tmp_path, modules=modules, rules={}, operation="query")

    return node, ctx, manifest, calls


def test_card_load_uses_exact_content_without_replaying_prior_skills(
    tmp_path,
):
    value = card("a", review_mode="code_gate")
    node, ctx, manifest, calls = fixture_context(tmp_path, {"a": value})
    node.load_card(ctx, manifest, "a", "historical")
    node.load_card(ctx, manifest, "a", "current")
    assert calls == []
    manifest["qualifications"] = {}
    assert node.load_card(ctx, manifest, "a", "current")["metadata"]["id"] == "a"


def test_optional_code_fingerprint_is_checked_from_root_config_without_catalog(tmp_path):
    value = card("a", review_mode="code_gate")
    node, ctx, manifest, calls = fixture_context(tmp_path, {"a": value})
    config = tmp_path / "config.yml"
    config.write_text("{}", encoding="utf-8")
    ctx.args = SimpleNamespace(catalog=None)
    observed = []
    ctx.modules["validation"] = SimpleNamespace(workspace_config_path=lambda root: config, load_yaml=lambda raw: {})
    ctx.modules["source_resources"].validate_current_code_identity = lambda *args: observed.append(args)
    identity = {"basis": "source", "repos": {"module": {"files": {"file.c": "a" * 64}}}}
    manifest["qualifications"]["a"].update(code_identity=identity, config_digest="b" * 64)
    node.load_card(ctx, manifest, "a")
    assert observed[0][:3] == (identity, config, "b" * 64)
    assert calls == []
    def changed(*args):
        raise ValueError("Actual code bytes changed")
    ctx.modules["source_resources"].validate_current_code_identity = changed
    stale = node.load_card(ctx, manifest, "a")
    assert stale["_portable_context_current"] is False
    assert stale["_context_gaps"][0]["code"] == "CURRENT_CODE_CONTEXT_CHANGED_OR_UNKNOWN"


@pytest.mark.parametrize("relation", ["requires", "derived_from"])
def test_stale_source_dependency_is_removed_even_when_downstream_source_is_current(
    tmp_path, relation
):
    values = {"a": card("a", (relation, "b")), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(tmp_path, values, stale=["b"])
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    assert evaluated.evaluate("a")[1] == set()


def test_related_to_does_not_propagate_staleness(tmp_path):
    values = {"a": card("a", ("related_to", "b")), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(tmp_path, values, stale=["b"])
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    assert evaluated.evaluate("a")[1] == {"c1"}


@pytest.mark.parametrize("relation", ["requires", "derived_from"])
def test_dependency_source_timeout_keeps_the_original_runtime_diagnostic(tmp_path, relation):
    values = {"a": card("a", (relation, "b")), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(tmp_path, values)
    original_call = ctx.modules["source_operations"].resolve_source
    failure = node.NodeError(
        "SIBLING_TIMEOUT", "Source resolver exceeded its call budget", "source-resolver", blocked=True
    )

    def resolve(context, source, bundle=None):
        if source["source_id"] == "b":
            raise failure
        return original_call(context, source, bundle)

    ctx.modules["source_operations"].resolve_source = resolve
    evaluator = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    with pytest.raises(node.NodeError) as raised:
        evaluator.evaluate("a")
    assert raised.value is failure


@pytest.mark.parametrize("code", ["SOURCE_UNAVAILABLE", "RECOVERY_UNAVAILABLE", "SOURCE_INPUT_UNAVAILABLE"])
def test_source_absence_still_filters_claims_and_reports_a_gap(tmp_path, code):
    node, ctx, manifest, _ = fixture_context(tmp_path, {"a": card("a")})

    def unavailable(*args):
        raise node.NodeError(code, "Exact source is unavailable", blocked=True)

    ctx.modules["source_operations"].resolve_source = unavailable
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    ).evaluate("a")
    assert evaluated[1] == set()
    assert evaluated[3][0]["code"] == "SOURCE_NOT_CURRENT"


def test_processing_review_status_does_not_gate_business_query(tmp_path):
    node, ctx, manifest, _ = fixture_context(tmp_path, {"a": card("a")})
    state = {"blocked_claims": [{"card_id": "a", "claim_id": "c1", "reason": "shared_pending_review", "conditions": {}}]}
    evaluated = node.EligibilityEvaluator(ctx, manifest, {"purpose": "guidance", "context": {}}, state).evaluate("a")
    assert evaluated[1] == {"c1"}
    assert evaluated[3] == []


def test_document_measurement_does_not_require_code_or_build_context(tmp_path):
    value = card("a")
    value["claims"][0].update(evidence_kind="measurement", verification_requirements=["runtime-support"])
    node, ctx, manifest, _ = fixture_context(tmp_path, {"a": value})
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    ).evaluate("a")
    assert evaluated[1] == {"c1"} and evaluated[3] == []


def test_portable_current_claim_is_independent_of_an_old_historical_code_reference(tmp_path):
    value = card("a", review_mode="code_gate")
    historical = {**value["claims"][0], "id": "old", "usage": "historical",
                  "source_records": [{"source_id": "old", "snapshot_id": "old-snapshot", "locator": {"kind": "lines", "start": 1, "end": 1}}]}
    value["claims"].append(historical)
    value["metadata"]["sources"] = [source for claim in value["claims"] for source in claim["source_records"]]
    node, ctx, manifest, _ = fixture_context(tmp_path, {"a": value}, stale=["old"], code_sources=["a", "old"])
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    ctx.args = SimpleNamespace(catalog=str(catalog), rules_digest="0" * 64)
    def registered_config(root, registrations, expected_rules):
        assert root == tmp_path and registrations is None and expected_rules == "0" * 64
        return tmp_path / "config.yml"
    ctx.modules["validation"] = SimpleNamespace(workspace_config_path=registered_config)
    ctx.modules["source_resources"].validate_current_code_identity = lambda *args: {}
    ctx.modules["source_resources"].read_source_lock = lambda root: {"resources": [{"source_id": identity, "kind": "code"} for identity in ("a", "old")]}
    ctx.modules["knowledge"].match_scope = lambda claim, context, purpose: purpose == "historical" or claim["usage"] == "current"
    manifest.update(channel="shared", publication={"verified_in_load_generation": True})
    manifest["qualifications"]["a"].update(kind="accepted_repository", code_identity={}, config_digest="a" * 64)
    evaluator = node.EligibilityEvaluator(ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []})
    assert evaluator.evaluate("a")[1] == {"c1"}
    original_call = ctx.modules["source_operations"].resolve_source
    def changed_current_source(context, source, bundle=None):
        response = original_call(context, source, bundle)
        response["current_source_matches"] = False
        return response
    ctx.modules["source_operations"].resolve_source = changed_current_source
    changed = node.EligibilityEvaluator(ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []})
    assert changed.evaluate("a")[1] == set()


def test_transitive_dependencies_do_not_need_query_term_hits(tmp_path):
    values = {
        "a": card("a", ("requires", "b")),
        "b": card("b", ("derived_from", "c")),
        "c": card("c"),
    }
    node, ctx, manifest, _ = fixture_context(tmp_path, values, stale=["c"])
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    assert evaluated.evaluate("a")[1] == set()


def test_changed_code_and_raw_snapshots_are_not_waived_by_workflow_proofs(
    tmp_path,
):
    values = {"a": card("a", review_mode="code_gate"), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(
        tmp_path, values, stale=["a", "b"], code_sources=["a"]
    )
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    assert evaluated.evaluate("a")[1] == set()
    assert evaluated.evaluate("b")[1] == set()


def test_old_workflow_proofs_do_not_override_explicit_source_restrictions(tmp_path):
    values = {"a": card("a", review_mode="code_gate"), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(tmp_path, values, code_sources=["a"])
    blocks = [
        {
            "card_id": identity,
            "claim_id": "c1",
            "source_id": identity,
            "old_snapshot_ids": [identity + "-snapshot"],
            "reason": "source_changed",
        }
        for identity in values
    ]
    evaluator = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": blocks}
    )
    assert evaluator.evaluate("a")[1] == set()
    assert evaluator.evaluate("b")[1] == set()
    blocks[0]["reason"] = "semantic_rejected"
    evaluator = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": blocks}
    )
    assert evaluator.evaluate("a")[1] == set()


def test_code_source_cas_rejects_change_after_current_proof_qualification(tmp_path):
    node, _ = load_node()
    source = {
        "source_ref": {"source_id": "code", "snapshot_id": "old"},
        "snapshot_digest": "fixed-old-snapshot",
        "current_source_sha256": "a" * 64,
        "current_code_verified": True,
        "current_source_matches": False,
    }
    fresh = {**source, "current_source_sha256": "b" * 64}
    ctx = SimpleNamespace(operation="query", modules={"source_operations": SimpleNamespace(resolve_source=lambda *args: fresh)})
    with pytest.raises(ValueError, match="changed"):
        node.refresh_sources(ctx, [source], "current", {"code"})


def test_dependency_context_is_checked_against_the_same_query_context(tmp_path):
    values = {"a": card("a", ("requires", "b")), "b": card("b")}
    values["a"]["metadata"]["scope"]["contexts"] = [
        {"context_id": "host", "side": "host"}
    ]
    values["a"]["metadata"]["relations"][0]["context_ids"] = ["host"]
    node, ctx, manifest, _ = fixture_context(tmp_path, values, stale=["b"])
    evaluator = node.EligibilityEvaluator(
        ctx,
        manifest,
        {"purpose": "current", "context": {"side": "device"}},
        {"blocked_claims": []},
    )
    assert evaluator.evaluate("a")[1] == {"c1"}
    evaluator = node.EligibilityEvaluator(
        ctx,
        manifest,
        {"purpose": "current", "context": {"side": "host"}},
        {"blocked_claims": []},
    )
    assert evaluator.evaluate("a")[1] == set()
