"""Pinned historical cards resolve without Git or old private operations."""

import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("stage_history_library", Path(__file__).with_name("test_code_ref_required.py"))
library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(library)
checks, validation = library.checks, library.validation
knowledge, staging = library._helper.module("knowledge"), library._helper.module("staging")
runtime = library._helper.module("runtime")


def setup(tmp_path):
    root, _, _, _, rules = library.library(tmp_path, kind="raw")
    path = "knowledge/ready.md"
    old = (root / path).read_bytes()
    changed = old + b"\nNew formal content.\n"
    (root / path).write_bytes(changed)
    cards = {"ready-card": knowledge.parse_card(changed, path, rules)}
    record = {"acceptance": {"cards": [{"card_id": "ready-card", "path": path,
                                        "sha256": validation.sha256_bytes(old)}]}}
    return root, path, old, rules, cards, record


def test_published_exact_old_body_needs_no_stage_or_git(tmp_path, monkeypatch):
    root, path, old, rules, cards, record = setup(tmp_path)
    final = "logs/evidence/published/cards/" + validation.sha256_bytes(old) + ".md"
    target = root / final
    target.parent.mkdir(parents=True)
    target.write_bytes(old)
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: pytest.fail("Exact published hash must not invoke Git"))
    resolved = checks._record_resolver(cards, rules, {}, root, {})("ready-card", record)
    assert resolved["raw"] == old and resolved["path"] == path
    target.write_bytes(b"corrupt")
    with pytest.raises(validation.ContractError) as failure:
        checks._record_resolver(cards, rules, {}, root, {})("ready-card", record)
    assert failure.value.code == "HISTORICAL_CARD_CHANGED"


def test_only_explicit_stage_mapping_can_supply_old_card(tmp_path, monkeypatch):
    from types import SimpleNamespace
    root, path, old, rules, cards, record = setup(tmp_path)
    final = "logs/evidence/published/cards/" + validation.sha256_bytes(old) + ".md"
    ctx = SimpleNamespace(root=root, operation="batch", base=".build/operations/batch")
    entry = staging.stage_bytes(ctx, final, old, kind="card")
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: pytest.fail("Explicit archive must not invoke Git"))
    resolve = checks._record_resolver(cards, rules, {}, root, {}, staged_objects=[entry])
    assert resolve("ready-card", record)["sha256"] == validation.sha256_bytes(old)
    # No implicit read of the abandoned physical stage, even though its bytes exist.
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("No Git")))
    with pytest.raises(validation.ContractError) as failure:
        checks._record_resolver(cards, rules, {}, root, {})("ready-card", record)
    assert failure.value.code == "RECORD_HISTORY_UNAVAILABLE"


@pytest.mark.parametrize("mode", ["formal", "candidate"])
def test_quality_checks_ignore_unreferenced_old_transaction_directories(tmp_path, mode):
    root, raw, _, _, rules = library.library(tmp_path, kind="raw")
    for ref in ("logs/operations/old/journal.json", ".build/operations/old/transaction/journal.json"):
        target = root / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"{broken unrelated old operation")
    candidate = None
    if mode == "candidate":
        candidate = library.records.seal({"schema_version": "2.0", "record_kind": "final_view",
            "operation_id": "new", "writes": [], "deletes": [], "source_refs": [],
            "source_set_digest": validation.sha256_bytes(validation.canonical_bytes([]))})
    report = checks.run(checks.prepare_view(root, candidate, mode=mode), rules,
                        inputs={"source_objects": {"v1": raw}}, scope="full")
    assert report["status"] == "passed", report["findings"]
