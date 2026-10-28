"""Public response paths cannot replace inputs or saved business evidence."""

import ast
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[3]
SKILLS = REPO / "skills/common/knowledge"
PACKAGES = sorted(path.name for path in SKILLS.glob("hs-*") if (path / "scripts/cli.py").is_file())


def invoke(slug, incoming, outgoing, root, action=None):
    command = [sys.executable, str(SKILLS / slug / "scripts/cli.py"),
               "--input", str(incoming), "--output", str(outgoing),
               "--knowledge-root", str(root)]
    if action:
        command += ["--action", action]
    return subprocess.run(command, capture_output=True, timeout=60)


def test_query_response_cannot_replace_an_existing_operation_journal(tmp_path):
    root = tmp_path / "knowledge"
    journal = root / "logs/operations/original/journal.json"
    journal.parent.mkdir(parents=True)
    original = b'{"state":"committed","marker":"keep exact bytes"}\n'
    journal.write_bytes(original)
    incoming = tmp_path / "request.json"
    incoming.write_text(json.dumps({"operation_id": "output-collision", "query": "marker"}))

    result = invoke("hs-knowledge-query", incoming, journal, root, "search")

    assert result.returncode == 2
    assert journal.read_bytes() == original
    assert b"output" in result.stderr.lower()


@pytest.mark.parametrize("slug", PACKAGES)
@pytest.mark.parametrize("victim", ["journal", "formal", "request", "receipt", "input", "external"])
def test_every_public_cli_rejects_existing_output_without_changing_bytes(tmp_path, slug, victim):
    root = tmp_path / "knowledge"
    root.mkdir()
    incoming = tmp_path / "input.json"
    incoming.write_bytes(b'{"operation_id":"fresh-output-only"}\n')
    targets = {
        "journal": root / "logs/operations/old/journal.json",
        "formal": root / "logs/ingest/old.yaml",
        "request": root / ".build/operations/old/request.json",
        "receipt": root / ".build/operations/old/search-receipt.json",
        "input": incoming,
        "external": tmp_path / "external-result.json",
    }
    outgoing = targets[victim]
    outgoing.parent.mkdir(parents=True, exist_ok=True)
    if victim != "input":
        outgoing.write_bytes(b'{"marker":"immutable original evidence"}\r\n')
    original = outgoing.read_bytes()

    result = invoke(slug, incoming, outgoing, root)

    assert result.returncode == 2
    assert outgoing.read_bytes() == original


def pipeline(tmp_path):
    spec = importlib.util.spec_from_file_location("output_safety_pipeline", REPO / "himate-knowledge-wifi-mp/evals/pipeline_harness.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    return fixture.Pipeline(tmp_path)


def test_output_collision_stops_scan_before_creating_business_artifacts(tmp_path):
    trial = pipeline(tmp_path)
    trial.write("docs-raw/specs/output-marker.md", b"# Output marker\nKeep the original source.\n")
    request = tmp_path / "scan-input.json"
    request.write_text('{"operation_id":"must-not-run"}')
    output = tmp_path / "existing-output.json"
    output.write_bytes(b"preserve this response exactly\n")
    before = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}

    result = invoke("hs-knowledge-source-scan", request, output, trial.root, "scan")

    assert result.returncode == 2
    assert output.read_bytes() == b"preserve this response exactly\n"
    after = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}
    assert after == before


def test_output_collision_stops_ready_apply_before_writing_cards_or_journal(tmp_path):
    trial = pipeline(tmp_path)
    bundle_ref, bundle = trial.capture("output-apply", b"# Source\nCapture marker is a documented rule.\n")
    view_ref = trial.view("output-apply", bundle_ref, "output-rule", trial.card("output-rule", bundle))
    review_ref, _ = trial.review("output-apply", view_ref)
    request = tmp_path / "apply-input.json"
    request.write_text(json.dumps({"operation_id": "output-apply", "view_ref": view_ref, "content_review_ref": review_ref}))
    output = tmp_path / "existing-apply-output.json"
    output.write_bytes(b"keep this external response\n")
    before = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}

    result = invoke("hs-knowledge-apply", request, output, trial.root)

    assert result.returncode == 2
    assert b"output" in result.stderr.lower()
    assert output.read_bytes() == b"keep this external response\n"
    after = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}
    assert after == before

    completed = invoke("hs-knowledge-apply", request, tmp_path / "fresh-apply-output.json", trial.root)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert json.loads((tmp_path / "fresh-apply-output.json").read_bytes())["phase"] == "committed"


