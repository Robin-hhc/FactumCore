"""P4 rejects publication plans that would break retained knowledge."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from contracts import module, write_plan


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "library"
    for name in ("docs-raw", "knowledge", "governance", "artifacts", ".build/cards"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for name in ("a", "b"):
        (root / "docs-raw" / f"{name}.md").write_text(
            f"# {name}\n\nA documented requirement.\n", encoding="utf-8")
    with module("catalog").Catalog(root) as catalog:
        for name in ("a", "b"):
            catalog.register("raw", f"docs-raw/{name}.md", source_id=f"doc-{name}")
    return root


def put_card(root, identity, doc_id, body, *, stage=False, **extra):
    metadata = {"id": identity,
                "doc_ref": [{"doc_id": doc_id, "line_start": 1, "line_end": 3}],
                "code_ref": [], **extra}
    path = root / (".build/cards" if stage else "knowledge") / f"{identity}.md"
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False)
                    + f"---\n# {identity}\n\n{body}\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("body", [
    "See [the old card](a.md).",
    "See [the old card][old].\n\n[old]: a.md",
], ids=["inline-link", "reference-link"])
def test_check_rejects_deletion_referenced_by_an_unchanged_card(library, body):
    old_card = put_card(library, "a", "doc-a", "Original requirement.")
    retained = put_card(library, "b", "doc-b", body)
    original = retained.read_bytes()
    put_card(library, "replacement", "doc-a", "Merged requirement.", stage=True)
    (library / ".build/changes.json").write_text(
        json.dumps({"delete": ["knowledge/a.md"]}), encoding="utf-8")
    write_plan(library, [("replacement", "knowledge/replacement.md")])

    result, status = module("ingest").check(library, {})

    assert status == "failed", result
    assert any(finding["code"] == "BROKEN_CARD_LINK"
               and finding["path"] == "knowledge/b.md" for finding in result["findings"])
    assert retained.read_bytes() == original
    assert old_card.exists()


def test_check_rejects_writing_and_deleting_the_same_card(library):
    old_card = put_card(library, "a", "doc-a", "Original requirement.")
    original = old_card.read_bytes()
    candidate = put_card(library, "a", "doc-a", "Updated requirement.", stage=True)
    (library / ".build/changes.json").write_text(
        json.dumps({"delete": ["knowledge/a.md"]}), encoding="utf-8")
    write_plan(library, [("a", "knowledge/a.md")])

    result, status = module("ingest").check(library, {})

    assert status == "failed", result
    assert any(finding["code"] == "WRITE_DELETE_CONFLICT" for finding in result["findings"])
    assert old_card.read_bytes() == original
    assert candidate.exists()


def test_check_rejects_replaced_identity_referenced_by_an_unchanged_card(library):
    old_card = put_card(library, "a", "doc-a", "Original requirement.")
    put_card(library, "b", "doc-b", "Requires the original card.",
             relations=[{"type": "requires", "target_card_id": "a", "context_ids": []}])
    candidate = put_card(library, "c", "doc-a", "Replacement requirement.", stage=True)
    candidate.rename(candidate.with_name("a.md"))
    write_plan(library, [("c", "knowledge/a.md")])

    result, status = module("ingest").check(library, {})

    assert status == "failed", result
    assert any(finding["code"] == "UNKNOWN_RELATED_CARD"
               and finding["path"] == "knowledge/b.md" for finding in result["findings"])
    assert old_card.exists()


@pytest.mark.parametrize(("target", "status", "code"), [
    ("index.md", "passed", None),
    ("index.md#missing", "failed", "BROKEN_CARD_ANCHOR"),
], ids=["existing-navigation", "missing-navigation-anchor"])
def test_check_resolves_navigation_links_without_indexing_navigation(library, target, status, code):
    (library / "knowledge/index.md").write_text(
        "# Navigation\n\nThis hand-maintained page is not a knowledge card.\n", encoding="utf-8")
    put_card(library, "b", "doc-b", "An existing requirement.")
    put_card(library, "a", "doc-a", f"See [navigation]({target}).", stage=True)
    write_plan(library, [("a", "knowledge/a.md")])

    result, actual_status = module("ingest").check(library, {})

    assert actual_status == status, result
    if code:
        assert any(finding["code"] == code and finding["path"] == "knowledge/a.md"
                   for finding in result["findings"])
    else:
        assert result["findings"] == []
    with module("catalog").Catalog(library) as catalog:
        assert [card["id"] for card in catalog.all_cards()] == ["b"]
