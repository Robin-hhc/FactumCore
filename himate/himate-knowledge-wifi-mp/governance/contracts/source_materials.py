"""Prepare exact reading material from a fixed inventory or explicit targets.

This module does not scan raw roots, evaluate card quality, make authoring
decisions, or dispatch another Skill. Material versions are immutable.
"""

from __future__ import annotations

import base64
import difflib

import yaml

from .runtime import NodeError, digest, fixed_bytes, fork_context, safe, sha, write_bytes
from . import code_context, staging, source_resources


def _save_bytes(context, ref, raw):
    write_bytes(context.root, ref, raw)
    context.register_owned(ref, raw)


def _source_changed(message, paths):
    paths = sorted(set(paths))
    return NodeError(
        "SOURCE_CHANGED", message, paths[0] if paths else "", blocked=True,
        data={"needs_scan": True, "affected_scope": paths},
    )


def domain_cards(context):
    """Decode card data for discovery without repeating P4 quality checks."""
    root = safe(context.root, "knowledge")
    cards = []
    if root.exists():
        for path in sorted(root.rglob("*.md")):
            if path.name in {"AGENTS.md", "index.md"}:
                continue
            ref = path.relative_to(context.root).as_posix()
            cards.append(context.modules["knowledge"].decode_card(
                fixed_bytes(context.root, ref, ["knowledge"]), ref, context.rules,
            ))
    if len({card["metadata"]["id"] for card in cards}) != len(cards):
        raise NodeError("DUPLICATE_CARD_ID", "Reading candidates need unique card identities")
    return cards


def _merge(entries, incoming, identity):
    for entry in incoming:
        key = entry[identity]
        if key in entries and entries[key] != entry:
            raise NodeError("MATERIAL_IDENTITY_CONFLICT", "Material inputs disagree on the same identity", key)
        entries[key] = entry


def _unique_records(values, key):
    result = {}
    _merge(result, values, key)
    return list(result.values())


def _target_request(context, supplied, lock):
    if not isinstance(supplied, dict):
        raise NodeError("INVALID_SOURCE_TARGET", "Each explicit target is an object")
    if "target_id" in supplied and (not isinstance(supplied["target_id"], str) or not supplied["target_id"].strip()
                                    or any(ord(char) < 32 for char in supplied["target_id"])):
        raise NodeError("INVALID_SOURCE_TARGET", "Explicit target_id must be nonempty printable text")
    kind = supplied.get("kind", "raw")
    if kind not in {"raw", "code"}:
        raise NodeError("INVALID_SOURCE_TARGET", "Explicit target kind is raw or code")
    allowed = {"kind", "source_id", "version", "context_ref", "expected_fingerprint", "target_id"}
    allowed |= {"source_path", "attachments"} if kind == "raw" else {"repo_id", "module_path", "relative_path", "text_encoding"}
    if set(supplied) - allowed:
        raise NodeError("INVALID_SOURCE_TARGET", "Explicit target contains unsupported fields", ",".join(sorted(set(supplied) - allowed)))
    request = {key: value for key, value in supplied.items() if key not in {"target_id", "expected_fingerprint"}}
    request["kind"] = kind
    if kind == "raw":
        path = request.get("source_path")
        if source_resources.is_dbox_path(path):
            source_resources.dbox_path(context.root, path, getattr(context, "expected_dbox_binding", None))
        else:
            safe(context.root, path, ["docs-raw/" + name for name in
                 ("conventions", "chips", "storys", "specs", "protocols", "troubleshooting")])
        matches = [row["source_id"] for row in lock["resources"]
                   if row.get("path") == path and row.get("kind") in {"raw", "attachment"}]
        fallback = "raw:" + sha(path.encode())[:32]
    else:
        path = request.get("relative_path")
        if not isinstance(path, str) or not path:
            raise NodeError("INVALID_SOURCE_TARGET", "Code target requires relative_path")
        if "module_path" in request:
            _, registered, *_ = context.modules["source_operations"].authorized_repo(
                context, request.get("repo_id"), module_path=request.pop("module_path"),
            )
            request["repo_id"] = registered["repo_id"]
        matches = [row["source_id"] for row in lock["resources"]
                   if row.get("kind") == "code" and row.get("path") == path and row.get("repo_id") == request.get("repo_id")]
        fallback = "code:" + digest({"repo_id": request.get("repo_id"), "path": path})[:32]
    if "source_id" not in request:
        if len(set(matches)) > 1:
            raise NodeError("AMBIGUOUS_SOURCE_ID", "Explicit source_id is needed for this registered path", path)
        request["source_id"] = next(iter(matches), fallback)
    if "context_ref" not in request and context.request.get("context_ref"):
        request["context_ref"] = context.request["context_ref"]
    target = {"target_id": supplied.get("target_id") or "target:" + digest(request), **request}
    if supplied.get("expected_fingerprint") is not None:
        target["expected_fingerprint"] = supplied["expected_fingerprint"]
    return target


