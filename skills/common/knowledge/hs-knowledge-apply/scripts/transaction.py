"""Single writer/CAS transaction engine with durable recovery."""
import base64
import importlib
import json
import pathlib
import secrets
import subprocess
import sys

from support import (Blocked, Invalid, WriterLock, atomic_bytes, authenticated_event,
                     canonical, checked_view, digest, package_digest, sync_directory)


def current_digest(ctx, path):
    target = ctx.path(path, ("knowledge", "governance/sources.lock.yaml", "index.md"))
    if target.exists() and not target.is_file():
        raise Invalid("transaction target is not a file")
    return digest(target.read_bytes()) if target.is_file() else None


def invoke_checker(ctx, request):
    spec = ctx.catalog.get("skills", {}).get("hs-knowledge-local-check")
    if not spec:
        raise Blocked("trusted code checker is not installed")
    if not ctx.catalog_path:
        raise Blocked("trusted installed catalog path is required")
    root = pathlib.Path(spec["root"]).resolve()
    entry = root / spec.get("entry", "scripts/cli.py")
    if entry.resolve() != root / "scripts/cli.py" or package_digest(root) != spec.get("package_digest"):
        raise Invalid("code checker package identity mismatch")
    op = ctx.operation(request)
    req_ref = f".build/operations/{op}/apply-code-proof-request.json"
    request_bytes = canonical({"operation_id": op, "view_ref": request["view_ref"], "proof_ref": request["proof_ref"]})
    target = ctx.path(req_ref)
    if target.exists() and target.read_bytes() != request_bytes:
        raise Blocked("code proof request already frozen")
    if not target.exists():
        atomic_bytes(target, request_bytes)
    response_ref = f".build/operations/{op}/apply-code-proof-response-{secrets.token_hex(12)}.json"
    response_path = ctx.path(response_ref)
    command = [spec["python"], str(entry), "--input", str(target), "--output", str(response_path), "--knowledge-root", str(ctx.root), "--rules-digest", ctx.rules_digest, "--catalog", ctx.catalog_path, "--action", "verify-proof"]
    completed = subprocess.run(command, check=False, capture_output=True, timeout=120)
    if completed.returncode != 0 or not response_path.is_file():
        raise Blocked("trusted code checker did not verify proof")
    response = ctx.read(response_ref)
    if response.get("tool_identity", {}).get("package_digest") != spec["package_digest"] or response.get("status") != "ok" or response.get("data", {}).get("proof_verified") is not True:
        raise Blocked("code proof is incomplete or unsupported")


def validate_proof(ctx, request, view):
    proof_ref = request.get("proof_ref")
    ctx.path(proof_ref, (f"logs/operations/{view['operation_id']}", f".build/operations/{view['operation_id']}"))
    proof = ctx.read(proof_ref)
    if proof.get("operation_id") != view["operation_id"] or proof.get("view_digest") != view["digest"]:
        raise Invalid("proof is not bound to this exact final view")
    if view.get("review_mode") == "manual_document":
        if proof.get("record_kind") != "manual_review" or proof.get("status") != "approved":
            raise Blocked("document view requires explicit real-human approval")
        ctx.path(proof.get("display_ref"), (f".build/operations/{view['operation_id']}",))
        display = ctx.read(proof.get("display_ref"))
        if display.get("digest") != proof.get("display_digest") or display.get("view_digest") != view["digest"] or display.get("writes") != view.get("writes") or display.get("deletes") != view.get("deletes"):
            raise Invalid("manual proof display binding mismatch")
        authenticated_event(ctx, display, proof.get("host_event", {}), allow_elapsed=True)
        if proof["host_event"]["payload"]["decision"] != "approve":
            raise Blocked("human rejected this view")
    elif view.get("review_mode") == "code_gate":
        if proof.get("record_kind") != "local_check" or proof.get("status") != "passed" or proof.get("mode") != "local":
            raise Blocked("code view requires a passing local code proof")
        claims = proof.get("claims")
        if not claims or any(row.get("status") != "supported" or not row.get("evidence") for row in claims):
            raise Blocked("every code Claim requires positive evidence")
        invoke_checker(ctx, request)
    else:
        raise Invalid("unknown review mode")
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
        elif row["path"].startswith("knowledge/") and pathlib.PurePosixPath(row["path"]).name not in ("AGENTS.md", "index.md", "README.md"):
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
        if path in {row["path"] for row in view["writes"]} and (card["metadata"]["review_mode"] != view["review_mode"] or card["metadata"]["lifecycle"] != "stable"):
            raise Invalid("final card review mode/lifecycle mismatches approved view")
    for card in cards.values():
        knowledge.validate_card(card, cards, rules)
    knowledge.validate_relations(cards)


def baseline(view):
    return digest({"files": {row["path"]: row["expected_old_digest"] for row in view["writes"] + view.get("deletes", [])}})


