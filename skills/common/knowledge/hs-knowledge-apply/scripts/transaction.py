"""Single writer/CAS transaction engine with durable recovery."""

import base64
import importlib
import pathlib
import re

from support import (
    Blocked,
    Invalid,
    WriterLock,
    atomic_bytes,
    checked_view,
    digest,
    native_path,
    strict_json,
    sync_directory,
    verify,
)


def current_digest(ctx, path):
    if isinstance(path, str) and path.startswith("logs/ingest/"):
        if not re.fullmatch(r"logs/ingest/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.yaml", path):
            raise Invalid("invalid controlled processing-record path")
        target = ctx.path(path, ("logs/ingest",))
    else:
        target = ctx.path(path, ("knowledge", "governance/sources.lock.yaml", "index.md"))
    if target.exists() and not target.is_file():
        raise Invalid("transaction target is not a file")
    return digest(target.read_bytes()) if target.is_file() else None


def read_other_journal(ctx, relative, directory_operation):
    """Read only another operation's supported journal for writer liveness.

    A terminal old-rules journal is not a current-rule proof. It is never
    resumed, re-signed, migrated or used to authorize the new operation.
    Same-operation reads keep Context.read's exact rules identity requirement.
    """
    path = ctx.path(relative, ("logs/operations",))
    other = verify(strict_json(pathlib.Path(native_path(path)).read_text(encoding="utf-8")))
    if other.get("record_kind") != "transaction_journal":
        raise Invalid("another operation has an unsupported transaction journal kind")
    if ctx.operation(other) != directory_operation:
        raise Invalid("another transaction journal operation does not match its directory")
    if not re.fullmatch(r"[0-9a-f]{64}", str(other.get("rules_digest", ""))):
        raise Invalid("another transaction journal has an invalid rules identity")
    if ctx.domain:
        ctx.domain.validate_shape("transaction_journal", other, ctx.rules)
    return other


def validate_proof(ctx, request, view):
    """Read optional supporting material; it is not permission to apply."""
    proof_ref = request.get("proof_ref")
    if not proof_ref:
        return {}
    ctx.path(
        proof_ref,
        (
            f"logs/operations/{view['operation_id']}",
            f".build/operations/{view['operation_id']}",
        ),
    )
    proof = ctx.read(proof_ref)
    if (
        proof.get("operation_id") != view["operation_id"]
        or proof.get("view_digest") != view["digest"]
    ):
        raise Invalid("proof is not bound to this exact final view")
    return proof


def validate_final_cards(ctx, view):
    if ctx.domain is None:
        return
    knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
    entries = {}
    knowledge_root = ctx.path("knowledge")
    if knowledge_root.exists():
        for path in knowledge_root.rglob("*.md"):
            rel = path.relative_to(ctx.root).as_posix()
            ctx.path(rel)
            if path.name in ("AGENTS.md", "index.md", "README.md"):
                continue
            entries[rel] = path.read_bytes()
    rules = dict(ctx.rules)
    for row in view.get("deletes", []):
        entries.pop(row["path"], None)
    for row in view["writes"]:
        raw = base64.b64decode(row["bytes_b64"], validate=True)
        if row["path"] == "governance/sources.lock.yaml":
            rules["source_lock"] = ctx.domain.load_yaml(raw)
            ctx.domain.validate_shape("sources", rules["source_lock"], rules)
        elif row["path"].startswith("knowledge/") and pathlib.PurePosixPath(
            row["path"]
        ).name not in ("AGENTS.md", "index.md", "README.md"):
            if not row["path"].endswith(".md"):
                raise Invalid("knowledge cards must be Markdown")
            entries[row["path"]] = raw
    cards = {}
    for path, raw in entries.items():
        card = knowledge.parse_card(raw, path, rules)
        key = card["metadata"]["id"]
        if key in cards:
            raise Invalid("duplicate card ID in final view")
        cards[key] = card
        if path in {row["path"] for row in view["writes"]} and (
            (view["review_mode"] != "mixed" and card["metadata"]["review_mode"] != view["review_mode"])
            or card["metadata"]["lifecycle"] not in ("stable", "deprecated")
        ):
            raise Invalid("final card review mode/lifecycle mismatches reviewed view")
    for card in cards.values():
        knowledge.validate_card(card, cards, rules)
    knowledge.validate_relations(cards)
    if view.get("review_mode") == "mixed":
        written_paths = {row["path"] for row in view["writes"]}
        actual = {mode: sorted(card["path"] for card in cards.values()
                               if card["path"] in written_paths and card["metadata"]["review_mode"] == mode)
                  for mode in ("manual_document", "code_gate")}
        if not all(actual.values()) or actual != {
            mode: sorted(paths) for mode, paths in view.get("review_requirements", {}).items()
        }:
            raise Invalid("mixed proof requirements must match both actual card partitions")


