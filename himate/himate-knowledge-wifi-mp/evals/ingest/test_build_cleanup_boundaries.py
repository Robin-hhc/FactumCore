"""Staging cleanup preserves directory boundaries around synthetic links."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def library_root(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True)
    return root


def make_link(path, target, kind):
    if kind == "symlink":
        try:
            path.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError) as error:
            pytest.skip(f"Symbolic links unavailable: {error}")
        return
    if os.name != "nt":
        pytest.skip("Windows directory junctions are unavailable on this platform")
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell is unavailable for creating a synthetic junction")
    env = dict(os.environ, FACTUM_TEST_LINK_PATH=str(path), FACTUM_TEST_LINK_TARGET=str(target))
    result = subprocess.run([
        powershell, "-NoProfile", "-NonInteractive", "-Command",
        "$ErrorActionPreference = 'Stop'; "
        "New-Item -ItemType Junction -Path $env:FACTUM_TEST_LINK_PATH "
        "-Target $env:FACTUM_TEST_LINK_TARGET | Out-Null",
    ], env=env, capture_output=True, text=True, timeout=30)
    if result.returncode:
        pytest.skip(f"Synthetic junction creation unavailable: {result.stderr.strip()}")


def remove_test_link(path, tmp_path):
    assert path.absolute().is_relative_to(tmp_path.resolve())
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        path.unlink()
    else:
        assert getattr(path.lstat(), "st_file_attributes", 0) & 0x400
        path.rmdir()


def test_scan_removes_a_directory_named_root_readme(tmp_path):
    root = library_root(tmp_path)
    readme_directory = root / ".build/README.md"
    readme_directory.mkdir(parents=True)
    (readme_directory / "stale.txt").write_bytes(b"Discard this stale staging directory.")

    result, status = module("ingest").scan(root, {})

    assert status == "unchanged", result
    assert list((root / ".build").iterdir()) == []


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_commit_unlinks_staging_directories_without_cleaning_their_targets(tmp_path, kind):
    root = library_root(tmp_path)
    (root / "docs-raw/design.md").write_text("# Design\n\nA synthetic requirement.\n", encoding="utf-8")
    prepared, status = module("ingest").scan(root, {})
    assert status == "prepared", prepared
    target = tmp_path / "outside-staging"
    target.mkdir()
    marker = target / "README.md"
    original = b"This synthetic target must remain unchanged.\r\n"
    marker.write_bytes(original)
    link = root / ".build/linked-directory"
    make_link(link, target, kind)

    try:
        result, status = module("ingest").commit(root, {"reason": "Reviewed; no new knowledge is needed."})

        assert status == "completed", result
        assert not (root / ".build").exists()
        assert list(target.iterdir()) == [marker]
        assert marker.read_bytes() == original
    finally:
        remove_test_link(link, tmp_path)


def test_scan_unlinks_a_readme_symlink_without_changing_the_external_file(tmp_path):
    root = library_root(tmp_path)
    (root / ".build").mkdir()
    target = tmp_path / "external-readme.md"
    original = b"This synthetic external README must not become the staging placeholder.\n"
    target.write_bytes(original)
    link = root / ".build/README.md"
    make_link(link, target, "symlink")

    try:
        result, status = module("ingest").scan(root, {})

        assert status == "unchanged", result
        assert list((root / ".build").iterdir()) == []
        assert target.read_bytes() == original
    finally:
        remove_test_link(link, tmp_path)


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_scan_rejects_a_linked_build_root_without_cleaning_the_target(tmp_path, kind):
    root = library_root(tmp_path)
    target = root / "artifacts/build-target"
    target.mkdir()
    marker = target / "keep.txt"
    original = b"This synthetic in-root target must remain untouched.\n"
    marker.write_bytes(original)
    link = root / ".build"
    make_link(link, target, kind)

    try:
        with pytest.raises(OSError, match="linked .build directory"):
            module("ingest").scan(root, {})

        assert list(target.iterdir()) == [marker]
        assert marker.read_bytes() == original
    finally:
        remove_test_link(link, tmp_path)
