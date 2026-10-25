"""Prepare immutable reading candidates; do not generate semantic conclusions."""

import difflib
import base64

from support import NodeError, fixed_bytes, safe, sha, write_bytes


def domain_cards(context):
    root = safe(context.root, "knowledge")
    cards = []
    if root.exists():
        for path in sorted(root.rglob("*.md")):
            if path.name in {"AGENTS.md", "index.md"}:
                continue
            ref = path.relative_to(context.root).as_posix()
            cards.append(context.modules["knowledge"].parse_card(fixed_bytes(context.root, ref, ["knowledge"]), ref, context.rules))
    if len({c["metadata"]["id"] for c in cards}) != len(cards):
        raise NodeError("DUPLICATE_CARD_ID", "Reading candidates need unique card identities")
    return cards


def prepare(context):
    request = context.request
    scan = context.record(request["scan_ref"], "source_inventory")
    if scan["operation_id"] != context.operation:
        raise NodeError("OPERATION_MISMATCH", "Inventory belongs to another operation")
    units = scan["units"]
    if "unit_ids" in request:
        selected = set(request["unit_ids"])
        if not selected.issubset({u["unit_id"] for u in units}):
            raise NodeError("UNKNOWN_SOURCE_UNIT", "Requested unit is outside the fixed inventory")
        units = [u for u in units if u["unit_id"] in selected]
    else:
        units = [u for u in units if u["change"] != "unchanged"]
    resources, snapshots, extractions, bundles, gaps = {}, {}, {}, [], []
    current_code, code_context_refs = [], set()
    for unit in units:
        if unit["change"] in {"missing", "read_failed"} or not unit["observed_fingerprint"]:
            gaps.append({"unit_id": unit["unit_id"], "code": "CURRENT_ORIGINAL_UNAVAILABLE", "path": unit["path"]})
            continue
        # Capture has a single immutable bundle per operation. Child operations
        # preserve that boundary; the parent gets one combined verified bundle.
        child = context.operation + "-" + unit["unit_id"][-12:]
        result = context.call("hs-knowledge-source-capture", {"operation_id": child, "source_path": unit["path"], "source_id": unit["source_id"]})
        bundle = context.record(result["data"]["bundle_ref"], "source_bundle")
        if bundle["snapshots"][0]["sha256"] != unit["observed_fingerprint"]:
            raise NodeError("SOURCE_CHANGED", "Original differs from fixed scan inventory", unit["path"])
        bundles.append({"unit_id": unit["unit_id"], "bundle_ref": result["data"]["bundle_ref"], "bundle_digest": bundle["digest"]})
        resources.update((r["source_id"], r) for r in bundle["resources"])
        snapshots.update((s["snapshot_id"], s) for s in bundle["snapshots"])
        extractions.update((e["snapshot_id"], e) for e in bundle.get("extractions", []))
        gaps.extend({"unit_id": unit["unit_id"], "code": "EXTRACTION_LIMITATION", "reason": text} for text in bundle.get("limitations", []))
    for supplied in request.get("code_bundle_refs", []):
        reference = supplied.get("bundle_ref") if isinstance(supplied, dict) else supplied
        verified = context.call("hs-knowledge-source-capture", {"operation_id": context.operation, "bundle_ref": reference}, "resolve")
        bundle = verified["data"]["bundle"]
        if isinstance(supplied, dict) and supplied.get("bundle_digest") != bundle["digest"]:
            raise NodeError("CODE_BUNDLE_MISMATCH", "Current code bundle differs from the explicit material input")
        if not bundle["resources"] or any(r.get("kind") != "code" for r in bundle["resources"]):
            raise NodeError("CODE_BUNDLE_REQUIRED", "Only explicitly captured registered code bundles are accepted here")
        if bundle.get("context_ref"):
            code_context_refs.add(bundle["context_ref"])
        for snapshot in bundle["snapshots"]:
            source_ref = {"evidence_ref": "material-code", "source_id": snapshot["source_id"], "snapshot_id": snapshot["snapshot_id"],
                          "locator": {"kind": "bytes", "start": 0, "end": snapshot["bytes"]}}
            resolved = context.call("hs-knowledge-source-capture", {"operation_id": context.operation, "bundle_ref": reference, "source_ref": source_ref}, "resolve-source")["data"]
            if resolved.get("source_kind") != "code" or resolved.get("current_source_matches") is not True:
                raise NodeError("CURRENT_CODE_REQUIRED", "Historical or unauthorized code cannot serve as current P2 material", blocked=True)
            raw = base64.b64decode(resolved["bytes_b64"], validate=True)
            suffix = snapshot.get("format", ".bin")
            if not isinstance(suffix, str) or not suffix.startswith(".") or not suffix[1:].isalnum():
                suffix = ".bin"
            original_ref = context.base + "/material/code/" + sha(raw) + suffix
            write_bytes(context.root, original_ref, raw)
            current_code.append({"source_ref": source_ref, "bundle_ref": reference, "bundle_digest": bundle["digest"],
                                 "original_ref": original_ref, "sha256": sha(raw), "bytes": len(raw), "current_source_matches": True,
                                 "code_identity": snapshot.get("code_identity"), "context_ref": bundle.get("context_ref")})
        for key, entries, identity in (("resources", resources, "source_id"), ("snapshots", snapshots, "snapshot_id"), ("extractions", extractions, "snapshot_id")):
            for entry in bundle.get(key, []):
                if entry[identity] in entries and entries[entry[identity]] != entry:
                    raise NodeError("CODE_BUNDLE_CONFLICT", "Explicit material bundles disagree on the same identity", entry[identity])
                entries[entry[identity]] = entry
    combined = context.seal({"resources": list(resources.values()), "snapshots": list(snapshots.values()),
                             "extractions": list(extractions.values()), "context_ref": request.get("context_ref") or (next(iter(code_context_refs)) if len(code_context_refs) == 1 else None),
                             "limitations": [g["code"] for g in gaps]}, "source_bundle")
    bundle_ref = context.base + "/capture.json"
    context.save(bundle_ref, combined)
    cards = domain_cards(context)
    current_affected = [item["card_id"] for item in scan.get("current_context", {}).get("affected_claims", [])]
    candidates = context.modules["knowledge"].maintenance_candidates(cards, [u["source_id"] for u in units], request.get("topics", []), sorted(set(request.get("candidate_card_ids", []) + current_affected)))
    lock = context.modules["source_resources"].read_source_lock(context.root)
    old_by_id = {s["snapshot_id"]: s for s in lock["snapshots"]}
    candidate_records = []
    for candidate in candidates:
        card, identity = candidate["card"], candidate["card_id"]
        card_ref = context.base + "/material/cards/" + identity + ".md"
        write_bytes(context.root, card_ref, card["raw"])
        adopted = []
        for source in card["metadata"]["sources"]:
            item = {**source, "claim_ids": [c["id"] for c in card["metadata"]["claims"] if source["evidence_ref"] in c["source_refs"]]}
            try:
                snapshot = old_by_id.get(source["snapshot_id"])
                if snapshot is None or snapshot["source_id"] != source["source_id"]:
                    raise NodeError("SOURCE_UNAVAILABLE", "Adopted exact old snapshot is not registered", source["snapshot_id"])
                raw = context.modules["source_resources"].recover_snapshot(context.root, snapshot)
                suffix = snapshot.get("format", ".bin")
                if suffix not in {".md", ".txt", ".pdf", ".docx"}:
                    suffix = ".bin"
                original_ref = context.base + "/material/originals/" + sha(raw) + suffix
                write_bytes(context.root, original_ref, raw)
                item.update(original_ref=original_ref, recovery=snapshot["recovery"], sha256=sha(raw), bytes=len(raw))
                extraction = snapshot.get("extraction")
                if snapshot.get("format") in {".txt", ".md"}:
                    item["text"] = raw.decode("utf-8-sig")
                    if extraction and sha(item["text"].encode()) != extraction["text_sha256"]:
                        raise NodeError("SOURCE_INTEGRITY_ERROR", "Recovered old text differs from frozen extraction")
                elif extraction:
                    try:
                        text = fixed_bytes(context.root, extraction["text_ref"], ["logs/evidence"])
                        if sha(text) != extraction["text_sha256"]:
                            raise NodeError("SOURCE_INTEGRITY_ERROR", "Adopted extraction changed")
                        item["text"] = text.decode("utf-8")
                    except OSError:
                        item["text"] = None
                        item["read_gap"] = "Frozen text cache unavailable; read the retained exact original_ref"
                        gaps.append({"card_id": identity, "snapshot_id": source["snapshot_id"], "code": "ADOPTED_EXTRACTION_UNAVAILABLE", "original_ref": original_ref})
                else:
                    item["text"] = None
                    item["read_gap"] = "Read full original via original_ref; no retained text extraction"
                current = next((s for s in snapshots.values() if s["source_id"] == source["source_id"]), None)
                if current and item.get("text") is not None and current.get("format") in {".md", ".txt"}:
                    now = context.modules["source_resources"].recover_snapshot(context.root, current).decode("utf-8-sig")
                    item["diff"] = "".join(difflib.unified_diff(item["text"].splitlines(True), now.splitlines(True), fromfile=source["snapshot_id"], tofile=current["snapshot_id"]))
            except (OSError, UnicodeError, NodeError, context.modules["validation"].ContractError) as exc:
                item["read_gap"] = str(exc)
                gaps.append({"card_id": identity, "snapshot_id": source["snapshot_id"], "code": "ADOPTED_ORIGINAL_UNAVAILABLE", "reason": str(exc)})
            adopted.append(item)
        candidate_records.append({"card_id": identity, "card_ref": card_ref, "formal_card_ref": card["path"],
                                  "card_digest": card["sha256"], "lifecycle": card["metadata"]["lifecycle"],
                                  "reasons": candidate["reasons"], "adopted_sources": adopted})
    material = context.seal({"purpose": "source_materials", "scan_ref": request["scan_ref"], "scan_digest": scan["digest"], "bundle_ref": bundle_ref,
                             "bundle_digest": combined["digest"], "bundles": bundles, "candidates": candidate_records,
                             "current_code": current_code, "gaps": gaps, "unit_ids": [u["unit_id"] for u in units]}, "artifact_manifest")
    ref = context.base + "/material.json"
    context.save(ref, material)
    return {"material_ref": ref, "material_digest": material["digest"], "bundle_ref": bundle_ref,
            "scan_ref": request["scan_ref"], "gaps": gaps}, "prepared"
