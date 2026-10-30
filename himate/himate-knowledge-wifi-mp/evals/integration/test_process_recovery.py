"""Actual process hard-exit/recovery mechanism with declared fixture review.

This is not a power-loss, hardware durability, real-human or production WiFi
acceptance test. The only fault injection lives in this test's apply subprocess.
"""

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SPEC = importlib.util.spec_from_file_location(
    "process_recovery_fixture", Path(__file__).parents[1] / "support/pipeline.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


@pytest.mark.parametrize("repository_cli", [False, True], ids=["compatibility-entry", "repository-only"])
def test_hard_exit_after_card_replace_preserves_journal_and_recovers_exact_view(tmp_path, repository_cli):
    p = FIXTURE.Pipeline(tmp_path, repository_cli=repository_cli)
    operation = "crash-operation"
    target_ref = "knowledge/rules/crash-rule.md"
    bundle_ref, bundle = p.capture(operation, b"# Fixture\nCrash recovery is a synthetic rule.\n")
    view_ref = p.view(operation, bundle_ref, "crash-rule", p.card("crash-rule", bundle))
    proof_ref, review = p.review(operation, view_ref)
    pending_ref = p.pending_record(operation, view_ref)
    view = p.record(view_ref)
    assert review["view_digest"] == view["digest"]
    expected = {row["path"]: base64.b64decode(row["bytes_b64"], validate=True) for row in view["writes"]}
    source_lock_before = (p.root / "governance/sources.lock.yaml").read_bytes()
    framework_lock_before = (p.root / "governance/framework.lock.yaml").read_bytes()
    source_before = (p.root / "docs-raw/specs/raw-source.md").read_bytes()
    incoming = tmp_path / "crash-input.json"
    outgoing = tmp_path / "crash-output.json"
    incoming.write_bytes(FIXTURE.canonical({"operation_id": operation, "view_ref": view_ref,
        "content_review_ref": proof_ref, "ingest_record_ref": pending_ref}))
    cli = p.root / "knowledge.py"
    target = p.root / target_ref
    # The test intercepts only the exact final target, after the genuine OS
    # replacement. os._exit bypasses Python finally/atexit and the normal CLI
    # result writer. No production fault switch or runtime source is modified.
    program = r"""
import os,pathlib,runpy,sys
cli,target,incoming,outgoing,knowledge,rules,catalog=sys.argv[1:]
expected=pathlib.Path(target).resolve()
if os.name=='nt' and not str(expected).startswith('\\\\?\\'):
    expected=pathlib.Path('\\\\?\\'+str(expected))
replace=os.replace
def hard_exit_after_exact_replace(source,destination,*args,**kwargs):
    result=replace(source,destination,*args,**kwargs)
    try:
        if pathlib.Path(destination).samefile(expected):
            os._exit(73)
    except FileNotFoundError:
        pass
    return result
os.replace=hard_exit_after_exact_replace
sys.path.insert(0,str(pathlib.Path(cli).parent))
prefix=['apply','--json'] if pathlib.Path(cli).name=='knowledge.py' else []
sys.argv=[cli,*prefix,'--input',incoming,'--output',outgoing,'--knowledge-root',knowledge,
          '--rules-digest',rules,'--catalog',catalog]
runpy.run_path(cli,run_name='__main__')
"""
    crashed = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(cli),
            str(target),
            str(incoming),
            str(outgoing),
            str(p.root),
            p.rules,
            str(p.catalog_path),
        ],
        capture_output=True,
        timeout=90,
    )
    assert crashed.returncode == 73, (crashed.stdout, crashed.stderr)
    assert not outgoing.exists(), "hard exit must happen before a normal ResultEnvelope is emitted"
    assert target.read_bytes() == expected[target_ref]
    journal_ref = f".build/operations/{operation}/transaction/journal.json"
    result_ref = f".build/operations/{operation}/transaction/apply-result.json"
    journal = p.record(journal_ref)
    assert journal["status"] not in {"committed", "rolled_back"}
    assert not (p.root / result_ref).exists()
    target_entry = next(row for row in journal["entries"] if row["path"] == target_ref)
    assert target_entry["attempted"] is True
    assert not target_entry.get("installed"), "process died before installed=true journal update"
    barrier = p.call("knowledge-index-build", {"operation_id": "index-after-hard-exit"}, expected=3)
    assert barrier["diagnostics"][0]["code"] == "TRANSACTION_PENDING"
    workflow = {"run_id": "crash-fixture", "node_id": "recover_transaction"}
    inspected = p.call(
        "knowledge-recover",
        {"operation_id": operation, "workflow": {**workflow, "attempt_id": "inspect-after-exit"}},
        "inspect",
    )
    assert inspected["data"]["transaction_status"] == journal["status"]
    # Simulate a different writer touching the exact transaction target after
    # process death. Recovery must preserve these external bytes and refuse.
    concurrent_bytes = b"external concurrent edit; never overwrite automatically\n"
    target.write_bytes(concurrent_bytes)
    unrelated_ref = "knowledge/concurrent-user-note.txt"
    p.write(unrelated_ref, b"unrelated external file\n")
    refused = p.call(
        "knowledge-recover",
        {"operation_id": operation, "workflow": {**workflow, "attempt_id": "resume-conflict"}},
        "resume",
        expected=3,
    )
    assert refused["status"] == "blocked"
    assert target.read_bytes() == concurrent_bytes
    assert not (p.root / result_ref).exists()
    assert p.record(journal_ref)["status"] not in {"committed", "rolled_back"}
    # Explicit test-actor conflict resolution restores the already approved
    # bytes; the recovery engine itself never overwrites the concurrent edit.
    target.write_bytes(expected[target_ref])
    resumed = p.call(
        "knowledge-recover",
        {"operation_id": operation, "workflow": {**workflow, "attempt_id": "resume-after-resolution"}},
        "resume",
    )
    assert resumed["data"]["transaction_status"] == "committed"
    assert p.record(journal_ref)["status"] == "committed"
    assert resumed["data"]["apply_result_ref"] == result_ref
    for ref, raw in expected.items():
        assert (p.root / ref).read_bytes() == raw
    for deletion in view.get("deletes", []):
        assert not (p.root / deletion["path"]).exists()
    assert (p.root / "governance/framework.lock.yaml").read_bytes() == framework_lock_before
    assert (p.root / "docs-raw/specs/raw-source.md").read_bytes() == source_before
    assert (p.root / unrelated_ref).read_bytes() == b"unrelated external file\n"
    lock_entry = next(row for row in journal["entries"] if row["path"] == "governance/sources.lock.yaml")
    backup = (p.root / lock_entry["backup_ref"]).absolute()
    if sys.platform == "win32" and not str(backup).startswith("\\\\?\\"):
        text = str(backup)
        backup = Path("\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text)
    assert backup.read_bytes() == source_lock_before
    verified = p.call(
        "knowledge-apply",
        {
            "operation_id": operation,
            "apply_result_ref": result_ref,
            "purpose": "current",
            "card_path": target_ref,
            "card_digest": FIXTURE.sha(expected[target_ref]),
        },
        "verify-result",
    )
    assert verified["data"]["result_verified"] is True
    assert verified["data"]["eligible_files"] == [{"path": target_ref, "sha256": FIXTURE.sha(expected[target_ref])}]
    (tmp_path / "process-recovery-evidence.json").write_text(
        json.dumps(
            {
                "level": "actual_subprocess_hard_exit_with_isolated_declared_fixture_review",
                "injection": "os._exit(73) after real os.replace of one exact card target; test process only",
                "exit_code": crashed.returncode,
                "interrupted_journal_status": journal["status"],
                "barrier": "TRANSACTION_PENDING",
                "external_edit_preserved": True,
                "explicit_fixture_actor_resolved_conflict": True,
                "recovered_status": "committed",
                "exact_writes": {ref: FIXTURE.sha(raw) for ref, raw in expected.items()},
                "framework_lock_unchanged": True,
                "original_raw_unchanged": True,
                "limits": [
                    "not power-loss or hardware durability",
                    "not real human/host approval",
                    "not real WiFi or external CI acceptance",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