def fixture_fault_allowed(ctx):
    marker = ctx.root / ".isolated-knowledge-fixture"
    adapters = ctx.catalog.get("review_trust", {}).get("adapters", {}).values()
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == "AIOTBOT_SYNTHETIC_FIXTURE_V2" and any(spec.get("synthetic") and spec.get("fixture_root") and pathlib.Path(spec["fixture_root"]).resolve() == ctx.root for spec in adapters)


def save_journal(ctx, journal):
    ctx.save(f"logs/operations/{journal['operation_id']}/journal.json", journal, immutable=False)


def preflight_recovery(ctx, journal):
    for row in journal["entries"]:
        actual = current_digest(ctx, row["path"])
        if actual not in (row["old_digest"], row["new_digest"]):
            raise Blocked("external edit preserved; recovery conflict: " + row["path"])


def validate_journal(ctx, journal, op):
    """A resealed Agent-written journal is not authority to mutate files."""
    if journal.get("record_kind") != "transaction_journal" or journal.get("operation_id") != op:
        raise Invalid("transaction journal identity mismatch")
    request = {"operation_id": op, "view_ref": journal.get("view_ref"), "proof_ref": journal.get("proof_ref")}
    view = checked_view(ctx, request)
    proof = validate_proof(ctx, request, view)
    if view["digest"] != journal.get("view_digest") or proof["digest"] != journal.get("proof_digest"):
        raise Invalid("journal is not bound to reviewed inputs")
    expected = []
    for row in view["writes"] + view.get("deletes", []):
        old = row["expected_old_digest"]
        expected.append({"path": row["path"], "old_digest": old, "new_digest": row.get("final_digest"), "bytes_b64": row.get("bytes_b64"), "backup_ref": f"logs/operations/{op}/backups/{old}.bin" if old else None})
    actual = [{key: row.get(key) for key in ("path", "old_digest", "new_digest", "bytes_b64", "backup_ref")} for row in journal.get("entries", [])]
    if actual != expected:
        raise Invalid("journal write set differs from reviewed exact bytes")
    return view, proof


def finish_commit(ctx, journal):
    op = journal["operation_id"]
    result_ref = f"logs/operations/{op}/apply-result.json"
    result = ctx.record("apply_result", op, status="committed", view_ref=journal["view_ref"], view_digest=journal["view_digest"], proof_ref=journal["proof_ref"], proof_digest=journal["proof_digest"], writes=[row["path"] for row in journal["entries"] if row["new_digest"] is not None], deletes=[row["path"] for row in journal["entries"] if row["new_digest"] is None], verification_tier=journal["verification_tier"])
    ctx.save(result_ref, result)
    journal["status"] = "committed"
    journal["result_ref"] = result_ref
    save_journal(ctx, journal)
    return {"apply_result_ref": result_ref, "apply_result_digest": result["digest"], "transaction_status": "committed", "phase": "committed"}