def _current_files(context, bundle):
    operations = context.modules["source_operations"]
    resources = {row["source_id"]: row for row in bundle["resources"]}
    bindings = {}
    for snapshot in bundle["snapshots"]:
        resource = resources[snapshot["source_id"]]
        if source_resources.is_dbox_path(resource.get("path")):
            _adopt_dbox_binding(context, bundle.get("dbox_binding"))
        for binding in operations.current_source_bindings(context, resource, snapshot,
                                                          expected_binding=bundle.get("dbox_binding")):
            previous = bindings.get(binding["path"])
            if previous is not None and previous != binding:
                raise NodeError("MATERIAL_IDENTITY_CONFLICT", "Current input path has conflicting fingerprints", binding["path"])
            bindings[binding["path"]] = binding
    return [bindings[key] for key in sorted(bindings)]


def _adopt_dbox_binding(context, binding):
    source_resources.validate_dbox_binding(binding)
    previous = getattr(context, "expected_dbox_binding", None)
    if previous is not None and previous != binding:
        raise NodeError("DBOX_BINDING_CHANGED", "Current materials disagree on the adopted dbox directory",
                        source_resources.DBOX_PREFIX, blocked=True,
                        data={"needs_scan": True, "affected_scope": [source_resources.DBOX_PREFIX]})
    source_resources.dbox_root(context.root, binding)
    context.expected_dbox_binding = binding


