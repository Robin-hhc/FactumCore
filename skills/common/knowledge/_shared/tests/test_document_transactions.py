"""Synthetic transaction checks; review authentication is a separate public seam."""

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from _shared import changes, receipts

ROOT = Path(__file__).resolve().parents[5]
TARGET = "knowledge/rules/synthetic.md"
INDEX = "knowledge/rules/index.md"
LOCK = "governance/sources.lock.yaml"


def card_bytes(card_id="synthetic-card", claim_id="synthetic-claim", **extra):
    metadata = {
        "schema_version": "1.0",
        "id": card_id,
        "profile": "rule",
        "title": "Synthetic transaction fixture",
        "summary": "No WiFi business assertion",
        "lifecycle": "stable",
        "review_mode": "manual_document",
        "owner": "synthetic",
        "scope": {"applicability": "unknown", "contexts": []},
        "aliases": [],
        "sources": ["snapshot-synthetic"],
        "claims": [
            {
                "id": claim_id,
                "text_ref": "#statement",
                "evidence_kind": "design",
                "source_ids": ["source-synthetic"],
                "context_ids": [],
                "usage": "guidance",
                "verification_requirements": [],
            }
        ],
        "relations": [],
        **extra,
    }
    body = '<a id="statement"></a>\nSynthetic fixture statement.\n'
    sections = (
        ("职责", "边界", "接口", "依赖", "证据")
        if extra.get("profile") == "entity"
        else ("规则对象", "约束", "例外", "批准身份", "检查办法", "证据")
    )
    for section in sections:
        body += f"\n## {section}\nSynthetic fixture.\n"
    return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n" + body).encode()


def sources_bytes():
    return yaml.safe_dump(
        {
            "schema_version": "1.0",
            "resources": [
                {
                    "source_id": "source-synthetic",
                    "kind": "raw_document",
                    "authority_domain": "synthetic",
                    "resolver": "raw",
                    "resource_id": "docs-raw/specs/synthetic.md",
                }
            ],
            "snapshots": [
                {
                    "source_id": "source-synthetic",
                    "snapshot_id": "snapshot-synthetic",
                    "declared_version": "unknown",
                    "object_digest": "a" * 64,
                    "bytes": 1,
                    "mime": "text/plain",
                    "encoding": "utf-8",
                    "digest_kind": "original_bytes",
                    "retrieval": {"method": "raw_file", "location": "docs-raw/specs/synthetic.md"},
                    "recovery": {
                        "status": "available",
                        "method": "evidence_bundle",
                        "reference": "logs/evidence/synthetic/manifest.json",
                        "retention_policy": "retained",
                    },
                    "acquired_at": "2026-10-20T00:00:00Z",
                    "acquisition_tool": "synthetic-test",
                    "locator_policy": "line",
                    "extraction": {
                        "status": "complete",
                        "tool": "synthetic",
                        "tool_version": "1",
                        "parameters": {},
                        "text_digest": "b" * 64,
                        "locator_ref": "logs/evidence/synthetic/locators.json",
                    },
                }
            ],
        },
        allow_unicode=True,
    ).encode()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "synthetic-knowledge"
    shutil.copytree(ROOT / "aiot-wifi-knowledge/governance/schemas", root / "governance/schemas")
    shutil.copyfile(
        ROOT / "aiot-wifi-knowledge/governance/framework.lock.yaml",
        root / "governance/framework.lock.yaml",
    )
    operation = "synthetic-op"
    outputs = {TARGET: card_bytes(), INDEX: b"# Synthetic\n", LOCK: sources_bytes()}
    baseline = {}
    for path, data in outputs.items():
        final = root / ".build" / operation / "final-view" / path
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(data)
        baseline[path] = None
    view = {
        "operation_id": operation,
        "decision": "create",
        "review_mode": "manual_document",
        "target_file_digests": {p: receipts.digest_bytes(b) for p, b in outputs.items()},
        "baseline": baseline,
        "final_view_digest": "synthetic-bound-view",
    }
    (root / f".build/{operation}/plan.json").write_bytes(
        changes.json_bytes(
            {
                "operation_id": operation,
                "decision": "create",
                "request": {"operation_id": operation, "decision": "create"},
            }
        )
    )
    monkeypatch.setattr(changes, "checked_view", lambda k, op: view)
    monkeypatch.setattr(
        changes,
        "validate_review",
        lambda k, op, ref, **kwargs: {"decision": "accepted", "extensions": {"synthetic": True}},
        raising=False,
    )
    review = root / "logs/document-reviews/synthetic.json"
    review.parent.mkdir(parents=True)
    review.write_bytes(b'{"decision":"accepted","extensions":{"synthetic":true}}')
    return root, operation, outputs, view


