def test_changed_raw_blocks_affected_claim_once_without_editing_official_card(harness):
    import yaml

    ref, old = harness.capture("old")
    card = harness.card("existing", old, lifecycle="stable")
    harness.write("knowledge/rules/existing.md", card)
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    new_ref, _ = harness.capture(
        "changed", b"# Source\nChanged authorized synthetic evidence.\n"
    )
    result = harness.run(
        "maintain",
        {"operation_id": "changed", "bundle_ref": new_ref},
        "register-source-change",
    )
    state = harness.record("logs/events/state.json")
    assert state["validity_epoch"] == 1
    assert state["blocked_claims"][0]["card_id"] == "existing"
    assert state["knowledge_apply_watermark"] is None
    assert (harness.root / "knowledge/rules/existing.md").read_bytes() == card
    assert result["data"]["event_refs"]
    assert (
        harness.run("maintain", {"operation_id": "changed"}, "status")["data"]["state"][
            "validity_epoch"
        ]
        == 1
    )


def test_manual_clear_without_applied_and_activated_proof_is_blocked(harness):
    response = harness.run(
        "maintain",
        {"operation_id": "untrusted", "clear_claims": ["claim"]},
        "advance",
        expected=3,
    )
    assert response["diagnostics"][0]["code"] == "VERIFIED_REVIEW_REQUIRED"
    assert not (harness.root / "logs/events/state.json").exists()


def test_interrupted_event_publish_keeps_blocks_and_resumes_without_epoch_duplication(
    harness,
):
    import json
    import subprocess
    import sys
    import yaml

    _, old = harness.capture("initial")
    harness.write(
        "knowledge/rules/existing.md", harness.card("existing", old, lifecycle="stable")
    )
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    # Capture the new bytes before declaring the old source formally, then restore the old lock.
    harness.write(
        "governance/sources.lock.yaml",
        b"schema_version: '2.0'\nresources: []\nsnapshots: []\n",
    )
    new_ref, _ = harness.capture("new", b"# Source\nChanged fixture evidence.\n")
    harness.write(
        "governance/sources.lock.yaml",
        yaml.safe_dump(
            {
                "schema_version": "2.0",
                "resources": old["resources"],
                "snapshots": old["snapshots"],
            }
        ).encode(),
    )
    script = harness.packages / "hs-knowledge-maintain/scripts"
    code = (
        "import sys; from pathlib import Path; from types import SimpleNamespace; "
        "sys.path.insert(0,sys.argv[1]); import support,maintain; "
        "args=SimpleNamespace(knowledge_root=sys.argv[2],rules_digest=sys.argv[3],catalog=sys.argv[4],action='register-source-change'); "
        "ctx=support.Context(args,{'operation_id':'new','bundle_ref':sys.argv[5]},Path(sys.argv[1]).parent); "
        "ctx.save=lambda *a: (_ for _ in ()).throw(RuntimeError('synthetic publish interruption')); "
        "maintain.execute(ctx)"
    )
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(script),
            str(harness.root),
            harness.rules,
            str(harness.catalog),
            new_ref,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode != 0
    interrupted = json.loads((harness.root / "logs/events/state.json").read_text())
    assert interrupted["validity_epoch"] == 1 and interrupted["blocked_claims"]
    assert interrupted["pending_event_ids"]
    harness.run(
        "maintain",
        {"operation_id": "new", "bundle_ref": new_ref},
        "register-source-change",
    )
    recovered = harness.record("logs/events/state.json")
    assert recovered["validity_epoch"] == 1 and not recovered["pending_event_ids"]
    assert recovered["impact_scan_watermark"]