def _previous(context, previous_view=None):
    ref = context.request.get("existing_material_ref") or (previous_view or {}).get("material_ref")
    if not ref:
        return None, None
    material = context.record(ref, "artifact_manifest")
    if material.get("purpose") != "source_materials":
        raise NodeError("WRONG_MATERIAL_PURPOSE", "Supplement input must be source reading material", ref)
    if previous_view and (previous_view.get("material_ref") != ref or previous_view.get("scan_ref") != material.get("scan_ref")):
        raise NodeError("MATERIAL_INPUT_MISMATCH", "Supplement must adopt the exact previous candidate material and inventory", ref)
    if material["operation_id"] != context.operation:
        if (not previous_view or previous_view.get("material_ref") != ref
                or previous_view.get("scan_ref") != material.get("scan_ref")):
            raise NodeError("OPERATION_MISMATCH", "Adopt old material only through its exact previous candidate", ref)
        semantic_ref = previous_view.get("semantic_plan_ref")
        if semantic_ref:
            semantic = context.record(semantic_ref, "semantic_plan")
            if (semantic["digest"] != previous_view.get("semantic_plan_digest") or semantic.get("material_ref") != ref
                    or semantic.get("material_digest") != material["digest"]
                    or semantic.get("scan_ref") != material.get("scan_ref")):
                raise NodeError("MATERIAL_INPUT_MISMATCH", "Previous candidate does not adopt these exact materials", ref)
        if previous_view.get("input_snapshot"):
            compared = context.modules["input_snapshot"].compare_inputs(context, previous_view["input_snapshot"], stage="prewrite")
            if not compared["unchanged"]:
                raise _source_changed("Previously adopted candidate inputs changed", [item.get("path", "") for item in compared["changes"] if item.get("path")])
    if material.get("context_ref"):
        if context.request.get("context_ref") not in {None, material["context_ref"]}:
            raise NodeError("MATERIAL_INPUT_MISMATCH", "Supplement cannot replace its adopted context", material["context_ref"])
        adopted_context = context.record(material["context_ref"], "project_context")
        if adopted_context["digest"] != material.get("context_digest"):
            raise _source_changed("The adopted context record changed", [material["context_ref"]])
    if material.get("scan_ref"):
        original_scan = context.record(material["scan_ref"], "source_inventory")
        if original_scan["digest"] != material.get("scan_digest"):
            raise NodeError("MATERIAL_INPUT_MISMATCH", "Original inventory differs from the material binding", material["scan_ref"])
    if context.request.get("scan_ref") and context.request["scan_ref"] != material.get("scan_ref"):
        scan = context.record(context.request["scan_ref"], "source_inventory")
        if scan["digest"] != material.get("scan_digest"):
            raise NodeError("MATERIAL_INPUT_MISMATCH", "Supplement cannot replace its original fixed inventory", ref)
    for candidate in material.get("candidates", []):
        path = candidate["formal_card_ref"]
        try:
            actual = sha(fixed_bytes(context.root, path, ["knowledge"]))
        except OSError:
            actual = None
        if actual != candidate["card_digest"]:
            raise _source_changed("An adopted formal card changed; start a new operation", [path])
    # Re-resolve only adopted current inputs, including code authorization.
    old_bundle = context.modules["source_operations"].resolve_bundle(context, material["bundle_ref"])["bundle"]
    if old_bundle["digest"] != material.get("bundle_digest"):
        raise NodeError("MATERIAL_INPUT_MISMATCH", "Original bundle differs from the material binding", material["bundle_ref"])
    if material.get("dbox_binding") or old_bundle.get("dbox_binding"):
        if material.get("dbox_binding") != old_bundle.get("dbox_binding"):
            raise NodeError("MATERIAL_INPUT_MISMATCH", "Material and source bundle disagree on the dbox binding", ref)
        _adopt_dbox_binding(context, material["dbox_binding"])
    try:
        bindings = _current_files(context, old_bundle)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        if getattr(exc, "code", None) == "SOURCE_INTEGRITY_ERROR":
            raise
        paths = [row["path"] for row in material.get("current_files", [])]
        raise _source_changed("An adopted current source or its authorization is unavailable", paths) from exc
    if material.get("current_files") and bindings != material["current_files"]:
        raise _source_changed("Current source binding differs from the original material", [item["path"] for item in bindings])
    return material, old_bundle


