"""One-pass authored byte assembly for P3; full quality rules belong to P4."""
from __future__ import annotations

import base64
import copy
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import re
import json
import yaml

from .runtime import NodeError, digest, fixed_bytes, identifier, load_yaml, safe, sha, write_bytes
from .input_snapshot import capture_inputs, compare_inputs
from . import publication, staging

PROFILES = {"entity": "concepts/entities", "flow": "concepts/flows", "protocol": "concepts/protocols",
            "rule": "rules", "command": "commands", "runbook": "runbooks", "glossary": "glossaries"}
DECISIONS = {"create", "update", "merge", "split", "deprecate", "defer"}

def encode_card(card, *, lifecycle=None, replacement=None, reason=None):
    metadata = copy.deepcopy(card["metadata"])
    if lifecycle:
        metadata["lifecycle"] = lifecycle
    if replacement is not None:
        metadata["replacement"] = replacement
    if reason:
        metadata["deprecation_reason"] = reason
    return (
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n"
        + card["body"]
    ).encode("utf-8")


def cards_in_root(context):
    cards = {}
    knowledge = safe(context.root, "knowledge")
    if not knowledge.exists():
        return cards
    for path in sorted(knowledge.rglob("*.md")):
        if path.name in {"AGENTS.md", "index.md", "README.md"}:
            continue
        ref = path.relative_to(context.root).as_posix()
        card = context.modules["knowledge"].decode_card(
            fixed_bytes(context.root, ref), ref, context.rules
        )
        identity = card["metadata"]["id"]
        if identity in cards:
            raise NodeError(
                "DUPLICATE_CARD_ID", "Existing Card ID is duplicated", identity
            )
        cards[identity] = card
    return cards


def merged_sources(context, bundle):
    path = safe(context.root, "governance/sources.lock.yaml")
    lock = (
        load_yaml(path.read_bytes())
        if path.exists()
        else {"schema_version": "2.0", "resources": [], "snapshots": []}
    )
    result = copy.deepcopy(lock)
    for key, id_key in (("resources", "source_id"), ("snapshots", "snapshot_id")):
        items = {item[id_key]: item for item in result.get(key, [])}
        if len(items) != len(result.get(key, [])):
            raise NodeError(
                "DUPLICATE_SOURCE_ID", "Source lock contains duplicate identities"
            )
        for item in bundle[key]:
            previous = items.get(item[id_key])
            if previous and previous != item and key == "snapshots":
                old_content = {k: v for k, v in previous.items() if k not in {"recovery", "local_recovery"}}
                new_content = {k: v for k, v in item.items() if k not in {"recovery", "local_recovery"}}
                old_git = previous.get("recovery", {}).get("kind") == "git"
                new_git = item.get("recovery", {}).get("kind") == "git"
                if old_content == new_content and (old_git or new_git):
                    # Recovery location is not a new semantic source version.
                    # Retain an existing exact Git original; never downgrade it.
                    candidate_snapshot = previous if old_git else item
                    context.modules["source_resources"].recover_snapshot(context.root, candidate_snapshot, allow_local_fallback=False)
                    item = candidate_snapshot
                else:
                    raise NodeError(
                        "SOURCE_IDENTITY_CONFLICT",
                        "Immutable snapshot changed",
                        item[id_key],
                    )
            items[item[id_key]] = item
        result[key] = [items[key] for key in sorted(items)]
    result["schema_version"] = "2.0"
    return result


def candidate(context, value, existing):
    ref = value if isinstance(value, str) else value["path"]
    raw = fixed_bytes(context.root, ref, [".build"])
    card = context.modules["knowledge"].decode_card(raw, ref, context.rules)
    metadata = card["metadata"]
    identity = identifier(metadata["id"])
    if metadata.get("profile") not in PROFILES:
        raise NodeError("INVALID_PROFILE", "Card profile is needed to choose a safe destination", identity)
    target = value.get("target_path") if isinstance(value, dict) else None
    if not target:
        target = (
            existing[identity]["path"]
            if identity in existing
            else ("knowledge/" + PROFILES[metadata["profile"]] + "/" + identity + ".md")
        )
    safe(context.root, target, ["knowledge/" + PROFILES[metadata["profile"]]])
    if PurePosixPath(target).name.casefold() in {
        "agents.md",
        "index.md",
    } or not target.endswith(".md"):
        raise NodeError(
            "UNSAFE_CARD_PATH", "Candidate cannot overwrite a control file", target
        )
    if identity not in existing and safe(context.root, target).exists():
        raise NodeError(
            "TARGET_EXISTS", "A new Card ID cannot overwrite another card path", target
        )
    if identity in existing and target != existing[identity]["path"]:
        raise NodeError(
            "CARD_PATH_CHANGED",
            "Existing Card path moves require an explicit separate migration",
            target,
        )
    card["path"] = target
    return card, ref, sha(raw)


def _historical_view(ctx, ref):
    value = json.loads(fixed_bytes(ctx.root, ref, [".build/operations", "logs"]))
    ctx.modules["records"].verify(value)
    if value.get("record_kind") != "final_view":
        raise NodeError("WRONG_RECORD_KIND", "Revision needs an exact old view", ref)
    return value


