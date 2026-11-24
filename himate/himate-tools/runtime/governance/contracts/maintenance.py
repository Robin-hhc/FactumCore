"""Prepare and publish a fixed set of existing-card reference repairs.

The workflow supplies independent content judgement. CLI task inputs are fixed
in the local catalog so editing the author-facing task cannot expand its scope.
"""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from .catalog import Catalog, atomic_write
from .validation import ContractError, canonical_bytes, safe_path
from . import ingest, source_resources


CHECK = ".build/maintenance-review-check.json"


def _location_candidates(root, source, cards, previous, current):
    """Offer uniquely resolved positions, never a semantic unchanged verdict."""
    if previous is None or current is None or source["kind"] != "code":
        return []
    from .code_symbols import resolve
    result = []
    for card in cards:
        metadata = card["metadata"]
        for reference in metadata.get("code_ref", []):
            if reference["code_id"] != source["id"]:
                continue
            selector = reference.get("selector") or ({"kind": "function", "name": reference["symbol"]}
                                                      if reference.get("symbol") else None)
            if selector is None:
                continue
            try:
                old = ingest._reference_check(root, source, reference, previous, extractor=ingest.code_extractor(source))
                new = resolve(current, selector, path=source["path"], extractor=ingest.code_extractor(source))
                if old is None or new["status"] != "resolved" or old["range"] == new["range"]:
                    continue
                old_text = source_resources.extract_code_text(previous, ingest.code_extractor(source))[0].splitlines()
                new_text = source_resources.extract_code_text(current, ingest.code_extractor(source))[0].splitlines()
                old_range, new_range = old["range"], new["range"]
                old_fragment = "\n".join(old_text[old_range["start_line"] - 1:old_range["end_line"]])
                new_fragment = "\n".join(new_text[new_range["start_line"] - 1:new_range["end_line"]])
                result.append({"card_id": card["id"], "path": card["path"], "old_reference": reference,
                               "proposed_reference": {**reference, "line_start": new_range["start_line"],
                                                      "line_end": new_range["end_line"]},
                               "previous_source_sha256": ingest.sha(previous), "current_source_sha256": ingest.sha(current),
                               "same_fragment": old_fragment == new_fragment, "requires_context_review": True})
            except (ContractError, ValueError, UnicodeError):
                continue
    return result


def required(task, catalog):
    source = catalog.get_file(task.get("source", {}).get("source_id"))
    return (catalog.maintenance_input() is not None or source is not None
            and (source["kind"] == "code" or task.get("source", {}).get("exists") is False))