def baseline(view):
    return digest(
        {
            "files": {
                row["path"]: row["expected_old_digest"]
                for row in view["writes"] + view.get("deletes", [])
            }
        }
    )


def fixture_fault_allowed(ctx):
    marker = ctx.root / ".isolated-knowledge-fixture"
    fixture_root = ctx.catalog.get("test_fixture_root")
    return (
        marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == "HIMATE_SYNTHETIC_FIXTURE_V2"
        and isinstance(fixture_root, str)
        and pathlib.Path(fixture_root).resolve() == ctx.root
    )


def save_journal(ctx, journal):
    ctx.save(
        f"logs/operations/{journal['operation_id']}/journal.json",
        journal,
        immutable=False,
    )


def preflight_recovery(ctx, journal):
    for row in journal["entries"]:
        actual = current_digest(ctx, row["path"])
        if not row.get("attempted") and actual != row["old_digest"]:
            raise Blocked(
                "external bytes on unattempted target are preserved: " + row["path"]
            )
        if actual not in (row["old_digest"], row["new_digest"]):
            raise Blocked("external edit preserved; recovery conflict: " + row["path"])


def validate_journal(ctx, journal, op):
    """A resealed Agent-written journal is not authority to mutate files."""
    if (
        journal.get("record_kind") != "transaction_journal"
        or journal.get("operation_id") != op
    ):
        raise Invalid("transaction journal identity mismatch")
    request = {
        "operation_id": op,
        "view_ref": journal.get("view_ref"),
    }
    view = checked_view(ctx, request)
    # Upstream reports are retained as observations, not recovery dependencies.
    proof = {"digest": journal["proof_digest"]} if journal.get("proof_digest") else {}
    if view["digest"] != journal.get("view_digest"):
        raise Invalid("journal is not bound to the exact transaction view")
    expected = []
    rows = view["writes"] + view.get("deletes", [])
    if journal.get("ingest_record_ref"):
        from transaction_v3 import record_input
        original, entry = record_input(ctx, {"operation_id": op, "ingest_record_ref": journal["ingest_record_ref"],
                                             "content_review_ref": journal.get("content_review_ref")}, view, proof)
        if original["digest"] != journal.get("ingest_record_digest"):
            raise Invalid("journal processing-record input changed")
        rows = rows + [entry]
    for row in rows:
        old = row["expected_old_digest"]
        expected.append(
            {
                "path": row["path"],
                "old_digest": old,
                "new_digest": row.get("final_digest"),
                "bytes_b64": row.get("bytes_b64"),
                "backup_ref": f"logs/operations/{op}/backups/{old}.bin"
                if old
                else None,
            }
        )
    actual = [
        {
            key: row.get(key)
            for key in ("path", "old_digest", "new_digest", "bytes_b64", "backup_ref")
        }
        for row in journal.get("entries", [])
    ]
    if actual != expected:
        raise Invalid("journal write set differs from reviewed exact bytes")
    return view, proof


def finish_commit(ctx, journal):
    op = journal["operation_id"]
    result_ref = f"logs/operations/{op}/apply-result.json"
    result = ctx.record(
        "apply_result",
        op,
        status="committed",
        view_ref=journal["view_ref"],
        view_digest=journal["view_digest"],
        **({"proof_ref": journal["proof_ref"], "proof_digest": journal["proof_digest"]}
           if journal.get("proof_ref") else {}),
        writes=[
            row["path"] for row in journal["entries"] if row["new_digest"] is not None
        ],
        deletes=[
            row["path"] for row in journal["entries"] if row["new_digest"] is None
        ],
        verification_tier=journal["verification_tier"],
        batch_kind=journal.get("batch_kind", "content"),
        **({"ingest_record_path": next(row["path"] for row in journal["entries"] if row["path"].startswith("logs/ingest/"))}
           if journal.get("ingest_record_ref") else {}),
    )
    ctx.save(result_ref, result)
    journal["status"] = "committed"
    journal["result_ref"] = result_ref
    save_journal(ctx, journal)
    return {
        "apply_result_ref": result_ref,
        "apply_result_digest": result["digest"],
        "transaction_status": "committed",
        "phase": "committed",
        "batch_kind": journal.get("batch_kind", "content"),
    }


