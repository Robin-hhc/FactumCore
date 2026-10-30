"""A material's fixed code/config context cannot be silently substituted."""
import hashlib
import json


def sealed(harness, path, kind, **value):
    record = {"schema_version": "2.0", "record_kind": kind, "operation_id": "op",
        "rules_digest": harness.rules, "tool_identity": {"skill": "hs-fixture", "package_digest": "a" * 64,
        "runtime": "synthetic", "requirements_digest": "b" * 64}, **value}
    record["digest"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    harness.write(path, json.dumps(record).encode())
    return path


def prepare(harness):
    bundle_ref, bundle = harness.capture()
    contexts = [sealed(harness, ".build/operations/op/context-" + name + ".json", "project_context",
        state="complete", workspace_id=name, knowledge_root=".", config_digest="c" * 64, entries=[])
        for name in ("a", "b")]
    material_ref = sealed(harness, ".build/operations/op/material.json", "artifact_manifest",
        purpose="source_materials", bundle_ref=bundle_ref, bundle_digest=bundle["digest"],
        context_ref=contexts[0], context_digest=harness.record(contexts[0])["digest"],
        units=[{"unit_id": "u1", "origin": "explicit_target", "target_id": "u1", "source_kind": "raw",
                "path": "docs-raw/specs/source.md", "observed_fingerprint": bundle["snapshots"][0]["sha256"]}])
    semantic = harness.run("change-plan", {"operation_id": "op", "material_ref": material_ref,
        "author_id": "author", "units": [{"unit_id": "u1", "outcome": "content", "reason": "Actual selected source"}],
        "claim_changes": [{"unit_ids": ["u1"], "card_id": "new", "claim_id": "new-claim", "action": "create",
            "before": None, "after": "Actual fixture statement", "conditions": "unknown", "evidence": [{"source": "actual", "locator": "L1"}],
            "preserved": [], "reason": "New explicit topic"}],
        "card_actions": [{"card_id": "new", "decision": "create", "author_id": "author", "unit_ids": ["u1"], "reason": "New topic"}],
        "target_queries": [{"id": "q1", "query": "fixture statement", "required": ["new"]}]}, action="plan")
    candidate = harness.write(".build/candidates/new.md", harness.card("new", bundle))
    request = {"operation_id": "op", "semantic_plan_ref": semantic["data"]["semantic_plan_ref"],
        "decisions": [{"candidate_id": "new", "decision": "create", "reason": "Authored final content", "card_inputs": [candidate]}]}
    return request, contexts


def test_material_context_cannot_be_overridden_by_request(harness):
    request, contexts = prepare(harness)
    result = harness.run("view-materialize", {**request, "context_ref": contexts[1]}, expected=2)
    assert result["diagnostics"][0]["code"] == "MATERIAL_BINDING"
    assert not (harness.root / ".build/operations/op/final-view.json").exists()


def test_material_context_digest_must_match_actual_record(harness):
    request, contexts = prepare(harness)
    old = harness.record(contexts[0])
    for key in ("schema_version", "record_kind", "operation_id", "rules_digest", "tool_identity", "digest"):
        old.pop(key)
    sealed(harness, contexts[0], "project_context", **{**old, "workspace_id": "altered-context"})
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "MATERIAL_BINDING"
    assert not (harness.root / ".build/operations/op/final-view.json").exists()


def test_material_context_is_used_without_requiring_a_request_override(harness):
    request, contexts = prepare(harness)
    result = harness.run("view-materialize", request)
    view = harness.record(result["data"]["view_ref"])
    assert view["context_ref"] == contexts[0]
    assert view["input_snapshot"]["business_records"][contexts[0]]["digest"] == harness.record(contexts[0])["digest"]


def test_semantic_create_accepts_exact_card_mapping(harness):
    request, _ = prepare(harness)
    candidate = request.pop("decisions")[0]["card_inputs"][0]
    result = harness.run("view-materialize", {**request, "cards": {"new": candidate}})
    assert result["phase"] == "ready"
    assert harness.record(result["data"]["plan_ref"])["decisions"][0]["card_ids"] == ["new"]


def test_semantic_create_requires_the_actual_draft_card(harness):
    request, _ = prepare(harness)
    request.pop("decisions")
    result = harness.run("view-materialize", request, expected=2)
    assert result["diagnostics"][0]["code"] == "CARD_INPUT_REQUIRED"
    assert not (harness.root / ".build/operations/op/final-view.json").exists()