def prepare(root, request, *, catalog=None):
    root = Path(root)
    if set(request) != {"source"} or not isinstance(request["source"], str) or not request["source"]:
        raise ContractError("MAINTENANCE_SOURCE_REQUIRED", "Select one registered source with --source")
    with (nullcontext(catalog) if catalog is not None else Catalog(root)) as active:
        source = active.get_file(request["source"])
        if source is None:
            matches = [row for row in active.list_files() if row["path"] == request["source"]]
            source = matches[0] if len(matches) == 1 else None
        if source is None:
            raise ContractError("MAINTENANCE_SOURCE_REQUIRED", "Select one registered source ID or exact path")
        if source["kind"] != "code" and ingest.source_path(root, source).exists():
            raise ContractError("DOCUMENT_INGEST_REQUIRED", "Existing documents use ingest scan")
        pending = ingest.observe(root, active, source["id"], code_review=source["kind"] == "code",
                                 include_code=True, first=True, keep_content=True)
        if not pending:
            return {"pending": 0, "task_type": "card_maintenance"}, "unchanged"
        selected = pending[0]
        cards = active.cards_for(source["id"])
        ingest._clear_build(root)
        active.touch_attempt(source["id"])
        material = safe_path(root, ".build/materials")
        material.mkdir()
        (root / ".build/cards").mkdir()
        fixed = {key: value for key, value in selected.items() if key != "content"}
        fixed.update(source_id=source["id"], **{"code_id" if source["kind"] == "code" else "doc_id": source["id"]})
        fixed["source_commit"] = (ingest.source_commit(ingest.source_path(root, source), selected["content"])
                                  if selected["content"] is not None else None)
        gaps = []
        if selected["content"] is not None:
            original = material / ("current" + Path(source["path"]).suffix)
            original.write_bytes(selected["content"])
            fixed["original_ref"] = original.relative_to(root).as_posix()
            try:
                text, _ = source_resources.extract_code_text(selected["content"], ingest.code_extractor(source))
                text_file = material / ("code-text.txt" if original.suffix == ".txt" else "current.txt")
                text_file.write_bytes(text.encode("utf-8"))
                fixed["text_ref"] = text_file.relative_to(root).as_posix()
            except (UnicodeError, ContractError) as error:
                gaps.append({"code": getattr(error, "code", "SOURCE_ENCODING"), "message": str(error)})
        previous = None
        reviewed = source.get("reference_review", {})
        previous_hash = reviewed.get("source_sha256") or reviewed.get("last_present_sha256") or source.get("processed_hash")
        if previous_hash:
            try:
                previous, revision = ingest.old_source(root, source, expected_hash=previous_hash)
                previous_file = material / ("previous" + Path(source["path"]).suffix)
                previous_file.write_bytes(previous)
                fixed["previous_ref"] = previous_file.relative_to(root).as_posix()
                fixed["previous_sha256"] = ingest.sha(previous)
                fixed["previous_commit"] = revision
                fixed["previous_basis"] = "reference_review" if source.get("reference_review") else "legacy_processed_version"
                if source["kind"] == "code":
                    text, _ = source_resources.extract_code_text(previous, ingest.code_extractor(source))
                    (material / "previous-code-text.txt").write_bytes(text.encode("utf-8"))
                    fixed["previous_text_ref"] = ".build/materials/previous-code-text.txt"
            except (OSError, ContractError, UnicodeError, subprocess.TimeoutExpired) as error:
                fixed["history_gap"] = {"code": getattr(error, "code", "OLD_SOURCE_UNAVAILABLE"), "message": str(error)}
        frozen_cards = []
        for card in cards:
            reference = ".build/materials/cards/" + ingest.sha(card["id"].encode("utf-8")) + ".md"
            path = safe_path(root, reference, [".build/materials"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(card["raw"])
            frozen_cards.append({"id": card["id"], "path": card["path"], "title": card["title"],
                                 "sha256": ingest.sha(card["raw"]), "original_ref": reference})
        task = {"task_type": "card_maintenance", "maintenance_id": uuid4().hex,
                "source": fixed, "affected_cards": frozen_cards, "cards_dir": ".build/cards",
                "plan_ref": ".build/plan.md", "gaps": gaps}
        locations = _location_candidates(root, source, cards, previous, selected["content"])
        if locations:
            task["location_candidates_ref"] = ".build/materials/location-candidates.json"
            ingest.write_json(root / task["location_candidates_ref"], {"candidates": locations})
        references = [fixed[key] for key in ("original_ref", "text_ref", "previous_ref", "previous_text_ref")
                      if fixed.get(key)]
        references.extend(card["original_ref"] for card in frozen_cards)
        if task.get("location_candidates_ref"):
            references.append(task["location_candidates_ref"])
        task["material_hashes"] = {
            reference: ingest.sha(safe_path(root, reference, [".build/materials"]).read_bytes())
            for reference in references
        }
        # The caller-facing affected_cards is only a reading aid. This copy is
        # derived from formal refs and is used again before check/publication.
        active.set_maintenance_input(task)
        ingest.write_json(root / ".build/task.json", task)
        result = {**task, "task_ref": ".build/task.json", "pending_at_least": 1}
        return result, "blocked" if gaps else "prepared"


def state(root, catalog, task, drafts=(), deletes=()):
    fixed = catalog.maintenance_input()
    if fixed is None or task.get("maintenance_id") != fixed["maintenance_id"]:
        raise ContractError("MAINTENANCE_TASK_CHANGED", "Run maintain prepare again for a fixed maintenance task")
    if task.get("affected_cards") != fixed["affected_cards"]:
        raise ContractError("MAINTENANCE_SCOPE", "Keep the prepared card scope and original-card material pointers")
    source = ingest._task_source(catalog, task)
    baseline = fixed["source"]
    if any(source.get(key) != baseline.get(key) for key in ("source_id", "kind", "path", "hash", "exists")):
        raise ContractError("MAINTENANCE_TASK_CHANGED", "Maintenance source differs from the prepared input")
    for key in ("original_ref", "text_ref", "previous_ref", "previous_text_ref"):
        if source.get(key) != baseline.get(key):
            raise ContractError("MAINTENANCE_MATERIAL_CHANGED", "Maintenance material pointer differs from the prepared input", key)
    if task.get("location_candidates_ref") != fixed.get("location_candidates_ref"):
        raise ContractError("MAINTENANCE_MATERIAL_CHANGED", "Location material pointer differs from the prepared input")
    material_hashes = fixed.get("material_hashes")
    if not isinstance(material_hashes, dict):
        raise ContractError("MAINTENANCE_TASK_CHANGED", "Prepare the maintenance materials again with this CLI version")
    for reference, expected in material_hashes.items():
        if ingest.sha(safe_path(root, reference, [".build/materials"]).read_bytes()) != expected:
            raise ContractError("MAINTENANCE_MATERIAL_CHANGED", "A prepared maintenance material changed", reference)
    source = ingest._task_source(catalog, fixed)
    try:
        content = ingest.source_path(root, source).read_bytes()
    except FileNotFoundError:
        content = None
    if (content is not None) != source["exists"] or (ingest.sha(content) if content is not None else None) != source["hash"]:
        raise ContractError("SOURCE_CHANGED", "Prepare maintenance again for the current source version")
    approved = {item["id"]: item for item in fixed["affected_cards"]}
    replacements = {card["id"]: card for card in drafts}
    current_ids = {identity for identity, _ in catalog.reference_rows(source["id"])}
    if deletes:
        raise ContractError("MAINTENANCE_SCOPE", "Maintenance cannot physically delete existing cards")
    for card in drafts:
        original = approved.get(card["id"])
        actual = catalog.get_card(card["id"])
        if (original is None or actual is None or original["path"] != card["path"]
                or actual["path"] != original["path"]
                or card["id"] not in current_ids and actual["raw"] != card["raw"]):
            raise ContractError("MAINTENANCE_SCOPE", "Update only the prepared associated cards at their original paths", card["path"])
    for identity, original in approved.items():
        if ingest.sha(safe_path(root, original["original_ref"], [".build/materials"]).read_bytes()) != original["sha256"]:
            raise ContractError("MAINTENANCE_MATERIAL_CHANGED", "A prepared original card copy changed", original["path"])
        actual = catalog.get_card(identity)
        if actual is None or actual["path"] != original["path"]:
            raise ContractError("MAINTENANCE_CARD_CHANGED", "A prepared card was removed or moved", original["path"])
        if ingest.sha(actual["raw"]) != original["sha256"]:
            candidate = replacements.get(identity)
            if candidate is None or actual["raw"] != candidate["raw"]:
                raise ContractError("MAINTENANCE_CARD_CHANGED", "A prepared card changed; prepare again before overwriting", original["path"])
    if current_ids - set(approved):
        raise ContractError("MAINTENANCE_CARD_CHANGED", "New associated cards require a new maintenance task")
    return fixed, source, content


def findings(root, catalog, task, drafts, deletes):
    try:
        fixed, source, content = state(root, catalog, task, drafts, deletes)
    except (ContractError, OSError, ValueError) as error:
        return [ingest._finding(error)]
    replacements = {card["id"]: card for card in drafts}
    references = []
    kind = "code" if source["kind"] == "code" else "doc"
    for item in fixed["affected_cards"]:
        card = replacements.get(item["id"]) or catalog.get_card(item["id"])
        references.extend((card["id"], reference) for reference in card[kind + "_ref"]
                          if reference[kind + "_id"] == source["id"])
    context = {"formal": False, "loaded": {}, "legacy": {}, "data": {}, "descriptors": {}}
    problems = []
    for identity, reference in references:
        try:
            ingest._card_reference_check(root, source, reference, kind, catalog.registry, context, content)
        except (ValueError, OSError, ContractError, subprocess.TimeoutExpired) as error:
            problems.append(ingest._finding(error, catalog.get_card(identity)["path"]))
    return problems


def digest(root, fixed, drafts, deletes):
    return ingest.sha(canonical_bytes({
        "input": fixed, "plan_sha256": ingest.sha(safe_path(root, ".build/plan.md").read_bytes()),
        "cards": sorted((card["id"], card["path"], ingest.sha(card["raw"])) for card in drafts),
        "deleted": sorted(deletes),
    }))


def check(root, request, rules=None):
    if request:
        raise ContractError("INVALID_INPUT", "Maintenance check uses the prepared task")
    task = ingest.read_json(safe_path(root, ".build/task.json"))
    with Catalog(root) as catalog:
        if not required(task, catalog):
            raise ContractError("MAINTENANCE_TASK_REQUIRED", "Run maintain prepare first")
    return ingest.check(root, {}, rules)


def commit(root, request):
    if set(request) - {"reason", "defer"}:
        raise ContractError("INVALID_INPUT", "Maintenance commit accepts reason or defer")
    root = Path(root)
    task = ingest.read_json(safe_path(root, ".build/task.json"))
    with Catalog(root, refresh=True, rollback_registry=True) as catalog:
        drafts = ingest._drafts(root, catalog)
        deletes = ingest._deletes(root)
        fixed, source, content = state(root, catalog, task, drafts, deletes)
        if request.get("defer"):
            return {"source_id": source["source_id"], "reason": request.get("reason", "Necessary evidence is missing")}, "deferred"
        problems = findings(root, catalog, task, drafts, deletes)
        if problems:
            first = problems[0]
            raise ContractError(first["code"], first["message"], first.get("path", ""))
        marker = safe_path(root, CHECK, [".build"])
        checked = ingest.read_json(marker) if marker.is_file() else {}
        if checked.get("sha256") != digest(root, fixed, drafts, deletes):
            raise ContractError("MAINTENANCE_NOT_CHECKED", "Run maintain check for the current plan and candidates")
        if not drafts and not request.get("reason"):
            raise ContractError("NO_CHANGE_REASON_REQUIRED", "Explain the reviewed zero-change result")
        for card in drafts:
            destination = safe_path(root, card["path"], ["knowledge"])
            atomic_write(destination, card["raw"])
        catalog.refresh()
        from .library import build_search
        build_search(catalog, panel_sources={})
        catalog.mark_reference_reviewed(source["id"], source["hash"], source["exists"],
                                        source_commit=source.get("source_commit"))
        result = {"source_id": source["source_id"], "source_kind": source["kind"],
                  "source_exists": source["exists"], "reviewed_hash": source["hash"],
                  "reviewed_card_ids": [item["id"] for item in fixed["affected_cards"]],
                  "card_ids": [card["id"] for card in drafts], "maintenance_complete": True,
                  "reason": request.get("reason", "Reviewed existing-card repairs published")}
        catalog.set_maintenance_input(None)
    receipt_ref = "artifacts/maintenance/latest.json"
    try:
        atomic_write(safe_path(root, receipt_ref), (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    except OSError as error:
        result["receipt_warning"] = {"code": "MAINTENANCE_RECEIPT_WRITE_FAILED", "message": str(error), "path": receipt_ref}
    try:
        ingest._clear_build(root, remove_empty=True)
    except OSError as error:
        result["cleanup_error"] = str(error)
    return result, "completed"
