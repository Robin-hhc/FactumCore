"""Ranking regressions exercise the real package in an isolated Python process."""

import json
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[3] / "runtime/himate_knowledge/stages/query"


def evaluate(cards, query, eligibility):
    public = Path(__file__).resolve().parents[5] / "himate/himate-knowledge-wifi-mp/evals/support/contracts.py"
    program = "import importlib.util,json,sys;s=importlib.util.spec_from_file_location('public_query',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);q=m.module('query_runtime');v=json.load(sys.stdin);g=q.term_groups(v['query']);print(json.dumps([q.score_card(c,g,set(e)) for c,e in zip(v['cards'],v['eligible'])]))"
    result = subprocess.run(
        [sys.executable, "-c", program, str(public)],
        cwd=SCRIPTS,
        input=json.dumps({"cards": cards, "query": query, "eligible": eligibility}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def sample(card_id, title, texts):
    return {
        "metadata": {
            "id": card_id,
            "title": title,
            "summary": title,
            "aliases": [title],
        },
        "claims": [{"id": str(i), "text": text} for i, text in enumerate(texts)],
    }


def test_partial_card_cannot_leak_header_alias_or_summary():
    rows = evaluate([sample("a", "secret", ["normal", "secret"])], "secret", [["0"]])
    assert rows == [[0, False]]


def test_rescoring_reorders_after_ineligible_claims():
    cards = [
        sample("a", "needle", ["ordinary", "needle"]),
        sample("b", "ordinary", ["needle"]),
    ]
    scores = evaluate(cards, "needle", [["0"], ["0"]])
    assert scores[0][0] == 0 and scores[1][0] > scores[0][0]


def test_splitting_duplicate_claim_does_not_inflate_score():
    cards = [
        sample("a", "normal", ["needle"]),
        sample("b", "normal", ["needle", "needle"]),
    ]
    scores = evaluate(cards, "needle", [["0"], ["0", "1"]])
    assert scores[0][0] == scores[1][0] == 1


def test_nfkc_and_chinese_bigrams_match_without_case_double_scoring():
    cards = [
        sample("a", "normal", ["MAC 知识库"]),
        sample("b", "normal", ["ＭＡＣ 知识库"]),
    ]
    scores = evaluate(cards, "MAC 知识库", [["0"], ["0"]])
    assert scores[0] == scores[1]
