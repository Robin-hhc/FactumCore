"""Transport output ownership, independent of rule loading and business writes."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


DOMAIN = Path(__file__).parents[2]
_spec = importlib.util.spec_from_file_location("staging_runtime_fixture", DOMAIN / "evals/support/contracts.py")
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)


@pytest.mark.parametrize("skill", ["source", "change-plan", "view-materialize"])
@pytest.mark.parametrize("request_owner", ["current", "borrowed", "external"])
def test_only_current_operation_request_and_output_are_owned(tmp_path, monkeypatch, skill, request_owner):
    package = DOMAIN / "runtime/himate_knowledge/stages" / skill.replace("-", "_")
    support = _fixture.runtime_module("protocol")
    root = tmp_path / "knowledge"
    root.mkdir()
    incoming = (root / ".build/operations" / ("op" if request_owner == "current" else "other") / "request.json"
                if request_owner != "external" else tmp_path / "request.json")
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_text(json.dumps({"operation_id": "op"}), encoding="utf-8")
    outgoing = root / ".build/operations/op/response.json"
    owned = []
    context = SimpleNamespace(root=root, operation_root=".build/operations/op",
                              register_owned=lambda ref, raw: owned.append(ref))
    monkeypatch.setattr(support, "Context", lambda *a: context)
    monkeypatch.setattr(support, "tool_identity", lambda *a: {})
    monkeypatch.setattr(sys, "argv", ["cli", "--input", str(incoming), "--output", str(outgoing),
                                     "--knowledge-root", str(root)])
    assert support.run(lambda ctx: ({"real_action": "observed"}, "prepared"), package, owned_io=True) == 0
    assert owned == ([".build/operations/op/request.json"] if request_owner == "current" else []) + [".build/operations/op/response.json"]
    assert json.loads(outgoing.read_bytes())["data"]["real_action"] == "observed"


@pytest.mark.parametrize("skill", ["source", "change-plan", "view-materialize"])
@pytest.mark.parametrize("output", ["logs/error.json", "artifacts/error.json", ".build/operations/other/result.json"])
def test_invalid_internal_output_never_runs_business_or_writes_error(tmp_path, monkeypatch, skill, output):
    package = DOMAIN / "runtime/himate_knowledge/stages" / skill.replace("-", "_")
    support = _fixture.runtime_module("protocol")
    root = tmp_path / "knowledge"
    root.mkdir()
    incoming = tmp_path / "request.json"
    incoming.write_text('{"operation_id":"op"}', encoding="utf-8")
    outgoing = root / output
    monkeypatch.setattr(support, "tool_identity", lambda *a: {})
    monkeypatch.setattr(sys, "argv", ["cli", "--input", str(incoming), "--output", str(outgoing),
                                     "--knowledge-root", str(root)])
    assert support.run(lambda ctx: pytest.fail("Unsafe output must stop before the handler"), package, owned_io=True) == 2
    assert not outgoing.exists()
