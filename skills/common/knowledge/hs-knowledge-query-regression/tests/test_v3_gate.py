"""Manual query regression checks actual behavior without an apply proof chain."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


class PublicFixture:
    operation = "op"
    base = ".build/operations/op"
    args = SimpleNamespace(action="run")

    def __init__(self, expected="actual"):
        self.request = {"operation_id": "op", "generation_ref": "generation", "expected_active": None,
                        "cases": [{"id": "manual", "query": "timeout", "required": [expected]}]}
        self.calls = []

    def call(self, name, request, action=None):
        self.calls.append((name, action))
        if name == "hs-knowledge-index-build":
            return {"data": {"channel": "local", "activated": action == "activate"}}
        if name == "hs-knowledge-query":
            if action == "search":
                return {"data": {"candidate_scan_truncated": False,
                                 "matches": [{"card_id": "actual", "card_digest": "card", "claim_ids": ["c1"]}],
                                 "receipt_ref": "search-receipt"}}
            return {"data": {"generation_ref": "generation", "card_digest": "card",
                             "claims": [{"id": "c1"}], "receipt_ref": "read-receipt"}}
        raise AssertionError("No upstream workflow verifier may be called")

    def seal(self, value, kind):
        return {**value, "digest": "report", "record_kind": kind}

    def save(self, ref, report):
        self.report = report


def test_manual_queries_do_not_need_an_authored_batch_or_apply_proof():
    result = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    # Skill support modules intentionally run in separate interpreter contexts.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from node import execute

    fixture = PublicFixture()
    result, phase = execute(fixture)
    assert phase == "checked" and result["passed"] and result["activated"]
    assert fixture.report["cases"] == fixture.request["cases"]
    assert ("hs-knowledge-query", "read") in fixture.calls
    failed = PublicFixture("absent")
    result, phase = execute(failed)
    assert phase == "needs_revision" and not result["passed"] and not result["activated"]
    assert ("hs-knowledge-index-build", "activate") not in failed.calls
