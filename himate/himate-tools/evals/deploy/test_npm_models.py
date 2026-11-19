"""Verify npm prepares complete OCR models before replacing an installation."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from support.contracts import module


TOOL_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def model_package(tmp_path):
    package = tmp_path / "model package"
    scripts = package / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(TOOL_ROOT / "distribution/models/scripts/install.js", scripts / "install.js")
    original = json.loads((TOOL_ROOT / "distribution/models/manifest.json").read_text(encoding="utf-8"))
    contents = {}
    for row in original["files"]:
        data = ("model fixture " + row["path"]).encode("utf-8")
        contents[row["path"]] = data
        row["bytes"], row["sha256"] = len(data), sha256(data).hexdigest()
        pieces = [data[:len(data) // 2], data[len(data) // 2:]] if "parts" in row else [data]
        sources = []
        for index, piece in enumerate(pieces, 1):
            reference = row["path"] + f".part{index:03d}" if "parts" in row else row["path"]
            source = package / "docling-cpu" / reference
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(piece)
            sources.append({"path": reference, "bytes": len(piece), "sha256": sha256(piece).hexdigest()})
        if "parts" in row:
            row["parts"] = sources
    original["total_bytes"] = sum(len(data) for data in contents.values())
    (package / "manifest.json").write_text(json.dumps(original), encoding="utf-8")
    (package / "README.md").write_text("Model source notes", encoding="utf-8")
    (package / "source-cards").mkdir()
    (package / "source-cards/LICENSE").write_text("Fixture license", encoding="utf-8")
    return package, original, contents


def install(package, home, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the model installation test")
    profile = tmp_path / "model-profile.cjs"
    profile.write_text("require('node:os').homedir = () => process.env.HIMATE_TEST_MODEL_HOME;\n", encoding="utf-8")
    return subprocess.run(
        [node, "--require", str(profile), str(package / "scripts/install.js")],
        env={**os.environ, "HIMATE_TEST_MODEL_HOME": str(home)},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


def model_root(home):
    return home / ".himate/knowledge/tools/deploy/models"


def test_model_install_joins_parts_and_keeps_cli_and_logs(model_package, tmp_path):
    package, manifest, contents = model_package
    home = tmp_path / "user profile"
    if os.name == "nt":
        longest_path = max(len(str(model_root(home) / "docling-cpu" / ref)) for ref in contents)
        home = home.with_name(home.name + "x" * max(0, 264 - longest_path))
    installed = home / ".himate/knowledge"
    for relative in ("runtime/manifest.json", "logs/setup.log"):
        target = installed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"existing CLI state")
    previous = model_root(home) / "docling-cpu/obsolete-model"
    previous.parent.mkdir(parents=True)
    previous.write_bytes(b"old model")

    result = install(package, home, tmp_path)

    assert result.returncode == 0, result.stderr
    models = Path(module("runtime").native_path(model_root(home)))
    for reference, data in contents.items():
        assert (models / "docling-cpu" / reference).read_bytes() == data
    assert not list((models / "docling-cpu").rglob("*.part*"))
    assert not previous.exists()
    assert json.loads((model_root(home) / "manifest.json").read_text()) == manifest
    assert (installed / "runtime/manifest.json").read_bytes() == b"existing CLI state"
    assert (installed / "logs/setup.log").read_bytes() == b"existing CLI state"
    assert not list(model_root(home).parent.glob(".staging-models-*"))
    assert not list(model_root(home).parent.glob(".previous-models-*"))


@pytest.mark.parametrize("damage", ["part", "combined-digest", "manifest-path", "missing-file"])
def test_invalid_models_preserve_the_previous_installation(model_package, tmp_path, damage):
    package, manifest, _ = model_package
    home = tmp_path / "user profile"
    installed = model_root(home)
    installed.mkdir(parents=True)
    previous = installed / "existing-model"
    previous.write_bytes(b"keep the previous working model")
    split = next(row for row in manifest["files"] if "parts" in row)
    if damage == "part":
        part = package / "docling-cpu" / split["parts"][0]["path"]
        part.write_bytes(b"x" * part.stat().st_size)
    elif damage == "combined-digest":
        split["sha256"] = "0" * 64
    elif damage == "manifest-path":
        split["parts"][0]["path"] = "../../outside-model"
    else:
        (package / "docling-cpu" / manifest["files"][0]["path"]).unlink()
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = install(package, home, tmp_path)

    assert result.returncode != 0
    assert previous.read_bytes() == b"keep the previous working model"
    assert sorted(path.name for path in installed.iterdir()) == ["existing-model"]
    assert not list(installed.parent.glob(".staging-models-*"))
    assert not (tmp_path / "outside-model").exists()


def test_model_install_rejects_linked_targets(model_package, tmp_path):
    package, _, _ = model_package
    home = tmp_path / "user profile"
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep"
    marker.write_bytes(b"unchanged")
    target = model_root(home)
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("The host does not allow synthetic symlinks")

    result = install(package, home, tmp_path)

    assert result.returncode != 0
    assert "links or junctions" in result.stderr
    assert marker.read_bytes() == b"unchanged"
