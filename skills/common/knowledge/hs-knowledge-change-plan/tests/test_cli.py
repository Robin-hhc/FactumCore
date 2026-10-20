"""Public boundary tests; no real WiFi originals or human approvals."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_missing_request_returns_structured_error_without_creating_knowledge(tmp_path):
    cli = Path(__file__).parents[1] / "scripts/cli.py"
    response = tmp_path / "response.json"
    knowledge = tmp_path / "absent-knowledge"
    result = subprocess.run(
        [
            sys.executable,
            str(cli),
            "--input",
            str(tmp_path / "missing.json"),
            "--output",
            str(response),
            "--knowledge-root",
            str(knowledge),
            "--rules-digest",
            "0" * 64,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    record = json.loads(response.read_text(encoding="utf-8"))
    assert record["status"] == "error"
    assert record["diagnostics"]
    assert not knowledge.exists()


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
        "change-plan",
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
        "change-plan",
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
    assert plan["writes"] == [] and result["phase"] == "deferred"
    assert plan["decisions"][0]["reason"] == "No evidence"


def test_changed_candidate_invalidates_public_plan_verify(harness):
    ref, _ = harness.plan()
    harness.write(".build/candidates/new.md", b"changed")
    result = harness.run(
        "change-plan", {"operation_id": "op", "plan_ref": ref}, "verify", expected=2
    )
    assert result["diagnostics"][0]["code"] == "CANDIDATE_CHANGED"


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
        "change-plan",
        {"operation_id": "operation", "bundle_ref": ref, "decisions": [item]},
    )
    materialized = harness.run(
        "view-materialize",
        {"operation_id": "operation", "plan_ref": planned["data"]["plan_ref"]},
    )
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
            "candidate-inspect",
            {"operation_id": "operation", "view_ref": materialized["data"]["view_ref"]},
        )["phase"]
        == "manual_ready"
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
        "change-plan",
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
        expected=2,
    )
    assert result["diagnostics"][0]["code"] == "CLAIM_DESTINATION_REQUIRED"


def test_new_identity_cannot_overwrite_another_card_path(harness):
    ref, bundle = harness.capture()
    harness.write(
        "knowledge/rules/old.md", harness.card("old", bundle, lifecycle="stable")
    )
    candidate = harness.write(".build/candidates/new.md", harness.card("new", bundle))
    result = harness.run(
        "change-plan",
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
        "change-plan", {"operation_id": "op", "bundle_ref": ref, "decisions": decisions}
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
        "change-plan", {"operation_id": "op", "plan_ref": ref}, "verify", expected=2
    )
    assert result["diagnostics"][0]["code"] == "OPERATION_CONFLICT"
