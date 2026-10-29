"""Migrated byte/action oracles at the P4 public boundary; P5 owns quality."""
import json
import pytest
import yaml

def test_create_freezes_agent_content_without_official_writes(harness):
    ref, _ = harness.plan()
    plan = harness.record(ref)
    assert len(plan["writes"]) == 1
    assert plan["writes"][0]["path"] == "knowledge/rules/new.md"
    assert not (harness.root / "knowledge").exists()
    assert plan["review_mode"] == "manual_document"


def test_enumerated_candidates_require_exact_disposition_coverage(harness):
    ref, _ = harness.capture()
    result = harness.run(
        "view-materialize",
        {
            "operation_id": "op",
            "bundle_ref": ref,
            "candidate_ids": ["one", "omitted"],
            "decisions": [
                {"candidate_id": "one", "decision": "defer", "reason": "No evidence"}
            ],
        },
        expected=2,
    )
    assert result["diagnostics"][0]["code"] == "DISPOSITION_COVERAGE"


def test_defer_retains_reason_without_official_card_writes(harness):
    ref, _ = harness.capture()
    result = harness.run(
        "view-materialize",
        {
            "operation_id": "op",
            "bundle_ref": ref,
            "decisions": [
                {
                    "candidate_id": "one",
                    "decision": "defer",
                    "reason": "No evidence",
                    "owner": "synthetic",
                    "next_step": "Obtain authorized source",
                }
            ],
        },
    )
    plan = harness.record(result["data"]["plan_ref"])
    assert plan["writes"] == [] and result["data"]["batch_kind"] == "record_only"
    assert plan["decisions"][0]["reason"] == "No evidence"


def test_changed_candidate_invalidates_public_plan_verify(harness):
    ref, _ = harness.plan()
    harness.write(".build/candidates/new.md", b"changed")
    result = harness.run(
        "view-materialize", harness.record(ref)["request"], expected=2
    )
    assert result["diagnostics"][0]["code"] in {"CANDIDATE_CHANGED", "INPUT_CHANGED"}


@pytest.mark.parametrize("decision", ["update", "merge", "split", "deprecate"])
def test_remaining_decisions_produce_real_complete_final_write_sets(harness, decision):
    import base64
    import yaml

    _, initial = harness.capture("initial")
    for identity in ["old-a", "old-b"]:
        harness.write(
            "knowledge/rules/" + identity + ".md",
            harness.card(identity, initial, lifecycle="stable"),
        )
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": initial["resources"],
                "snapshots": initial["snapshots"],
            }
        ).encode(),
    )
    ref, bundle = harness.capture("operation")
    item = {
        "candidate_id": "one",
        "decision": decision,
        "reason": "Explicit synthetic authored change",
    }
    if decision == "update":
        ids = ["old-a"]
    elif decision == "merge":
        ids = ["merged"]
        item.update(
            replaces=["old-a", "old-b"],
            claim_mapping={
                "old-a-claim": ["merged-claim"],
                "old-b-claim": ["merged-claim"],
            },
        )
    elif decision == "split":
        ids = ["part-a", "part-b"]
        item.update(
            replaces=["old-a"],
            claim_mapping={"old-a-claim": ["part-a-claim", "part-b-claim"]},
        )
    else:
        ids = []
        item["replaces"] = ["old-a"]
    item["card_inputs"] = [
        harness.write(".build/candidates/" + i + ".md", harness.card(i, bundle))
        for i in ids
    ]
    planned = harness.run(
        "view-materialize",
        {"operation_id": "operation", "bundle_ref": ref, "decisions": [item]},
    )
    materialized = planned
    view = harness.record(materialized["data"]["view_ref"])
    cards = {
        w["path"]: base64.b64decode(w["bytes_b64"])
        for w in view["writes"]
        if w["path"].endswith(".md") and not w["path"].endswith("/index.md")
    }
    assert len(cards) == {"update": 1, "merge": 3, "split": 3, "deprecate": 1}[decision]
    if decision != "update":
        assert b"lifecycle: deprecated" in cards["knowledge/rules/old-a.md"]
    assert (harness.root / "knowledge/rules/old-a.md").read_bytes() == harness.card(
        "old-a", initial, lifecycle="stable"
    )
    assert (
        harness.run(
            "view-materialize",
            {"operation_id": "operation", "view_ref": materialized["data"]["view_ref"]},
            action="describe",
        )["phase"]
        == "described"
    )


