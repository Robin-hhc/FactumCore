"""A real Office/figure workflow through the shipped CLI in a synthetic root."""

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from docx import Document
from PIL import Image
import pytest
import yaml


SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture
def rapid_ocr_models(monkeypatch):
    pytest.importorskip("docling.document_converter")
    installed = os.environ.get("HIMATE_TEST_DOCLING_MODELS")
    models = Path(installed) if installed else Path.home() / ".himate/knowledge/tools/deploy/models/docling-cpu"
    rapid = models / "RapidOcr"
    if installed is None and not rapid.is_dir():
        pytest.skip("Install the local OCR models or set HIMATE_TEST_DOCLING_MODELS")
    assert rapid.is_dir(), f"Local RapidOcr models are missing from {models}"
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    return rapid


def invoke(root, *arguments):
    environment = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-B", str(SOURCE / "knowledge.py"), *arguments, "--knowledge-root", str(root), "--json"],
        cwd=root, env=environment, capture_output=True, encoding="utf-8", timeout=180,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_office_figures_p5_cleanup_query_and_independent_source_release(tmp_path, rapid_ocr_models):
    project = tmp_path / "project"
    root = project / "himate/synthetic"
    root.mkdir(parents=True)
    (root / "governance").mkdir()
    (root / "governance/sources.lock.yaml").write_text(
        "schema_version: '2.0'\nresources: []\nsnapshots: []\n", encoding="utf-8")
    (root / "config.yml").write_text(
        "schema_version: '2.0'\nworkspace_id: synthetic\n"
        "code_root: ../../main\nmodules: []\n", encoding="utf-8")
    (root / "docs-raw").mkdir()
    (root / "knowledge").mkdir()
    original = root / "docs-raw/design.docx"
    document = Document()
    document.add_paragraph("The design requires three retry attempts.")
    picture = BytesIO()
    Image.new("RGB", (40, 40), "navy").save(picture, format="PNG")
    picture.seek(0)
    document.add_picture(picture)
    document.save(original)
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()

    models_ref = "artifacts/models/local"
    shutil.copytree(rapid_ocr_models, root / models_ref / "RapidOcr")
    request = root / "artifacts/scan.json"
    request.write_text(json.dumps({"source": "docs-raw/design.docx", "parser": {"models_path": models_ref}}),
                       encoding="utf-8")
    scanned = invoke(root, "ingest", "scan", "--input", str(request))["data"]
    source_id = scanned["source"]["source_id"]
    parsed = scanned["source"]["parsed"]
    assert parsed["parse_status"] == "parsed", parsed
    manifest = json.loads((root / parsed["manifest_ref"]).read_bytes())
    markdown = (root / parsed["markdown_ref"]).read_text(encoding="utf-8")
    assert manifest["images"] and "three retry" in markdown
    for item in manifest["images"]:
        asset = root / item["ref"]
        if os.name == "nt":
            asset = Path("\\\\?\\" + str(asset))
        assert asset.is_file() and f"images/{asset.name}" in markdown
    metadata = {"id": "retry-design", "doc_ref": [
        {"doc_id": source_id, "locator": {"kind": "paragraph", "paragraph": 1}},
    ], "code_ref": []}
    (root / ".build/cards/retry.md").write_text(
        "---\n" + yaml.safe_dump(metadata, sort_keys=False)
        + "---\n# Retry design\n\nretry_count is three by design; runtime behavior is unverified.\n",
        encoding="utf-8")
    (root / ".build/plan.md").write_text(
        "---\ncards: [{id: retry-design, path: knowledge/retry.md}]\n---\n"
        "Preserve the documented retry design.\n", encoding="utf-8")
    assert invoke(root, "ingest", "check")["phase"] == "passed"
    assert invoke(root, "ingest", "commit")["phase"] == "completed"
    assert not (root / ".build").exists()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    assert invoke(root, "search", "retry_count")["data"]["matches"][0]["card_id"] == "retry-design"

    # A later, separate ingestion remains intact while this document is read.
    (root / "docs-raw/next.md").write_text("# Another source\n\nA separate design.\n", encoding="utf-8")
    invoke(root, "ingest", "scan", "--source", "docs-raw/next.md")
    build_before = {p.relative_to(root).as_posix(): p.read_bytes()
                    for p in (root / ".build").rglob("*") if p.is_file()}
    request = root / "artifacts/extract.json"
    request.write_text(json.dumps({"source_id": source_id}), encoding="utf-8")
    reading = invoke(root, "source", "extract", "--input", str(request))["data"]
    assert reading["parsed"]["images"]
    assert all((root / item["ref"]).is_file() for item in reading["parsed"]["images"])
    assert invoke(root, "read", "retry-design")["data"]["card_id"] == "retry-design"
    request.write_text(json.dumps({"read_id": reading["read_id"]}), encoding="utf-8")
    assert invoke(root, "source", "release", "--input", str(request))["data"]["released"] is True
    assert not (root / "artifacts/source-read" / reading["read_id"]).exists()
    assert {p.relative_to(root).as_posix(): p.read_bytes()
            for p in (root / ".build").rglob("*") if p.is_file()} == build_before
