"""SQLite read-only URIs support UNC without weakening generation immutability."""

import importlib.util
from pathlib import Path, PurePosixPath, PureWindowsPath
import sqlite3
import sys
from types import SimpleNamespace

import pytest


DOMAIN = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sqlite_path_contracts", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)
from sqlite_path_contracts import indexing  # noqa: E402


@pytest.mark.parametrize(("path", "expected"), [
    (PureWindowsPath(r"\\server\share\index.sqlite"), "file:////server/share/index.sqlite"),
    (PureWindowsPath(r"\\?\UNC\server\share\index.sqlite"), "file:////%3F/UNC/server/share/index.sqlite"),
    (PureWindowsPath(r"C:\indexes\index.sqlite"), "file:///C:/indexes/index.sqlite"),
    (PureWindowsPath(r"\\?\C:\indexes\index.sqlite"), "file:////%3F/C:/indexes/index.sqlite"),
    (PureWindowsPath(r"\\server\share\中文 100%#\index.sqlite"),
     "file:////server/share/%E4%B8%AD%E6%96%87%20100%25%23/index.sqlite"),
    (PureWindowsPath(r"\\?\UNC\server\share\中文 100%#\index.sqlite"),
     "file:////%3F/UNC/server/share/%E4%B8%AD%E6%96%87%20100%25%23/index.sqlite"),
    (PureWindowsPath(r"C:\中文 100%#\index.sqlite"),
     "file:///C:/%E4%B8%AD%E6%96%87%20100%25%23/index.sqlite"),
    (PurePosixPath("/tmp/中文 100%#?/index.sqlite"),
     "file:///tmp/%E4%B8%AD%E6%96%87%20100%25%23%3F/index.sqlite"),
])
def test_readonly_uri_has_no_unc_authority_and_preserves_filename(path, expected):
    assert indexing.sqlite_readonly_uri(path) == expected + "?mode=ro&immutable=1"
    if isinstance(path, PureWindowsPath):
        assert indexing.sqlite_readonly_uri(str(path)) == expected + "?mode=ro&immutable=1"


@pytest.mark.parametrize("path", [
    PureWindowsPath("relative/index.sqlite"),
    PureWindowsPath("C:index.sqlite"),
    PurePosixPath("relative/index.sqlite"),
])
def test_readonly_uri_requires_absolute_filesystem_path(path):
    with pytest.raises(ValueError):
        indexing.sqlite_readonly_uri(path)


def test_sqlite_opens_encoded_filename_readonly_and_never_creates_missing_input(tmp_path):
    database = tmp_path / "中文 100%# index.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE marker(value TEXT)")
        connection.execute("INSERT INTO marker VALUES('immutable generation')")
    uri = indexing.sqlite_readonly_uri(database)
    with sqlite3.connect(uri, uri=True) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("immutable generation",)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM marker")
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        sqlite3.connect(indexing.sqlite_readonly_uri(missing), uri=True)
    assert not missing.exists()


def test_full_verifier_uses_the_shared_readonly_uri(tmp_path, monkeypatch):
    database = tmp_path / "verify.sqlite"
    indexing.build_database([], "1" * 64, database)
    original = indexing.sqlite_readonly_uri
    observed = []

    def readonly_uri(path):
        observed.append(path)
        return original(path)

    monkeypatch.setattr(indexing, "sqlite_readonly_uri", readonly_uri)
    assert indexing.verify_database([], "1" * 64, database)["complete"] is True
    assert len(observed) == 1


def test_build_and_verify_long_generation_path(tmp_path):
    database = tmp_path / ("segment" * 16) / ("segment" * 16) / "中文 100%# index.sqlite"
    assert len(str(database)) > 260
    assert indexing.build_database([], "1" * 64, database)["complete"] is True
    with sqlite3.connect(indexing.sqlite_readonly_uri(database), uri=True) as connection:
        assert connection.execute("SELECT value FROM metadata WHERE key='rules_digest'").fetchone() == ("1" * 64,)


def test_query_uses_shared_readonly_uri_for_unc_generation(monkeypatch):
    scripts = DOMAIN.parent / "skills/common/knowledge/hs-knowledge-query/scripts"
    previous = sys.modules.get("support")
    support_spec = importlib.util.spec_from_file_location("support", scripts / "support.py")
    support = importlib.util.module_from_spec(support_spec)
    sys.modules["support"] = support
    support_spec.loader.exec_module(support)
    try:
        node_spec = importlib.util.spec_from_file_location("sqlite_path_query", scripts / "node.py")
        node = importlib.util.module_from_spec(node_spec)
        node_spec.loader.exec_module(node)
    finally:
        if previous is None:
            sys.modules.pop("support", None)
        else:
            sys.modules["support"] = previous

    database = PureWindowsPath(r"\\?\UNC\server\share\index.sqlite")
    monkeypatch.setattr(node, "load_generation", lambda *args: ("generation", {}, database, None))
    monkeypatch.setattr(node, "event_state", lambda ctx: {"validity_epoch": 0})
    monkeypatch.setattr(node, "EligibilityEvaluator", lambda *args: None)

    class SharedUriReached(Exception):
        pass

    def readonly_uri(path):
        assert path == database
        raise SharedUriReached

    ctx = SimpleNamespace(
        request={"query": "marker"}, args=SimpleNamespace(action="search"),
        modules={"indexing": SimpleNamespace(term_groups=lambda query: [], sqlite_readonly_uri=readonly_uri)},
    )
    with pytest.raises(SharedUriReached):
        node.execute(ctx)
