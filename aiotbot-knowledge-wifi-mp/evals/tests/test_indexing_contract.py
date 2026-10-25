"""Full SQLite verification uses independent expected records, not counts alone."""

import copy
import importlib.util
from pathlib import Path
import sqlite3
import sys

import pytest

DOMAIN = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "wifi_index_contract", DOMAIN / "governance/contracts/__init__.py",
    submodule_search_locations=[str(DOMAIN / "governance/contracts")],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from wifi_index_contract import indexing  # noqa: E402


def cards():
    return [{
        "metadata": {"id": "card-a", "title": "发送队列", "summary": "dispatch limit",
                     "aliases": ["TX queue"], "search_terms": ["队列限制"],
                     "relations": [{"target_card_id": "card-b", "type": "requires"}]},
        "path": "knowledge/concepts/a.md", "sha256": "a" * 64,
        "body_digest": "b" * 64,
        "claims": [{"id": "claim-1", "text": "条件 A 时最多 8 个条目。", "search_terms": ["发送窗口"]}],
    }]


def test_build_full_verify_and_versions(tmp_path):
    database = tmp_path / "index.sqlite"
    indexing.build_database(cards(), "1" * 64, database)
    report = indexing.verify_database(cards(), "1" * 64, database)
    assert report["complete"] is True
    assert report["documents"] == 1 and report["claims"] == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM metadata WHERE key='tokenizer_version'").fetchone() == ("2.0",)
        assert connection.execute("SELECT token FROM postings WHERE token='发送'").fetchone() == ("发送",)


@pytest.mark.parametrize("mutation", [
    "DELETE FROM claims",
    "UPDATE documents SET path='knowledge/wrong.md'",
    "UPDATE postings SET token='wrong' WHERE token='发送'",
    "UPDATE claims SET metadata='{}'",
    "UPDATE relations SET target_id='unrelated'",
    "INSERT INTO documents VALUES('extra','knowledge/extra.md','{}')",
    "UPDATE metadata SET value='old' WHERE key='rules_digest'",
    "UPDATE metadata SET value='old' WHERE key='tokenizer_version'",
    "CREATE TABLE unexpected(value TEXT)",
])
def test_same_count_and_extra_or_missing_rows_do_not_verify(tmp_path, mutation):
    database = tmp_path / "index.sqlite"
    indexing.build_database(cards(), "1" * 64, database)
    with sqlite3.connect(database) as connection:
        connection.execute(mutation)
    with pytest.raises(ValueError, match="INDEX_"):
        indexing.verify_database(cards(), "1" * 64, database)


def test_changed_expected_body_and_duplicate_id_rejected(tmp_path):
    database = tmp_path / "index.sqlite"
    indexing.build_database(cards(), "1" * 64, database)
    changed = cards()
    changed[0]["claims"][0]["text"] = "条件 A 时最多 9 个条目。"
    with pytest.raises(ValueError, match="INDEX_"):
        indexing.verify_database(changed, "1" * 64, database)
    with pytest.raises(ValueError, match="INDEX_DUPLICATE"):
        indexing.build_database(cards() + copy.deepcopy(cards()), "1" * 64, tmp_path / "duplicate.sqlite")


def test_check_has_no_active_or_formal_writes(tmp_path):
    before = set(tmp_path.iterdir())
    result = indexing.check(cards(), {"rules_digest": "1" * 64}, tmp_path)
    assert result["complete"] is True
    assert set(tmp_path.iterdir()) == before
