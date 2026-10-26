"""Candidate readiness keeps current content checks across old terminal history."""
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


@pytest.mark.parametrize("status", ["committed", "rolled_back"])
def test_old_foreign_terminal_allows_current_candidate_checks(harness, status):
    view, _ = harness.view()
    old = journal(harness, status=status)
    before = old.read_bytes()
    result = harness.run("candidate-inspect", {"operation_id": "op", "view_ref": view})
    assert result["phase"] == "manual_ready"
    assert old.read_bytes() == before
    assert not (harness.root / "knowledge").exists()


@pytest.mark.parametrize("kind", ["prepared", "bad-seal", "bad-op", "bad-schema", "bad-kind", "same-operation"])
def test_unverified_or_own_old_journal_cannot_make_candidate_ready(harness, kind):
    view, _ = harness.view()
    changes = {"status": "prepared"} if kind == "prepared" else {}
    changes.update({"operation_id": "wrong"} if kind == "bad-op" else {})
    changes.update({"schema_version": "3.0"} if kind == "bad-schema" else {})
    changes.update({"record_kind": "apply_result"} if kind == "bad-kind" else {})
    old = journal(harness, operation="op" if kind == "same-operation" else "legacy", **changes)
    if kind == "bad-seal":
        value = json.loads(old.read_bytes())
        value["digest"] = "0" * 64
        old.write_bytes(canonical(value))
    before = old.read_bytes()
    result = harness.run("candidate-inspect", {"operation_id": "op", "view_ref": view}, expected=3 if kind == "prepared" else 2)
    assert result["phase"] not in {"manual_ready", "code_ready", "mixed_ready"}
    assert old.read_bytes() == before
    assert not (harness.root / "knowledge").exists()


def test_old_foreign_terminal_never_hides_current_display_tamper(harness):
    view, _ = harness.view()
    old = journal(harness)
    before = old.read_bytes()
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", b"tampered displayed bytes")
    result = harness.run("candidate-inspect", {"operation_id": "op", "view_ref": view}, expected=2)
    assert result["diagnostics"][0]["code"] == "FINAL_BYTES_CHANGED"
    assert old.read_bytes() == before
