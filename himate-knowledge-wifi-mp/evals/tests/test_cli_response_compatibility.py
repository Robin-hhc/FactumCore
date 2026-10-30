"""Supported public-call retries retain the original response transport contract."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SPEC = importlib.util.spec_from_file_location(
    "response_compatibility_fixture", Path(__file__).parents[1] / "pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


@pytest.mark.parametrize("skill", FIXTURE.PUBLIC_SKILLS)
def test_missing_repository_runtime_returns_an_external_diagnostic_without_creating_k(tmp_path, skill):
    knowledge = tmp_path / "missing-knowledge"
    response = tmp_path / "response.json"
    cli = FIXTURE.REPO / "skills/common/knowledge" / skill / "scripts/cli.py"
    action = ["--action", "review"] if skill == "hs-knowledge-lint" else []
    process = subprocess.run([
        sys.executable, str(cli), "--knowledge-root", str(knowledge),
        "--input", str(tmp_path / "missing-request.json"), "--output", str(response),
        *action,
    ], capture_output=True, timeout=30)
    assert process.returncode == 2, process.stderr
    report = json.loads(process.stdout.decode("ascii"))
    assert report == json.loads(response.read_bytes())
    assert report["status"] == "error"
    assert report["diagnostics"][0]["code"] == "KNOWLEDGE_RUNTIME_UNAVAILABLE"
    assert not knowledge.exists()
    assert b"Traceback" not in process.stderr


@pytest.mark.parametrize("action", [None, "lint", "run", "check"])
def test_missing_runtime_formal_lint_keeps_incomplete_stdout_without_a_report(tmp_path, action):
    knowledge = tmp_path / "missing-knowledge"
    response = tmp_path / "must-not-be-written.json"
    command = [
        sys.executable, str(FIXTURE.REPO / "skills/common/knowledge/hs-knowledge-lint/scripts/cli.py"),
        "--knowledge-root", str(knowledge), "--output", str(response),
    ]
    if action is not None:
        command += ["--action", action]
    process = subprocess.run(command, capture_output=True, timeout=30)
    assert process.returncode == 2
    report = json.loads(process.stdout.decode("ascii"))
    assert report["report_version"] == "1.0"
    assert report["status"] == report["phase"] == "incomplete"
    assert report["exit_code"] == 2 and report["complete"] is False
    assert report["checks"] == [] and report["findings"][0]["code"] == "LINT_UNAVAILABLE"
    assert not response.exists() and not knowledge.exists()


@pytest.mark.parametrize("sink", ["existing", "inside-missing", "other-knowledge", "linked"])
def test_missing_runtime_diagnostic_preserves_unsafe_or_existing_output(tmp_path, sink):
    knowledge = tmp_path / "missing-knowledge"
    response, link = tmp_path / "response.json", None
    if sink == "existing":
        response.write_bytes(b"existing response is not overwritten")
    elif sink == "inside-missing":
        response = knowledge / ".build/response.json"
    elif sink == "other-knowledge":
        other = tmp_path / "other-knowledge"
        (other / "governance").mkdir(parents=True)
        (other / "governance/framework.lock.yaml").write_text("explicit fixture marker", encoding="utf-8")
        response = other / "knowledge/new.md"
    else:
        target = tmp_path / "actual"
        target.mkdir()
        link = tmp_path / "alias"
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
        response = link / "response.json"
    try:
        process = subprocess.run([
            sys.executable, str(FIXTURE.REPO / "skills/common/knowledge/hs-knowledge-apply/scripts/cli.py"),
            "--knowledge-root", str(knowledge), "--input", str(tmp_path / "missing.json"),
            "--output", str(response),
        ], capture_output=True, timeout=30)
        assert process.returncode == 2 and json.loads(process.stdout.decode("ascii"))["status"] == "error"
        if sink == "existing":
            assert response.read_bytes() == b"existing response is not overwritten"
        else:
            assert not response.exists()
        assert not knowledge.exists()
        assert b"Traceback" not in process.stderr
    finally:
        if link is not None:
            link.rmdir() if sys.platform == "win32" else link.unlink()


def invoke(pipeline, slug, request, response, action=None):
    command = [sys.executable, str(pipeline.skills / ("hs-" + slug) / "scripts/cli.py"),
               "--input", str(request), "--output", str(response),
               "--knowledge-root", str(pipeline.root)]
    if action:
        command += ["--action", action]
    return subprocess.run(command, capture_output=True, timeout=90)


def business_files(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def test_status_retry_can_reuse_its_ordinary_response_path(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    request = tmp_path / "status-request.json"
    response = tmp_path / "status-response.json"
    request.write_text('{"operation_id":"status-retry"}', encoding="utf-8")
    before = business_files(pipeline.root)

    first = invoke(pipeline, "knowledge-source", request, response, "status")
    assert first.returncode == 0, first.stderr.decode(errors="replace")
    original_response = response.read_bytes()
    assert json.loads(original_response)["status"] == "ok"
    second = invoke(pipeline, "knowledge-source", request, response, "status")

    assert second.returncode == 0, second.stderr.decode(errors="replace")
    assert response.read_bytes() == original_response
    assert business_files(pipeline.root) == before


def test_committed_apply_retry_accepts_its_same_exact_response(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = pipeline.capture("apply-retry", b"# Source\nCapture marker is a documented rule.\n")
    view_ref = pipeline.view("apply-retry", bundle_ref, "retry-rule", pipeline.card("retry-rule", bundle))
    review_ref, _ = pipeline.review("apply-retry", view_ref)
    pending_ref = pipeline.pending_record("apply-retry", view_ref)
    request = tmp_path / "apply-request.json"
    response = tmp_path / "apply-response.json"
    request.write_text(json.dumps({"operation_id": "apply-retry", "view_ref": view_ref,
                                   "content_review_ref": review_ref, "ingest_record_ref": pending_ref}), encoding="utf-8")

    first = invoke(pipeline, "knowledge-apply", request, response)
    assert first.returncode == 0, first.stderr.decode(errors="replace")
    original_response = response.read_bytes()
    assert json.loads(original_response)["phase"] == "committed"
    committed_files = business_files(pipeline.root)
    second = invoke(pipeline, "knowledge-apply", request, response)

    assert second.returncode == 0, second.stderr.decode(errors="replace")
    assert response.read_bytes() == original_response
    assert business_files(pipeline.root) == committed_files
