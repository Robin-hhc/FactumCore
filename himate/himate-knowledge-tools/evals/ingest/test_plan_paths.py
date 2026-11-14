"""P4 checks the author's explicit card IDs and final paths before publication."""

from pathlib import Path
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


def library(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts", ".build/cards"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "docs-raw/design.md").write_text("# Reply\n\nWait for a reply.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        catalog.register("raw", "docs-raw/design.md", source_id="doc-design")
    return root


def candidate(root, identity, relative):
    header = {"id": identity,
              "doc_ref": [{"doc_id": "doc-design", "line_start": 1, "line_end": 3}],
              "code_ref": []}
    path = root / ".build/cards" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(header, sort_keys=False)
                    + "---\n# Reply\n\nWait for a reply.\n", encoding="utf-8")
    return path


def test_p4_blocks_a_root_candidate_until_it_matches_the_planned_path(tmp_path):
    root = library(tmp_path)
    task, phase = module("ingest").scan(root, {"source": "doc-design"})
    assert phase == "prepared", task
    write_plan(root, [("waiting", "knowledge/rules/waiting.md")])
    misplaced = candidate(root, "waiting", "waiting.md")
    original = misplaced.read_bytes()

    result, phase = module("ingest").check(root, {})

    assert phase == "failed", result
    finding = next(item for item in result["findings"] if item["code"] == "PLAN_CARD_MISMATCH")
    assert finding["card_id"] == "waiting"
    assert finding["expected_path"] == "knowledge/rules/waiting.md"
    assert finding["actual_path"] == "knowledge/waiting.md"
    assert not (root / "knowledge/waiting.md").exists()
    assert not (root / "knowledge/rules/waiting.md").exists()
    assert misplaced.read_bytes() == original

    corrected = misplaced.parent / "rules/waiting.md"
    corrected.parent.mkdir()
    misplaced.rename(corrected)
    result, phase = module("ingest").check(root, {})
    assert phase == "passed", result
    result, phase = module("ingest").commit(root, {})
    assert phase == "completed", result
    assert (root / "knowledge/rules/waiting.md").read_bytes() == original
    assert not (root / "knowledge/waiting.md").exists()


@pytest.mark.parametrize(("cards", "drafts", "affected_id"), [
    ([("waiting", "knowledge/waiting.md")], [("waiting", "waiting.md"), ("extra", "extra.md")], "extra"),
    ([("waiting", "knowledge/waiting.md"), ("missing", "knowledge/missing.md")], [("waiting", "waiting.md")], "missing"),
    ([("waiting", "knowledge/waiting.md")], [("unexpected", "waiting.md")], "waiting"),
], ids=["extra-candidate", "missing-candidate", "different-id-at-planned-path"])
def test_p4_rejects_a_candidate_set_that_differs_from_the_plan(tmp_path, cards, drafts, affected_id):
    root = library(tmp_path)
    write_plan(root, cards)
    for identity, relative in drafts:
        candidate(root, identity, relative)

    result, phase = module("ingest").check(root, {})

    assert phase == "failed", result
    assert any(item["code"] == "PLAN_CARD_MISMATCH" and item["card_id"] == affected_id
               for item in result["findings"])
    assert not list((root / "knowledge").rglob("*.md"))


def test_p4_accepts_an_explicit_no_card_plan_and_rejects_an_unplanned_candidate(tmp_path):
    root = library(tmp_path)
    write_plan(root, [], body="Fully read; this document adds no independent knowledge.")

    result, phase = module("ingest").check(root, {})

    assert phase == "passed", result
    assert result["card_ids"] == []
    assert result["findings"] == []
    candidate(root, "unplanned", "unplanned.md")
    result, phase = module("ingest").check(root, {})
    assert phase == "failed", result
    assert any(item["code"] == "PLAN_CARD_MISMATCH" and item["card_id"] == "unplanned"
               for item in result["findings"])


def test_p4_requires_a_plan_even_when_there_are_no_candidate_cards(tmp_path):
    root = library(tmp_path)

    result, phase = module("ingest").check(root, {})

    assert phase == "failed", result
    assert any(item["code"] == "PLAN_REQUIRED" for item in result["findings"])


@pytest.mark.parametrize("contents", [
    "Keep waiting.md at its original path.\n",
    "---\ncards: [\n---\nAn unfinished author plan.\n",
    "---\nnotes: no declared card set\n---\nA plan without cards.\n",
    "---\ncards: null\n---\nAn ambiguous card set.\n",
    "---\ncards:\n- id: waiting\n---\nA card without its intended path.\n",
    "---\ncards:\n- id: waiting\n  path: ../waiting.md\n---\nAn escaping path.\n",
    "---\ncards:\n- id: waiting\n  path: rules/waiting.md\n---\nThe final path lacks knowledge/.\n",
    "---\ncards:\n- id: waiting\n  path: knowledge/waiting.txt\n---\nA non-card file.\n",
    "---\ncards:\n- id: waiting\n  path: knowledge/waiting.md\n- id: waiting\n  path: knowledge/other.md\n---\nAn ambiguous identity.\n",
], ids=["no-yaml-header", "broken-yaml", "missing-cards", "null-cards", "missing-path",
        "escaping-path", "missing-knowledge-prefix", "not-markdown", "duplicate-id"])
def test_p4_reports_invalid_plan_as_a_finding(tmp_path, contents):
    root = library(tmp_path)
    (root / ".build/plan.md").write_text(contents, encoding="utf-8")
    candidate(root, "waiting", "waiting.md")

    result, phase = module("ingest").check(root, {})

    assert phase == "failed", result
    assert any(item["code"] == "INVALID_PLAN" for item in result["findings"])


def test_an_existing_card_can_keep_its_original_path_without_directory_classification(tmp_path):
    root = library(tmp_path)
    staged = candidate(root, "waiting", "waiting.md")
    formal = root / "knowledge/waiting.md"
    formal.write_bytes(staged.read_bytes())
    old = formal.read_bytes()
    staged.write_bytes(old.replace(b"Wait for a reply.", b"Wait for the documented reply."))
    write_plan(root, [("waiting", "knowledge/waiting.md")])

    result, phase = module("ingest").check(root, {})

    assert phase == "passed", result
    assert formal.read_bytes() == old
    assert staged.read_bytes() != old


def test_formal_check_uses_the_existing_card_set_without_a_private_plan(tmp_path):
    root = library(tmp_path)
    staged = candidate(root, "waiting", "waiting.md")
    formal = root / "knowledge/waiting.md"
    formal.write_bytes(staged.read_bytes())
    staged.unlink()

    result, phase = module("ingest").check(root, {"formal": True})

    assert phase == "passed", result
    assert result["card_ids"] == ["waiting"]
    assert result["findings"] == []
    assert not (root / ".build/plan.md").exists()
