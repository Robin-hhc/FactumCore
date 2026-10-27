"""Reject malformed retrieval intent before reading or activating an index."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("purpose", ["gudiance", "", None, 17, ["guidance"]])
def test_invalid_purpose_is_reported_before_index_verification(monkeypatch, purpose):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    spec = importlib.util.spec_from_file_location("regression_purpose_support", scripts / "support.py")
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    with monkeypatch.context() as isolated:
        isolated.setitem(sys.modules, "support", support)
        spec = importlib.util.spec_from_file_location("regression_purpose_node", scripts / "node.py")
        node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node)

    class Context:
        operation = "purpose-check"
        args = SimpleNamespace(action="run")
        request = {"generation_ref": "not-read", "cases": [{
            "id": "background", "query": "design", "purpose": purpose, "required": ["design-card"],
        }]}

        def call(self, *args, **kwargs):
            pytest.fail("Invalid purposes must be rejected before any index or query call")

    with pytest.raises(support.NodeError) as caught:
        node.execute(Context())
    assert caught.value.code == "INVALID_PURPOSE"
