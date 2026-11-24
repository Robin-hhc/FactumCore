"""Public raw upload behavior during a cooperating process's directory creation."""

import hashlib
import importlib.util
import os
from pathlib import Path

import pytest


_spec = importlib.util.spec_from_file_location(
    "raw_materials_contract_support", Path(__file__).resolve().parents[1] / "support/contracts.py",
)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
module = _helper.module


@pytest.mark.skipif(os.name != "nt", reason="Windows realpath prefix race")
def test_raw_save_handles_artifact_directory_created_during_lock_path_resolution(tmp_path, monkeypatch):
    import ntpath

    root = tmp_path / "knowledge-root"
    (root / "docs-raw/specs").mkdir(parents=True)
    staged = tmp_path / "staged.md"
    content = b"# Complete uploaded document\n"
    staged.write_bytes(content)
    target = root / "artifacts/raw-save.lock"
    original = ntpath._getfinalpathname

    def create_parent_after_missing_path(path):
        try:
            return original(path)
        except OSError as error:
            if str(path) == str(target) and error.winerror == 3:
                # A cooperating upload creates artifacts after the first
                # realpath miss, changing Windows' next error from 3 to 2.
                target.parent.mkdir(exist_ok=True)
            raise

    monkeypatch.setattr(ntpath, "_getfinalpathname", create_parent_after_missing_path)
    result, phase = module("panel").run(root, "raw-save", {
        "path": "specs/uploaded.md", "staged_path": str(staged),
        "expected_size": len(content), "expected_sha256": hashlib.sha256(content).hexdigest(),
    })
    assert phase == "saved"
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert (root / "docs-raw/specs/uploaded.md").read_bytes() == content
    assert [path.name for path in (root / "docs-raw/specs").iterdir()] == ["uploaded.md"]


def test_raw_save_refuses_an_artifact_directory_case_alias(tmp_path):
    root = tmp_path / "knowledge-root"
    (root / "docs-raw/specs").mkdir(parents=True)
    (root / "Artifacts").mkdir()
    staged = tmp_path / "staged.md"
    staged.write_bytes(b"# Upload\n")
    with pytest.raises(module("validation").ContractError, match="PATH_CASE_ALIAS"):
        module("panel").run(root, "raw-save", {
            "path": "specs/uploaded.md", "staged_path": str(staged),
        })
    assert list((root / "Artifacts").iterdir()) == []
    assert list((root / "docs-raw/specs").iterdir()) == []


def test_raw_save_refuses_linked_artifacts_without_writing_outside_root(tmp_path):
    root = tmp_path / "knowledge-root"
    (root / "docs-raw/specs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "artifacts").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable")
    staged = tmp_path / "staged.md"
    staged.write_bytes(b"# Upload\n")
    with pytest.raises(module("validation").ContractError, match="PATH_ESCAPE"):
        module("panel").run(root, "raw-save", {
            "path": "specs/uploaded.md", "staged_path": str(staged),
        })
    assert list(outside.iterdir()) == []
    assert list((root / "docs-raw/specs").iterdir()) == []