def test_fresh_response_cannot_be_created_in_governed_knowledge(tmp_path):
    trial = pipeline(tmp_path)
    request = tmp_path / "scan-input.json"
    request.write_text('{"operation_id":"governed-output"}')
    output = trial.root / "knowledge/rules/response.json"

    result = invoke("hs-knowledge-source-scan", request, output, trial.root, "scan")

    assert result.returncode == 2
    assert not output.exists()
    assert not (trial.root / ".build/operations/governed-output").exists()


def test_concurrent_output_reservation_runs_only_one_business_operation(tmp_path):
    trial = pipeline(tmp_path)
    trial.write("docs-raw/specs/output-marker.md", b"# Output marker\nOne owner only.\n")
    output = tmp_path / "shared-response.json"
    processes = []
    for op in ("output-one", "output-two"):
        request = tmp_path / (op + ".json")
        request.write_text(json.dumps({"operation_id": op}))
        processes.append(subprocess.Popen([
            sys.executable, str(SKILLS / "hs-knowledge-source-scan/scripts/cli.py"),
            "--input", str(request), "--output", str(output),
            "--knowledge-root", str(trial.root), "--action", "scan",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    results = []
    for process in processes:
        process.communicate(timeout=60)
        results.append(process.returncode)

    assert sorted(results) == [0, 2]
    assert json.loads(output.read_bytes())["status"] == "ok"
    assert sum((trial.root / ".build/operations" / op).exists() for op in ("output-one", "output-two")) == 1


@pytest.mark.parametrize("dangling", [False, True])
def test_output_symlink_never_writes_its_target(tmp_path, dangling):
    root = tmp_path / "knowledge"
    root.mkdir()
    incoming = tmp_path / "input.json"
    incoming.write_text('{"operation_id":"linked-output"}')
    target = tmp_path / "outside.json"
    if not dangling:
        target.write_bytes(b"untouched target\n")
    output = tmp_path / "response-link.json"
    try:
        output.symlink_to(target)
    except OSError:
        pytest.skip("Host does not permit file symlinks")

    result = invoke("hs-knowledge-query", incoming, output, root)

    assert result.returncode == 2
    assert output.is_symlink()
    assert not target.exists() if dangling else target.read_bytes() == b"untouched target\n"


def test_output_parent_junction_is_rejected_before_business_execution(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction case")
    root = tmp_path / "knowledge"
    root.mkdir()
    incoming = tmp_path / "input.json"
    incoming.write_text('{"operation_id":"linked-parent"}')
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(target)], capture_output=True, check=True)

    result = invoke("hs-knowledge-query", incoming, alias / "response.json", root)

    assert result.returncode == 2
    assert list(target.iterdir()) == []


COMMON = [slug for slug in PACKAGES if "def run(handler, package):" in (SKILLS / slug / "scripts/support.py").read_text(encoding="utf-8")]


@pytest.mark.parametrize("slug", COMMON)
def test_sibling_with_no_response_reports_output_failure_without_leaking_stderr(tmp_path, monkeypatch, slug):
    spec = importlib.util.spec_from_file_location("output_support_" + slug.replace("-", "_"), SKILLS / slug / "scripts/support.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "knowledge"
    root.mkdir()
    package = tmp_path / "skills/caller"
    sibling = package.parent / "hs-knowledge-query/scripts/cli.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("# public child boundary\n")
    context = object.__new__(module.Context)
    context.root, context.package = root, package
    context.base = ".build/operations/sibling-output"
    context.args = SimpleNamespace(catalog=None, rules_digest="a" * 64)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 2, b"", b"secret-output-error"))

    with pytest.raises(module.NodeError) as captured:
        context.call("hs-knowledge-query", {"operation_id": "sibling-output"}, "search")

    assert captured.value.code == "SIBLING_RESULT_UNAVAILABLE"
    assert "secret-output-error" not in str(captured.value)


def test_independent_packages_ship_identical_output_guards():
    assert len(PACKAGES) == 18
    expected = {}
    for slug in PACKAGES:
        tree = ast.parse((SKILLS / slug / "scripts/support.py").read_text(encoding="utf-8"))
        for name in ("reserve_output", "finish_output"):
            node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
            normalized = ast.dump(node, include_attributes=False)
            assert normalized == expected.setdefault(name, normalized), (slug, name)


def explore_workspace(tmp_path, *, missing_entry=False):
    trial = pipeline(tmp_path)
    workspace = trial.root.parent
    (workspace / "main").mkdir()
    (workspace / "AGENTS.md").write_text("Read actual project rules.\n", encoding="utf-8")
    if not missing_entry:
        (trial.root / "AGENTS.md").write_text("Read actual domain rules.\n", encoding="utf-8")
    (workspace / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: output-workspace\n"
        "knowledge_roots:\n  wifi: himate-knowledge-wifi-mp\n"
        "code_root: main\nmodules: []\n", encoding="utf-8")
    request = tmp_path / "explore-request.json"
    request.write_text(json.dumps({"operation_id": "preflight-explore", "target_path": str(workspace / "main")}))
    return trial, request


def explore_command(request, output, explicit_root=None):
    command = [sys.executable, str(SKILLS / "hs-knowledge-explore/scripts/cli.py"),
               "--input", str(request), "--output", str(output)]
    if explicit_root is not None:
        command += ["--knowledge-root", str(explicit_root)]
    return command


@pytest.mark.parametrize("missing_entry", [False, True])
@pytest.mark.parametrize("wrong_explicit_root", [False, True])
def test_explore_discovers_actual_root_before_output_or_context_writes(tmp_path, missing_entry, wrong_explicit_root):
    trial, request = explore_workspace(tmp_path, missing_entry=missing_entry)
    output = trial.root / "knowledge/rules/response.md"
    before = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}
    explicit = tmp_path / "wrong-knowledge-root" if wrong_explicit_root else None

    result = subprocess.run(explore_command(request, output, explicit), capture_output=True, timeout=60)

    assert result.returncode == 2
    assert not output.exists()
    after = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}
    assert after == before
    assert result.stderr