def revision_view(ctx, request, *, required=False):
    """Read explicit immutable predecessor data; this is not an approval gate."""
    ref = request.get("previous_view_ref")
    if not ref:
        if required:
            raise NodeError("REVISION_CONTEXT_REQUIRED", "A new round adopting old inputs needs its exact previous view")
        return None
    previous = _historical_view(ctx, ref)
    if request.get("previous_view_digest", previous["digest"]) != previous["digest"]:
        raise NodeError("PREVIOUS_VIEW_CHANGED", "The previous candidate differs from its fixed digest")
    if previous["operation_id"] == ctx.operation:
        raise NodeError("NEW_OPERATION_REQUIRED", "Revision must use a new operation")
    if not isinstance(request.get("revision_reason"), str) or not request["revision_reason"].strip():
        raise NodeError("REVISION_REASON_REQUIRED", "Revision needs its actual return reason")
    return previous


def _load_inputs(ctx, request, previous=None):
    semantic = ctx.record(request["semantic_plan_ref"], "semantic_plan") if request.get("semantic_plan_ref") else None
    if semantic and semantic["operation_id"] != ctx.operation:
        if (not previous or previous.get("semantic_plan_ref") != request["semantic_plan_ref"]
                or previous.get("semantic_plan_digest") != semantic["digest"]):
            raise NodeError("PLAN_OPERATION_MISMATCH", "Adopt an old authored plan only through its exact previous view")
    if semantic and semantic["operation_id"] == ctx.operation and semantic.get("previous_view_ref"):
        if (request.get("previous_view_ref") != semantic["previous_view_ref"]
                or not previous or semantic.get("previous_view_digest") != previous["digest"]):
            raise NodeError("REVISION_CONTEXT_REQUIRED", "The new plan and candidate must name the same previous view")
    material_ref = request.get("material_ref") or (semantic or {}).get("material_ref")
    material = ctx.record(material_ref) if material_ref else {}
    if material and material.get("purpose") != "source_materials":
        raise NodeError("MATERIAL_BINDING", "Expected actual source reading materials")
    if semantic and material.get("digest") != semantic.get("material_digest"):
        raise NodeError("STALE_PLAN_INPUT", "Author decisions bind another material version")
    if material and material["operation_id"] != ctx.operation:
        if not previous or previous.get("material_ref") != material_ref:
            raise NodeError("MATERIAL_BINDING", "Adopt old materials only through the exact previous candidate")
    bundle_ref = request.get("bundle_ref") or material.get("bundle_ref")
    if not bundle_ref:
        raise NodeError("MATERIAL_REQUIRED", "Provide source materials or an explicit captured bundle")
    bundle = ctx.record(bundle_ref, "source_bundle")
    if material.get("bundle_digest") and material["bundle_digest"] != bundle["digest"]:
        raise NodeError("MATERIAL_BINDING", "Material bundle bytes differ")
    fixed_context_ref = material.get("context_ref") or bundle.get("context_ref")
    if material and fixed_context_ref and request.get("context_ref", fixed_context_ref) != fixed_context_ref:
        raise NodeError("MATERIAL_BINDING", "Do not replace the exact context adopted by the source materials")
    if material.get("context_ref") and bundle.get("context_ref") and material["context_ref"] != bundle["context_ref"]:
        raise NodeError("MATERIAL_BINDING", "Material and captured bundle bind different contexts")
    context_ref = request.get("context_ref", fixed_context_ref)
    context = ctx.record(context_ref, "project_context") if context_ref else {}
    context_digests = {value for value in (material.get("context_digest"), bundle.get("context_digest")) if value}
    if context_digests and context_digests != {context.get("digest")}:
        raise NodeError("MATERIAL_BINDING", "Actual project context differs from its frozen material digest")
    return semantic, material, material_ref, bundle, bundle_ref, context, context_ref


def _decisions(ctx, request, semantic, existing):
    decisions = request.get("decisions")
    if decisions is None:
        supplied = request.get("cards", {})
        if not isinstance(supplied, (dict, list)):
            raise NodeError("DECISIONS_REQUIRED", "Provide authored decisions or actual draft cards")
        by_id = supplied if isinstance(supplied, dict) else {
            candidate(ctx, item, existing)[0]["metadata"]["id"]: item for item in supplied}
        decisions = []
        for action in (semantic or {}).get("card_actions", []):
            kind, identity = action["decision"], action["card_id"]
            if kind not in {"create", "update", "defer"}:
                raise NodeError("DECISIONS_REQUIRED", "Merge, split and retirement need explicit authored decisions")
            if kind != "defer" and identity not in by_id:
                raise NodeError("CARD_INPUT_REQUIRED", "Provide the actual draft for this authored card", identity)
            decisions.append({"candidate_id": identity, "decision": kind, "reason": action["reason"],
                              "card_inputs": [] if kind == "defer" else [by_id[identity]]})
    if not isinstance(decisions, list):
        raise NodeError("DECISIONS_REQUIRED", "Authored card decisions must be a list")
    ids = [identifier(row.get("candidate_id")) for row in decisions]
    if len(set(ids)) != len(ids) or set(request.get("candidate_ids", ids)) != set(ids):
        raise NodeError("DISPOSITION_COVERAGE", "Each enumerated candidate needs one decision")
    return decisions


