"""Observe exact business inputs; no workflow credentials or sibling execution.

The prewrite observation belongs to the old formal tree.  A consumer building an
index after application must capture its own postwrite observation instead of
comparing the old formal tree with the files it has just installed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath

from .runtime import NodeError, fixed_bytes, native_path, safe


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    native = Path(native_path(path))
    raw = native.read_bytes()
    if native.read_bytes() != raw:
        raise NodeError("INPUT_CHANGED", "Bound file changed while reading", str(path))
    return raw


def _expected(ctx):
    return getattr(ctx.args, "rules_digest", None) or _sha(
        fixed_bytes(ctx.root, "governance/framework.lock.yaml"))


def _formal(ctx):
    files = {}
    for prefix, suffixes in (("knowledge", {".md"}),
                             ("logs/ingest", {".yaml", ".yml", ".json"}),
                             ("logs/events", {".yaml", ".yml", ".json"})):
        root = safe(ctx.root, prefix)
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in suffixes:
                    ref = path.relative_to(ctx.root).as_posix()
                    raw = fixed_bytes(ctx.root, ref, [prefix])
                    files[ref] = {"sha256": _sha(raw), "bytes": len(raw)}
    lock = safe(ctx.root, "governance/sources.lock.yaml")
    raw = fixed_bytes(ctx.root, "governance/sources.lock.yaml") if lock.exists() else None
    files["governance/sources.lock.yaml"] = (
        {"sha256": _sha(raw), "bytes": len(raw)} if raw is not None else None)
    return files


def _configuration(ctx):
    validation = ctx.modules["validation"]
    try:
        path = Path(validation.workspace_config_path(ctx.root)).resolve(strict=True)
    except (OSError, ValueError):
        return None, None
    raw = _read(path)
    config = validation.normalize_workspace(validation.load_yaml(raw), path.parent)
    return path, config


def _path(ctx, reference, *, current=False, explicit_external=()):
    if not isinstance(reference, str) or not reference:
        raise NodeError("INVALID_INPUT_SNAPSHOT", "A bound file needs an explicit path")
    path = Path(reference)
    if not path.is_absolute():
        return safe(ctx.root, reference), reference
    root = Path(ctx.root).resolve(strict=True)
    absolute = path.absolute()
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError:
        relative = None
    if relative is not None:
        return safe(root, relative), relative
    # Explicit historical objects supplied by the calling job remain explicit
    # inputs.  Paths merely encountered in source prose never enter this list.
    if str(absolute) in explicit_external:
        if absolute.is_symlink() or absolute.resolve() != absolute:
            raise NodeError("UNSAFE_PATH", "Historical input cannot be a path alias", reference)
        return absolute, str(absolute)
    if not current:
        raise NodeError("UNSAFE_PATH", "Retained input must be inside the knowledge root", reference)
    config_path, config = _configuration(ctx)
    if config_path is not None and absolute == config_path:
        return absolute, str(absolute)
    if config_path is not None and absolute == config_path.parent / "AGENTS.md":
        # The actual project entry is a fixed input, not workspace-wide access.
        entry = ctx.modules["validation"].safe_path(config_path.parent, absolute.name)
        if entry.is_symlink() or entry.resolve() != absolute:
            raise NodeError("UNSAFE_PATH", "Project entry cannot be a path alias", reference)
        return entry, str(absolute)
    if config is not None:
        validation = ctx.modules["validation"]
        for repo in config.get("repos", []):
            repo_root = Path(repo["root"])
            repo_root = repo_root if repo_root.is_absolute() else config_path.parent / repo_root
            repo_root = repo_root.resolve(strict=True)
            try:
                relative = absolute.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if not validation.workspace_file_allowed(config, repo["repo_id"], relative):
                continue
            return validation.safe_path(repo_root, relative), str(absolute)
    raise NodeError("UNSAFE_PATH", "Current input is outside actual configured modules", reference)


def _file(ctx, entry, *, current=False, explicit_external=()):
    if isinstance(entry, str):
        entry = {"path": entry}
    if not isinstance(entry, dict):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "A bound file must be a path or object")
    reference = entry.get("path", entry.get("ref"))
    if entry.get("kind") == "external_raw" or _dbox_path(reference):
        if not current or entry.get("kind") != "external_raw":
            raise NodeError("INVALID_INPUT_SNAPSHOT", "External current input requires its directory binding", reference)
        _external_entry(reference, entry)
        observed = ctx.modules["source_resources"].read_dbox(
            ctx.root, reference, expected_binding=entry["dbox_binding"])
        actual = {"kind": "external_raw", "path": reference,
                  "sha256": observed["sha256"], "bytes": observed["bytes"],
                  "dbox_binding": copy.deepcopy(observed["dbox_binding"])}
        if actual != entry:
            raise NodeError("INPUT_CHANGED", "External input differs from its original observation", reference)
        return reference, actual
    path, key = _path(ctx, reference, current=current, explicit_external=explicit_external)
    before = _read(path)
    actual = {"kind": "file", "path": key, "sha256": _sha(before), "bytes": len(before)}
    expected = entry.get("sha256", entry.get("digest"))
    if expected is not None and expected != actual["sha256"]:
        raise NodeError("INPUT_CHANGED", "Bound input no longer has its observed bytes", key)
    if entry.get("bytes") is not None and entry["bytes"] != len(before):
        raise NodeError("INPUT_CHANGED", "Bound input size differs", key)
    return key, actual


def _dbox_path(reference):
    return isinstance(reference, str) and reference.startswith("docs-raw/sources/dbox/")


def _hex_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_execution_scope(scope):
    """Validate the public logical file set, never a producer's local mapping."""
    if not isinstance(scope, list):
        raise NodeError("INVALID_PUBLICATION", "External execution scope must be a list")
    paths = []
    for row in scope:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise NodeError("INVALID_PUBLICATION", "External execution scope has invalid fields")
        path = row["path"]
        if (not _dbox_path(path) or "\\" in path or ":" in path
                or str(PurePosixPath(path)) != path or ".." in PurePosixPath(path).parts
                or not _hex_digest(row["sha256"]) or type(row["bytes"]) is not int or row["bytes"] < 0):
            raise NodeError("INVALID_PUBLICATION", "External execution scope has an invalid logical file")
        paths.append(path)
    if paths != sorted(set(paths)):
        raise NodeError("INVALID_PUBLICATION", "External execution scope must be sorted and unique")
    return scope


