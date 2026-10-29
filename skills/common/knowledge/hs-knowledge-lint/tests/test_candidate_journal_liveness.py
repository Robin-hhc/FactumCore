"""Candidate quality reads explicit inputs; writer barriers belong to P7."""
import hashlib
import json

import pytest


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def journal(harness, operation="legacy", **changes):
    record = {"schema_version": "2.0", "record_kind": "transaction_journal", "operation_id": operation,
        "rules_digest": "a" * 64, "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
        "runtime": "fixture", "requirements_digest": "0" * 64}, "status": "committed", "entries": [],
        "view_ref": ".build/operations/legacy/view.json", "view_digest": "1" * 64,
        "proof_ref": "logs/operations/legacy/proof.json", "proof_digest": "2" * 64, **changes}
    record["digest"] = hashlib.sha256(canonical(record)).hexdigest()
    ref = "logs/operations/" + operation + "/journal.json"
    harness.write(ref, canonical(record))
    return harness.root / ref


def check(harness, view, expected=0):
    return harness.run("lint", {"operation_id": "op", "mode": "candidate", "view_ref": view}, expected=expected)


@pytest.mark.parametrize("status", ["committed", "rolled_back"])
def test_old_foreign_terminal_allows_current_candidate_checks(harness, status):
    view, _ = harness.view()
    old = journal(harness, status=status)
    before = old.read_bytes()
    result = check(harness, view)
    assert result["status"] == "passed"
    assert old.read_bytes() == before
    assert not (harness.root / "knowledge").exists()


@pytest.mark.parametrize("kind", ["prepared", "bad-seal", "bad-op", "bad-schema", "bad-kind", "same-operation", "bad-json", "unknown-state"])
def test_unreferenced_old_journal_does_not_change_candidate_quality(harness, kind):
    view, _ = harness.view()
    changes = {"status": "prepared"} if kind == "prepared" else {}
    changes.update({"operation_id": "wrong"} if kind == "bad-op" else {})
    changes.update({"schema_version": "3.0"} if kind == "bad-schema" else {})
    changes.update({"record_kind": "apply_result"} if kind == "bad-kind" else {})
    changes.update({"status": "unrecognized"} if kind == "unknown-state" else {})
    old = journal(harness, operation="op" if kind == "same-operation" else "legacy", **changes)
    if kind == "bad-seal":
        value = json.loads(old.read_bytes())
        value["digest"] = "0" * 64
        old.write_bytes(canonical(value))
    if kind == "bad-json":
        old.write_bytes(b"{unfinished")
    before = old.read_bytes()
    result = check(harness, view)
    assert result["status"] == "passed" and result["complete"] is True
    findings = [finding for row in result["checks"] if row["group"] == "view" for finding in row["findings"]]
    assert not findings
    assert old.read_bytes() == before
    assert not (harness.root / "knowledge").exists()


def test_old_foreign_terminal_never_hides_current_display_tamper(harness):
    view, _ = harness.view()
    old = journal(harness)
    before = old.read_bytes()
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", b"tampered displayed bytes")
    result = check(harness, view, expected=1)
    assert result["status"] == "failed" and "FINAL_BYTES_CHANGED" in json.dumps(result)
    assert old.read_bytes() == before