def test_missing_merge_claim_destinations_are_rejected(harness):
    ref, bundle = harness.capture()
    harness.write(
        "knowledge/rules/old.md", harness.card("old", bundle, lifecycle="stable")
    )
    candidate = harness.write(
        ".build/candidates/merged.md", harness.card("merged", bundle)
    )
    result = harness.run(
        "view-materialize",
        {
            "operation_id": "op",
            "bundle_ref": ref,
            "decisions": [
                {
                    "candidate_id": "one",
                    "decision": "merge",
                    "reason": "Synthetic merge",
                    "replaces": ["old"],
                    "card_inputs": [candidate],
                }
            ],
        },
    )
    report = harness.lint(result["data"]["view_ref"], expected=1)
    assert "CLAIM_DESTINATION_REQUIRED" in json.dumps(report)


def test_new_identity_cannot_overwrite_another_card_path(harness):
    ref, bundle = harness.capture()
    harness.write(
        "knowledge/rules/old.md", harness.card("old", bundle, lifecycle="stable")
    )
    candidate = harness.write(".build/candidates/new.md", harness.card("new", bundle))
    result = harness.run(
        "view-materialize",
        {
            "operation_id": "op",
            "bundle_ref": ref,
            "decisions": [
                {
                    "candidate_id": "one",
                    "decision": "create",
                    "reason": "Synthetic overwrite",
                    "card_inputs": [
                        {"path": candidate, "target_path": "knowledge/rules/old.md"}
                    ],
                }
            ],
        },
        expected=2,
    )
    assert result["diagnostics"][0]["code"] == "TARGET_EXISTS"


def test_distinct_cards_may_share_a_local_claim_id(harness):
    ref, bundle = harness.capture()
    decisions = []
    for identity in ["first", "second"]:
        candidate = harness.write(
            ".build/candidates/" + identity + ".md",
            harness.card(identity, bundle, claim="c1"),
        )
        decisions.append(
            {
                "candidate_id": identity,
                "decision": "create",
                "reason": "Separate card identity",
                "card_inputs": [candidate],
            }
        )
    planned = harness.run(
        "view-materialize", {"operation_id": "op", "bundle_ref": ref, "decisions": decisions}
    )
    assert len(harness.record(planned["data"]["plan_ref"])["writes"]) == 2


def test_resealed_plan_writes_must_rederive_from_authored_candidate(harness):
    import base64
    import hashlib
    import json

    ref, _ = harness.plan()
    plan = harness.record(ref)
    changed = base64.b64decode(plan["writes"][0]["bytes_b64"]).replace(
        b"Synthetic fixture statement.", b"Undeclared statement mutation."
    )
    plan["writes"][0]["bytes_b64"] = base64.b64encode(changed).decode()
    plan["writes"][0]["final_digest"] = hashlib.sha256(changed).hexdigest()
    plan.pop("digest")
    plan["digest"] = hashlib.sha256(
        json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    harness.write(
        ref,
        json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode(),
    )
    result = harness.run(
        "view-materialize", harness.record(ref)["request"], expected=2
    )
    assert result["diagnostics"][0]["code"] == "PLAN_CHANGED"


def test_registered_snapshot_keeps_original_fields_after_source_is_committed(harness):
    import subprocess

    _, old = harness.capture("old")
    harness.write("governance/sources.lock.yaml", yaml.safe_dump({"schema_version": "2.0", "resources": old["resources"],
                  "snapshots": old["snapshots"]}).encode())
    (harness.base / "config.yml").write_text(yaml.safe_dump({"knowledge_roots": {"wifi": harness.root.name}, "repos": []}), encoding="utf-8")
    def git(*args):
        subprocess.run(["git", "-C", str(harness.base), *args], check=True, capture_output=True)
    git("init", "-q")
    git("add", "--", harness.root.name + "/docs-raw/specs/source.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "source")
    ref, current = harness.capture("new")
    assert old["snapshots"][0]["snapshot_id"] == current["snapshots"][0]["snapshot_id"]
    assert current["snapshots"] == old["snapshots"]
    before = (harness.root / "governance/sources.lock.yaml").read_bytes()
    candidate = harness.write(".build/candidates/new.md", harness.card("new", current))
    result = harness.run("view-materialize", {"operation_id": "new", "bundle_ref": ref, "decisions": [
        {"candidate_id": "new", "decision": "create", "reason": "First accepted card", "card_inputs": [candidate]}]})
    assert result["phase"] == "ready"
    assert (harness.root / "governance/sources.lock.yaml").read_bytes() == before