@pytest.mark.parametrize("external_output", [False, True])
def test_explore_unresolved_mapping_keeps_diagnostics_on_console_only(tmp_path, external_output):
    trial, request = explore_workspace(tmp_path)
    config = trial.root.parent / "config.yml"
    config.write_text("knowledge_roots: {}\n", encoding="utf-8")
    request.write_text(json.dumps({"operation_id": "preflight-explore", "target_path": str(trial.root.parent / "main"), "config_path": str(config)}))
    output = tmp_path / "external-error.json" if external_output else trial.root / "knowledge/rules/error.md"
    before = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}

    result = subprocess.run(explore_command(request, output), capture_output=True, timeout=60)

    assert result.returncode == 2
    assert not output.exists()
    after = {p.relative_to(trial.root).as_posix(): p.read_bytes() for p in trial.root.rglob("*") if p.is_file()}
    assert after == before
    assert result.stderr
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "DOMAIN_MAPPING_INVALID"


def test_explore_implicit_root_still_accepts_fresh_allowed_response(tmp_path):
    trial, request = explore_workspace(tmp_path)
    output = trial.root / ".build/responses/context.json"

    result = subprocess.run(explore_command(request, output), capture_output=True, timeout=60)

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    response = json.loads(output.read_bytes())
    assert response["phase"] == "context_loaded"
    assert Path(response["data"]["knowledge_root"]) == trial.root


def test_explore_checks_config_snapshot_after_output_preflight(tmp_path):
    trial, request = explore_workspace(tmp_path)
    output = trial.root / ".build/responses/context.json"
    cli = SKILLS / "hs-knowledge-explore/scripts/cli.py"
    config = trial.root.parent / "config.yml"
    launch = """
import runpy
from pathlib import Path
import sys
cli, config = sys.argv[1:3]
sys.path.insert(0, str(Path(cli).parent))
import support
original = support.reserve_output
def reserve(*args, **kwargs):
    stream = original(*args, **kwargs)
    path = Path(config)
    path.write_text(path.read_text(encoding='utf-8').replace('output-workspace', 'changed-workspace'), encoding='utf-8')
    return stream
support.reserve_output = reserve
sys.argv = [cli] + sys.argv[3:]
runpy.run_path(cli, run_name='__main__')
"""
    result = subprocess.run([sys.executable, "-c", launch, str(cli), str(config),
                             "--input", str(request), "--output", str(output)], capture_output=True, timeout=60)

    assert result.returncode == 3
    response = json.loads(output.read_bytes())
    assert response["diagnostics"][0]["code"] == "ENTRY_CHANGED"
    assert not (trial.root / ".build/project-context").exists()