def test_confirmed_final_bytes_are_applied_once_and_unrelated_dirty_is_preserved(prepared):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    unrelated = root / "knowledge/unrelated-notes.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"other task's uncommitted bytes\n")
    result = transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert result["phase"] == "applied"
    for path, data in outputs.items():
        assert (root / path).read_bytes() == data
    assert unrelated.read_bytes() == b"other task's uncommitted bytes\n"
    journal_path = root / "logs/operations" / operation / "journal.json"
    assert json.loads(journal_path.read_bytes())["state"] == "committed"
    journal_bytes = journal_path.read_bytes()
    assert (
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
        == result
    )
    assert journal_path.read_bytes() == journal_bytes
    assert list(root.rglob("*LocalCheck*")) == []
    assert list(root.rglob("*MergeGate*")) == []


@pytest.mark.parametrize("identity", ["card", "claim"])
def test_duplicate_identity_added_outside_touched_paths_is_rejected(prepared, identity):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    other = root / "knowledge/rules/other.md"
    other.parent.mkdir(parents=True)
    data = card_bytes(
        card_id="synthetic-card" if identity == "card" else "other-card",
        claim_id="synthetic-claim" if identity == "claim" else "other-claim",
    )
    other.write_bytes(data)
    with pytest.raises(changes.ChangeError, match="DUPLICATE_.*_ID"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert other.read_bytes() == data
    assert all(not (root / path).exists() for path in outputs)


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        ({"replacement": ["missing-card"]}, "UNRESOLVED_CARD_REF"),
        (
            {"relations": [{"type": "related_to", "target_card_id": "missing", "context_ids": []}]},
            "UNRESOLVED_CARD_REF",
        ),
        (
            {
                "relations": [
                    {
                        "type": "related_to",
                        "target_card_id": "synthetic-card",
                        "target_claim_id": "missing",
                        "context_ids": [],
                    }
                ]
            },
            "UNRESOLVED_CLAIM_REF",
        ),
        ({"replacement": ["synthetic-card"]}, "CYCLIC_CARD_RELATION"),
        (
            {
                "relations": [
                    {"type": "requires", "target_card_id": "synthetic-card", "context_ids": []}
                ]
            },
            "CYCLIC_CARD_RELATION",
        ),
    ],
)
def test_reference_closure_and_required_acyclic_relations(prepared, extra, code):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, view = prepared
    outputs[TARGET] = card_bytes(**extra)
    (root / ".build" / operation / "final-view" / TARGET).write_bytes(outputs[TARGET])
    view["target_file_digests"][TARGET] = receipts.digest_bytes(outputs[TARGET])
    with pytest.raises(changes.ChangeError, match=code):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


def test_other_process_holding_domain_lock_blocks_apply_then_release_allows_it(prepared):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    script = (
        "import sys; from _shared.transactions import domain_write_lock; "
        "context=domain_write_lock(sys.argv[1]); context.__enter__(); "
        "print('locked',flush=True); sys.stdin.readline(); context.__exit__(None,None,None)"
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "skills/common/knowledge")}
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(changes.ChangeError, match="BUSY"):
            transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
        assert all(not (root / path).exists() for path in outputs)
    finally:
        process.communicate(input="\n", timeout=10)
    assert process.returncode == 0
    assert (
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")[
            "phase"
        ]
        == "applied"
    )


