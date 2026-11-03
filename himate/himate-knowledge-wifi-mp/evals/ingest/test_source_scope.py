"""Explicit document directories remain scopes, including empty/deleted sources."""

from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts"):
        (root / name).mkdir(parents=True)
    return root


def put(root, relative, content=b"# Synthetic source\n\nA bounded requirement.\n"):
    path = root / "docs-raw" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def complete_selected(root):
    write_plan(root, [], body="Synthetic complete assessment; no new card is needed.")
    result, phase = module("ingest").check(root, {})
    assert phase == "passed", result
    result, phase = module("ingest").commit(
        root, {"reason": "Synthetic assessed material adds no new card."})
    assert phase == "completed", result
    return result


@pytest.mark.parametrize("scope", ["docs-raw/selected", "selected"])
def test_directory_scope_drains_supported_descendants_without_widening(library, scope):
    first = put(library, "selected/a.md")
    second = put(library, "selected/nested/b.md")
    outside = put(library, "outside.md")
    originals = {path: path.read_bytes() for path in (first, second, outside)}
    seen = set()
    for _ in range(2):
        result, phase = module("ingest").scan(library, {"source": scope})
        assert phase == "prepared", result
        path = result["source"]["path"]
        assert path in {"docs-raw/selected/a.md", "docs-raw/selected/nested/b.md"}
        assert path not in seen
        seen.add(path)
        complete_selected(library)
    result, phase = module("ingest").scan(library, {"source": scope})
    assert phase == "unchanged" and result["pending"] == 0, result
    result, phase = module("ingest").scan(library, {})
    assert phase == "prepared", result
    assert result["source"]["path"] == "docs-raw/outside.md"
    assert all(path.read_bytes() == original for path, original in originals.items())


def test_raw_root_scope_includes_root_files_and_nested_documents(library):
    put(library, "root.md")
    put(library, "nested/child.md")
    seen = set()
    for _ in range(2):
        result, phase = module("ingest").scan(library, {"source": "docs-raw"})
        assert phase == "prepared", result
        seen.add(result["source"]["path"])
        complete_selected(library)
    assert seen == {"docs-raw/root.md", "docs-raw/nested/child.md"}
    result, phase = module("ingest").scan(library, {"source": "docs-raw"})
    assert phase == "unchanged" and result["pending"] == 0, result


@pytest.mark.parametrize("scope", ["docs-raw/empty", "empty", "docs-raw"])
@pytest.mark.parametrize("contents", [
    [],
    ["README.md", "index.md", "AGENTS.md", ".gitkeep"],
    ["unsupported.bin", "archive.zip"],
    ["README.md", "unsupported.bin"],
], ids=["empty", "navigation-only", "unsupported-only", "navigation-and-unsupported"])
def test_directory_with_no_ingest_documents_is_unchanged(library, scope, contents):
    directory = library / ("docs-raw" if scope == "docs-raw" else "docs-raw/empty")
    directory.mkdir(exist_ok=True)
    files = []
    for name in contents:
        path = directory / name
        path.write_bytes(b"Directory fixture data.\n")
        files.append(path)
    originals = {path: path.read_bytes() for path in files}
    if scope != "docs-raw":
        put(library, "outside.md")

    result, phase = module("ingest").scan(library, {"source": scope})

    assert phase == "unchanged" and result["pending"] == 0, result
    assert not (library / ".build/task.json").exists()
    assert all(path.read_bytes() == original for path, original in originals.items())
    with module("catalog").Catalog(library) as catalog:
        assert catalog.list_files() == []


@pytest.mark.parametrize("scope", ["docs-raw/absent", "absent", "docs-raw/absent.md"])
def test_unknown_missing_scope_does_not_mean_empty_success(library, scope):
    put(library, "outside.md")
    with pytest.raises(module("validation").ContractError) as error:
        module("ingest").scan(library, {"source": scope})
    assert error.value.code == "SOURCE_MISSING"
    assert not (library / ".build/task.json").exists()


@pytest.mark.parametrize("scope", ["docs-raw/data.bin", "data.bin"])
def test_explicit_unsupported_file_remains_an_error(library, scope):
    original = put(library, "data.bin", b"Not a supported source format.")
    before = original.read_bytes()
    with pytest.raises(module("validation").ContractError) as error:
        module("ingest").scan(library, {"source": scope})
    assert error.value.code == "UNSUPPORTED_DOCUMENT_FORMAT"
    assert original.read_bytes() == before
    assert not (library / ".build/task.json").exists()


@pytest.mark.parametrize("directory_exists", [True, False], ids=["directory-retained", "directory-removed"])
def test_directory_scope_still_schedules_registered_deleted_document(library, directory_exists):
    original = put(library, "selected/deleted.md")
    scope = {"source": "docs-raw/selected"}
    result, phase = module("ingest").scan(library, scope)
    assert phase == "prepared", result
    identity = result["source"]["source_id"]
    complete_selected(library)
    original.unlink()
    if not directory_exists:
        original.parent.rmdir()

    result, phase = module("ingest").scan(library, scope)

    assert phase == "prepared", result
    assert result["source"]["source_id"] == identity
    assert result["source"]["path"] == "docs-raw/selected/deleted.md"
    assert result["source"]["change"] == "deleted"
    assert result["source"]["exists"] is False
    assert result["source"]["hash"] is None
    assert "original_ref" not in result["source"]
    complete_selected(library)
    with module("catalog").Catalog(library) as catalog:
        assert catalog.get_file(identity)["processed_exists"] is False
    result, phase = module("ingest").scan(library, scope)
    assert phase == "unchanged" and result["pending"] == 0, result
