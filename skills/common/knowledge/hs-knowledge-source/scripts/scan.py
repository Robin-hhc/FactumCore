"""File observations only; semantic decisions belong to the reading Agent."""

import os
import stat
from pathlib import PurePosixPath

from support import NodeError, fixed_bytes, load_yaml, safe, sha

RAW_DIRS = tuple(
    "docs-raw/" + name
    for name in ("conventions", "chips", "storys", "specs", "protocols", "troubleshooting")
)
IGNORED = {"AGENTS.md", ".gitkeep"}
FINISHED = {"completed", "skipped", "withdrawn"}


def progress_status(disposition):
    value = disposition["progress"]
    return value.get("status") if isinstance(value, dict) else value


def record_applied(record):
    stage = record.get("progress", {}).get("apply", {})
    expected = "recorded" if record.get("batch_kind") == "record_only" else "applied"
    return record.get("status") == expected and stage.get("status") == expected and stage.get("operation_id") == record.get("operation_id")


def selected(path, scope):
    return any(path == ref or path.startswith(ref + "/") for ref in scope)


def scopes(request):
    source = request.get("source")
    if source is None:
        return list(RAW_DIRS), True
    parts = PurePosixPath(source).parts if isinstance(source, str) else ()
    if not parts or "\\" in source or ":" in source or ".." in parts or source.startswith("/"):
        raise NodeError("RAW_SCOPE_REQUIRED", "Expected a relative supported raw path", source)
    ref = "/".join(parts)
    if not any(ref == raw or ref.startswith(raw + "/") for raw in RAW_DIRS):
        raise NodeError("RAW_SCOPE_REQUIRED", "Expected a supported landed raw directory or file", source)
    return [ref], False


def histories(context):
    directory = safe(context.root, "logs/ingest")
    refs = list(context.request.get("prior_record_refs", []))
    if directory.exists():
        refs += ["logs/ingest/" + p.name for p in sorted(directory.iterdir()) if p.suffix in (".yaml", ".yml", ".json")]
    result = []
    for ref in sorted(set(refs)):
        if not ref.startswith("logs/ingest/"):
            raise NodeError("RECORD_SCOPE_REQUIRED", "Only formal processing records can form scan history", ref)
        record = load_yaml(fixed_bytes(context.root, ref, ["logs/ingest"]))
        context.modules["records"].verify(record)
        context.modules["records"].validate_ingest_record(record)
        result.append(record)
    superseded = {d for r in result for d in r.get("prior_record_digests", [])}
    return result, [r for r in result if r["digest"] not in superseded]


def previous_units(records):
    values = {}
    parents = {r["digest"]: set(r.get("prior_record_digests", [])) for r in records}

    def ancestors(identity):
        result, pending = set(), list(parents.get(identity, []))
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            pending.extend(parents.get(current, []))
        return result

    for record in records:
        units = {u["unit_id"]: u for u in record["inventory"]["units"]}
        for disposition in record["dispositions"]:
            unit = units[disposition["unit_id"]]
            values.setdefault(unit["path"], []).append((unit, disposition, record))
    # A narrow later scan supersedes only the paths it actually covered. Keep
    # earlier observations outside that scope, even if the batch is its ancestor.
    return {path: [entry for entry in entries if not any(entry[2]["digest"] in ancestors(other[2]["digest"]) for other in entries)]
            for path, entries in values.items()}


def observe(context, scope):
    found, errors, complete = {}, {}, True
    for ref in scope:
        try:
            path = safe(context.root, ref)
            if not path.exists():
                continue
            if path.is_file():
                candidates = [(ref, path)]
            else:
                candidates = []

                def failed(error):
                    nonlocal complete
                    complete = False
                    errors[ref] = type(error).__name__

                for parent, dirs, files in os.walk(path, followlinks=False, onerror=failed):
                    for name in list(dirs):
                        child = safe(context.root, ref) / PurePosixPath(os.path.relpath(parent, path)) / name
                        if child.is_symlink() or (
                            os.path.lexists(child)
                            and getattr(child.lstat(), "st_file_attributes", 0)
                            & stat.FILE_ATTRIBUTE_REPARSE_POINT
                        ):
                            dirs.remove(name)
                            complete = False
                            errors[(PurePosixPath(ref) / PurePosixPath(os.path.relpath(child, path).replace("\\", "/"))).as_posix()] = "LINKED_PATH"
                    for name in files:
                        relative = os.path.relpath(os.path.join(parent, name), path).replace("\\", "/")
                        candidates.append(((PurePosixPath(ref) / relative).as_posix(), None))
            for item, _ in candidates:
                if PurePosixPath(item).name in IGNORED:
                    continue
                try:
                    found[item] = sha(fixed_bytes(context.root, item, ["docs-raw"]))
                except (OSError, NodeError) as exc:
                    complete = False
                    errors[item] = getattr(exc, "code", type(exc).__name__)
        except (OSError, NodeError) as exc:
            complete = False
            errors[ref] = getattr(exc, "code", type(exc).__name__)
    return found, errors, complete