def mutate(ctx, journal, fault_after=None):
    performed = 0
    journal["status"] = "applying"
    save_journal(ctx, journal)
    try:
        for row in journal["entries"]:
            actual = current_digest(ctx, row["path"])
            if actual == row["new_digest"] and (
                row.get("attempted") or row["old_digest"] == row["new_digest"]
            ):
                continue
            if actual != row["old_digest"]:
                raise Blocked("external edit preserved during apply: " + row["path"])
            target = ctx.path(row["path"])
            row["attempted"] = True
            save_journal(ctx, journal)
            if row["new_digest"] is None:
                if target.exists():
                    target.unlink()
                    sync_directory(target.parent)
            else:
                content = base64.b64decode(row["bytes_b64"], validate=True)
                if digest(content) != row["new_digest"]:
                    raise Invalid("journal final bytes changed")
                atomic_bytes(target, content)
            performed += 1
            # A crash here is reconciled from old/final digests on recovery.
            row["installed"] = True
            save_journal(ctx, journal)
            if fault_after is not None and performed >= fault_after:
                raise Blocked("synthetic injected interruption")
        return finish_commit(ctx, journal)
    except Exception as exc:
        journal["status"] = "recovery_required"
        journal["diagnostic"] = str(exc)
        save_journal(ctx, journal)
        if isinstance(exc, (Invalid, Blocked)):
            raise
        raise Blocked("apply interrupted; inspect or recover the journal") from exc