def mutate(ctx, journal, fault_after=None):
    performed = 0
    journal["status"] = "applying"
    save_journal(ctx, journal)
    try:
        for row in journal["entries"]:
            actual = current_digest(ctx, row["path"])
            if actual == row["new_digest"]:
                continue
            if actual != row["old_digest"]:
                raise Blocked("external edit preserved during apply: " + row["path"])
            target = ctx.path(row["path"])
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
    if action == "verify-result":
        result_ref = request.get("apply_result_ref")
        ctx.path(result_ref, (f"logs/operations/{op}",))
        result = ctx.read(result_ref)
        journal = ctx.read(f"logs/operations/{op}/journal.json")
        view, proof = validate_journal(ctx, journal, op)
        if journal.get("status") != "committed" or journal.get("result_ref") != result_ref or result.get("record_kind") != "apply_result" or result.get("status") != "committed" or result.get("operation_id") != op or result.get("view_digest") != view["digest"] or result.get("proof_digest") != proof["digest"]:
            raise Invalid("apply result is not an authenticated committed transaction")
        expected_writes = [row["path"] for row in view["writes"]]
        expected_deletes = [row["path"] for row in view.get("deletes", [])]
        if result.get("writes") != expected_writes or result.get("deletes") != expected_deletes:
            raise Invalid("apply result write set was changed")
        eligible = []
        for row in view["writes"]:
            if not row["path"].startswith("knowledge/") or pathlib.PurePosixPath(row["path"]).name in ("index.md", "AGENTS.md", "README.md"):
                continue
            if current_digest(ctx, row["path"]) != row["final_digest"]:
                continue
            if ctx.domain:
                knowledge = importlib.import_module(ctx.domain.__package__ + ".knowledge")
                sources = importlib.import_module(ctx.domain.__package__ + ".source_resources")
                card = knowledge.parse_card(ctx.path(row["path"]).read_bytes(), row["path"], ctx.rules)
                knowledge.validate_card(card, None, ctx.rules)
                source_lock = sources.read_source_lock(ctx.root)
                for ref in card["metadata"]["sources"]:
                    snapshot = sources.validate_source_ref(ref, source_lock)
                    sources.recover_snapshot(ctx.root, snapshot)
            eligible.append({"path": row["path"], "sha256": row["final_digest"]})
        if request.get("card_path") and not any(row["path"] == request["card_path"] and row["sha256"] == request.get("card_digest") for row in eligible):
            raise Blocked("requested card has no current authenticated exact-content eligibility")
        return {"result_verified": True, "verification_scope": "authenticated_content_eligibility", "eligible_files": eligible, "view_ref": journal["view_ref"], "view_digest": view["digest"], "proof_ref": journal["proof_ref"], "verification_tier": proof.get("verification_tier", "code_gate"), "phase": "verified"}
    if action not in ("run", "inspect", "resume", "rollback"):
        raise Invalid("unsupported transaction action")
    journal_ref = f"logs/operations/{op}/journal.json"
    with WriterLock(ctx.root):
        journal = ctx.read(journal_ref) if ctx.path(journal_ref).exists() else None
        if action == "inspect":
            if not journal:
                raise Blocked("operation has no transaction journal")
            return {"journal_ref": journal_ref, "transaction_status": journal["status"], "entries": [{"path": row["path"], "old_digest": row["old_digest"], "final_digest": row["new_digest"], "current_digest": current_digest(ctx, row["path"])} for row in journal["entries"]], "phase": "inspected"}
        if journal and journal["status"] == "committed":
            if action == "rollback":
                raise Blocked("committed transactions require a new reviewed change, not rollback")
            if request.get("view_ref", journal["view_ref"]) != journal["view_ref"] or request.get("proof_ref", journal["proof_ref"]) != journal["proof_ref"]:
                raise Invalid("operation ID already committed another request")
            result = ctx.read(journal["result_ref"])
            return {"apply_result_ref": journal["result_ref"], "apply_result_digest": result["digest"], "transaction_status": "committed", "phase": "committed"}
        if journal and journal["status"] == "rolled_back":
            if action == "rollback":
                return {"journal_ref": journal_ref, "transaction_status": "rolled_back", "phase": "rolled_back"}
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
                    current = current_digest(ctx, row["path"])
                    if current == row["old_digest"]:
                        continue
                    if current != row["new_digest"]:
                        raise Blocked("external edit preserved during rollback: " + row["path"])
                    target = ctx.path(row["path"])
                    if row["old_digest"] is None:
                        target.unlink()
                        sync_directory(target.parent)
                    else:
                        atomic_bytes(target, ctx.path(row["backup_ref"]).read_bytes())
                journal["status"] = "rolled_back"
                save_journal(ctx, journal)
                return {"journal_ref": journal_ref, "transaction_status": "rolled_back", "phase": "rolled_back"}
            request = {"operation_id": op, "view_ref": journal["view_ref"], "proof_ref": journal["proof_ref"]}
            view = checked_view(ctx, request)
            proof = validate_proof(ctx, request, view)
            if view["digest"] != journal["view_digest"] or proof["digest"] != journal["proof_digest"]:
                raise Invalid("recovery inputs changed")
            validate_final_cards(ctx, view)
            return mutate(ctx, journal)
        if journal:
            raise Blocked("interrupted operation requires explicit resume or rollback")
        view = checked_view(ctx, request)
        proof = validate_proof(ctx, request, view)
        if view.get("baseline_digest", baseline(view)) != baseline(view):
            raise Invalid("complete write-set baseline digest mismatch")
        validate_final_cards(ctx, view)
        rows = view["writes"] + view.get("deletes", [])
        for row in rows:
            if current_digest(ctx, row["path"]) != row["expected_old_digest"]:
                raise Blocked("complete write-set CAS conflict: " + row["path"])
        fault = request.get("fault_after")
        if fault is not None and (not isinstance(fault, int) or isinstance(fault, bool) or fault < 1 or not fixture_fault_allowed(ctx)):
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
            entries.append({"path": row["path"], "old_digest": old, "new_digest": row.get("final_digest"), "bytes_b64": row.get("bytes_b64"), "backup_ref": backup_ref, "installed": False})
        # Recheck all files after durable backups, before the prepared journal.
        for row in rows:
            if current_digest(ctx, row["path"]) != row["expected_old_digest"]:
                raise Blocked("write set changed while preparing transaction")
        journal = ctx.record("transaction_journal", op, status="prepared", view_ref=request["view_ref"], view_digest=view["digest"], proof_ref=request["proof_ref"], proof_digest=proof["digest"], verification_tier=proof.get("verification_tier", "code_gate"), entries=entries)
        save_journal(ctx, journal)
        return mutate(ctx, journal, fault)