def _external_entry(path, entry):
    if (not isinstance(entry, dict) or set(entry) != {"kind", "path", "sha256", "bytes", "dbox_binding"}
            or entry.get("kind") != "external_raw" or entry.get("path") != path):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "External current input has invalid fields", path)
    validate_execution_scope([{key: entry[key] for key in ("path", "sha256", "bytes")}])
    binding = entry["dbox_binding"]
    if (not isinstance(binding, dict) or set(binding) != {"config_sha256", "root_token"}
            or any(not _hex_digest(value) for value in binding.values())):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "External current input has no valid directory binding", path)


def source_execution_files(snapshot):
    """The exact current dbox inputs retained only in this batch's local state."""
    result = {}
    current = (snapshot or {}).get("current_files", {})
    if not isinstance(current, dict):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Current input files must be a mapping")
    for path, entry in current.items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            raise NodeError("INVALID_INPUT_SNAPSHOT", "Current input entry is invalid")
        if entry.get("kind") == "external_raw" or _dbox_path(path):
            _external_entry(path, entry)
            result[path] = copy.deepcopy(entry)
    return result


def execution_scope(files):
    scope = []
    for path, entry in sorted(files.items()):
        _external_entry(path, entry)
        scope.append({key: entry[key] for key in ("path", "sha256", "bytes")})
    return validate_execution_scope(scope)