def scan(context):
    scope, full_scan = scopes(context.request)
    inspection = context.modules["runtime"].fork_context(
        context, request={"operation_id": context.operation}, action="inspect-context")
    current_context, _ = context.modules["maintenance"].inspect_context(inspection)
    records, leaves = histories(context)
    previous = previous_units(records)
    if context.request.get("source") is not None and not safe(context.root, scope[0]).exists() and not any(
            selected(path, scope) for path in previous):
        raise NodeError("RAW_SCOPE_NOT_FOUND", "Explicit raw scope does not exist and has no registered deletion history", scope[0])
    found, errors, complete = observe(context, scope)
    lock = context.modules["source_resources"].read_source_lock(context.root)
    identities = {r["path"]: r["source_id"] for r in lock["resources"] if r.get("path")}
    affected_cards = {item["card_id"] for item in current_context.get("affected_claims", [])}
    affected_sources = set()
    if affected_cards:
        for card in context.modules["source_materials"].domain_cards(context):
            if card["metadata"]["id"] in affected_cards:
                affected_sources.update(s["source_id"] for s in card["metadata"]["sources"])
    paths = set(found) | set(errors)
    paths.update(path for path in previous if selected(path, scope))
    units = []
    for path in sorted(paths):
        prior = previous.get(path, [])
        prior_fingerprints = {u.get("observed_fingerprint") for u, _, _ in prior}
        prior_ids = {u["source_id"] for u, _, _ in prior}
        fingerprint = found.get(path)
        old = next(iter(prior_fingerprints)) if len(prior_fingerprints) == 1 else None
        source_id = identities.get(path) or (next(iter(prior_ids)) if len(prior_ids) == 1 else "raw:" + sha(path.encode())[:32])
        finished = bool(prior) and all(progress_status(d) in FINISHED and record_applied(r) and r.get("rules_digest") == context.args.rules_digest for _, d, r in prior)
        ambiguous = len(prior_fingerprints) > 1 or len(prior_ids) > 1 or (bool(prior_ids) and source_id not in prior_ids)
        progress = "completed" if finished and not ambiguous else None
        prior_progress = {progress_status(d) for _, d, _ in prior}
        if not ambiguous and len(prior_progress) == 1:
            status = next(iter(prior_progress))
            if status not in FINISHED:
                progress = status
        if path in errors:
            change = "read_failed"
        elif fingerprint is None:
            change = "missing" if complete and prior else "unfinished"
        elif prior and old is not None and fingerprint != old and not ambiguous:
            change = "changed"
        elif ambiguous or (prior and fingerprint == old and (not finished or source_id in affected_sources)):
            change = "unfinished"
        elif not prior:
            change = "new"
        elif fingerprint != old:
            change = "changed"
        else:
            change = "unchanged"
        units.append({"unit_id": "raw-" + sha(path.encode())[:24], "path": path, "source_id": source_id,
                      "observed_fingerprint": fingerprint, "previous_fingerprint": old,
                      "change": change, "read_error": errors.get(path), "progress": progress})
    manifest = context.seal({"scope": scope, "full_scan": full_scan, "complete": complete, "units": units,
                             "current_context": current_context,
                             "prior_record_digests": sorted(r["digest"] for r in leaves)}, "source_inventory")
    context.modules["records"].validate_scan_manifest(manifest, context.rules)
    ref = context.base + "/source-inventory.json"
    context.save(ref, manifest)
    return {"scan_ref": ref, "scan_digest": manifest["digest"], "complete": complete,
            "affected_claims": current_context.get("affected_claims", []), "context_gaps": current_context.get("gaps", []),
            "finalization_pending": [],
            "historical_finalization_unknown": [],
            "execution_history": {"status": "not_inspected"},
            "actionable_unit_ids": [u["unit_id"] for u in units if u["change"] != "unchanged"],
            "unchanged_unit_ids": [u["unit_id"] for u in units if u["change"] == "unchanged"]}, "scanned"
