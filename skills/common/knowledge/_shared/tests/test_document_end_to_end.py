"""Full synthetic raw pipeline through the public apply CLI, with no real card approval."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from _shared import cards, changes, receipts, sources, transactions
from test_document_changes import card, official, plan
from test_document_changes import domain as domain_fixture
from test_document_confirmation import confirm_fixture

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def domain(tmp_path):
    return domain_fixture.__wrapped__(tmp_path)


def public_apply(root, operation_id, review_ref, cwd):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "skills/common/knowledge/_shared/cli.py"),
            "ingest",
            "apply",
            "--knowledge-root",
            str(root),
            "--operation-id",
            operation_id,
            "--review-ref",
            review_ref,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "Traceback" not in result.stderr
    return result.returncode, json.loads(result.stdout)


def test_full_create_then_versioned_update_and_readonly_replay(domain, tmp_path):
    root, capture = domain
    before = official(root)
    plan(root, capture)
    view = changes.materialize(root, "fixture-op")
    assert official(root) == before
    review = confirm_fixture(root)
    assert official(root) == before
    code, response = public_apply(root, "fixture-op", review["review_ref"], tmp_path)
    assert code == 0, response
    assert response["operation_id"] == "fixture-op"
    assert response["result"]["index_activated"] is False
    for path, digest in view["target_file_digests"].items():
        assert receipts.digest_file(root / path) == digest
    unchanged = official(root)
    code, replay = public_apply(root, "fixture-op", review["review_ref"], tmp_path)
    assert code == 0 and replay["result"] == response["result"]
    assert official(root) == unchanged

    raw = root / "docs-raw/specs/v2/sample.md"
    raw.parent.mkdir()
    raw.write_bytes(b"# Version two\nSynthetic updated evidence.\n")
    second = sources.capture_document(
        root, "docs-raw/specs/v2/sample.md", source_id="fixture", declared_version="v2"
    )
    changes.create_plan(
        root,
        operation_id="update-op",
        bundle_ref=second["bundle_ref"],
        manifest_digest=second["manifest_digest"],
        decision="update",
        rationale="Synthetic version update",
        target_path="knowledge/glossaries/fixture.md",
        candidate=card(second, title="Updated synthetic card"),
    )
    new_view = changes.materialize(root, "update-op")
    new_review = confirm_fixture(root, operation_id="update-op")
    code, response = public_apply(root, "update-op", new_review["review_ref"], tmp_path)
    assert code == 0, response
    lock = changes.source_lock(root)
    assert len(lock["snapshots"]) == 2
    assert lock["snapshots"][0] == capture["snapshots"][0]
    parsed = cards.parse_card((root / "knowledge/glossaries/fixture.md").read_bytes(), root)
    assert parsed["metadata"]["sources"] == [second["snapshots"][0]["snapshot_id"]]
    for path, digest in new_view["target_file_digests"].items():
        assert receipts.digest_file(root / path) == digest


def test_document_apply_has_no_lint_network_or_publish_call(domain, monkeypatch):
    root, capture = domain
    plan(root, capture)
    changes.materialize(root, "fixture-op")
    review = confirm_fixture(root)

    def forbidden(*args, **kwargs):
        raise AssertionError("Document apply must not run external lint, network or Git")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    result = transactions.apply_document(root, "fixture-op", review["review_ref"])
    assert result["phase"] == "applied"


def test_nonaccepted_review_never_mutates_official_assets(domain):
    root, capture = domain
    plan(root, capture)
    changes.materialize(root, "fixture-op")
    review = confirm_fixture(root, decision="deferred")
    before = official(root)
    with pytest.raises(ValueError, match="REVIEW_NOT_ACCEPTED"):
        transactions.apply_document(root, "fixture-op", review["review_ref"])
    assert official(root) == before


@pytest.mark.parametrize("decision", ["merge", "split", "deprecate", "defer", "no_change"])
def test_planned_only_decisions_have_structured_deferred_apply(domain, tmp_path, decision):
    root, capture = domain
    plan(root, capture, decision=decision)
    changes.materialize(root, "fixture-op")
    before = official(root)
    code, response = public_apply(
        root, "fixture-op", "logs/document-reviews/not-applicable.json", tmp_path
    )
    assert code == 2, response
    assert response["diagnostics"][0]["code"] == "DEFERRED_OPERATION"
    assert official(root) == before