def _candidate_material(context, candidates, snapshots, lock, gaps, staged_objects):
    old_by_id = {snapshot["snapshot_id"]: snapshot for snapshot in lock["snapshots"]}
    resources = {row["source_id"]: row for row in lock["resources"]}
    operations = context.modules["source_operations"]
    records, adopted_objects = [], []
    for candidate in candidates:
        card, identity = candidate["card"], candidate["card_id"]
        card_ref = context.base + "/material/cards/" + card["sha256"] + ".md"
        _save_bytes(context, card_ref, card["raw"])
        staged_objects.append(staging.stage_bytes(context, "logs/evidence/published/cards/" + card["sha256"] + ".md",
                                                 card["raw"], kind="card"))
        adopted_objects.append({"path": card_ref, "sha256": card["sha256"], "bytes": len(card["raw"]), "kind": "card"})
        adopted = []
        for source in card["metadata"].get("sources", []):
            item = {**source, "claim_ids": [claim["id"] for claim in card["metadata"].get("claims", [])
                                           if source["evidence_ref"] in claim.get("source_refs", [])]}
            try:
                snapshot = old_by_id.get(source["snapshot_id"])
                if snapshot is None or snapshot["source_id"] != source["source_id"] or source["source_id"] not in resources:
                    raise NodeError("SOURCE_UNAVAILABLE", "Adopted exact old snapshot is not registered", source["snapshot_id"])
                raw = operations.recovered_bytes(context, snapshot)
                if sha(raw) != snapshot["sha256"] or len(raw) != snapshot["bytes"]:
                    raise NodeError("SOURCE_INTEGRITY_ERROR", "Adopted original differs from its fixed snapshot")
                suffix = snapshot.get("format", ".bin")
                if suffix not in {".md", ".txt", ".pdf", ".docx"}:
                    suffix = ".bin"
                original_ref = context.base + "/material/originals/" + sha(raw) + suffix
                _save_bytes(context, original_ref, raw)
                staged_objects.append(staging.stage_bytes(context, "logs/evidence/published/objects/" + sha(raw) + ".bin",
                                                         raw, kind="original"))
                item.update(original_ref=original_ref, original_sha256=sha(raw), recovery=snapshot["recovery"], sha256=sha(raw), bytes=len(raw))
                adopted_objects.append({"path": original_ref, "sha256": sha(raw), "bytes": len(raw), "kind": "original"})
                try:
                    item["text"], locators, limitations = operations.snapshot_text(context, snapshot, resources[source["source_id"]], raw)
                    if snapshot.get("extraction") and item["text"] is not None:
                        extracted = item["text"].encode("utf-8")
                        locator_bytes = context.modules["validation"].canonical_bytes({"locators": locators})
                        staged_objects.extend([
                            staging.stage_bytes(context, "logs/evidence/published/extractions/" + sha(extracted) + ".txt", extracted, kind="extraction"),
                            staging.stage_bytes(context, "logs/evidence/published/locators/" + sha(locator_bytes) + ".json", locator_bytes, kind="locator"),
                        ])
                    if limitations:
                        item["limitations"] = limitations
                except (OSError, UnicodeError, NodeError, context.modules["validation"].ContractError) as exc:
                    item["text"] = None
                    item["read_gap"] = str(exc)
                    gaps.append({"card_id": identity, "snapshot_id": source["snapshot_id"], "code": "ADOPTED_EXTRACTION_UNAVAILABLE", "original_ref": original_ref, "reason": str(exc)})
                current = next((row for row in snapshots.values() if row["source_id"] == source["source_id"]), None)
                if current and item.get("text") is not None and current.get("format") in {".md", ".txt"}:
                    now = operations.recovered_bytes(context, current, staged_objects=staged_objects).decode("utf-8-sig")
                    item["diff"] = "".join(difflib.unified_diff(item["text"].splitlines(True), now.splitlines(True),
                                                               fromfile=source["snapshot_id"], tofile=current["snapshot_id"]))
            except (OSError, UnicodeError, NodeError, context.modules["validation"].ContractError) as exc:
                item["read_gap"] = str(exc)
                gaps.append({"card_id": identity, "snapshot_id": source["snapshot_id"], "code": "ADOPTED_ORIGINAL_UNAVAILABLE", "reason": str(exc)})
            adopted.append(item)
        records.append({"card_id": identity, "card_ref": card_ref, "formal_card_ref": card["path"],
                        "card_digest": card["sha256"], "lifecycle": card["metadata"].get("lifecycle"),
                        "reasons": candidate["reasons"], "adopted_sources": adopted})
    return records, _unique_records(adopted_objects, "path")


