"""Raw navigation and instruction files are never ingest work items."""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module


def raw_root(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True)
    for name in ("index.md", "README.md", "AGENTS.md"):
        (root / "docs-raw" / name).write_text("# Directory guidance\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("registered", [False, True])
def test_scaffold_only_scan_has_no_pending_task(tmp_path, registered):
    root = raw_root(tmp_path)
    if registered:
        with module("catalog").Catalog(root) as catalog:
            catalog.register("raw", "docs-raw/index.md", source_id="old-index")

    result, status = module("ingest").scan(root, {})

    assert status == "unchanged", result
    assert result["pending"] == 0
    assert not (root / ".build/task.json").exists()
    if registered:
        with module("catalog").Catalog(root) as catalog:
            assert catalog.get_file("old-index") is not None


def test_registered_navigation_does_not_block_a_real_document(tmp_path):
    root = raw_root(tmp_path)
    original = root / "docs-raw/specs/design.md"
    original.parent.mkdir()
    original.write_text("# Design\n\nA business requirement.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/index.md", source_id="old-index")

    result, status = module("ingest").scan(root, {})

    assert status == "prepared", result
    assert result["source"]["path"] == "docs-raw/specs/design.md"
    assert (root / result["source"]["original_ref"]).read_bytes() == original.read_bytes()


def test_explicit_registered_navigation_id_has_no_pending_work(tmp_path):
    root = raw_root(tmp_path)
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/index.md", source_id="old-index")

    result, status = module("ingest").scan(root, {"source": "old-index"})

    assert status == "unchanged", result
    assert not (root / ".build/task.json").exists()
