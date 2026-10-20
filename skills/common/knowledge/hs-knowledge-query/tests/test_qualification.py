"""Same-generation qualification and source/relationship rejection boundaries."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


def load_node():
    scripts = Path(__file__).parents[1] / "scripts"
    previous = sys.modules.get("support")
    spec = importlib.util.spec_from_file_location("support", scripts / "support.py")
    support = importlib.util.module_from_spec(spec)
    sys.modules["support"] = support
    spec.loader.exec_module(support)
    try:
        spec = importlib.util.spec_from_file_location(
            "query_under_test", scripts / "node.py"
        )
        node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node)
    finally:
        if previous is None:
            sys.modules.pop("support", None)
        else:
            sys.modules["support"] = previous
    return node, support


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

    def call(skill, request, action):
        calls.append((skill, request, action))
        if skill == "hs-knowledge-apply":
            identity = request["card_path"].rsplit("/", 1)[1][:-3]
            return {
                "data": {
                    "result_verified": True,
                    "purpose": request.get("purpose"),
                    "current_code_proof_ref": request.get("current_code_proof_ref"),
                    "eligible_files": [
                        {
                            "path": cards[identity]["path"],
                            "sha256": cards[identity]["sha256"],
                        }
                    ],
                    "historical_files": [
                        {
                            "path": cards[identity]["path"],
                            "sha256": cards[identity]["sha256"],
                        }
                    ],
                }
            }
        source = request["source_ref"]
        return {
            "data": {
                "source_ref": source,
                "snapshot_digest": source["snapshot_id"],
                "current_source_matches": source["source_id"] not in stale,
            }
        }

    ctx = SimpleNamespace(
        root=tmp_path, modules=modules, rules={}, operation="query", call=call
    )
    return node, ctx, manifest, calls


def test_historical_load_uses_exact_historical_content_and_current_forwards_fresh_proof(
    tmp_path,
):
    value = card("a", review_mode="code_gate")
    node, ctx, manifest, calls = fixture_context(tmp_path, {"a": value})
    node.load_card(ctx, manifest, "a", "historical")
    assert calls[-1][1]["purpose"] == "historical"
    node.load_card(ctx, manifest, "a", "current")
    assert calls[-1][1]["current_code_proof_ref"].endswith("fresh-check.json")


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


def test_code_snapshot_mismatch_requires_current_authenticated_code_proof_but_raw_never_waives(
    tmp_path,
):
    values = {"a": card("a", review_mode="code_gate"), "b": card("b")}
    node, ctx, manifest, _ = fixture_context(
        tmp_path, values, stale=["a", "b"], code_sources=["a"]
    )
    evaluated = node.EligibilityEvaluator(
        ctx, manifest, {"purpose": "current", "context": {}}, {"blocked_claims": []}
    )
    assert evaluated.evaluate("a")[1] == {"c1"}
    assert evaluated.evaluate("b")[1] == set()


def test_fresh_code_proof_supersedes_only_code_source_blocks(tmp_path):
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
    assert evaluator.evaluate("a")[1] == {"c1"}
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
    ctx = SimpleNamespace(operation="query", call=lambda *args: {"data": fresh})
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