def prepare(context):
    request = context.request
    operations = context.modules["source_operations"]
    tolerate_errors = request.get("tolerate_source_errors", False)
    if not isinstance(tolerate_errors, bool):
        raise NodeError("INVALID_INPUT", "tolerate_source_errors must be a boolean")
    collect_attachments = request.get("collect_local_attachments", False)
    if not isinstance(collect_attachments, bool):
        raise NodeError("INVALID_INPUT", "collect_local_attachments must be a boolean")
    try:
        previous_view = context.modules["production"].revision_view(context, request) if request.get("previous_view_ref") else None
        previous, previous_bundle = _previous(context, previous_view)
        scan_ref = request.get("scan_ref") or (previous.get("scan_ref") if previous else None)
        scan = context.record(scan_ref, "source_inventory") if scan_ref else None
        if scan and scan.get("dbox_binding"):
            _adopt_dbox_binding(context, scan["dbox_binding"])
    except NodeError as exc:
        if exc.code == "STALE_RULES":
            raise _source_changed("Adopted rules changed; refresh inputs under a new operation", ["governance/framework.lock.yaml"]) from exc
        raise
    if request.get("unit_ids") is not None and scan is None:
        raise NodeError("SOURCE_INVENTORY_REQUIRED", "unit_ids select an explicit fixed inventory")
    if not scan and not previous and not any(key in request for key in ("targets", "code_bundle_refs", "candidate_card_ids", "topics")):
        raise NodeError("SOURCE_TARGET_REQUIRED", "Supply a fixed scan or explicit material targets")
    lock = context.modules["source_resources"].read_source_lock(context.root)
    units = scan["units"] if scan else []
    if "unit_ids" in request:
        selected = set(request["unit_ids"])
        if not selected.issubset({unit["unit_id"] for unit in units}):
            raise NodeError("UNKNOWN_SOURCE_UNIT", "Requested unit is outside the fixed inventory")
        units = [unit for unit in units if unit["unit_id"] in selected]
    else:
        units = [unit for unit in units if unit["change"] != "unchanged"]
    resources, snapshots, extractions = {}, {}, {}
    staged_objects, event_proposals = [], []
    bundles, gaps, current_code = [], [], []
    material_units = {unit["unit_id"]: unit for unit in units}
    context_refs, config_digests = set(), set()
    targets = {}
    if previous:
        bundle = previous_bundle
        staged_objects.extend(staging.entries_from_bundle(bundle))
        event_proposals.extend(bundle.get("event_proposals", []))
        for key, entries, identity in (("resources", resources, "source_id"), ("snapshots", snapshots, "snapshot_id"), ("extractions", extractions, "snapshot_id")):
            _merge(entries, bundle.get(key, []), identity)
        bundles.extend(previous.get("bundles", []))
        gaps.extend(gap for gap in previous.get("gaps", [])
                    if gap.get("code") in {"EXTRACTION_LIMITATION", "CURRENT_ORIGINAL_UNAVAILABLE"})
        current_code.extend(previous.get("current_code", []))
        targets.update((target["target_id"], target) for target in previous.get("targets", []))
        _merge(material_units, previous.get("units", []), "unit_id")
        if bundle.get("context_ref"):
            context_refs.add(bundle["context_ref"])
        if bundle.get("config_digest"):
            config_digests.add(bundle["config_digest"])
    captures = []
    for unit in units:
        if unit["change"] in {"missing", "read_failed"} or not unit.get("observed_fingerprint"):
            gaps.append({"unit_id": unit["unit_id"], "code": "CURRENT_ORIGINAL_UNAVAILABLE", "path": unit["path"]})
            continue
        captures.append(({"kind": "raw", "source_path": unit["path"], "source_id": unit["source_id"]},
                         {"unit_id": unit["unit_id"]}, unit["observed_fingerprint"]))
    for supplied in request.get("targets", []):
        target = _target_request(context, supplied, lock)
        _merge(targets, [target], "target_id")
        captures.append(({key: value for key, value in target.items() if key not in {"target_id", "expected_fingerprint"}},
                         {"target_id": target["target_id"]}, target.get("expected_fingerprint")))
    incoming = []
    for capture_request, origin, expected in captures:
        try:
            # A malformed replacement must not turn a frozen-input change into
            # an ordinary per-document debt before capture can compare hashes.
            if tolerate_errors and expected:
                if capture_request.get("kind") == "raw":
                    observed = operations.raw_member(context, capture_request["source_path"])["data"]
                else:
                    checkout, *_ = operations.authorized_repo(context, capture_request["repo_id"])
                    observed, _ = operations.read_code(checkout, capture_request["relative_path"])
                if sha(observed) != expected:
                    raise _source_changed("Selected original differs from its fixed observation", [capture_request.get("source_path", capture_request.get("relative_path"))])
            if collect_attachments and capture_request.get("kind") == "raw":
                capture_request = {**capture_request, "attachments": sorted(set(
                    capture_request.get("attachments", []) + operations.local_attachments(context, capture_request["source_path"])))}
            child_context = fork_context(context, request={**capture_request, "operation_id": context.operation}, action="capture")
            child_context.base = context.base + "/sources/" + digest(capture_request)[:32]
            if getattr(context, "expected_dbox_binding", None) is not None:
                child_context.expected_dbox_binding = context.expected_dbox_binding
            captured, _ = operations.capture(child_context)
        except (OSError, UnicodeError, NodeError, context.modules["validation"].ContractError) as exc:
            code = getattr(exc, "code", type(exc).__name__)
            if tolerate_errors and code in {"SOURCE_CHANGED", "CODE_CHANGED", "INPUT_CHANGED", "CONFIG_CHANGED", "KNOWLEDGE_CHANGED", "STALE_RULES"}:
                raise _source_changed("Selected input changed during material capture", [capture_request.get("source_path", capture_request.get("relative_path"))]) from exc
            missing_primary = code == "SOURCE_MISSING" and (
                not tolerate_errors or getattr(exc, "path", None) == capture_request.get("source_path", capture_request.get("relative_path")))
            if expected and (isinstance(exc, OSError) or missing_primary or code in {"SOURCE_CHANGED", "CODE_CHANGED"}):
                raise _source_changed("Selected original changed after its inventory observation", [capture_request.get("source_path", capture_request.get("relative_path"))]) from exc
            if tolerate_errors and code not in {"SOURCE_INTEGRITY_ERROR", "OPERATION_CONFLICT", "MATERIAL_IDENTITY_CONFLICT"}:
                if "target_id" in origin:
                    observation = {"unit_id": origin["target_id"], "target_id": origin["target_id"],
                                   "origin": "explicit_target", "source_kind": capture_request["kind"],
                                   "source_id": capture_request["source_id"], "status": "unavailable",
                                   "path": capture_request.get("source_path", capture_request.get("relative_path")),
                                   "observed_fingerprint": expected}
                    if capture_request.get("repo_id"):
                        observation["repo_id"] = capture_request["repo_id"]
                    _merge(material_units, [observation], "unit_id")
                gaps.append({**origin, "code": "CURRENT_ORIGINAL_UNAVAILABLE", "error_code": code,
                             "path": capture_request.get("source_path", capture_request.get("relative_path")),
                             "reason": str(exc)})
                continue
            raise
        bundle = context.record(captured["bundle_ref"], "source_bundle")
        if bundle.get("dbox_binding"):
            _adopt_dbox_binding(context, bundle["dbox_binding"])
        if expected and bundle["snapshots"][0]["sha256"] != expected:
            raise _source_changed("Original differs from its fixed inventory; refresh the affected P1 scope", [capture_request.get("source_path", capture_request.get("relative_path"))])
        if "target_id" in origin:
            snapshot = bundle["snapshots"][0]
            observation = {"unit_id": origin["target_id"], "target_id": origin["target_id"], "origin": "explicit_target",
                           "source_kind": capture_request["kind"], "source_id": snapshot["source_id"],
                           "path": capture_request.get("source_path", capture_request.get("relative_path")),
                           "observed_fingerprint": snapshot["sha256"], "snapshot_id": snapshot["snapshot_id"]}
            if capture_request.get("repo_id"):
                observation["repo_id"] = capture_request["repo_id"]
            previous_unit = material_units.get(observation["unit_id"])
            if (tolerate_errors and previous_unit and previous_unit.get("status") == "unavailable"
                    and all(previous_unit.get(key) == observation.get(key)
                            for key in ("target_id", "source_kind", "source_id", "path", "repo_id"))):
                # A failed attempt adopted no snapshot. Only this exact target
                # may replace that debt with newly captured, fixed evidence.
                material_units[observation["unit_id"]] = observation
            else:
                _merge(material_units, [observation], "unit_id")
        if tolerate_errors:
            gaps[:] = [gap for gap in gaps if not (gap.get("code") == "CURRENT_ORIGINAL_UNAVAILABLE"
                       and all(gap.get(key) == value for key, value in origin.items()))]
        bundles.append({**origin, "bundle_ref": captured["bundle_ref"], "bundle_digest": bundle["digest"]})
        gaps.extend({**origin, "code": "EXTRACTION_LIMITATION", "reason": text} for text in bundle.get("limitations", []))
        incoming.append((captured["bundle_ref"], bundle, capture_request.get("kind") == "code"))
    for supplied in request.get("code_bundle_refs", []):
        reference = supplied.get("bundle_ref") if isinstance(supplied, dict) else supplied
        bundle = operations.resolve_bundle(context, reference)["bundle"]
        if isinstance(supplied, dict) and supplied.get("bundle_digest") != bundle["digest"]:
            raise NodeError("CODE_BUNDLE_MISMATCH", "Current code bundle differs from the explicit material input")
        if not bundle["resources"] or any(resource.get("kind") != "code" for resource in bundle["resources"]):
            raise NodeError("CODE_BUNDLE_REQUIRED", "Only explicit registered code bundles are accepted here")
        incoming.append((reference, bundle, True))
    for reference, bundle, is_code in incoming:
        staged_objects.extend(staging.entries_from_bundle(bundle))
        event_proposals.extend(bundle.get("event_proposals", []))
        if bundle.get("context_ref"):
            context_refs.add(bundle["context_ref"])
        if bundle.get("config_digest"):
            config_digests.add(bundle["config_digest"])
        if is_code:
            for snapshot in bundle["snapshots"]:
                source_ref = {"evidence_ref": "material-code", "source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"],
                              "locator": {"kind": "bytes", "start": 0, "end": snapshot["bytes"]}}
                resolved = operations.resolve_source(context, source_ref, bundle)
                if resolved.get("source_kind") != "code" or resolved.get("current_source_matches") is not True:
                    raise NodeError("CURRENT_CODE_REQUIRED", "Historical or unauthorized code cannot serve as current P1 material", blocked=True)
                raw = base64.b64decode(resolved["bytes_b64"], validate=True)
                original_ref = context.base + "/material/code/" + sha(raw) + ".bin"
                _save_bytes(context, original_ref, raw)
                current_code.append({"source_ref": source_ref, "bundle_ref": reference, "bundle_digest": bundle["digest"],
                                     "original_ref": original_ref, "sha256": sha(raw), "bytes": len(raw), "current_source_matches": True,
                                     "code_identity": snapshot.get("code_identity"), "context_ref": bundle.get("context_ref")})
        for key, entries, identity in (("resources", resources, "source_id"), ("snapshots", snapshots, "snapshot_id"), ("extractions", extractions, "snapshot_id")):
            _merge(entries, bundle.get(key, []), identity)
    if len(config_digests) > 1:
        raise _source_changed("Explicit code materials were captured under different configurations", ["config.yml"])
    context_ref = request.get("context_ref") or (previous or {}).get("context_ref") or (next(iter(context_refs)) if len(context_refs) == 1 else None)
    if context_refs - {context_ref}:
        raise NodeError("MATERIAL_INPUT_MISMATCH", "Code materials bind different explicit project contexts")
    context_binding = code_context.prepare(
        context, list(resources.values()), list(snapshots.values()), context_ref,
        explicit=bool(request.get("context_ref") or (context_ref and context_ref in context_refs
                      and not previous)),
    )
    combined = context.seal({"resources": [resources[key] for key in sorted(resources)], "snapshots": [snapshots[key] for key in sorted(snapshots)],
                             "extractions": [extractions[key] for key in sorted(extractions)],
                             "staged_objects": staging.validate_entries(context.root, staged_objects),
                             "event_proposals": list({digest(row): row for row in event_proposals}.values()),
                             **context_binding,
                             **({"config_digest": next(iter(config_digests))} if config_digests else {}),
                             **({"dbox_binding": context.expected_dbox_binding} if getattr(context, "expected_dbox_binding", None) else {}),
                             "limitations": sorted({gap["code"] for gap in gaps})}, "source_bundle")
    current_files = _current_files(context, combined)
    if config_digests:
        actual = {item["sha256"] for item in current_files if item.get("kind") == "config"}
        if actual != config_digests:
            raise _source_changed("Workspace configuration changed after code capture", [item["path"] for item in current_files if item.get("kind") == "config"])
    cards = domain_cards(context)
    affected = [item["card_id"] for item in (scan or {}).get("current_context", {}).get("affected_claims", [])]
    explicit_candidates = request.get("candidate_card_ids", []) + affected + [item["card_id"] for item in (previous or {}).get("candidates", [])]
    topics = sorted(set(request.get("topics", []) + (previous or {}).get("topics", [])))
    candidates = context.modules["knowledge"].maintenance_candidates(cards, resources, topics, sorted(set(explicit_candidates)))
    candidate_records, adopted_objects = _candidate_material(context, candidates, snapshots, lock, gaps, staged_objects)
    combined = context.seal({**{key: value for key, value in combined.items() if key != "digest"},
                             "staged_objects": staging.validate_entries(context.root, staged_objects)}, "source_bundle")
    bundle_ref = context.base + "/materials/" + combined["digest"] + "/capture.json"
    context.save(bundle_ref, combined)
    for code in current_code:
        adopted_objects.append({"path": code["original_ref"], "sha256": code["sha256"], "bytes": code["bytes"], "kind": "original"})
    if _current_files(context, combined) != current_files:
        raise _source_changed("An adopted current source or configuration changed during preparation", [item["path"] for item in current_files])
    for candidate in candidate_records:
        if sha(fixed_bytes(context.root, candidate["formal_card_ref"], ["knowledge"])) != candidate["card_digest"]:
            raise _source_changed("A reading candidate changed during material preparation", [candidate["formal_card_ref"]])
    if sha(fixed_bytes(context.root, "governance/framework.lock.yaml")) != context.args.rules_digest:
        raise _source_changed("Rules changed during material preparation", ["governance/framework.lock.yaml"])
    gaps = list({digest(gap): gap for gap in gaps}.values())
    value = {"purpose": "source_materials", "bundle_ref": bundle_ref, "bundle_digest": combined["digest"],
             **({"dbox_binding": combined["dbox_binding"]} if combined.get("dbox_binding") else {}),
             **context_binding,
             "bundles": list({digest(bundle): bundle for bundle in bundles}.values()), "candidates": candidate_records,
             "current_code": list({digest(code): code for code in current_code}.values()), "gaps": gaps,
             "unit_ids": sorted(set([unit["unit_id"] for unit in units] + (previous or {}).get("unit_ids", []))),
             "targets": [targets[key] for key in sorted(targets)], "topics": topics,
             "units": [material_units[key] for key in sorted(material_units)],
             "current_files": current_files, "adopted_objects": _unique_records(adopted_objects, "path")}
    if scan:
        value.update(scan_ref=scan_ref, scan_digest=scan["digest"], origin_scan_operation_id=scan["operation_id"])
    if previous:
        previous_ref = request.get("existing_material_ref") or previous_view["material_ref"]
        value.update(previous_material_ref=previous_ref, previous_material_digest=previous["digest"])
    if previous_view:
        value.update(previous_view_ref=request["previous_view_ref"], previous_view_digest=previous_view["digest"],
                     revision_reason=request["revision_reason"])
    material = context.seal(value, "artifact_manifest")
    ref = context.base + "/materials/" + material["digest"] + "/material.json"
    context.save(ref, material)
    return {"material_ref": ref, "material_digest": material["digest"], "bundle_ref": bundle_ref,
            **(context_binding if context_binding.get("context_ref") else {}),
            **({"scan_ref": scan_ref} if scan_ref else {}),
            **({"origin_scan_operation_id": scan["operation_id"]} if scan else {}),
            **({"previous_view_ref": request["previous_view_ref"]} if previous_view else {}), "gaps": gaps}, "prepared"


def execute(context):
    return prepare(context)