def test_another_operations_incomplete_journal_blocks_all_new_writes(prepared):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    journal = root / "logs/operations/interrupted/journal.json"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b'{"state":"replacing","operation_id":"interrupted"}')
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


@pytest.mark.parametrize(
    ("changed", "code"),
    [
        (TARGET, "APPLIED_STATE_CHANGED"),
        ("review", "REVIEW_STALE"),
        ("result", "RECOVERY_REQUIRED"),
    ],
)
def test_committed_replay_never_overwrites_later_edits_or_trusts_changed_receipts(
    prepared, changed, code
):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, _, _ = prepared
    reference = "logs/document-reviews/synthetic.json"
    transactions.apply_document(root, operation, reference)
    path = root / {"review": reference, "result": f"logs/operations/{operation}/result.json"}.get(
        changed, changed
    )
    data = b'{"phase":"forged"}' if changed == "result" else b"external edit\n"
    path.write_bytes(data)
    with pytest.raises(changes.ChangeError, match=code):
        transactions.apply_document(root, operation, reference)
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "fault", ["backup", "prepared", "before_replace", "after_replace", "result", "commit"]
)
def test_write_failures_restore_exact_prior_bytes_with_journal_evidence(
    prepared, monkeypatch, fault
):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, view = prepared
    previous = {
        TARGET: card_bytes().replace(b"statement.", b"prior statement."),
        INDEX: b"# Prior\n",
        LOCK: sources_bytes(),
    }
    for path, data in previous.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        view["baseline"][path] = receipts.digest_bytes(data)
    view["decision"] = "update"
    real_write = changes.atomic_write
    failed = False

    def failing_write(k, path, data):
        nonlocal failed
        state = json.loads(data).get("state") if path.endswith("journal.json") else None
        selected = (
            (fault == "backup" and "/backups/" in path)
            or (fault == "prepared" and state == "prepared")
            or (fault in {"before_replace", "after_replace"} and path == INDEX)
            or (fault == "result" and path.endswith("/result.json"))
            or (fault == "commit" and state == "committed")
        )
        if selected and not failed:
            failed = True
            if fault == "after_replace":
                real_write(k, path, data)
            raise OSError("synthetic injected write failure")
        return real_write(k, path, data)

    monkeypatch.setattr(changes, "atomic_write", failing_write)
    with pytest.raises(changes.ChangeError, match="TRANSACTION_(FAILED|ROLLED_BACK)"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert failed
    assert {path: (root / path).read_bytes() for path in outputs} == previous
    journal = root / "logs/operations" / operation / "journal.json"
    if journal.exists():
        assert json.loads(journal.read_bytes())["state"] == "rolled_back"


def test_late_duplicate_created_after_preparation_is_detected_without_erasing_other_writer(
    prepared, monkeypatch
):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    real_write = changes.atomic_write
    other = root / "knowledge/rules/concurrent.md"
    data = card_bytes(claim_id="different-claim")

    def concurrent_write(k, path, payload):
        real_write(k, path, payload)
        if path.endswith("journal.json") and json.loads(payload)["state"] == "prepared":
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_bytes(data)

    monkeypatch.setattr(changes, "atomic_write", concurrent_write)
    with pytest.raises(changes.ChangeError, match="TRANSACTION_ROLLED_BACK"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert other.read_bytes() == data
    assert all(not (root / path).exists() for path in outputs)


def test_rollback_preserves_external_edit_and_blocks_further_apply(prepared, monkeypatch):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, _, _ = prepared
    real_write = changes.atomic_write
    external = b"later editor's content\n"

    def external_edit(k, path, data):
        real_write(k, path, data)
        if path == INDEX:
            (root / INDEX).write_bytes(external)
            raise OSError("synthetic failure after external edit")

    monkeypatch.setattr(changes, "atomic_write", external_edit)
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert (root / INDEX).read_bytes() == external
    assert not (root / TARGET).exists()
    assert not (root / LOCK).exists()
    journal = json.loads((root / f"logs/operations/{operation}/journal.json").read_bytes())
    assert journal["state"] == "recovery_required"
    assert journal["recovery_diagnostics"][0]["path"] == INDEX
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")


def test_hard_kill_retains_backup_journal_and_next_process_refuses_blind_restart(
    prepared, tmp_path
):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, _, view = prepared
    fixture = tmp_path / "synthetic-view.json"
    fixture.write_bytes(changes.json_bytes(view))
    script = "\n".join(
        [
            "import json,sys",
            "from pathlib import Path",
            "from _shared import changes,transactions",
            "root,op,fixture=sys.argv[1:]",
            "view=json.loads(Path(fixture).read_bytes())",
            "changes.checked_view=lambda k,o:view",
            "changes.validate_review=lambda k,o,r,**kw:{'decision':'accepted','extensions':{'synthetic':True}}",
            "write=changes.atomic_write",
            "def stop_after_write(k,p,data):",
            "    write(k,p,data)",
            "    if p=='governance/sources.lock.yaml':",
            "        print('replaced',flush=True)",
            "        sys.stdin.readline()",
            "changes.atomic_write=stop_after_write",
            "transactions.apply_document(root,op,'logs/document-reviews/synthetic.json')",
        ]
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(root), operation, str(fixture)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "skills/common/knowledge")},
    )
    try:
        assert process.stdout.readline().strip() == "replaced"
    finally:
        process.kill()
        process.communicate(timeout=10)
    assert (root / LOCK).exists()
    assert not (root / TARGET).exists()
    assert (
        json.loads((root / f"logs/operations/{operation}/journal.json").read_bytes())["state"]
        == "replacing"
    )
    assert (root / f"logs/operations/{operation}/backup-manifest.json").exists()
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")


