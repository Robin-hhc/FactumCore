"""Former regression oracles at the shared implementation and apply actions."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location("p7_regression_helpers", Path(__file__).resolve().parents[2] / "support/stages/apply_helpers.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
REGRESSION = HELPER.load_contract("query_regression")
RUNTIME = HELPER.load_contract("runtime")


@pytest.mark.parametrize("purpose", ["gudiance", "", None, 17, ["guidance"]])
def test_invalid_purpose_is_rejected_before_reading_any_generation(purpose):
    context = SimpleNamespace(args=SimpleNamespace(action="run"), request={
        "generation_ref": "not-read", "cases": [{"id": "background", "query": "design",
                                                   "purpose": purpose, "required": ["design-card"]}]})
    with pytest.raises(RUNTIME.NodeError) as caught:
        REGRESSION.execute(context)
    assert caught.value.code == "INVALID_PURPOSE"


@pytest.mark.parametrize("expected", ["actual", "absent"])
def test_manual_cases_need_no_authored_batch_and_failed_cases_never_activate(tmp_path, monkeypatch, expected):
    calls = []

    class Context:
        root = tmp_path
        operation, base = "op", ".build/operations/op"
        args = SimpleNamespace(action="run", rules_digest="0" * 64, catalog=None)
        rules, modules, tool = {}, {}, {}
        request = {"operation_id": "op", "generation_ref": "generation", "expected_active": None,
                   "cases": [{"id": "manual", "query": "timeout", "required": [expected]}]}

        def seal(self, value, kind):
            return {**value, "digest": "report", "record_kind": kind}

        def save(self, ref, report):
            self.report = report

        def record(self, *args):
            pytest.fail("Manual query cases must not require an authored view or approval record")

    def search(ctx, request, **kwargs):
        calls.append("search")
        return {"candidate_scan_truncated": False,
                "matches": [{"card_id": "actual", "card_digest": "card", "claim_ids": ["c1"]}],
                "receipt_ref": "search-receipt"}

    def read(ctx, request, **kwargs):
        calls.append("read")
        return {"generation_ref": "generation", "card_digest": "card", "claims": [{"id": "c1"}],
                "receipt_ref": "read-receipt"}

    def activate(ctx, **kwargs):
        calls.append("activate")
        assert ctx.request["expected_active"] is None
        return {"activated": True}, "activated"

    monkeypatch.setattr(REGRESSION.index_runtime, "verify_generation", lambda *args: object())
    monkeypatch.setattr(REGRESSION.index_runtime, "reuse_generation", lambda *args: {
        "channel": "local", "expected_active": None, "digest": "manifest"})
    monkeypatch.setattr(REGRESSION.index_runtime, "active", lambda *args: None)
    monkeypatch.setattr(REGRESSION.index_runtime, "execute", activate)
    monkeypatch.setattr(REGRESSION.query_runtime, "search", search)
    monkeypatch.setattr(REGRESSION.query_runtime, "read", read)
    context = Context()
    result, phase = REGRESSION.execute(context)
    assert context.report["cases"] == context.request["cases"]
    assert "read" in calls
    if expected == "actual":
        assert phase == "checked" and result["passed"] and result["activated"]
        assert "activate" in calls
    else:
        assert phase == "needs_revision" and not result["passed"] and not result["activated"]
        assert "activate" not in calls
