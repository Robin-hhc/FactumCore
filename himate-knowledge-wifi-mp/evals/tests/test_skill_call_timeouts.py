"""Fast tests at the real sibling-CLI process boundary; no sleeping or live work.

Every distributed Context.call implementation must apply the same fixed process
budgets and turn an expired sibling call into a safe, retryable blocked result.
The subprocess itself is replaced, while request files, argv construction,
response-envelope digest verification and CLI result handling remain real.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[3]
SUPPORT_SKILLS = (
    "hs-knowledge-candidate-inspect",
    "hs-knowledge-candidate-revise",
    "hs-knowledge-change-plan",
    "hs-knowledge-explore",
    "hs-knowledge-governance-handoff",
    "hs-knowledge-index-build",
    "hs-knowledge-lint",
    "hs-knowledge-maintain",
    "hs-knowledge-query",
    "hs-knowledge-query-regression",
    "hs-knowledge-source-capture",
    "hs-knowledge-source-scan",
    "hs-knowledge-view-materialize",
)
CALL_BUDGETS = (
    ("hs-knowledge-query", None, 300),
    ("hs-knowledge-query", "", 300),
    ("hs-knowledge-query", "search", 300),
    ("hs-knowledge-query", "receipt", 300),
    ("hs-knowledge-query", "read", 120),
    ("hs-knowledge-query", "run", 120),
    ("hs-knowledge-query", "unknown-action", 120),
    ("hs-knowledge-lint", None, 120),
    ("hs-knowledge-change-plan", None, 120),
    ("hs-knowledge-change-plan", "run", 120),
    ("hs-knowledge-change-plan", "rederive", 120),
    ("hs-knowledge-change-plan", "verify", 120),
    ("hs-knowledge-source-capture", None, 120),
    ("hs-knowledge-source-capture", "run", 120),
    ("hs-knowledge-source-capture", "resolve", 120),
    ("hs-knowledge-source-capture", "resolve-source", 120),
    ("hs-knowledge-maintain", "register-source-change", 120),
    ("hs-knowledge-view-materialize", None, 120),
    ("hs-knowledge-candidate-inspect", None, 120),
    ("hs-knowledge-candidate-revise", None, 120),
    ("hs-knowledge-query-regression", None, 1200),
    ("hs-knowledge-query-regression", "run", 1200),
    ("hs-knowledge-query-regression", "verify", 1200),
    ("hs-knowledge-index-build", "verify", 120),
    ("hs-knowledge-governance-handoff", None, 120),
    ("hs-knowledge-fixture-other", "unknown-action", 120),
)
_MODULES = {}
MOCK_SECRET = "synthetic-timeout-command-credential-must-not-be-disclosed"


def load_support(slug):
    if slug not in _MODULES:
        location = REPO / "skills/common/knowledge" / slug / "scripts/support.py"
        assert location.is_file(), "Every declared public Context.call boundary must exist"
        name = "skill_call_timeout_" + slug.replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, location)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _MODULES[slug] = module
    return _MODULES[slug]


def fake_identity(slug):
    return {"skill": slug, "package_digest": "b" * 64,
            "requirements_digest": "c" * 64, "runtime": "synthetic-timeout-boundary"}


@pytest.fixture(params=SUPPORT_SKILLS)
def boundary(request, tmp_path):
    module = load_support(request.param)
    root = tmp_path / "knowledge"
    root.mkdir()
    package = tmp_path / "skills" / request.param
    package.mkdir(parents=True)
    context = module.Context.__new__(module.Context)
    context.root = root
    context.package = package
    context.operation = "call-timeout-test"
    context.base = ".build/operations/" + context.operation
    context.args = SimpleNamespace(catalog=None, rules_digest="a" * 64)
    context.request = {"operation_id": context.operation}
    return SimpleNamespace(module=module, context=context, slug=request.param)


def install_sibling(boundary, name):
    entry = boundary.context.package.parent / name / "scripts/cli.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# Synthetic sibling: subprocess execution must be mocked.\n", encoding="utf-8")
    return entry


def capture_success(monkeypatch, boundary):
    observations = []

    def process(argv, *, capture_output, timeout, check):
        assert capture_output is True and check is False
        incoming = Path(argv[argv.index("--input") + 1])
        outgoing = Path(argv[argv.index("--output") + 1])
        request = json.loads(incoming.read_bytes())
        identity = fake_identity(Path(argv[1]).parents[1].name)
        response = {"schema_version": "2.0", "record_kind": "result", "status": "ok",
                    "phase": "tested", "data": {"boundary": "ok"}, "diagnostics": [],
                    "tool_identity": identity, "rules_digest": boundary.context.args.rules_digest}
        response["digest"] = boundary.module.digest(response)
        outgoing.parent.mkdir(parents=True, exist_ok=True)
        outgoing.write_bytes(boundary.module.canonical(response))
        observations.append({"argv": argv, "timeout": timeout, "request": request})
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(boundary.module.subprocess, "run", process)
    return observations


@pytest.mark.parametrize("callee,action,seconds", CALL_BUDGETS)
def test_distributed_public_sibling_calls_use_fixed_workload_budget(boundary, monkeypatch, callee, action, seconds):
    install_sibling(boundary, callee)
    observed = capture_success(monkeypatch, boundary)
    request = {"operation_id": "call-timeout-test", "fixture": "fixed-budget"}
    result = boundary.context.call(callee, request, action)
    assert result["status"] == "ok" and result["data"] == {"boundary": "ok"}
    assert len(observed) == 1
    assert observed[0]["timeout"] == seconds
    assert observed[0]["request"] == request
    assert observed[0]["argv"][observed[0]["argv"].index("--rules-digest") + 1] == "a" * 64
    if action:
        assert observed[0]["argv"][observed[0]["argv"].index("--action") + 1] == action
    else:
        assert "--action" not in observed[0]["argv"]


def test_request_content_cannot_override_process_deadline(boundary, monkeypatch):
    install_sibling(boundary, "hs-knowledge-query")
    observed = capture_success(monkeypatch, boundary)
    request = {"operation_id": "call-timeout-test", "timeout": 0.001, "timeout_seconds": 999999,
               "deadline": "now", "call_timeout_seconds": 1,
               "query": "Synthetic request fields are data, not process-budget configuration"}
    boundary.context.call("hs-knowledge-query", request, "search")
    assert observed[0]["timeout"] == 300
    assert observed[0]["request"] == request


def test_only_measured_search_and_batch_paths_get_longer_budgets(boundary, monkeypatch):
    observed = capture_success(monkeypatch, boundary)
    ordinary = (("hs-knowledge-source-capture", "resolve-source"),
                ("hs-knowledge-query", "read"),
                ("hs-knowledge-change-plan", None),
                ("hs-knowledge-change-plan", "verify"),
                ("hs-knowledge-view-materialize", None),
                ("hs-knowledge-candidate-inspect", None),
                ("hs-knowledge-candidate-revise", None))
    targets = ordinary + (("hs-knowledge-query", "search"),
                          ("hs-knowledge-query-regression", None))
    actual = {}
    for callee, action in targets:
        install_sibling(boundary, callee)
        boundary.context.call(callee, {"operation_id": "call-timeout-test"}, action)
        actual[(callee, action)] = observed[-1]["timeout"]
    assert all(actual[target] == 120 for target in ordinary)
    assert actual[("hs-knowledge-query-regression", None)] == 1200
    assert actual[("hs-knowledge-query", "search")] == 300
    assert actual[("hs-knowledge-query-regression", None)] > actual[("hs-knowledge-query", "search")]
    assert actual[("hs-knowledge-query", "search")] > actual[("hs-knowledge-query", "read")]


def timeout_process(*args, **kwargs):
    # Deliberately keep a fake credential in the process exception: only the
    # safe capability/action/timeout context may cross the public boundary.
    raise subprocess.TimeoutExpired(["synthetic-sibling", MOCK_SECRET], kwargs["timeout"],
                                    output=MOCK_SECRET.encode(), stderr=MOCK_SECRET.encode())


def test_expired_sibling_call_is_a_safe_blocked_node_error(boundary, monkeypatch):
    install_sibling(boundary, "hs-knowledge-query")
    monkeypatch.setattr(boundary.module.subprocess, "run", timeout_process)
    with pytest.raises(boundary.module.NodeError) as captured:
        boundary.context.call("hs-knowledge-query", {"operation_id": "call-timeout-test"}, "search")
    error = captured.value
    assert error.code == "SIBLING_TIMEOUT"
    assert error.blocked is True
    assert "hs-knowledge-query" in error.message
    assert "300-second call budget" in error.message
    assert MOCK_SECRET not in str(error)
    assert MOCK_SECRET not in error.message
    assert MOCK_SECRET not in error.path


def test_cli_envelope_preserves_timeout_as_blocked_exit_three(boundary, monkeypatch):
    module = boundary.module
    install_sibling(boundary, "hs-knowledge-query")
    request_path = boundary.context.root / ".build/entry-request.json"
    request_path.parent.mkdir(parents=True)
    request_path.write_bytes(module.canonical({"operation_id": "call-timeout-test"}))
    response_path = boundary.context.root / ".build/entry-response.json"

    def minimal_context(self, args, request, package):
        self.args = args
        self.request = request
        self.package = package
        self.root = Path(args.knowledge_root).resolve()
        self.operation = request["operation_id"]
        self.base = ".build/operations/" + self.operation

    monkeypatch.setattr(module.Context, "__init__", minimal_context)
    monkeypatch.setattr(module, "tool_identity", lambda package: fake_identity(boundary.slug))
    monkeypatch.setattr(module.subprocess, "run", timeout_process)
    monkeypatch.setattr(sys, "argv", ["synthetic-cli", "--input", str(request_path), "--output", str(response_path),
                                     "--knowledge-root", str(boundary.context.root), "--rules-digest", "a" * 64])

    def handler(context):
        return context.call("hs-knowledge-query", context.request, "search")["data"], "tested"

    code = module.run(handler, boundary.context.package)
    response = json.loads(response_path.read_bytes())
    assert code == 3
    assert response["status"] == "blocked" and response["phase"] == "blocked"
    assert response["diagnostics"][0]["code"] == "SIBLING_TIMEOUT"
    assert "300-second call budget" in response["diagnostics"][0]["message"]
    assert response["digest"] == module.digest({key: value for key, value in response.items() if key != "digest"})
    assert MOCK_SECRET not in response_path.read_text(encoding="utf-8")
