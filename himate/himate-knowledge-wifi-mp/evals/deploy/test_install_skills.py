"""Contained deployment and shared interaction; no real pip or user directories."""

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2]


def test_ocr_dependencies_accept_standard_mirror_distributions():
    runtime = KNOWLEDGE_ROOT / "runtime"
    lock = runtime / "requirements.lock.txt"
    pins = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        if line.startswith(("torch==", "torchvision==")):
            name, version = line.split("==", 1)
            pins[name] = version.split(";", 1)[0].strip()
    assert set(pins) == {"torch", "torchvision"}
    assert all("+" not in version for version in pins.values())
    lines = [line.strip() for line in lock.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert all("://" not in line for line in lines)


@pytest.fixture
def distribution(tmp_path):
    spec = importlib.util.spec_from_file_location("skill_deploy", KNOWLEDGE_ROOT / "tools/deploy/deploy.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    source = tmp_path / "project with spaces" / "himate" / "knowledge-root"
    package = source / "skills/hs-knowledge-example"
    (package / "references").mkdir(parents=True)
    (package / "SKILL.md").write_text("current instructions", encoding="utf-8")
    (package / "references/guide.md").write_text("business reference", encoding="utf-8")
    workflows = source / "workflows"
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        template = workflows / name
        template.mkdir(parents=True)
        (template / "workflow.yaml").write_text("id: " + name + "\n", encoding="utf-8")
        (template / "layouts.yaml").write_text("canvas: {}\n", encoding="utf-8")
        (template / "README.md").write_text("工作流说明\n", encoding="utf-8")
    (workflows / "not-a-template").mkdir()
    (workflows / "not-a-template/README.md").write_text("not a workflow", encoding="utf-8")
    lock = source / "runtime/requirements.lock.txt"
    lock.parent.mkdir(parents=True)
    lock.write_text("PyYAML==6.0.3\nrapidocr==3.10.0\n", encoding="utf-8")
    (source / "config.yml").write_text("workspace_id: synthetic\n", encoding="utf-8")
    (source / "AGENTS-code-root.md").write_text("# Synthetic project instructions\n", encoding="utf-8")
    assert not (source.parents[1] / ".git").exists()
    return backend, source, package, workflows, lock


def arguments(source, tmp_path):
    return ["--source-root", str(source),
            "--skills-root", str(tmp_path / "installed skills"),
            "--cac-skills-root", str(tmp_path / "cac skills"),
            "--workflows-root", str(tmp_path / "workflow templates"), "--non-interactive"]


def test_copy_all_destinations_then_project_entries_without_git(distribution, tmp_path, monkeypatch):
    backend, source, package, workflows, lock = distribution
    skill_targets = [tmp_path / "installed skills", tmp_path / "cac skills"]
    workflow_target = tmp_path / "workflow templates"
    stale = []
    for target in skill_targets:
        (target / package.name).mkdir(parents=True)
        (target / package.name / "SKILL.md").write_text("old", encoding="utf-8")
        old = target / package.name / "old-script.py"
        old.write_text("retired script", encoding="utf-8")
        stale.append(old)
        (target / "user-package").mkdir()
        (target / "user-package/SKILL.md").write_text("keep", encoding="utf-8")
    (workflow_target / "hs-knowledge-ingest").mkdir(parents=True)
    old = workflow_target / "hs-knowledge-ingest/user-notes.txt"
    old.write_text("old", encoding="utf-8")
    stale.append(old)
    (workflow_target / "user-workflow").mkdir()
    (workflow_target / "user-workflow/workflow.yaml").write_text("keep", encoding="utf-8")
    calls, phases = [], []

    def run(command, **kwargs):
        assert all(path.is_file() for path in stale)
        assert not (source.parents[1] / "config.yml").exists()
        calls.append((command, kwargs))
        phases.append("install" if command[1:3] == ["-m", "pip"] else "models")

    monkeypatch.setattr(backend.subprocess, "run", run)
    original_remove, original_copy = backend.shutil.rmtree, backend.shutil.copytree

    def remove(*args, **kwargs):
        phases.append("delete")
        return original_remove(*args, **kwargs)

    def copy(*args, **kwargs):
        phases.append("copy")
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(backend.shutil, "rmtree", remove)
    monkeypatch.setattr(backend.shutil, "copytree", copy)
    selected_python = str(tmp_path / "chosen-env/python.exe")
    assert backend.main([*arguments(source, tmp_path), "--python", selected_python]) == 0
    for target in skill_targets:
        assert (target / package.name / "SKILL.md").read_text(encoding="utf-8") == "current instructions"
        assert (target / package.name / "references/guide.md").read_text(encoding="utf-8") == "business reference"
        assert (target / "user-package/SKILL.md").read_text(encoding="utf-8") == "keep"
        assert set(path.name for path in target.iterdir()) == {package.name, "user-package"}
    for name in ("hs-knowledge-ingest", "hs-knowledge-lint"):
        for filename in ("workflow.yaml", "layouts.yaml", "README.md"):
            assert (workflow_target / name / filename).read_bytes() == (workflows / name / filename).read_bytes()
    assert all(not path.exists() for path in stale)
    assert (workflow_target / "user-workflow/workflow.yaml").read_text(encoding="utf-8") == "keep"
    assert not (workflow_target / "not-a-template").exists()
    for original, name in (("config.yml", "config.yml"), ("AGENTS-code-root.md", "AGENTS.md")):
        assert (source.parents[1] / name).read_bytes() == (source / original).read_bytes()
        assert (source / original).is_file()
    assert calls == [
        ([selected_python, "-m", "pip", "install", "-r",
          str(lock)], {"check": True}),
        ([selected_python, "-c", backend.OCR_PREPARE, str(source), "local"], {"check": True}),
    ]
    assert phases[:2] == ["install", "models"]
    assert max(index for index, phase in enumerate(phases) if phase == "delete") < phases.index("copy")


def test_failed_pip_keeps_packages_and_project_files(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    for root, name, filename in ((tmp_path / "installed skills", package.name, "SKILL.md"),
                                 (tmp_path / "cac skills", package.name, "SKILL.md"),
                                 (tmp_path / "workflow templates", "hs-knowledge-ingest", "workflow.yaml")):
        old = root / name / filename
        old.parent.mkdir(parents=True)
        old.write_bytes(b"old installed package")
    for name in ("config.yml", "AGENTS.md"):
        (source.parents[1] / name).write_text("old project file", encoding="utf-8")
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backend.subprocess, "run", fail)
    assert backend.main(arguments(source, tmp_path)) == 1
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_failed_model_preparation_keeps_packages_and_project_files(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    protected = []
    for root, name, filename in ((tmp_path / "installed skills", package.name, "SKILL.md"),
                                 (tmp_path / "cac skills", package.name, "SKILL.md"),
                                 (tmp_path / "workflow templates", "hs-knowledge-ingest", "workflow.yaml")):
        old = root / name / filename
        old.parent.mkdir(parents=True)
        old.write_bytes(b"old installed package")
        protected.append(old)
    for name in ("config.yml", "AGENTS.md"):
        old = source.parents[1] / name
        old.write_bytes(b"old project file")
        protected.append(old)
    before = {path: path.read_bytes() for path in protected}
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "-c":
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(backend.subprocess, "run", run)
    assert backend.main(arguments(source, tmp_path)) == 1
    assert len(calls) == 2
    assert {path: path.read_bytes() for path in protected} == before


def test_missing_runtime_lock_fails_before_install(distribution, tmp_path, monkeypatch):
    backend, source, _, _, lock = distribution
    lock.unlink()
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(arguments(source, tmp_path)) == 1
    assert calls == []


@pytest.mark.parametrize("extra", [[], ["--download-models"]])
def test_removed_skip_option_is_rejected_before_install(distribution, tmp_path, monkeypatch, extra):
    backend, source, _, _, _ = distribution
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(SystemExit) as error:
        backend.main([*arguments(source, tmp_path), "--skip-ocr", *extra])
    assert error.value.code == 2
    assert calls == []


def test_explicit_download_is_forwarded_to_selected_python(distribution, tmp_path, monkeypatch):
    backend, source, _, _, _ = distribution
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda command, **kwargs: calls.append(command))
    assert backend.main([*arguments(source, tmp_path), "--download-models", "--python", "chosen-python"]) == 0
    assert calls[0][:5] == ["chosen-python", "-m", "pip", "install", "-r"]
    assert calls[1] == ["chosen-python", "-c", backend.OCR_PREPARE, str(source), "download"]


@pytest.fixture
def model_preparation(distribution, tmp_path, tmp_path_factory):
    backend, _, _, _, _ = distribution
    # Model names are long; keep fixtures below ordinary Windows path limits.
    source = tmp_path_factory.mktemp("models") / "source root"
    contracts = source / "governance/contracts"
    contracts.mkdir(parents=True)
    for name in ("__init__.py", "document_parser.py", "validation.py", "workspace_config.py"):
        shutil.copyfile(KNOWLEDGE_ROOT / "governance/contracts" / name, contracts / name)
    required = (
        "docling-project--docling-layout-heron/config.json",
        "docling-project--docling-layout-heron/preprocessor_config.json",
        "docling-project--docling-layout-heron/model.safetensors",
        "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
        "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
        "RapidOcr/PP-OCRv6_det_small.onnx", "RapidOcr/PP-OCRv6_rec_small.onnx",
        "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    )
    fake = tmp_path / "fake document packages"
    downloader = fake / "docling/utils/model_downloader.py"
    downloader.parent.mkdir(parents=True)
    for directory in (downloader.parent, downloader.parent.parent):
        (directory / "__init__.py").write_text("", encoding="utf-8")
    downloader.write_text(
        "import json\nimport os\nfrom pathlib import Path\n\n"
        "def download_models(**options):\n"
        "    directory = options.pop('output_dir')\n"
        "    Path(os.environ['FACTUM_MODEL_CAPTURE']).write_text(json.dumps(\n"
        "        dict(options, output_dir=str(directory))), encoding='utf-8')\n"
        "    mode = os.environ.get('FACTUM_MODEL_MODE', 'complete')\n"
        "    if mode == 'download-error':\n"
        "        raise RuntimeError('Synthetic model download failure')\n"
        "    if mode == 'missing-output':\n"
        "        return\n"
        f"    for reference in {required!r}:\n"
        "        target = directory / reference\n"
        "        target.parent.mkdir(parents=True, exist_ok=True)\n"
        "        if options.get('force', False) or not target.exists():\n"
        "            target.write_bytes(b'synthetic model')\n", encoding="utf-8")
    capture = tmp_path / "download.json"
    environment = {**os.environ, "PYTHONPATH": str(fake), "FACTUM_MODEL_CAPTURE": str(capture),
                   "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, "-c", backend.OCR_PREPARE, str(source), "download"]
    return source / "artifacts/models/docling-cpu", required, downloader, capture, command, environment


def test_default_model_preparation_requires_offline_models_without_downloader(model_preparation):
    directory, _, downloader, capture, command, environment = model_preparation
    downloader.write_text("raise AssertionError('Default deployment must not import the downloader')\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "preinstall the models offline or explicitly use --download-models" in result.stderr
    assert "No model download was attempted" in result.stderr
    assert "AssertionError" not in result.stderr
    assert not capture.exists()
    assert not directory.exists()


def test_model_preparation_downloads_chinese_models_then_reuses_complete_set(model_preparation):
    directory, required, downloader, capture, command, environment = model_preparation
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Prepared local CPU OCR models" in result.stdout
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "output_dir": str(directory), "with_layout": True, "with_tableformer": True,
        "with_code_formula": False, "with_picture_classifier": False,
        "with_rapidocr": True, "rapidocr_models": ["onnxruntime:ch"], "progress": False, "force": True,
    }
    assert all((directory / reference).stat().st_size for reference in required)
    before = {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    downloader.write_text("raise AssertionError('Complete models must not import the downloader')\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Reused complete local CPU OCR models" in result.stdout
    assert {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("mode", ["download-error", "missing-output"])
def test_model_preparation_reports_download_and_incomplete_model_failures(model_preparation, mode):
    directory, required, _, capture, command, environment = model_preparation
    old = directory / required[0]
    old.parent.mkdir(parents=True)
    old.write_bytes(b"existing partial model")
    result = subprocess.run(command, env={**environment, "FACTUM_MODEL_MODE": mode},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert capture.is_file()
    assert old.read_bytes() == b"existing partial model"
    assert "Prepared local CPU OCR models" not in result.stdout
    assert ("Synthetic model download failure" if mode == "download-error"
            else "PARSER_MODELS_REQUIRED") in result.stderr


def test_model_preparation_replaces_empty_required_asset(model_preparation):
    directory, required, _, capture, command, environment = model_preparation
    for reference in required:
        path = directory / reference
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"existing model")
    (directory / required[-1]).write_bytes(b"")
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert capture.is_file()
    assert (directory / required[-1]).stat().st_size


@pytest.mark.parametrize("linked_directory", ["RapidOcr", ".cache"])
def test_model_download_rejects_later_link_before_loading_downloader(model_preparation, linked_directory):
    directory, required, downloader, capture, command, environment = model_preparation
    external = directory.parents[2] / "outside models"
    external.mkdir(parents=True)
    keep = external / "keep.txt"
    keep.write_bytes(b"keep external model directory")
    directory.mkdir(parents=True)
    try:
        (directory / linked_directory).symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links unavailable")
    assert not (directory / required[0]).exists()
    downloader.write_text("raise AssertionError('Unsafe model subtree must fail before downloader import')\n", encoding="utf-8")
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "AssertionError" not in result.stderr
    assert not capture.exists()
    assert not (directory / required[0]).exists()
    assert {path.name: path.read_bytes() for path in external.iterdir()} == {
        "keep.txt": b"keep external model directory"}


def write_model_bundle(model_preparation):
    directory, required, _, _, _, _ = model_preparation
    base = directory.parents[2] / "tools/deploy/models"
    bundle = base / "docling-cpu"
    rows = []
    for reference in required:
        data = ("bundled model: " + reference).encode("utf-8")
        path = bundle / reference
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        rows.append({"path": reference, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()})
    manifest = base / "manifest.json"
    value = {"schema_version": "1.0", "model_set": "docling-cpu", "files": rows,
             "total_bytes": sum(row["bytes"] for row in rows)}
    manifest.write_text(json.dumps(value), encoding="utf-8")
    return bundle, manifest, value


def write_split_model_bundle(model_preparation):
    bundle, manifest, value = write_model_bundle(model_preparation)
    originals = {}
    for row in value["files"]:
        if not row["path"].endswith(".safetensors"):
            continue
        source = bundle / row["path"]
        data = source.read_bytes()
        originals[row["path"]] = data
        midpoint = len(data) // 2
        row["parts"] = []
        for index, part in enumerate((data[:midpoint], data[midpoint:]), start=1):
            reference = row["path"] + f".part{index:03d}"
            (bundle / reference).write_bytes(part)
            row["parts"].append({"path": reference, "bytes": len(part),
                                 "sha256": hashlib.sha256(part).hexdigest()})
        source.unlink()
    value["schema_version"] = "1.1"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    return bundle, manifest, value, originals


def test_default_model_preparation_reassembles_split_weights_without_downloader(model_preparation):
    directory, required, downloader, capture, command, environment = model_preparation
    bundle, _, _, originals = write_split_model_bundle(model_preparation)
    downloader.write_text("raise AssertionError('Split models must not import downloader')\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Installed bundled CPU OCR models" in result.stdout
    assert not capture.exists()
    for reference in required:
        expected = originals[reference] if reference in originals else (bundle / reference).read_bytes()
        assert (directory / reference).read_bytes() == expected
    assert not list(directory.rglob("*.part*"))
    assert not list(directory.rglob("*.tmp"))
    assert all(not (bundle / reference).exists() for reference in originals)


@pytest.mark.parametrize("damage", ["missing-part", "part-digest", "order", "duplicate", "escape",
                                    "parts-total", "whole-digest", "empty-parts"])
def test_invalid_split_bundle_fails_before_writing_or_downloading(model_preparation, damage):
    directory, _, downloader, capture, command, environment = model_preparation
    bundle, manifest, value, _ = write_split_model_bundle(model_preparation)
    row = next(row for row in value["files"] if "parts" in row)
    if damage == "missing-part":
        (bundle / row["parts"][-1]["path"]).unlink()
    elif damage == "part-digest":
        path = bundle / row["parts"][-1]["path"]
        path.write_bytes(b"x" * path.stat().st_size)
    elif damage == "order":
        row["parts"].reverse()
    elif damage == "duplicate":
        row["parts"][-1] = dict(row["parts"][0])
    elif damage == "escape":
        row["parts"][-1]["path"] = "../outside.part002"
    elif damage == "parts-total":
        row["parts"][-1]["bytes"] += 1
    elif damage == "whole-digest":
        row["sha256"] = "0" * 64
    elif damage == "empty-parts":
        row["parts"] = []
    manifest.write_text(json.dumps(value), encoding="utf-8")
    downloader.write_text("raise AssertionError('Invalid split bundle must not import downloader')\n", encoding="utf-8")
    directory.mkdir(parents=True)
    (directory / "keep.txt").write_bytes(b"unrelated local file")
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "AssertionError" not in result.stderr
    assert not capture.exists()
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == {"keep.txt": b"unrelated local file"}


def test_interrupted_split_copy_preserves_old_model_and_removes_temporary(model_preparation):
    directory, _, downloader, capture, command, environment = model_preparation
    _, manifest, value, _ = write_split_model_bundle(model_preparation)
    split = next(row for row in value["files"] if "parts" in row)
    value["files"].remove(split)
    value["files"].insert(0, split)
    manifest.write_text(json.dumps(value), encoding="utf-8")
    existing = directory / split["path"]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing local model")
    (downloader.parents[2] / "sitecustomize.py").write_text(
        "import shutil\n"
        "original_copy = shutil.copyfileobj\n"
        "def interrupted_copy(source, destination, length):\n"
        "    if str(source.name).endswith('.part002'):\n"
        "        destination.write(b'partial second part')\n"
        "        raise OSError('Synthetic interrupted split copy')\n"
        "    return original_copy(source, destination, length)\n"
        "shutil.copyfileobj = interrupted_copy\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and "Synthetic interrupted split copy" in result.stderr
    assert not capture.exists()
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == {split["path"]: b"existing local model"}


def test_default_model_preparation_installs_verified_bundle_without_downloader(model_preparation):
    directory, required, downloader, capture, command, environment = model_preparation
    bundle, manifest, _ = write_model_bundle(model_preparation)
    (bundle / required[0]).chmod(0o640)
    downloader.write_text("raise AssertionError('Bundled models must not import downloader')\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Installed bundled CPU OCR models" in result.stdout
    assert not capture.exists()
    for reference in required:
        assert (directory / reference).read_bytes() == (bundle / reference).read_bytes()
        assert stat.S_IMODE((directory / reference).stat().st_mode) == stat.S_IMODE((bundle / reference).stat().st_mode)
    assert not list(directory.rglob("*.tmp"))
    before = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    manifest.write_text("invalid bundle, but runtime models are already complete", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0 and "Reused complete" in result.stdout, result.stderr
    assert {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("damage", ["hash", "size", "missing-file", "missing-entry", "duplicate",
                                    "escape", "invalid-hash", "total", "schema", "missing-manifest"])
def test_invalid_model_bundle_fails_before_writing_or_downloading(model_preparation, damage):
    directory, required, downloader, capture, command, environment = model_preparation
    bundle, manifest, value = write_model_bundle(model_preparation)
    if damage == "hash":
        path = bundle / required[-1]
        path.write_bytes(b"x" * path.stat().st_size)
    elif damage == "size":
        value["files"][-1]["bytes"] += 1
    elif damage == "missing-file":
        (bundle / required[-1]).unlink()
    elif damage == "missing-entry":
        value["files"].pop()
        value["total_bytes"] = sum(row["bytes"] for row in value["files"])
    elif damage == "duplicate":
        value["files"].append(value["files"][0])
    elif damage == "escape":
        value["files"][-1]["path"] = "../outside.onnx"
    elif damage == "invalid-hash":
        value["files"][-1]["sha256"] = "not a digest"
    elif damage == "total":
        value["total_bytes"] += 1
    elif damage == "schema":
        value["schema_version"] = "unsupported"
    if damage == "missing-manifest":
        manifest.unlink()
    else:
        manifest.write_text(json.dumps(value), encoding="utf-8")
    downloader.write_text("raise AssertionError('Invalid bundle must not import downloader')\n", encoding="utf-8")
    directory.mkdir(parents=True)
    keep = directory / "keep.txt"
    keep.write_bytes(b"unrelated local file")
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "AssertionError" not in result.stderr
    assert not capture.exists()
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == {"keep.txt": b"unrelated local file"}


@pytest.mark.parametrize("location", ["bundle", "runtime"])
@pytest.mark.parametrize("subtree", ["RapidOcr", ".cache"])
def test_bundle_install_rejects_links_before_any_copy(model_preparation, location, subtree):
    directory, required, downloader, capture, command, environment = model_preparation
    bundle, _, _ = write_model_bundle(model_preparation)
    external = directory.parents[2] / "outside bundle"
    external.mkdir()
    keep = external / "keep.txt"
    keep.write_bytes(b"keep external")
    selected = bundle if location == "bundle" else directory
    selected.mkdir(parents=True, exist_ok=True)
    target = selected / subtree
    if target.exists():
        shutil.rmtree(target)
    try:
        target.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links unavailable")
    downloader.write_text("raise AssertionError('Unsafe subtree must not import downloader')\n", encoding="utf-8")
    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert "AssertionError" not in result.stderr
    assert not capture.exists()
    assert not (directory / required[0]).exists()
    assert {p.name: p.read_bytes() for p in external.iterdir()} == {"keep.txt": b"keep external"}


def test_interrupted_bundle_copy_preserves_old_file_and_removes_partial_temporary(model_preparation):
    directory, required, downloader, capture, command, environment = model_preparation
    write_model_bundle(model_preparation)
    existing = directory / required[0]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing local model")
    (downloader.parents[2] / "sitecustomize.py").write_text(
        "import shutil\n"
        "def interrupted_copy(source, destination, length):\n"
        "    destination.write(b'partial model')\n"
        "    raise OSError('Synthetic interrupted model copy')\n"
        "shutil.copyfileobj = interrupted_copy\n", encoding="utf-8")
    result = subprocess.run([*command[:-1], "local"], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and "Synthetic interrupted model copy" in result.stderr
    assert not capture.exists()
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == {required[0]: b"existing local model"}


def test_interactive_defaults_show_three_roots_and_keep_one_entry(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    home = tmp_path / "synthetic user"
    project = source.parents[1]
    (project / "config.yml").write_text("keep config", encoding="utf-8")
    (project / "AGENTS.md").write_text("replace instructions", encoding="utf-8")
    answers, prompts = iter(["", "", "", "n", ""]), []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source)]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    assert len(prompts) == 5
    for prompt, relative in zip(prompts, (".openflow/config/skills", ".cac/skills",
                                          ".openflow/config/workflow-templates")):
        assert str(home / relative) in prompt
    assert str(project / "config.yml") in prompts[3] and "Y/n" in prompts[3]
    assert str(project / "AGENTS.md") in prompts[4] and "Y/n" in prompts[4]
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep config"
    assert (project / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()


def test_interactive_custom_directories_and_yes_overwrite(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    destinations = [tmp_path / name for name in ("custom openflow", "custom cac", "custom workflow")]
    (source.parents[1] / "config.yml").write_text("old config", encoding="utf-8")
    (source.parents[1] / "AGENTS.md").write_text("old instructions", encoding="utf-8")
    answers = iter([*(str(path) for path in destinations), "y", "N"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source)]) == 0
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (source.parents[1] / "config.yml").read_bytes() == (source / "config.yml").read_bytes()
    assert (source.parents[1] / "AGENTS.md").read_text(encoding="utf-8") == "old instructions"


def test_noninteractive_defaults_overwrite_existing_entries(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    home = tmp_path / "synthetic user"
    for name in ("config.yml", "AGENTS.md"):
        (source.parents[1] / name).write_text("old project entry", encoding="utf-8")
    monkeypatch.setattr(backend.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: None)
    assert backend.main(["--source-root", str(source), "--non-interactive"]) == 0
    for relative in (".openflow/config/skills", ".cac/skills"):
        assert (home / relative / package.name / "SKILL.md").is_file()
    assert (home / ".openflow/config/workflow-templates/hs-knowledge-ingest/workflow.yaml").is_file()
    assert (source.parents[1] / "config.yml").read_bytes() == (source / "config.yml").read_bytes()
    assert (source.parents[1] / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()


@pytest.mark.parametrize("kind", ["skills", "cac", "workflows"])
def test_replacement_cannot_delete_distribution_sources(distribution, tmp_path, monkeypatch, kind):
    backend, source, package, workflows, _ = distribution
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    option = {"skills": "--skills-root", "cac": "--cac-skills-root", "workflows": "--workflows-root"}[kind]
    target = workflows if kind == "workflows" else package.parent
    assert backend.main([*arguments(source, tmp_path), option, str(target)]) == 1
    assert {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()} == before
    assert calls == []


def test_replacement_cannot_delete_another_installation_root(distribution, tmp_path, monkeypatch):
    backend, source, package, _, _ = distribution
    shared = tmp_path / "installation"
    nested = shared / package.name
    nested.mkdir(parents=True)
    keep = nested / "keep.txt"
    keep.write_bytes(b"keep")
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main([*arguments(source, tmp_path), "--skills-root", str(shared),
                         "--cac-skills-root", str(nested)]) == 1
    assert keep.read_bytes() == b"keep" and calls == []


@pytest.mark.parametrize("name", ["config.yml", "AGENTS-code-root.md"])
def test_missing_project_template_fails_before_install(distribution, tmp_path, monkeypatch, name):
    backend, source, _, _, _ = distribution
    (source / name).unlink()
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(arguments(source, tmp_path)) == 1
    assert calls == []


def test_entry_symlink_cannot_overwrite_external_file(distribution, tmp_path, monkeypatch):
    backend, source, _, _, _ = distribution
    external = tmp_path / "outside.yml"
    external.write_text("keep external", encoding="utf-8")
    try:
        (source.parents[1] / "config.yml").symlink_to(external)
    except OSError:
        pytest.skip("Symbolic links unavailable")
    calls = []
    monkeypatch.setattr(backend.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert backend.main(arguments(source, tmp_path)) == 1
    assert calls == [] and external.read_text(encoding="utf-8") == "keep external"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
@pytest.mark.parametrize("explicit_roots", [False, True], ids=["backend-defaults", "explicit"])
@pytest.mark.parametrize("download_models", [False, True])
def test_powershell_forwards_options_without_its_own_prompts(tmp_path, explicit_roots, download_models):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    capture = tmp_path / "arguments.json"
    recorder = tmp_path / "chosen python.ps1"
    recorder.write_text(
        "[System.IO.File]::WriteAllText($env:FACTUM_DEPLOY_TEST_CAPTURE, "
        "(ConvertTo-Json -InputObject @($args) -Compress))\nexit 0\n", encoding="utf-8")
    source = tmp_path / "source root"
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(KNOWLEDGE_ROOT / "deploy.ps1"), "-NonInteractive", "-Python", str(recorder),
               "-SourceRoot", str(source)]
    if explicit_roots:
        for flag, name in (("-SkillsRoot", "skills"), ("-CacSkillsRoot", "cac"),
                           ("-WorkflowsRoot", "workflows")):
            command += [flag, str(tmp_path / name)]
    if download_models:
        command.append("-DownloadModels")
    result = subprocess.run(command, capture_output=True, timeout=30,
                            env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    received = json.loads(capture.read_text(encoding="utf-8"))
    assert Path(received[0]) == KNOWLEDGE_ROOT / "tools/deploy/deploy.py"
    assert received[received.index("--source-root") + 1] == str(source)
    assert received[received.index("--python") + 1] == str(recorder)
    assert "--non-interactive" in received
    assert "--skip-ocr" not in received
    assert ("--download-models" in received) is download_models
    for flag, name in (("--skills-root", "skills"), ("--cac-skills-root", "cac"),
                       ("--workflows-root", "workflows")):
        if explicit_roots:
            assert received[received.index(flag) + 1] == str(tmp_path / name)
        else:
            assert flag not in received


@pytest.mark.skipif(os.name != "nt", reason="PowerShell wrapper targets Windows")
def test_powershell_rejects_removed_skip_option_without_starting_python(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    capture = tmp_path / "python-started.txt"
    recorder = tmp_path / "chosen python.ps1"
    recorder.write_text(
        "[System.IO.File]::WriteAllText($env:FACTUM_DEPLOY_TEST_CAPTURE, 'started')\nexit 0\n",
        encoding="utf-8")
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(KNOWLEDGE_ROOT / "deploy.ps1"), "-NonInteractive", "-Python", str(recorder), "-SkipOcr"],
        capture_output=True, timeout=30,
        env={**os.environ, "FACTUM_DEPLOY_TEST_CAPTURE": str(capture)})
    assert result.returncode != 0
    assert b"SkipOcr" in result.stderr
    assert not capture.exists()


@pytest.mark.parametrize("kind", [
    pytest.param("sh", marks=pytest.mark.skipif(os.name != "posix", reason="POSIX wrapper")),
    pytest.param("powershell", marks=pytest.mark.skipif(os.name != "nt", reason="Windows wrapper")),
])
def test_wrapper_uses_shared_interaction_and_fixed_project_root(distribution, tmp_path, kind):
    _, source, package, _, _ = distribution
    project = source.parents[1]
    (project / "config.yml").write_text("keep project", encoding="utf-8")
    (project / "AGENTS.md").write_text("old instructions", encoding="utf-8")
    fake = tmp_path / "fake pip"
    fake.mkdir()
    (fake / "pip.py").write_text("# Synthetic pip substitute: no installation.\n", encoding="utf-8")
    contracts = source / "governance/contracts"
    contracts.mkdir(parents=True)
    (contracts / "__init__.py").write_text("", encoding="utf-8")
    (contracts / "document_parser.py").write_text(
        "from pathlib import Path\nimport os\nOCR_MODEL_FILES = ()\n"
        "def _models(root, options):\n"
        "    Path(os.environ['FACTUM_MODEL_READY']).write_text('complete document runtime')\n"
        "    return root / options['models_path']\n"
        "def safe_path(root, reference, *args):\n"
        "    return root / reference\n", encoding="utf-8")
    (contracts / "validation.py").write_text("class ContractError(Exception):\n    pass\n", encoding="utf-8")
    models_ready = tmp_path / "models-prepared.txt"
    backend = source / "tools/deploy/deploy.py"
    backend.parent.mkdir(parents=True)
    shutil.copyfile(KNOWLEDGE_ROOT / "tools/deploy/deploy.py", backend)
    wrapper_name = "deploy.sh" if kind == "sh" else "deploy.ps1"
    wrapper = source / wrapper_name
    shutil.copyfile(KNOWLEDGE_ROOT / wrapper_name, wrapper)
    if kind == "sh":
        command = ["sh", str(wrapper), "--python", sys.executable]
    else:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            pytest.skip("PowerShell unavailable")
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(wrapper), "-Python", sys.executable]
    destinations = [tmp_path / name for name in ("openflow skill", "cac skill", "openflow workflow")]
    result = subprocess.run(command, input="\n".join([*(str(path) for path in destinations), "n", "", ""]),
                            text=True, capture_output=True, timeout=30, cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(fake), "PYTHONDONTWRITEBYTECODE": "1",
                                 "FACTUM_MODEL_READY": str(models_ready)})
    assert result.returncode == 0, result.stderr
    assert ".openflow" in result.stdout and ".cac" in result.stdout and "Y/n" in result.stdout
    assert all((path / package.name / "SKILL.md").is_file() for path in destinations[:2])
    assert (destinations[2] / "hs-knowledge-ingest/workflow.yaml").is_file()
    assert (project / "config.yml").read_text(encoding="utf-8") == "keep project"
    assert (project / "AGENTS.md").read_bytes() == (source / "AGENTS-code-root.md").read_bytes()
    assert models_ready.read_text() == "complete document runtime"
    assert not (project / ".git").exists()
