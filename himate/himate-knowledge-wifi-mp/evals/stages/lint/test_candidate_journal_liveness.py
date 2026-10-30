"""Candidate quality reads explicit inputs; writer barriers belong to P6."""
import hashlib
import json


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


def test_unreferenced_execution_history_does_not_change_candidate_quality(harness):
    """CLI wiring sentinel; all ten journal variants have guarded contract coverage."""
    view, _ = harness.view()
    old = journal(harness)
    unfinished = journal(harness, operation="op", status="prepared")
    unfinished.write_bytes(b"{unfinished")
    private = ".build/operations/abandoned/transaction/journal.json"
    harness.write(private, b"{unfinished")
    files = {path: path.read_bytes() for path in (old, unfinished, harness.root / private)}
    result = check(harness, view)
    assert result["status"] == "passed" and result["complete"] is True
    findings = [finding for row in result["checks"] if row["group"] == "view" for finding in row["findings"]]
    assert not findings
    assert all(path.read_bytes() == before for path, before in files.items())
    assert not (harness.root / "knowledge").exists()


def test_old_foreign_terminal_never_hides_current_display_tamper(harness):
    view, _ = harness.view()
    old = journal(harness)
    before = old.read_bytes()
    harness.write(".build/operations/op/final-view/knowledge/rules/new.md", b"tampered displayed bytes")
    result = check(harness, view, expected=1)
    assert result["status"] == "failed" and "FINAL_BYTES_CHANGED" in json.dumps(result)
    assert old.read_bytes() == before
