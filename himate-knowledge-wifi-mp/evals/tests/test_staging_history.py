"""Pinned historical cards resolve without Git or old private operations."""

import builtins
import importlib.util
import io
import os
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


def unreferenced_journals(root):
    """Keep every former public-CLI variant below both execution-history roots."""
    changes = {
        "committed": {"status": "committed"},
        "rolled_back": {"status": "rolled_back"},
        "prepared": {"status": "prepared"},
        "bad-seal": {},
        "bad-op": {"operation_id": "wrong"},
        "bad-schema": {"schema_version": "3.0"},
        "bad-kind": {"record_kind": "apply_result"},
        "same-operation": {},
        "bad-json": {},
        "unknown-state": {"status": "unrecognized"},
    }
    files = {}
    for kind, changed in changes.items():
        operation = "new" if kind == "same-operation" else "old-" + kind
        record = library.records.seal({
            "schema_version": "2.0", "record_kind": "transaction_journal",
            "operation_id": operation, "rules_digest": "a" * 64,
            "tool_identity": {"skill": "hs-fixture", "package_digest": "0" * 64,
                              "runtime": "fixture", "requirements_digest": "0" * 64},
            "status": "committed", "entries": [],
            "view_ref": ".build/operations/" + operation + "/view.json",
            "view_digest": "1" * 64,
            "proof_ref": "logs/operations/" + operation + "/proof.json",
            "proof_digest": "2" * 64, **changed,
        })
        if kind == "bad-seal":
            record["digest"] = "0" * 64
        raw = b"{unfinished" if kind == "bad-json" else validation.canonical_bytes(record)
        for ref in ("logs/operations/" + operation + "/journal.json",
                    ".build/operations/" + operation + "/transaction/journal.json"):
            target = root / ref
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            files[target] = raw
    return files


def deny_execution_history(monkeypatch, root, files):
    """Fail at IO, including errors a caller might otherwise catch and ignore."""
    private = root / ".build/operations"
    old_operations = {path.parent.parent for path in files
                      if private in path.parents and path.parent.parent.name != "new"}
    forbidden = (root / "logs/operations", private / "new/transaction", *old_operations)

    def checked(path, action):
        if isinstance(path, int):  # Existing file descriptors have no path to inspect.
            return
        native = os.fsdecode(path)
        if native.startswith("\\\\?\\UNC\\"):
            native = "\\\\" + native[8:]
        elif native.startswith("\\\\?\\"):
            native = native[4:]
        resolved = Path(os.path.abspath(native))
        if any(resolved == folder or folder in resolved.parents for folder in forbidden):
            pytest.fail("Unreferenced execution history must not be " + action + ": " + str(path))

    def guarded(original, action):
        def call(*args, **kwargs):
            path = args[0] if args else kwargs.get("file", kwargs.get("path", "."))
            checked(path, action)
            return original(*args, **kwargs)
        return call

    for module, name, action in ((builtins, "open", "opened"), (io, "open", "opened"),
                                 (os, "open", "opened"),
                                 (os, "listdir", "enumerated"), (os, "scandir", "enumerated")):
        monkeypatch.setattr(module, name, guarded(getattr(module, name), action))


@pytest.mark.parametrize("mode", ["formal", "candidate"])
def test_quality_checks_never_access_unreferenced_execution_history(tmp_path, monkeypatch, mode):
    root, raw, _, _, rules = library.library(tmp_path, kind="raw")
    files = unreferenced_journals(root)
    candidate = None
    if mode == "candidate":
        candidate = library.records.seal({"schema_version": "2.0", "record_kind": "final_view",
            "operation_id": "new", "writes": [], "deletes": [], "source_refs": [],
            "source_set_digest": validation.sha256_bytes(validation.canonical_bytes([]))})
    # Parent-directory case-alias checks for this round's lint-index are valid;
    # history subtrees, including this operation's journal, are never inputs.
    with monkeypatch.context() as guarded:
        deny_execution_history(guarded, root, files)
        # Prove both read and enumeration tripwires are armed on the real IO paths.
        with pytest.raises(pytest.fail.Exception, match="must not be opened"):
            next(iter(files)).read_bytes()
        with pytest.raises(pytest.fail.Exception, match="must not be enumerated"):
            list((root / ".build/operations/old-committed").iterdir())
        report = checks.run(checks.prepare_view(root, candidate, mode=mode), rules,
                            inputs={"source_objects": {"v1": raw}}, scope="full")
    assert report["status"] == "passed", report["findings"]
    assert all(path.read_bytes() == before for path, before in files.items())
