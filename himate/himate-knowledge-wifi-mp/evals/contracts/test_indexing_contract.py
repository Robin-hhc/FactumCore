"""Exact lexical terms remain stable when the old generation machinery retires."""

import importlib.util
from pathlib import Path

import pytest


_spec = importlib.util.spec_from_file_location("terms_support", Path(__file__).parents[1] / "support/contracts.py")
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
indexing = _helper.module("indexing")


@pytest.mark.parametrize("text,expected", [
    ("", set()),
    ("TX_LIMIT", {"tx_limit", "=TX_LIMIT"}),
    ("tx_limit", {"tx_limit", "=tx_limit"}),
    ("ＦＯＯ", {"foo", "=FOO"}),
    ("发送窗口", {"发送", "送窗", "窗口"}),
    ("帧", {"帧"}),
    ("TX / retry", {"tx", "=TX", "retry", "=retry"}),
])
def test_lexical_terms_match_independent_expected_tokens(text, expected):
    assert set(indexing.lexical(text)) == expected


def test_query_terms_keep_case_variants_in_one_alternative_group():
    assert indexing.term_groups("TX_LIMIT") == [{"tx_limit", "=TX_LIMIT"}]


def test_repeated_terms_do_not_increase_the_number_of_query_conditions():
    assert indexing.term_groups("TX_LIMIT TX_LIMIT") == [{"tx_limit", "=TX_LIMIT"}]


def test_chinese_query_requires_each_adjacent_term():
    assert {frozenset(group) for group in indexing.term_groups("发送窗口")} == {
        frozenset({"发送"}), frozenset({"送窗"}), frozenset({"窗口"}),
    }


def test_unrelated_meanings_are_not_semantic_matches():
    assert set(indexing.lexical("transmit")).isdisjoint(indexing.lexical("send"))
