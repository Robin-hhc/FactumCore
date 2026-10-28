"""Supported public-call retries retain the original response transport contract."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


SPEC = importlib.util.spec_from_file_location(
    "response_compatibility_fixture", Path(__file__).parents[1] / "pipeline_harness.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


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

    first = invoke(pipeline, "knowledge-source-scan", request, response, "status")
    assert first.returncode == 0, first.stderr.decode(errors="replace")
    original_response = response.read_bytes()
    assert json.loads(original_response)["status"] == "ok"
    second = invoke(pipeline, "knowledge-source-scan", request, response, "status")

    assert second.returncode == 0, second.stderr.decode(errors="replace")
    assert response.read_bytes() == original_response
    assert business_files(pipeline.root) == before


def test_committed_apply_retry_accepts_its_same_exact_response(tmp_path):
    pipeline = FIXTURE.Pipeline(tmp_path)
    bundle_ref, bundle = pipeline.capture("apply-retry", b"# Source\nCapture marker is a documented rule.\n")
    view_ref = pipeline.view("apply-retry", bundle_ref, "retry-rule", pipeline.card("retry-rule", bundle))
    review_ref, _ = pipeline.review("apply-retry", view_ref)
    request = tmp_path / "apply-request.json"
    response = tmp_path / "apply-response.json"
    request.write_text(json.dumps({"operation_id": "apply-retry", "view_ref": view_ref,
                                   "content_review_ref": review_ref}), encoding="utf-8")

    first = invoke(pipeline, "knowledge-apply", request, response)
    assert first.returncode == 0, first.stderr.decode(errors="replace")
    original_response = response.read_bytes()
    assert json.loads(original_response)["phase"] == "committed"
    committed_files = business_files(pipeline.root)
    second = invoke(pipeline, "knowledge-apply", request, response)

    assert second.returncode == 0, second.stderr.decode(errors="replace")
    assert response.read_bytes() == original_response
    assert business_files(pipeline.root) == committed_files
