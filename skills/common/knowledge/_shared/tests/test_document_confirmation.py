"""Test-only simulated terminal events, never production knowledge approval."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from _shared import changes, receipts
from test_document_changes import card, official, plan
from test_document_changes import domain as domain_fixture

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def domain(tmp_path):
    return domain_fixture.__wrapped__(tmp_path)


class FixtureTerminal(io.StringIO):
    def isatty(self):
        return True


def confirm_fixture(root, *, decision="accepted", operation_id="fixture-op", claim_ids=None):
    """Only test files call this helper; production CLI has no bypass flag."""
    view = changes.checked_view(root, operation_id)
    terminal = FixtureTerminal(f"{decision} {view['final_view_digest'][:12]}\n")
    result = changes.confirm_document(
        root,
        operation_id,
        decision=decision,
        confirmed_by="synthetic-human",
        input_stream=terminal,
        output_stream=io.StringIO(),
        claim_ids=claim_ids,
    )
    # Label persisted fixture records explicitly; never copy these into the real domain.
    record = changes.read_json(root, result["review_ref"])
    record["extensions"]["synthetic"] = True
    changes.atomic_write(root, result["review_ref"], changes.json_bytes(record))
    result["review_digest"] = receipts.digest_json(record)
    return result


def prepared(domain):
    root, capture = domain
    plan(root, capture)
    changes.materialize(root, "fixture-op")
    return root, capture


def test_no_real_action_or_wrong_challenge_cannot_create_review(domain):
    root, _ = prepared(domain)
    for stream, code in [
        (io.StringIO("accepted\n"), "HUMAN_ACTION_REQUIRED"),
        (FixtureTerminal("wrong\n"), "CONFIRMATION_MISMATCH"),
        (FixtureTerminal(""), "HUMAN_ACTION_REQUIRED"),
    ]:
        with pytest.raises(ValueError, match=code):
            changes.confirm_document(
                root,
                "fixture-op",
                decision="accepted",
                confirmed_by="Agent-name",
                input_stream=stream,
                output_stream=io.StringIO(),
            )
    assert not (root / "logs/document-reviews").exists()


@pytest.mark.parametrize("decision", ["accepted", "confirmed_no_impact"])
def test_self_confirmation_binds_all_exact_inputs(domain, decision):
    root, _ = prepared(domain)
    before = official(root)
    result = confirm_fixture(root, decision=decision)
    record = changes.validate_review(root, "fixture-op", result["review_ref"])
    assert record["confirmed_by"] == "synthetic-human"
    assert record["decision"] == decision
    assert record["extensions"]["changeset_digest"] == receipts.digest_json(
        changes.checked_view(root, "fixture-op")
    )
    assert official(root) == before
    final = root / ".build/fixture-op/final-view/knowledge/glossaries/fixture.md"
    final.write_bytes(final.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.validate_review(root, "fixture-op", result["review_ref"])


@pytest.mark.parametrize("decision", ["returned", "deferred", "deprecated", "partially_accepted"])
def test_non_acceptance_does_not_authorize_apply(domain, decision):
    root, _ = prepared(domain)
    result = confirm_fixture(root, decision=decision)
    with pytest.raises(ValueError, match="REVIEW_NOT_ACCEPTED"):
        changes.validate_review(root, "fixture-op", result["review_ref"])


def test_non_tty_cli_name_cannot_manufacture_approval(domain, tmp_path):
    root, _ = prepared(domain)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "skills/common/knowledge/_shared/cli.py"),
            "document",
            "confirm",
            "--knowledge-root",
            str(root),
            "--operation-id",
            "fixture-op",
            "--decision",
            "accepted",
            "--confirmed-by",
            "Agent-name",
        ],
        cwd=tmp_path,
        input="accepted\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "HUMAN_ACTION_REQUIRED"
    assert not (root / "logs/document-reviews").exists()


def test_partial_selection_requires_narrowed_view_and_new_human_action(domain):
    import copy

    import yaml

    root, capture = domain
    original = card(capture).decode()
    front, body = original[4:].split("---\n", 1)
    metadata = yaml.safe_load(front)
    second = copy.deepcopy(metadata["claims"][0])
    second.update(id="second-claim", text_ref="#second")
    metadata["claims"].append(second)
    content = (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True)
        + "---\n"
        + body
        + '<a id="second"></a>\nSecond synthetic conclusion.\n'
    ).encode()
    plan(root, capture, content=content)
    old = changes.materialize(root, "fixture-op")
    partial = confirm_fixture(root, decision="partially_accepted", claim_ids=["fixture-claim"])
    child = changes.narrow_document(
        root,
        "fixture-op",
        review_ref=partial["review_ref"],
        new_operation_id="narrowed",
        candidate=card(capture),
    )
    assert child["requires_new_confirmation"] is True
    assert child["final_view_digest"] != old["final_view_digest"]
    assert child["claim_ids"] == ["fixture-claim"]
    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.validate_review(root, "narrowed", partial["review_ref"])
    fresh = confirm_fixture(root, operation_id="narrowed")
    assert changes.validate_review(root, "narrowed", fresh["review_ref"])["decision"] == "accepted"


def test_input_changes_during_human_read_do_not_get_a_record(domain):
    root, _ = prepared(domain)
    view = changes.checked_view(root, "fixture-op")

    class ChangingTerminal(FixtureTerminal):
        def readline(self):
            target = root / ".build/fixture-op/final-view/knowledge/glossaries/fixture.md"
            target.write_bytes(target.read_bytes() + b"changed while reviewing")
            return super().readline()

    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.confirm_document(
            root,
            "fixture-op",
            decision="accepted",
            confirmed_by="synthetic-human",
            input_stream=ChangingTerminal(f"accepted {view['final_view_digest'][:12]}\n"),
            output_stream=io.StringIO(),
        )
    assert not (root / "logs/document-reviews").exists()


def test_confirmation_refuses_display_bytes_that_differ_then_recover(domain, monkeypatch):
    root, _ = prepared(domain)
    view = changes.checked_view(root, "fixture-op")
    target = root / ".build/fixture-op/final-view/knowledge/glossaries/fixture.md"
    original = Path.read_bytes
    reads = 0

    def transient(path):
        nonlocal reads
        if path == target:
            reads += 1
            if reads == 3:
                return b"Forged transient display text, not the reviewed bytes.\n"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", transient)
    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.confirm_document(
            root,
            "fixture-op",
            decision="accepted",
            confirmed_by="synthetic-human",
            input_stream=FixtureTerminal(f"accepted {view['final_view_digest'][:12]}\n"),
            output_stream=io.StringIO(),
        )
    assert not (root / "logs/document-reviews").exists()


def test_related_baseline_edit_invalidates_persistent_review(domain):
    root, _ = prepared(domain)
    result = confirm_fixture(root)
    (root / "governance/sources.lock.yaml").write_bytes(b"unrelated writer on relevant target")
    with pytest.raises(ValueError, match="REVIEW_STALE"):
        changes.validate_review(root, "fixture-op", result["review_ref"])


def test_reversed_complete_claim_selection_has_a_consumable_record(domain):
    import copy

    import yaml

    root, capture = domain
    front, body = card(capture).decode()[4:].split("---\n", 1)
    metadata = yaml.safe_load(front)
    second = copy.deepcopy(metadata["claims"][0])
    second.update(id="second-claim", text_ref="#second")
    metadata["claims"].append(second)
    content = (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True)
        + "---\n"
        + body
        + '<a id="second"></a>\nSecond synthetic conclusion.\n'
    ).encode()
    plan(root, capture, content=content)
    changes.materialize(root, "fixture-op")
    result = confirm_fixture(root, claim_ids=["second-claim", "fixture-claim"])
    assert (
        changes.validate_review(root, "fixture-op", result["review_ref"])["decision"] == "accepted"
    )