def test_change_to_materialized_view_during_writing_rolls_back(prepared, monkeypatch):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, view = prepared
    real_write = changes.atomic_write

    def changed_view(k, path, data):
        real_write(k, path, data)
        if path == TARGET:
            view["final_view_digest"] = "changed-after-approval"

    monkeypatch.setattr(changes, "atomic_write", changed_view)
    with pytest.raises(changes.ChangeError, match="TRANSACTION_ROLLED_BACK"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


@pytest.mark.parametrize(
    "metadata", [{"lifecycle": "draft"}, {"review_mode": "code_gate"}, {"profile": "entity"}]
)
def test_document_apply_requires_stable_document_card_at_profile_path(prepared, metadata):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, view = prepared
    data = card_bytes(**metadata)
    (root / ".build" / operation / "final-view" / TARGET).write_bytes(data)
    view["target_file_digests"][TARGET] = receipts.digest_bytes(data)
    with pytest.raises(changes.ChangeError, match="INVALID_DOCUMENT_TARGET"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


@pytest.mark.parametrize(
    "target",
    [
        "../outside.md",
        "docs-raw/specs/not-a-card.md",
        "knowledge/rules/../escape.md",
        "knowledge/rules/CON.md",
        "knowledge/rules/evil:stream.md",
    ],
)
def test_unsafe_or_non_card_target_is_rejected_before_formal_write(prepared, target):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, view = prepared
    digest = view["target_file_digests"].pop(TARGET)
    view["target_file_digests"][target] = digest
    view["baseline"][target] = view["baseline"].pop(TARGET)
    with pytest.raises(changes.ChangeError, match="UNSAFE_(PATH|TARGET)"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


def test_related_baseline_edit_is_preserved_and_rejected_before_backups(prepared):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    path = root / INDEX
    path.parent.mkdir(parents=True)
    path.write_bytes(b"unreviewed navigation edit\n")
    with pytest.raises(changes.ChangeError, match="BASELINE_CHANGED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert path.read_bytes() == b"unreviewed navigation edit\n"
    assert not (root / TARGET).exists()
    assert not (root / LOCK).exists()
    assert not (root / f"logs/operations/{operation}/backup-manifest.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_windows_junction_cannot_redirect_final_placement(prepared, tmp_path):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, _, _ = prepared
    external = tmp_path / "outside-domain"
    external.mkdir()
    (root / "knowledge").mkdir()
    junction = root / "knowledge/rules"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(external)], capture_output=True, check=True
    )
    try:
        with pytest.raises(changes.ChangeError, match="UNSAFE_PATH"):
            transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
        assert list(external.iterdir()) == []
    finally:
        junction.rmdir()


def test_missing_committed_review_is_not_silently_treated_as_idempotent_success(prepared):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, _, _ = prepared
    reference = "logs/document-reviews/synthetic.json"
    transactions.apply_document(root, operation, reference)
    (root / reference).unlink()
    with pytest.raises(changes.ChangeError, match="REVIEW_STALE"):
        transactions.apply_document(root, operation, reference)


def test_rollback_does_not_delete_matching_new_bytes_written_externally_to_unattempted_target(
    prepared, monkeypatch
):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    real_write = changes.atomic_write

    def different_writer(k, path, data):
        real_write(k, path, data)
        if path == INDEX:
            (root / TARGET).write_bytes(outputs[TARGET])
            raise OSError("another writer created the future target before our attempt")

    monkeypatch.setattr(changes, "atomic_write", different_writer)
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert (root / TARGET).read_bytes() == outputs[TARGET]
    assert not (root / INDEX).exists()
    assert not (root / LOCK).exists()


@pytest.mark.parametrize("broken", ["missing", "incomplete_structure", "non_object"])
def test_missing_or_structurally_broken_other_transaction_journal_fails_closed(prepared, broken):
    transactions = importlib.import_module("_shared.transactions")
    root, operation, outputs, _ = prepared
    directory = root / "logs/operations/old-operation"
    directory.mkdir(parents=True)
    if broken == "missing":
        (directory / "backup-manifest.json").write_bytes(b'{"targets":[]}')
    elif broken == "incomplete_structure":
        (directory / "journal.json").write_bytes(b'{"state":"committed"}')
    else:
        (directory / "journal.json").write_bytes(b"[]")
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


def test_card_identity_cannot_hide_outside_registered_profile_folders(prepared):
    from _shared import transactions

    root, operation, outputs, _ = prepared
    rogue = root / "knowledge/other/duplicate.md"
    rogue.parent.mkdir(parents=True)
    rogue.write_bytes(card_bytes())
    with pytest.raises(changes.ChangeError, match="DUPLICATE_CARD_ID|INVALID_CARD_PATH"):
        transactions.apply_document(root, operation, "logs/document-reviews/synthetic.json")
    assert all(not (root / path).exists() for path in outputs)


def test_missing_old_committed_result_blocks_a_new_operation(prepared):
    from _shared import transactions

    root, operation, outputs, view = prepared
    reference = "logs/document-reviews/synthetic.json"
    transactions.apply_document(root, operation, reference)
    (root / f"logs/operations/{operation}/result.json").unlink()
    new_op = "next-operation"
    view.update(
        operation_id=new_op,
        decision="update",
        baseline={path: receipts.digest_bytes(data) for path, data in outputs.items()},
    )
    for path, data in outputs.items():
        target = root / f".build/{new_op}/final-view/{path}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / f".build/{new_op}/plan.json").write_bytes(
        changes.json_bytes(
            {
                "operation_id": new_op,
                "decision": "update",
                "request": {"operation_id": new_op, "decision": "update"},
            }
        )
    )
    with pytest.raises(changes.ChangeError, match="RECOVERY_REQUIRED"):
        transactions.apply_document(root, new_op, reference)
    assert not (root / f"logs/operations/{new_op}/journal.json").exists()


def test_saved_review_bytes_must_match_the_record_actually_validated(prepared):
    from _shared import transactions

    root, operation, outputs, _ = prepared
    reference = "logs/document-reviews/synthetic.json"
    # The validation seam simulates reading accepted B between reads of deferred A.
    (root / reference).write_bytes(b'{"decision":"deferred","extensions":{"synthetic":true}}')
    with pytest.raises(changes.ChangeError, match="REVIEW_STALE"):
        transactions.apply_document(root, operation, reference)
    assert all(not (root / path).exists() for path in outputs)