def _navigation_intro(text):
    replacements = (
        ("当前正式业务卡为空。", "正式业务卡见各类型导航。"),
        ("当前没有已落位的正式业务卡。", "本页维护已落位的正式业务卡导航。"),
    )
    lines = []
    for line in text.splitlines(keepends=True):
        for old, new in replacements:
            if line.startswith(old):
                line = new + line[len(old):]
                break
        lines.append(line)
    return "".join(lines)


def _navigation(ctx, writes, cards):
    navigation = {}
    for identity, card in cards.items():
        index_ref = str(PurePosixPath(card["path"]).parent / "index.md")
        if index_ref not in navigation:
            path = safe(ctx.root, index_ref)
            navigation[index_ref] = _navigation_intro(path.read_text(encoding="utf-8")) if path.exists() else "# Knowledge\n"
        marker = "<!-- card:" + sha(identity.encode()) + " -->"
        lines = navigation[index_ref].splitlines()
        matches = [i for i, line in enumerate(lines) if marker in line]
        if len(matches) > 1:
            raise NodeError("NAVIGATION_CONFLICT", "Duplicate navigation markers", index_ref)
        title = re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", card["metadata"]["title"].replace("\n", " "))
        entry = "- [" + title + "](" + quote(PurePosixPath(card["path"]).name, safe="") + ") " + marker
        if card["metadata"]["lifecycle"] == "deprecated":
            entry += " (deprecated)"
        if matches:
            lines[matches[0]] = entry
        else:
            lines += ["", entry]
        navigation[index_ref] = "\n".join(lines) + "\n"
    root_ref = "knowledge/index.md"
    if cards and root_ref not in navigation:
        root = safe(ctx.root, root_ref)
        if root.is_file():
            original = root.read_text(encoding="utf-8")
            updated = _navigation_intro(original)
            if updated != original:
                navigation[root_ref] = updated
    return {ref: value.encode() for ref, value in navigation.items()}


def _write(ctx, path, raw):
    current = safe(ctx.root, path, ["knowledge", "governance/sources.lock.yaml"])
    return {"path": path, "expected_old_digest": sha(current.read_bytes()) if current.exists() else None,
            "final_digest": sha(raw), "bytes_b64": base64.b64encode(raw).decode()}


def _result(view_ref, view):
    return {"view_ref": view_ref, "view_digest": view["digest"],
            "plan_ref": view["plan_ref"], "plan_digest": view["plan_digest"],
            "review_mode": view["review_mode"], "batch_kind": view.get("batch_kind", "content" if view.get("writes") else "record_only"),
            **({"disposition_preview_ref": view["disposition_preview_ref"]} if view.get("disposition_preview_ref") else {}),
            **({"summary_ref": view["summary_ref"]} if view.get("summary_ref") else {}),
            **({"revision_ref": view["revision_ref"], "content_review_required": True} if view.get("revision_ref") else {})}


def _reenter(ctx, request):
    ref = ctx.base + "/final-view.json"
    if not safe(ctx.root, ref).exists():
        return None
    view = ctx.record(ref, "final_view")
    if view.get("production_request_digest") != digest(request):
        raise NodeError("NEW_OPERATION_REQUIRED", "This operation already freezes different authored input")
    observed = compare_inputs(ctx, view["input_snapshot"])
    if not observed["unchanged"]:
        raise NodeError("INPUT_CHANGED", "Saved candidate inputs changed; create a fresh operation", observed["changes"])
    plan = ctx.record(view["plan_ref"], "change_plan")
    if plan["digest"] != view["plan_digest"]:
        raise NodeError("PLAN_CHANGED", "Saved candidate binds another byte plan")
    _validate_authored_bytes(ctx, view, plan, cards_in_root(ctx))
    for row in view["writes"]:
        raw = fixed_bytes(ctx.root, ctx.base + "/final-view/" + row["path"], [".build/operations"])
        if sha(raw) != row["final_digest"]:
            raise NodeError("FINAL_BYTES_CHANGED", "Saved candidate display bytes differ", row["path"])
    return _result(ref, view), "ready"


def _lost_card_hashes(existing, writes, deletes=()):
    changed = {row["path"] for row in writes
               if row.get("expected_old_digest") is not None
               and row["expected_old_digest"] != row["final_digest"]}
    changed.update(row["path"] for row in deletes)
    return {card["sha256"] for card in existing.values() if card["path"] in changed}


def _reading_card_refs(ctx, material):
    references = [row["card_ref"] for row in material.get("candidates", []) if row.get("card_ref")]
    objects = material.get("adopted_objects", [])
    if isinstance(objects, dict):
        objects = [{"path": path, **value} for path, value in objects.items() if isinstance(value, dict)]
    references.extend(row["path"] for row in objects
                      if isinstance(row, dict) and row.get("kind") in {"card", "historical_card"} and row.get("path"))
    result = set()
    for reference in references:
        path = Path(reference)
        if path.is_absolute():
            absolute = path.absolute()
            reference = absolute.relative_to(ctx.root).as_posix() if absolute.is_relative_to(ctx.root) else str(absolute)
        result.add(reference)
    return result


