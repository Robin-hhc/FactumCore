"""No sibling transport remains; real external Git work stays bounded and safe.

The retired Context.call budget matrix tested a mechanism removed by the new
design. Its timeout, request-data and secret-redaction oracles now exercise the
actual shared Git boundaries and the retained public response adapters.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("external_boundary_contracts", REPO / "himate-knowledge-wifi-mp/evals/contract_test_support.py")
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)
fixture_spec = importlib.util.spec_from_file_location("external_boundary_packages", REPO / "himate-knowledge-wifi-mp/evals/pipeline_harness.py")
fixture = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture)
MOCK_SECRET = "synthetic-timeout-command-credential-must-not-be-disclosed"


def load_support(name):
    path = REPO / "skills/common/knowledge" / name / "scripts/support.py"
    spec = importlib.util.spec_from_file_location("public_support_" + name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", fixture.PUBLIC_SKILLS)
def test_retained_public_context_has_no_sibling_cli_transport(name):
    support = load_support(name)
    assert not hasattr(support.Context, "call")
    assert not hasattr(contracts.module("runtime").OperationContext, "call")
    scripts = REPO / "skills/common/knowledge" / name / "scripts"
    for path in scripts.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        delegated = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "call"
                     and isinstance(node.func.value, ast.Name) and node.func.value.id in {"ctx", "context", "self"}]
        assert not delegated, (name, path.name)


@pytest.mark.parametrize("kind,seconds", [("capture", 20), ("recovery", 30)])
def test_actual_git_read_has_fixed_noninteractive_budget(tmp_path, monkeypatch, kind, seconds):
    observed = []
    def process(argv, **kwargs):
        observed.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"exact fixture object")
    monkeypatch.setattr(subprocess, "run", process)
    if kind == "capture":
        result = contracts.module("source_operations").git_read(tmp_path, ["rev-parse", "HEAD"])
    else:
        result = contracts.module("source_resources")._git_read(tmp_path, "rev-parse", "HEAD")
    assert result == b"exact fixture object"
    assert len(observed) == 1
    argv, options = observed[0]
    assert argv[0] == "git" and options["timeout"] == seconds
    assert options["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert options["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert "protocol.allow=never" in argv


@pytest.mark.parametrize("kind,code", [("capture", "GIT_UNAVAILABLE"), ("recovery", "GIT_SOURCE_UNAVAILABLE")])
def test_actual_git_timeout_exposes_safe_diagnostic(tmp_path, monkeypatch, kind, code):
    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(["git", MOCK_SECRET], kwargs["timeout"],
            output=MOCK_SECRET.encode(), stderr=MOCK_SECRET.encode())
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ValueError) as captured:
        if kind == "capture":
            contracts.module("source_operations").git_read(tmp_path, ["rev-parse", "HEAD"])
        else:
            contracts.module("source_resources")._git_read(tmp_path, "rev-parse", "HEAD")
    assert captured.value.code == code
    assert MOCK_SECRET not in str(captured.value)
    if kind == "capture":
        assert captured.value.blocked is True


@pytest.mark.parametrize("name", [name for name in fixture.PUBLIC_SKILLS if name != "hs-knowledge-apply"])
def test_public_adapter_preserves_safe_external_timeout_and_ignores_request_deadline(tmp_path, monkeypatch, name):
    support = load_support(name)
    request = {"operation_id": "timeout", "timeout": 0.001, "timeout_seconds": 999999,
               "deadline": "now", "call_timeout_seconds": 1}
    knowledge_root = tmp_path / "knowledge-root"
    knowledge_root.mkdir()
    incoming, outgoing = tmp_path / "input.json", tmp_path / "response.json"
    incoming.write_bytes(support.canonical(request))
    monkeypatch.setattr(support, "tool_identity", lambda package: {"skill": name, "package_digest": "b" * 64,
        "requirements_digest": "c" * 64, "runtime": "synthetic-external-timeout"})
    monkeypatch.setattr(support, "Context", lambda args, value, package: SimpleNamespace(root=knowledge_root, request=value))
    def timeout(argv, **kwargs):
        assert kwargs["timeout"] == 20
        raise subprocess.TimeoutExpired(["git", MOCK_SECRET], kwargs["timeout"],
            output=MOCK_SECRET.encode(), stderr=MOCK_SECRET.encode())
    monkeypatch.setattr(subprocess, "run", timeout)
    monkeypatch.setattr(sys, "argv", ["public-cli", "--input", str(incoming), "--output", str(outgoing),
        "--knowledge-root", str(knowledge_root), "--rules-digest", "a" * 64])
    def handler(ctx):
        contracts.module("source_operations").git_read(ctx.root, ["rev-parse", "HEAD"])
        raise AssertionError("A timed-out read must not report success")
    assert support.run(handler, tmp_path / name) == 3
    result = json.loads(outgoing.read_bytes())
    assert result["status"] == result["phase"] == "blocked"
    assert result["diagnostics"][0]["code"] == "GIT_UNAVAILABLE"
    assert result["digest"] == support.digest({key: value for key, value in result.items() if key != "digest"})
    assert MOCK_SECRET not in outgoing.read_text(encoding="utf-8")
