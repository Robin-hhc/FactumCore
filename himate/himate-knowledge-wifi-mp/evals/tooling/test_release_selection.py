"""Explicit frozen-release auditing is isolated from normal repository tests."""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from support.releases import select_release

from support.stages import apply_formats


def frozen_legacy(tmp_path):
    root = tmp_path / "frozen"
    files = {
        "himate-knowledge-wifi-mp/evals/tests/test_manual_skills.py": (
            "ORIGIN = 'frozen legacy'\nclass ManualPipeline: pass\n"
        ),
        "himate-knowledge-wifi-mp/governance/framework.lock.yaml": "tool_version: '0.0.1'\n",
        "skills/common/knowledge/hs-knowledge-source/scripts/cli.py": "print('frozen source')\n",
        "skills/common/knowledge/hs-knowledge-source/requirements.lock.txt": "# frozen fixture\n",
    }
    hashes = {}
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps({"commit": apply_formats.RELEASE, "files": hashes}), encoding="utf-8")
    return root, manifest


def test_verified_legacy_checkout_loads_its_own_original_helper(tmp_path, monkeypatch):
    root, manifest = frozen_legacy(tmp_path)
    monkeypatch.setenv("HIMATE_DBOX_RELEASE_CHECKOUT", str(root))
    monkeypatch.setenv("HIMATE_DBOX_RELEASE_MANIFEST", str(manifest))
    selected = apply_formats.release_runtime.__wrapped__(None)
    assert selected[0] == root
    assert selected[1].ORIGIN == "frozen legacy"
    assert selected[2]["execution_layout"] == "legacy_skill"


@pytest.mark.parametrize("damage", ["manifest-missing", "digest", "version", "unmanifested-code", "traversal"])
def test_unverified_release_cannot_select_legacy_execution(tmp_path, damage):
    root, path = frozen_legacy(tmp_path)
    value = json.loads(path.read_bytes())
    if damage == "manifest-missing":
        path.unlink()
    elif damage == "digest":
        (root / "skills/common/knowledge/hs-knowledge-source/scripts/cli.py").write_text("raise RuntimeError('changed')\n")
    elif damage == "version":
        value["commit"] = "0" * 40
        path.write_text(json.dumps(value), encoding="utf-8")
    elif damage == "unmanifested-code":
        (root / "skills/common/knowledge/hs-knowledge-source/scripts/extra.py").write_text("# unverified\n")
    else:
        value["files"]["../outside.py"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        select_release(tmp_path, checkout=root, manifest_path=path)


def test_current_layout_does_not_implicitly_fall_back_to_legacy(tmp_path):
    root, _ = frozen_legacy(tmp_path)
    with pytest.raises(ValueError, match="current checkout requires"):
        select_release(root)


def test_normal_acceptance_selects_only_the_current_repository_entry(tmp_path):
    selected = select_release(Path(__file__).resolve().parents[4])
    assert selected.layout == "repository_cli" and selected.explicit is False
    assert selected.knowledge_root == Path(__file__).resolve().parents[2]
    argv = selected.command(tmp_path / "isolated-k", "knowledge-source")
    assert str(tmp_path / "isolated-k/knowledge.py") in argv
    assert "source" in argv and "--json" in argv
    assert not any("scripts/cli.py" in item.replace("\\", "/") for item in argv)


def test_modified_copied_legacy_code_cannot_execute(tmp_path):
    root, manifest = frozen_legacy(tmp_path)
    selected = select_release(tmp_path, checkout=root, manifest_path=manifest)
    assert selected.knowledge_root == root / "himate-knowledge-wifi-mp"
    installed = tmp_path / "installed-legacy"
    shutil.copytree(root / "skills/common/knowledge", installed)
    command = selected.command(root / "himate-knowledge-wifi-mp", "source", skills=installed)
    assert command[-1] == str(installed / "hs-knowledge-source/scripts/cli.py")
    (installed / "hs-knowledge-source/scripts/cli.py").write_text("raise RuntimeError('untrusted')\n")
    with pytest.raises(ValueError, match="differs from its manifest"):
        selected.command(root / "himate-knowledge-wifi-mp", "source", skills=installed)