def execution_inputs(ctx, snapshot, files, scope):
    """Restore local guards without changing the publication's portable inputs."""
    validate_execution_scope(scope)
    if not isinstance(files, dict) or execution_scope(files) != scope:
        raise NodeError("EXECUTION_INPUTS_UNAVAILABLE", "Original external input bindings are missing or different")
    result = copy.deepcopy(snapshot)
    for path, entry in files.items():
        prior = result["current_files"].get(path)
        if prior is not None and prior != entry:
            raise NodeError("BATCH_INPUT_CHANGED", "External execution input was replaced", path)
        result["current_files"][path] = copy.deepcopy(entry)
    result["snapshot_digest"] = _digest({key: value for key, value in result.items() if key != "snapshot_digest"})
    observed = compare_inputs(ctx, result, stage="postwrite")
    if not observed["unchanged"]:
        raise NodeError("BATCH_INPUT_CHANGED", "Original external execution inputs changed", data=observed)
    return result


def _entries(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [{"path": path, **(entry if isinstance(entry, dict) else {"sha256": entry})}
                for path, entry in value.items()]
    if isinstance(value, list):
        return value
    raise NodeError("INVALID_INPUT_SNAPSHOT", "Input file declarations must be a list or mapping")


def _legacy_current_files(ctx, bundle):
    result = []
    for resource in bundle.get("resources", []):
        snapshots = [row for row in bundle.get("snapshots", []) if row["source_id"] == resource["source_id"]]
        if len(snapshots) != 1:
            raise NodeError("CURRENT_INPUTS_REQUIRED", "Multiple source versions require explicit current_files", resource["source_id"])
        snapshot = snapshots[0]
        if resource.get("kind") in {"raw", "attachment"}:
            item = {"path": resource["path"], "sha256": snapshot["sha256"], "bytes": snapshot["bytes"]}
            if _dbox_path(resource["path"]):
                item.update(kind="external_raw", dbox_binding=copy.deepcopy(bundle.get("dbox_binding")))
            result.append(item)
        elif resource.get("kind") == "code":
            config_path, config = _configuration(ctx)
            matches = [row for row in (config or {}).get("repos", []) if row["repo_id"] == resource["repo_id"]]
            if len(matches) != 1:
                raise NodeError("CURRENT_INPUTS_REQUIRED", "Captured code needs its actual configured module", resource["source_id"])
            root = Path(matches[0]["root"])
            root = root if root.is_absolute() else config_path.parent / root
            result.append({"path": str(root / resource["path"]), "sha256": snapshot["sha256"], "bytes": snapshot["bytes"]})
    return result


def capture_inputs(ctx, *, material=None, semantic_plan=None, bundle=None, context=None,
                   check_inputs=None, stage="prewrite", references=None):
    """Capture five groups of actual inputs, not a record of earlier approvals.

    ``material.current_files`` and ``material.adopted_objects`` accept lists of
    {path, sha256, bytes?}, or path-keyed mappings.  ``references`` explicitly
    binds additional immutable business-record refs.  Private review/lint
    reports are deliberately not discovered or required.
    """
    if stage not in {"prewrite", "postwrite"}:
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Unknown input snapshot stage", stage)
    material, semantic_plan, bundle, context = (
        value or {} for value in (material, semantic_plan, bundle, context))
    check_inputs = check_inputs or {}
    snapshot = {"schema_version": "1.0", "stage": stage, "rules_digest": _expected(ctx),
                "formal_files": _formal(ctx), "business_records": {},
                "adopted_objects": {}, "current_files": {}}
    actual_rules = _sha(fixed_bytes(ctx.root, "governance/framework.lock.yaml"))
    if actual_rules != snapshot["rules_digest"]:
        raise NodeError("STALE_RULES", "Rules changed before inputs were captured")
    refs = list(references or [])
    for value in (getattr(ctx, "request", {}), material, semantic_plan, bundle):
        for key in ("scan_ref", "material_ref", "semantic_plan_ref", "bundle_ref", "context_ref"):
            if value.get(key):
                refs.append(value[key])
    for ref in sorted(set(refs)):
        record = ctx.record(ref)
        raw = fixed_bytes(ctx.root, ref, [".build/operations", ".build/project-context", "logs"])
        snapshot["business_records"][ref] = {"sha256": _sha(raw), "bytes": len(raw),
                                               "digest": record.get("digest"),
                                               "record_kind": record.get("record_kind")}
    explicit_objects = check_inputs.get("historical_card_objects", {})
    external = {str(Path(path).absolute()) for path in explicit_objects.values()
                if isinstance(path, str) and Path(path).is_absolute()}
    objects = _entries(material.get("adopted_objects"))
    for expected, path in explicit_objects.items():
        objects.append({"path": path, "sha256": expected})
    for card in material.get("candidates", []):
        if card.get("card_ref"):
            objects.append({"path": card["card_ref"], "sha256": card.get("card_digest")})
        for source in card.get("adopted_sources", card.get("sources", [])):
            if source.get("original_ref"):
                objects.append({"path": source["original_ref"],
                                "sha256": source.get("sha256", source.get("original_sha256"))})
    for entry in objects:
        key, actual = _file(ctx, entry, explicit_external=external)
        snapshot["adopted_objects"][key] = actual
    for source in bundle.get("snapshots", []):
        entries = bundle.get("staged_objects", [])
        raw = ctx.modules["source_resources"].recover_snapshot(ctx.root, source, staged_objects=entries)
        if _sha(raw) != source["sha256"] or len(raw) != source["bytes"]:
            raise NodeError("SOURCE_CHANGED", "Exact adopted source cannot be recovered", source["snapshot_id"])
        snapshot["adopted_objects"]["snapshot:" + source["snapshot_id"]] = {
            "kind": "source_snapshot", "snapshot": copy.deepcopy(source),
            **({"staged_objects": copy.deepcopy(entries)} if entries else {}),
            "sha256": source["sha256"], "bytes": source["bytes"]}
    current = (_entries(material["current_files"]) if "current_files" in material else
               _legacy_current_files(ctx, bundle)) + _entries(context.get("current_files"))
    config_path, _ = _configuration(ctx)
    if config_path is not None:
        current.append({"path": str(config_path), "sha256": context.get("config_digest")})
    for entry in current:
        key, actual = _file(ctx, entry, current=True)
        previous = snapshot["current_files"].get(key)
        if previous is not None and previous != actual:
            raise NodeError("INPUT_CHANGED", "Same current input has conflicting observations", key)
        snapshot["current_files"][key] = actual
    snapshot["snapshot_digest"] = _digest(snapshot)
    return snapshot


def published_inputs(ctx, prewrite, *, staged_objects=()):
    """Bind current inputs and retained evidence after actual formal publication.

    Producer plans, drafts and reports describe how the publication was made;
    they are not index inputs. Their adopted content is now identified by the
    publication's formal byte set. Explicit retained objects keep their exact
    bytes, with private copies mapped only to an explicitly published object.
    """
    snapshot = capture_inputs(ctx, stage="postwrite")
    execution = source_execution_files(prewrite)
    for entry in execution.values():
        _file(ctx, entry, current=True)
    snapshot["current_files"] = {key: copy.deepcopy(value) for key, value in prewrite.get("current_files", {}).items()
                                 if key not in execution}
    entries = list(staged_objects)
    for key, entry in prewrite.get("adopted_objects", {}).items():
        value = copy.deepcopy(entry)
        if value.get("kind") == "source_snapshot":
            value.pop("staged_objects", None)
            snapshot["adopted_objects"][key] = value
            continue
        reference = value.get("path", key)
        matches = [row for row in entries
                   if row["sha256"] == value["sha256"] and row["bytes"] == value["bytes"]]
        if matches:
            reference = sorted(row["final_ref"] for row in matches)[0]
            value["path"] = reference
        elif reference.startswith(".build/"):
            # Unmapped drafts are execution inputs, already checked before
            # application. Do not retain their paths in a live generation.
            continue
        snapshot["adopted_objects"][reference] = value
    snapshot["snapshot_digest"] = _digest({key: value for key, value in snapshot.items()
                                            if key != "snapshot_digest"})
    observed = compare_inputs(ctx, snapshot, stage="postwrite")
    if not observed["unchanged"]:
        raise NodeError("BATCH_INPUT_CHANGED", "Published inputs differ from adopted bytes", data=observed)
    return snapshot


def compare_inputs(ctx, snapshot, *, stage="prewrite"):
    """Observe the current inputs and return explicit changes without writing.

    Callers decide their own transition.  A changed/missing/unreadable input is
    never silently rebound.  This function neither loads another Skill nor
    checks a review identity/status.
    """
    if not isinstance(snapshot, dict) or snapshot.get("stage") != stage:
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot has the wrong stage")
    core = {key: value for key, value in snapshot.items() if key != "snapshot_digest"}
    if _digest(core) != snapshot.get("snapshot_digest"):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot digest differs")
    required = {"rules_digest", "formal_files", "business_records", "adopted_objects", "current_files"}
    if not required <= set(snapshot):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot omits a business input group")
    if (snapshot.get("schema_version") != "1.0" or stage not in {"prewrite", "postwrite"}
            or not isinstance(snapshot["rules_digest"], str)
            or any(not isinstance(snapshot[group], dict) for group in required - {"rules_digest"})):
        raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot has invalid business input groups")
    for group in required - {"rules_digest"}:
        for key, entry in snapshot[group].items():
            if not isinstance(key, str):
                raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot file keys must be paths")
            if group == "formal_files" and entry is None:
                continue
            if (not isinstance(entry, dict)
                    or not isinstance(entry.get("sha256"), str)
                    or not isinstance(entry.get("bytes"), int) or isinstance(entry.get("bytes"), bool)
                    or entry["bytes"] < 0
                    or (entry.get("kind") == "source_snapshot" and not isinstance(entry.get("snapshot"), dict))):
                raise NodeError("INVALID_INPUT_SNAPSHOT", "Input snapshot has an invalid file observation", key)
    changes = []
    try:
        actual_rules = _sha(fixed_bytes(ctx.root, "governance/framework.lock.yaml"))
        if actual_rules != snapshot["rules_digest"] or actual_rules != _expected(ctx):
            changes.append({"group": "rules_digest", "reason": "rules_changed",
                            "expected": snapshot["rules_digest"], "actual": actual_rules})
    except (OSError, ValueError) as exc:
        changes.append({"group": "rules_digest", "reason": "input_unavailable", "detail": str(exc)})
    try:
        current_formal = _formal(ctx)
        for ref in sorted(set(current_formal) | set(snapshot["formal_files"])):
            before, after = snapshot["formal_files"].get(ref), current_formal.get(ref)
            if before != after:
                changes.append({"group": "formal_files", "path": ref, "reason": "formal_changed",
                                "expected": before, "actual": after})
    except (OSError, ValueError) as exc:
        changes.append({"group": "formal_files", "reason": "input_unavailable", "detail": str(exc)})
    for group in ("business_records", "adopted_objects", "current_files"):
        for key, entry in snapshot[group].items():
            try:
                if entry.get("kind") == "source_snapshot":
                    raw = ctx.modules["source_resources"].recover_snapshot(
                        ctx.root, entry["snapshot"], staged_objects=entry.get("staged_objects"))
                elif group == "current_files" and (entry.get("kind") == "external_raw" or _dbox_path(key)):
                    _, observed = _file(ctx, entry, current=True)
                    raw = None
                else:
                    reference = entry.get("path", key)
                    # Retained external objects were explicit on capture.  Keep
                    # their exact original path; never discover new locations.
                    external = (reference,) if group == "adopted_objects" and Path(reference).is_absolute() else ()
                    path, _ = _path(ctx, reference, current=group == "current_files", explicit_external=external)
                    raw = _read(path)
                actual = ({"sha256": observed["sha256"], "bytes": observed["bytes"]}
                          if raw is None else {"sha256": _sha(raw), "bytes": len(raw)})
                expected = {"sha256": entry["sha256"], "bytes": entry["bytes"]}
                if actual != expected:
                    changes.append({"group": group, "path": key, "reason": "input_changed",
                                    "expected": expected, "actual": actual})
            except (OSError, ValueError) as exc:
                changes.append({"group": group, "path": key, "reason": "input_unavailable", "detail": str(exc)})
    return {"unchanged": not changes, "changes": changes, "stage": stage,
            "snapshot_digest": snapshot["snapshot_digest"]}