def execute(ctx, request, action="run"):
    op = ctx.operation(request)
    if action == "run" and not request.get("view_ref") and request.get("ingest_record_ref"):
        from transaction_v3 import record_only_view
        request = record_only_view(ctx, request)
    if action == "verify-result":
        purpose = request.get("purpose", "current")
        if purpose not in ("current", "historical"):
            raise Invalid("unknown content verification purpose")
        result_ref = request.get("apply_result_ref")
        ctx.path(result_ref, (f"logs/operations/{op}",))
        result = ctx.read(result_ref)
        journal = ctx.read(f"logs/operations/{op}/journal.json")
        view, proof = validate_journal(ctx, journal, op)
        if (
            journal.get("status") != "committed"
            or journal.get("result_ref") != result_ref
            or result.get("record_kind") != "apply_result"
            or result.get("status") != "committed"
            or result.get("operation_id") != op
            or result.get("view_digest") != view["digest"]
            or result.get("proof_digest") != proof.get("digest")
        ):
            raise Invalid("apply result does not match the verified committed transaction")
        expected_writes = [row["path"] for row in journal["entries"] if row["new_digest"] is not None]
        expected_deletes = [row["path"] for row in view.get("deletes", [])]
        if (
            result.get("writes") != expected_writes
            or result.get("deletes") != expected_deletes
        ):
            raise Invalid("apply result write set was changed")
        eligible, historical = [], []
        current_proof_ref = (
            request.get("current_code_proof_ref") or journal.get("proof_ref")
        )
        if purpose == "current":
            from transaction_v3 import check_current_code
            check_current_code(ctx, view, request.get("check_inputs", journal.get("check_inputs")))
        source_overlay = None
        for write in view["writes"]:
            if write["path"] == "governance/sources.lock.yaml":
                source_overlay = (
                    ctx.domain.load_yaml(
                        base64.b64decode(write["bytes_b64"], validate=True)
                    )
                    if ctx.domain
                    else None
                )
        for row in view["writes"]:
            if not row["path"].startswith("knowledge/") or pathlib.PurePosixPath(
                row["path"]
            ).name in ("index.md", "AGENTS.md", "README.md"):
                continue
            if request.get("card_path") and row["path"] != request["card_path"]:
                continue
            actual_matches = (
                purpose == "historical"
                or current_digest(ctx, row["path"]) == row["final_digest"]
            )
            if purpose == "current" and not actual_matches:
                continue
            if ctx.domain:
                knowledge = importlib.import_module(
                    ctx.domain.__package__ + ".knowledge"
                )
                sources = importlib.import_module(
                    ctx.domain.__package__ + ".source_resources"
                )
                card_raw = (
                    base64.b64decode(row["bytes_b64"], validate=True)
                    if purpose == "historical"
                    else ctx.path(row["path"]).read_bytes()
                )
                card_rules = {
                    **ctx.rules,
                    **(
                        {"source_lock": source_overlay}
                        if purpose == "historical" and source_overlay
                        else {}
                    ),
                }
                card = knowledge.parse_card(card_raw, row["path"], card_rules)
                knowledge.validate_card(card, None, card_rules)
                source_lock = (
                    source_overlay
                    if purpose == "historical" and source_overlay
                    else sources.read_source_lock(ctx.root)
                )
                for ref in card["metadata"]["sources"]:
                    snapshot = sources.validate_source_ref(ref, source_lock)
                    sources.recover_snapshot(ctx.root, snapshot)
                if (
                    purpose == "historical"
                    or card["metadata"]["lifecycle"] == "deprecated"
                ):
                    historical.append(
                        {"path": row["path"], "sha256": row["final_digest"]}
                    )
                    continue
            if purpose == "historical":
                historical.append({"path": row["path"], "sha256": row["final_digest"]})
            else:
                eligible.append({"path": row["path"], "sha256": row["final_digest"]})
        if request.get("card_path") and not any(
            row["path"] == request["card_path"]
            and row["sha256"] == request.get("card_digest")
            for row in (historical if purpose == "historical" else eligible)
        ):
            raise Blocked(
                "requested card has no current verified exact-content eligibility"
            )
        return {
            "result_verified": True,
            "verification_scope": "verified_content_integrity",
            "purpose": purpose,
            "eligible_files": eligible,
            "historical_files": historical,
            "view_ref": journal["view_ref"],
            "view_digest": view["digest"],
            "write_manifest": [{"path": row["path"], "sha256": row["new_digest"]}
                               for row in journal["entries"] if row["new_digest"] is not None],
            "delete_manifest": [row["path"] for row in journal["entries"] if row["new_digest"] is None],
            "batch_kind": journal.get("batch_kind", "content"),
            "proof_ref": journal.get("proof_ref"),
            "current_code_proof_ref": current_proof_ref
            if purpose == "current" and view["review_mode"] in {"code_gate", "mixed"}
            else None,
            "verification_tier": journal["verification_tier"],
            "phase": "verified",
        }
    if action not in ("run", "inspect", "resume", "rollback"):
        raise Invalid("unsupported transaction action")
    journal_ref = f"logs/operations/{op}/journal.json"
    with WriterLock(ctx.root):
        journal = ctx.read(journal_ref) if ctx.path(journal_ref).exists() else None
        if action == "inspect":
            if not journal:
                raise Blocked("operation has no transaction journal")
            return {
                "journal_ref": journal_ref,
                "transaction_status": journal["status"],
                "entries": [
                    {
                        "path": row["path"],
                        "old_digest": row["old_digest"],
                        "final_digest": row["new_digest"],
                        "current_digest": current_digest(ctx, row["path"]),
                    }
                    for row in journal["entries"]
                ],
                "phase": "inspected",
            }
        operations = ctx.path("logs/operations")
        for other_path in (
            operations.glob("*/journal.json")
            if action == "run" and journal is None
            else []
        ):
            if other_path.parent.name == op:
                continue
            other = read_other_journal(ctx, other_path.relative_to(ctx.root).as_posix(), other_path.parent.name)
            if other.get("record_kind") != "transaction_journal" or other.get(
                "status"
            ) not in ("committed", "rolled_back"):
                raise Blocked(
                    "another operation requires recovery before domain writes: "
                    + other_path.parent.name
                )
        if journal and journal["status"] == "committed":
            if action == "rollback":
                raise Blocked(
                    "committed transactions require a new reviewed change, not rollback"
                )
            if (
                request.get("view_ref", journal["view_ref"]) != journal["view_ref"]
                or request.get("proof_ref", journal.get("proof_ref"))
                != journal.get("proof_ref")
            ):
                raise Invalid("operation ID already committed another request")
            result = ctx.read(journal["result_ref"])
            return {
                "apply_result_ref": journal["result_ref"],
                "apply_result_digest": result["digest"],
                "transaction_status": "committed",
                "phase": "committed",
                "batch_kind": journal.get("batch_kind", "content"),
            }
        if journal and journal["status"] == "rolled_back":
            if action == "rollback":
                return {
                    "journal_ref": journal_ref,
                    "transaction_status": "rolled_back",
                    "phase": "rolled_back",
                }
            raise Blocked("rolled-back operation is closed; create a new operation")
        if action in ("resume", "rollback"):
            if not journal:
                raise Blocked("no interrupted transaction to recover")
            validate_journal(ctx, journal, op)
            preflight_recovery(ctx, journal)
            if action == "rollback":
                # Check every old backup before changing any target.
                for row in journal["entries"]:
                    if row["old_digest"] is not None:
                        raw = ctx.path(row["backup_ref"]).read_bytes()
                        if digest(raw) != row["old_digest"]:
                            raise Invalid("recovery backup digest mismatch")
                for row in reversed(journal["entries"]):
                    if not row.get("attempted"):
                        continue
                    current = current_digest(ctx, row["path"])
                    if current == row["old_digest"]:
                        continue
                    if current != row["new_digest"]:
                        raise Blocked(
                            "external edit preserved during rollback: " + row["path"]
                        )
                    target = ctx.path(row["path"])
                    if row["old_digest"] is None:
                        target.unlink()
                        sync_directory(target.parent)
                    else:
                        atomic_bytes(target, ctx.path(row["backup_ref"]).read_bytes())
                journal["status"] = "rolled_back"
                save_journal(ctx, journal)
                return {
                    "journal_ref": journal_ref,
                    "transaction_status": "rolled_back",
                    "phase": "rolled_back",
                }
            request = {
                "operation_id": op,
                "view_ref": journal["view_ref"],
            }
            view = checked_view(ctx, request)
            if view["digest"] != journal["view_digest"]:
                raise Invalid("recovery inputs changed")
            validate_final_cards(ctx, view)
            from transaction_v3 import check_current_code
            check_current_code(ctx, view, journal.get("check_inputs"))
            return mutate(ctx, journal)
        if journal:
            raise Blocked("interrupted operation requires explicit resume or rollback")
        view = checked_view(ctx, request)
        proof = validate_proof(ctx, request, view)
        content_review = None
        if request.get("content_review_ref"):
            from transaction_v3 import validate_content_review
            content_review = ctx.read(request["content_review_ref"])
            validate_content_review(ctx, view, content_review)
        if view.get("baseline_digest", baseline(view)) != baseline(view):
            raise Invalid("complete write-set baseline digest mismatch")
        validate_final_cards(ctx, view)
        rows = view["writes"] + view.get("deletes", [])
        ingest_record = None
        if view.get("review_mode") != "record_only":
            from transaction_v3 import check_admission, check_current_code
            inputs = check_current_code(ctx, view, request.get("check_inputs"))
            if inputs:
                request = {**request, "check_inputs": inputs}
            check_admission(ctx, request, view)
        if request.get("ingest_record_ref"):
            from transaction_v3 import record_input
            ingest_record, entry = record_input(ctx, request, view, proof)
            rows = rows + [entry]
        for row in rows:
            if current_digest(ctx, row["path"]) != row["expected_old_digest"]:
                raise Blocked("complete write-set CAS conflict: " + row["path"])
        fault = request.get("fault_after")
        if fault is not None and (
            not isinstance(fault, int)
            or isinstance(fault, bool)
            or fault < 1
            or not fixture_fault_allowed(ctx)
        ):
            raise Invalid("fault injection requires an explicit isolated fixture")
        entries = []
        for row in rows:
            old = row["expected_old_digest"]
            backup_ref = f"logs/operations/{op}/backups/{old}.bin" if old else None
            if old:
                raw = ctx.path(row["path"]).read_bytes()
                if digest(raw) != old:
                    raise Blocked("input changed while backing up")
                backup_path = ctx.path(backup_ref)
                if backup_path.exists() and digest(backup_path.read_bytes()) != old:
                    raise Invalid("backup object corrupted")
                if not backup_path.exists():
                    atomic_bytes(backup_path, raw)
            entries.append(
                {
                    "path": row["path"],
                    "old_digest": old,
                    "new_digest": row.get("final_digest"),
                    "bytes_b64": row.get("bytes_b64"),
                    "backup_ref": backup_ref,
                    "installed": False,
                    "attempted": False,
                }
            )
        # Recheck all files after durable backups, before the prepared journal.
        for row in rows:
            if current_digest(ctx, row["path"]) != row["expected_old_digest"]:
                raise Blocked("write set changed while preparing transaction")
        journal = ctx.record(
            "transaction_journal",
            op,
            status="prepared",
            view_ref=request["view_ref"],
            view_digest=view["digest"],
            **({"proof_ref": request["proof_ref"], "proof_digest": proof["digest"]}
               if proof else {}),
            verification_tier="fixed_business_checks" if ctx.domain else "transaction_bytes_only",
            entries=entries,
            **({"check_inputs": request["check_inputs"]} if request.get("check_inputs") else {}),
            **({"content_review_ref": request["content_review_ref"],
                "content_review_digest": content_review["digest"]} if content_review else {}),
            **({"ingest_record_ref": request["ingest_record_ref"], "ingest_record_digest": ingest_record["digest"],
                "batch_kind": ingest_record["batch_kind"], "lint_report_ref": request.get("lint_report_ref")} if ingest_record else {}),
        )
        save_journal(ctx, journal)
        return mutate(ctx, journal, fault)