def assemble(ctx, request=None):
    """Produce the exact authored batch once; do not execute P4 quality rules."""
    request = request if request is not None else ctx.request
    previous = revision_view(ctx, request)
    repeated = _reenter(ctx, request)
    if repeated is not None:
        return repeated
    semantic, material, material_ref, bundle, bundle_ref, context, context_ref = _load_inputs(ctx, request, previous)
    existing = cards_in_root(ctx)
    decisions = _decisions(ctx, request, semantic, existing)
    source_lock = merged_sources(ctx, bundle)
    proposed, inputs, dispositions = {}, {}, []
    targets = {}
    for decision in decisions:
        action, reason = decision.get("decision"), decision.get("reason")
        if action not in DECISIONS or not isinstance(reason, str) or not reason.strip():
            raise NodeError("INVALID_DECISION", "Explicit supported decision and reason are required")
        authored = [candidate(ctx, item, existing) for item in decision.get("card_inputs", [])]
        card_ids = [card["metadata"]["id"] for card, _, _ in authored]
        replaces = decision.get("replaces", [])
        if len(set(card_ids)) != len(card_ids) or len(set(replaces)) != len(replaces) or any(i not in existing for i in replaces):
            raise NodeError("INVALID_REPLACES", "Distinct authored/replaced identities must be resolvable")
        if action == "defer" and (authored or replaces):
            raise NodeError("INVALID_DEFER", "Defer cannot write knowledge")
        if action in {"create", "update"} and (len(authored) != 1 or replaces):
            raise NodeError("INVALID_CARDINALITY", "Create/update needs one authored card")
        if action == "create" and card_ids[0] in existing:
            raise NodeError("TARGET_EXISTS", "Create cannot overwrite an existing Card ID")
        if action == "update" and card_ids[0] not in existing:
            raise NodeError("TARGET_MISSING", "Update retains an existing Card ID")
        if action == "merge" and (len(authored) != 1 or not replaces):
            raise NodeError("INVALID_CARDINALITY", "Merge needs a canonical card and replaced cards")
        if action == "split" and (len(authored) < 2 or len(replaces) != 1 or any(i in existing for i in card_ids)):
            raise NodeError("INVALID_CARDINALITY", "Split needs one old identity and new distinct cards")
        if action == "deprecate" and (authored or not replaces):
            raise NodeError("INVALID_CARDINALITY", "Retirement selects existing cards")
        for card, ref, observed in authored:
            identity = card["metadata"]["id"]
            if identity in proposed:
                raise NodeError("DUPLICATE_WRITE", "Two decisions write the same card", identity)
            proposed[identity] = encode_card(card, lifecycle="stable")
            targets[identity], inputs[ref] = card["path"], observed
        for identity in replaces:
            if identity in card_ids:
                continue
            if identity in proposed:
                raise NodeError("DUPLICATE_WRITE", "Card is replaced more than once", identity)
            proposed[identity] = encode_card(existing[identity], lifecycle="deprecated", replacement=card_ids, reason=reason)
            targets[identity] = existing[identity]["path"]
        for item in decision.get("related_card_inputs", []):
            card, ref, observed = candidate(ctx, item, existing)
            identity = card["metadata"]["id"]
            if identity not in existing or identity in proposed:
                raise NodeError("INVALID_IMPACT_WRITE", "Related edit needs a distinct existing destination")
            proposed[identity] = encode_card(card, lifecycle="stable")
            targets[identity], inputs[ref] = card["path"], observed
        dispositions.append({key: copy.deepcopy(value) for key, value in {
            "candidate_id": decision["candidate_id"], "decision": action, "reason": reason,
            "card_ids": card_ids, "replaces": replaces,
            "claim_mapping": decision.get("claim_mapping", {}),
            "retired_claim_ids": decision.get("retired_claim_ids", []),
            "owner": decision.get("owner", "unknown"), "next_step": decision.get("next_step", "unknown")}.items()})
    if len({path.casefold() for path in targets.values()}) != len(targets):
        raise NodeError("DUPLICATE_WRITE", "Card destinations overlap or alias")
    authored_cards = {identity: ctx.modules["knowledge"].decode_card(raw, targets[identity], ctx.rules)
                      for identity, raw in proposed.items()}
    writes = [_write(ctx, targets[identity], raw) for identity, raw in proposed.items()]
    if writes:
        extra = _navigation(ctx, writes, authored_cards)
        extra["governance/sources.lock.yaml"] = yaml.safe_dump(source_lock, allow_unicode=True, sort_keys=False).encode()
        writes.extend(_write(ctx, path, raw) for path, raw in extra.items())
    queries = copy.deepcopy((semantic or {}).get("target_queries", request.get("target_queries", [])))
    if semantic and "target_queries" in request and request["target_queries"] != queries:
        raise NodeError("TARGET_QUERIES_CHANGED", "Do not replace the authored query expectations")
    refs = [value for value in (request.get("semantic_plan_ref"), material_ref, bundle_ref, context_ref) if value]
    snapshot = capture_inputs(ctx, material=material, semantic_plan=semantic, bundle=bundle, context=context,
                              check_inputs=request.get("check_inputs"), references=refs)
    if previous:
        previous_ref = request["previous_view_ref"]
        raw = fixed_bytes(ctx.root, previous_ref, [".build/operations", "logs"])
        observed_previous = json.loads(raw)
        ctx.modules["records"].verify(observed_previous)
        if observed_previous["digest"] != previous["digest"]:
            raise NodeError("PREVIOUS_VIEW_CHANGED", "The adopted previous candidate changed during production")
        snapshot["business_records"][previous_ref] = {"sha256": sha(raw), "bytes": len(raw),
            "digest": previous["digest"], "record_kind": "final_view"}
    for ref, observed in inputs.items():
        raw = fixed_bytes(ctx.root, ref, [".build"])
        if sha(raw) != observed:
            raise NodeError("CANDIDATE_CHANGED", "Authored bytes changed during assembly", ref)
        snapshot["adopted_objects"][ref] = {"kind": "file", "path": ref, "sha256": observed, "bytes": len(raw)}
    snapshot.pop("snapshot_digest")
    snapshot["snapshot_digest"] = digest(snapshot)
    modes = {card["metadata"]["review_mode"] for card in authored_cards.values()}
    review_mode = "mixed" if len(modes) > 1 else next(iter(modes), "record_only")
    requirements = {mode: sorted(card["path"] for card in authored_cards.values()
                                 if card["metadata"]["review_mode"] == mode) for mode in sorted(modes)}
    plan = ctx.seal({"bundle_ref": bundle_ref, "bundle_digest": bundle["digest"],
                     "context_ref": context_ref, "decisions": dispositions,
                     "authored_decisions": copy.deepcopy(decisions),
                     "candidate_ids": [row["candidate_id"] for row in decisions],
                     "writes": [row for row in writes if row["path"] in targets.values()], "deletes": [],
                     "baseline": {row["path"]: row["expected_old_digest"] for row in writes},
                     "input_digests": inputs, "source_lock": source_lock,
                     "review_mode": review_mode, "review_requirements": requirements,
                     "v3_required": semantic is not None, "target_queries": queries,
                     **({"semantic_plan_ref": request["semantic_plan_ref"], "semantic_plan_digest": semantic["digest"],
                         "material_ref": material_ref, **({"scan_ref": semantic["scan_ref"]} if semantic.get("scan_ref") else {})}
                        if semantic else {}),
                     "request_digest": digest(request), "request": copy.deepcopy(request)}, "change_plan")
    plan_ref = ctx.save(ctx.base + "/plan.json", plan)
    preview = ctx.seal({"purpose": "disposition_preview", "semantic_plan_ref": request.get("semantic_plan_ref"),
                        "semantic_plan_digest": (semantic or {}).get("digest"),
                        **({"origin_scan_operation_id": semantic.get("origin_scan_operation_id", semantic["operation_id"])}
                           if semantic and semantic.get("scan_ref") else {}),
                        "units": copy.deepcopy((semantic or {}).get("units", request.get("units", []))),
                        "maintenance_units": copy.deepcopy((semantic or {}).get("maintenance_units", [])),
                        "card_decisions": dispositions,
                        "input_snapshot_digest": snapshot["snapshot_digest"]}, "artifact_manifest")
    preview_ref = ctx.save(ctx.base + "/disposition-preview.json", preview)
    referenced = {source["snapshot_id"] for card in authored_cards.values() for source in card["metadata"].get("sources", [])}
    sources = sorted((source for source in source_lock["snapshots"] if source["snapshot_id"] in referenced),
                     key=lambda source: source["snapshot_id"])
    summary_ref = ctx.base + "/view-summary.json"
    revision_ref = ctx.base + "/revision.json" if request.get("previous_view_ref") else None
    historical_hashes = set((request.get("check_inputs") or {}).get("historical_card_objects", {}))
    retained_cards = _lost_card_hashes(existing, writes) | historical_hashes
    reading_cards = _reading_card_refs(ctx, material)
    staged = [row for row in bundle.get("staged_objects", [])
              if (row.get("kind") not in {"card", "historical_card"}
                  and not row["final_ref"].startswith("logs/evidence/published/cards/"))
              or row["sha256"] in retained_cards]
    # Retain the exact preimage before an update replaces its only formal copy.
    # This also covers P3 callers that supplied a bundle without P1 materials.
    for identity in sorted(set(proposed) & set(existing)):
        card = existing[identity]
        if card["sha256"] in retained_cards:
            staged.append(staging.stage_bytes(ctx, "logs/evidence/published/cards/" + card["sha256"] + ".md",
                                             card["raw"], kind="card"))
    for ref, entry in snapshot["adopted_objects"].items():
        if entry.get("kind") == "source_snapshot" or ref in inputs:
            continue
        if ref in reading_cards and entry["sha256"] not in retained_cards:
            continue  # Reading a candidate binds prewrite inputs, not publication.
        is_card = ref in reading_cards or entry["sha256"] in historical_hashes
        final = ("logs/evidence/published/" + ("cards/" if is_card else "objects/")
                 + entry["sha256"] + (".md" if is_card else ".bin"))
        if any(row["final_ref"] == final and row["sha256"] == entry["sha256"]
               and row["bytes"] == entry["bytes"] for row in staged):
            continue
        # Explicit adopted history can live outside this batch. Copy its exact
        # bytes into our publication; never clean the borrowed original.
        raw = Path(ref).read_bytes() if Path(ref).is_absolute() else fixed_bytes(ctx.root, ref)
        if sha(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
            raise NodeError("INPUT_CHANGED", "Retained input changed before staging", ref)
        staged.append(staging.stage_bytes(ctx, final, raw, kind="card" if is_card else "original"))
    for ref, entry in {**snapshot["business_records"], **snapshot["adopted_objects"]}.items():
        if ref.startswith(ctx.operation_root + "/") and entry.get("kind") != "source_snapshot":
            ctx.register_owned(ref, fixed_bytes(ctx.root, ref, [ctx.operation_root]))
    view_fields = {"operation_id": ctx.operation, "writes": sorted(writes, key=lambda row: row["path"]), "deletes": [],
                     "plan_ref": plan_ref, "plan_digest": plan["digest"],
                     "review_mode": review_mode, "review_requirements": requirements,
                     "batch_kind": "content" if writes else "record_only",
                     "source_refs": sources, "source_set_digest": digest(sources),
                     "bundle_ref": bundle_ref, "context_ref": context_ref,
                     "baseline_digest": digest({"files": {row["path"]: row["expected_old_digest"] for row in writes}}),
                     "dispositions": dispositions, "target_queries": queries,
                     "semantic_plan_ref": request.get("semantic_plan_ref"),
                     "semantic_plan_digest": (semantic or {}).get("digest"),
                     "scan_ref": (semantic or material).get("scan_ref"), "material_ref": material_ref,
                     "material_digest": material.get("digest"),
                     **({"origin_scan_operation_id": semantic.get("origin_scan_operation_id", semantic["operation_id"])}
                        if semantic and semantic.get("scan_ref") else {}),
                     "v3_required": semantic is not None, "input_snapshot": snapshot,
                     "disposition_preview_ref": preview_ref, "summary_ref": summary_ref,
                     "production_request_digest": digest(request),
                     **({"revision_ref": revision_ref, "previous_view_ref": request["previous_view_ref"],
                         "previous_view_digest": previous["digest"],
                         "revision_reason": request["revision_reason"],
                         "previous_semantic_plan_ref": previous.get("semantic_plan_ref"),
                         "previous_semantic_plan_digest": previous.get("semantic_plan_digest")} if revision_ref else {}),
                     "staged_objects": staging.merge_entries(staged),
                     # Record-only dispositions do not register a new source
                     # version. Their unresolved debt stays in the record.
                     "event_proposals": copy.deepcopy(bundle.get("event_proposals", [])) if writes else [],
                     "owned_files": ctx.owned_files()}
    view_fields["publication_plan"] = publication.prepare_plan(ctx, view_fields, disposition_preview=preview)
    view_fields["content_digest"] = view_fields["publication_plan"]["content_digest"]
    view = ctx.seal(view_fields, "final_view")
    for row in writes:
        raw = base64.b64decode(row["bytes_b64"])
        output_ref = ctx.base + "/final-view/" + row["path"]
        write_bytes(ctx.root, output_ref, raw)
        ctx.register_owned(output_ref, raw)
    view_ref = ctx.save(ctx.base + "/final-view.json", view)
    summary = ctx.seal({"purpose": "candidate_summary", "view_ref": view_ref, "view_digest": view["digest"],
                        "plan_ref": plan_ref, "plan_digest": plan["digest"],
                        "source_set_digest": view["source_set_digest"], "source_refs": sources,
                        "baseline_digest": view["baseline_digest"], "review_mode": review_mode,
                        "batch_kind": view["batch_kind"], "disposition_preview_ref": preview_ref,
                        "input_snapshot_digest": snapshot["snapshot_digest"],
                        "limitations": ["Describes authored bytes; P4 owns quality and OpenFlow owns ordering"]}, "artifact_manifest")
    ctx.save(summary_ref, summary)
    if revision_ref:
        ctx.save(revision_ref, ctx.seal({"purpose": "candidate_revision", "previous_view_ref": request["previous_view_ref"],
                                      "previous_view_digest": previous["digest"], "revision_reason": request["revision_reason"],
                                      "view_ref": view_ref, "view_digest": view["digest"]}, "artifact_manifest"))
    return _result(view_ref, view), "ready"


def revise(ctx, request=None):
    request = request if request is not None else ctx.request
    if not request.get("previous_view_ref"):
        raise NodeError("REVISION_CONTEXT_REQUIRED", "Revision needs its exact previous candidate")
    return assemble(ctx, request)


def describe(ctx, request=None):
    request = request if request is not None else ctx.request
    view = _historical_view(ctx, request["view_ref"])
    if view["operation_id"] != ctx.operation:
        raise NodeError("OPERATION_MISMATCH", "Description must name the candidate's actual operation")
    return {**_result(request["view_ref"], view), "source_refs": view["source_refs"],
            "source_set_digest": view["source_set_digest"], "baseline_digest": view["baseline_digest"],
            "limitations": ["Exact saved candidate only; no quality, identity or workflow approval"]}, "described"


def _claim_identity(reference, available):
    if "#" in reference:
        identity = tuple(reference.split("#", 1))
        if identity in available:
            return identity
    else:
        matches = [pair for pair in available if pair[1] == reference]
        if len(matches) == 1:
            return matches[0]
    raise NodeError("INVALID_CLAIM_MAPPING", "Use an unambiguous CardID#ClaimID", reference)


def _validate_authored_bytes(ctx, view, plan, existing):
    """Bounded exact-input binding, not replay of planning or full production."""
    writes = {row["path"]: row for row in view.get("writes", [])}
    for ref, expected in plan.get("input_digests", {}).items():
        if sha(fixed_bytes(ctx.root, ref, [".build"])) != expected:
            raise NodeError("CANDIDATE_CHANGED", "Authored candidate input changed", ref)
    for decision in plan.get("authored_decisions", plan.get("request", {}).get("decisions", [])):
        for item in decision.get("card_inputs", []) + decision.get("related_card_inputs", []):
            card, _, _ = candidate(ctx, item, existing)
            expected = encode_card(card, lifecycle="stable")
            row = writes.get(card["path"])
            if not row or row["final_digest"] != sha(expected) or base64.b64decode(row["bytes_b64"], validate=True) != expected:
                raise NodeError("FINAL_BYTES_CHANGED", "Final draft differs from actual authored candidate", card["path"])


def _validate_dispositions(ctx, view, plan, semantic):
    """Compare the exact authored record preview, without choosing an action."""
    if not view.get("disposition_preview_ref"):
        if view.get("input_snapshot"):
            raise NodeError("DISPOSITION_PREVIEW_REQUIRED", "Produced candidates need their authored record preview")
        return
    preview = ctx.record(view["disposition_preview_ref"], "artifact_manifest")
    if (preview.get("purpose") != "disposition_preview" or preview.get("operation_id") != view["operation_id"]
            or preview.get("card_decisions") != plan["decisions"]
            or view.get("dispositions") != plan["decisions"]
            or preview.get("input_snapshot_digest") != view.get("input_snapshot", {}).get("snapshot_digest")):
        raise NodeError("DISPOSITION_PREVIEW_CHANGED", "Record preview differs from this candidate's exact authored decisions")
    if not semantic:
        return
    if (preview.get("semantic_plan_ref") != view.get("semantic_plan_ref")
            or preview.get("semantic_plan_digest") != semantic["digest"]
            or any(preview.get(field) != semantic.get(field, []) for field in ("units", "maintenance_units"))):
        raise NodeError("DISPOSITION_PREVIEW_CHANGED", "Record preview must copy the exact frozen semantic units")
    if semantic.get("scan_ref"):
        scan = ctx.record(semantic["scan_ref"], "source_inventory")
        origin = scan["operation_id"]
        if (semantic.get("scan_digest") != scan["digest"]
                or semantic.get("origin_scan_operation_id", semantic["operation_id"]) != origin
                or view.get("origin_scan_operation_id") != origin
                or preview.get("origin_scan_operation_id") != origin):
            raise NodeError("PLAN_OPERATION_MISMATCH", "The candidate and disposition preview must bind the actual original scan")
    for unit in semantic.get("units", []) + semantic.get("maintenance_units", []):
        identity = unit["unit_id"]
        actions = [row for row in semantic["card_actions"] if identity in row["unit_ids"]]
        decisions = {row["decision"] for row in actions if row["decision"] != "defer"}
        cards = sorted({row["card_id"] for row in actions})
        claims = sorted({row["card_id"] + "#" + row["claim_id"] for row in semantic["claim_changes"]
                         if identity in row["unit_ids"]})
        selected = unit.get("record_action")
        if ((unit["outcome"] == "content" and selected not in decisions)
                or (unit["outcome"] != "content" and selected != unit["outcome"])):
            raise NodeError("PLAN_RECORD_ACTION_REQUIRED", "Source record action differs from its actual authored decisions", identity)
        if unit.get("card_refs") != cards or unit.get("claim_refs") != claims:
            raise NodeError("PLAN_RECORD_REFERENCES_CHANGED", "Source record references differ from exact authored judgments", identity)
        if unit["outcome"] == "content":
            actual = {row["decision"] for row in plan["decisions"]
                      if set(cards) & set(row.get("card_ids", []) + row.get("replaces", []))}
            if selected not in actual:
                raise NodeError("PLAN_ACTION_MISMATCH", "Record action is absent from the actual produced card decisions", identity)


def validate_candidate(ctx, view, plan=None, semantic=None, *, cards=None):
    """Check authored production judgments at P4, never during assembly.

    Generic Profile/source/relation checks remain in checks.run.  This function
    preserves the additional plan-to-draft, old-Claim preservation, replacement
    mapping and impact-closure oracles of the former planning engine.  ``cards``
    may be the already parsed full candidate set from that single full lint.
    Formal/CI callers without producer plans do not need this function.
    """
    if plan is None:
        if not view.get("plan_ref"):
            return {"checked": False, "reason": "No authored production plan supplied"}
        plan = ctx.record(view["plan_ref"], "change_plan")
    if view.get("plan_digest") != plan["digest"]:
        raise NodeError("PLAN_CHANGED", "Candidate binds another authored byte plan")
    if semantic is None and view.get("semantic_plan_ref"):
        semantic = ctx.record(view["semantic_plan_ref"], "semantic_plan")
    if semantic and view.get("semantic_plan_digest") != semantic["digest"]:
        raise NodeError("PLAN_CHANGED", "Candidate binds another content judgment")
    if semantic and semantic["operation_id"] != view["operation_id"]:
        previous = revision_view(ctx, view, required=True)
        if (previous.get("semantic_plan_ref") != view.get("semantic_plan_ref")
                or previous.get("semantic_plan_digest") != semantic["digest"]):
            raise NodeError("PLAN_OPERATION_MISMATCH", "Candidate did not explicitly adopt this unchanged previous plan")
    _validate_dispositions(ctx, view, plan, semantic)
    if not view.get("writes") and not view.get("deletes"):
        if semantic and any(row["outcome"] == "content" for row in semantic.get("units", []) + semantic.get("maintenance_units", [])):
            raise NodeError("PLAN_WRITE_COVERAGE", "Content judgments need an actual authored write set")
        _validate_authored_bytes(ctx, view, plan, {})
        return {"checked": True, "card_ids": [], "replaced_card_ids": []}
    existing = cards_in_root(ctx)
    rules = {**ctx.rules, "source_lock": plan["source_lock"]}
    if cards is None:
        cards = dict(existing)
        for row in view.get("deletes", []):
            cards = {key: card for key, card in cards.items() if card["path"] != row["path"]}
        for row in view.get("writes", []):
            if row["path"].startswith("knowledge/") and PurePosixPath(row["path"]).name not in {"index.md", "AGENTS.md", "README.md"}:
                card = ctx.modules["knowledge"].parse_card(base64.b64decode(row["bytes_b64"], validate=True), row["path"], rules)
                cards[card["metadata"]["id"]] = card
    # Compile old Claim values only for an old card actually referenced by an
    # authored judgment; no second whole-library quality scan.
    old = {}
    required_old = {row["card_id"] for row in (semantic or {}).get("claim_changes", [])}
    required_old |= {identity for row in plan["decisions"] for identity in row.get("replaces", [])}
    for identity in required_old & set(existing):
        item = existing[identity]
        old[identity] = ctx.modules["knowledge"].parse_card(item["raw"], item["path"], rules)
        if item["path"] not in {row["path"] for row in view.get("writes", [])}:
            cards[identity] = old[identity]
    writes = {row["path"]: row for row in view.get("writes", [])}
    _validate_authored_bytes(ctx, view, plan, existing)
    replaced = set()
    proposed = {identity for identity, card in cards.items() if card["path"] in writes}
    for decision in plan["decisions"]:
        action, ids, replaces = decision["decision"], decision.get("card_ids", []), decision.get("replaces", [])
        replaced.update(identity for identity in replaces if identity not in ids)
        if action in {"merge", "split"}:
            old_claims = {(identity, claim["id"]) for identity in replaces if identity not in ids
                          for claim in old[identity]["metadata"]["claims"]}
            new_claims = {(identity, claim["id"]) for identity in ids for claim in cards[identity]["metadata"]["claims"]}
            mapping = {_claim_identity(key, old_claims): targets
                       for key, targets in decision.get("claim_mapping", {}).items()}
            retired = {_claim_identity(key, old_claims) for key in decision.get("retired_claim_ids", [])}
            if set(mapping) | retired != old_claims or set(mapping) & retired:
                raise NodeError("CLAIM_DESTINATION_REQUIRED", "Every replaced Claim needs a destination or explicit retirement")
            for targets in mapping.values():
                if not targets:
                    raise NodeError("INVALID_CLAIM_MAPPING", "Mapped Claim needs a destination")
                for target in targets:
                    _claim_identity(target, new_claims)
    for card in cards.values():
        if card["metadata"]["lifecycle"] == "stable" and any(
                row["type"] in {"requires", "replacement"} and row["target_card_id"] in replaced
                for row in card["metadata"].get("relations", [])):
            raise NodeError("IMPACT_CLOSURE_REQUIRED", "Stable dependency still points to a replaced card", card["metadata"]["id"])
    if semantic:
        declared = {row["card_id"]: row for row in semantic["card_actions"] if row["decision"] != "defer"}
        if proposed != set(declared):
            raise NodeError("PLAN_WRITE_COVERAGE", "Draft targets differ from authored card decisions")
        for decision in plan["decisions"]:
            for identity in decision.get("card_ids", []):
                if declared[identity]["decision"] != decision["decision"]:
                    raise NodeError("PLAN_ACTION_MISMATCH", "Draft action differs from authored decision", identity)
        for change in semantic["claim_changes"]:
            identity, claim_id = change["card_id"], change["claim_id"]
            if change["action"] in {"create", "update"} and claim_id not in {c["id"] for c in cards[identity]["claims"]}:
                raise NodeError("PLAN_CLAIM_MISSING", "Planned Claim is absent from final candidate")
            if change["action"] == "preserve":
                before = next((claim for claim in old.get(identity, {}).get("claims", []) if claim["id"] == claim_id), None)
                after = next((claim for claim in cards.get(identity, {}).get("claims", []) if claim["id"] == claim_id), None)
                if not before or not after or {k: v for k, v in before.items() if k != "span"} != {k: v for k, v in after.items() if k != "span"}:
                    raise NodeError("PRESERVED_CLAIM_CHANGED", "A preserved Claim changed without a revised judgment", identity + "#" + claim_id)
        for identity, action in declared.items():
            if action["decision"] == "update" and identity in old:
                judged = {row["claim_id"] for row in semantic["claim_changes"] if row["card_id"] == identity}
                if not {row["id"] for row in old[identity]["claims"]} <= judged:
                    raise NodeError("OLD_CLAIM_JUDGMENT_REQUIRED", "Every old Claim needs an explicit judgment", identity)
    return {"checked": True, "card_ids": sorted(proposed), "replaced_card_ids": sorted(replaced)}
