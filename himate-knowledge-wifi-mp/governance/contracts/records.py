"""Record integrity and exact-view Agent review summaries."""

from .validation import ContractError, digest_payload, validate_shape


def seal(record):
    result = dict(record)
    result["digest"] = digest_payload(result)
    return result


def verify(record, expected=None):
    if not isinstance(record, dict) or record.get("digest") != digest_payload(record):
        raise ContractError("RECORD_DIGEST_MISMATCH", "Record fields changed")
    if record.get("schema_version") != "2.0":
        raise ContractError("UNSUPPORTED_RECORD_VERSION", "Expected 2.0")
    for field, value in (expected or {}).items():
        if record.get(field) != value:
            raise ContractError("RECORD_BINDING_MISMATCH", field)
    return record


def rebuild_restrictions(records, rules=None, *, cards=None, _validated_records=()):
    """Reconstruct unresolved shared facts; input authenticity belongs to caller.

    No timestamps, names, raw text or local events choose a winner. A restriction
    is cleared only by a same-Claim descendant's explicit disposition. Workflow
    review/approval credentials do not determine record validity.
    """
    import re
    unresolved = {"defer", "failed", "uncovered", "pending", "blocked", "partial"}
    gaps, by_digest, blocks, resolutions = [], {}, [], []
    paths = {}
    if cards is not None:
        values = cards.values() if isinstance(cards, dict) else cards
        for card in values:
            if isinstance(card, dict) and "metadata" in card:
                paths[card.get("path")] = card["metadata"]["id"]

    def gap(code, reason, record=None):
        gaps.append({"code": code, "reason": str(reason), "record_digest": (record or {}).get("digest")})

    def add(record, card_id, claim_id, row):
        if not isinstance(card_id, str) or not card_id or not isinstance(claim_id, str) or not claim_id:
            gap("PROCESSING_TARGET_UNAVAILABLE", "An unresolved fact needs an explicit Card/Claim identity", record)
            return
        conditions = row.get("conditions", {})
        if not isinstance(conditions, dict):
            gap("PROCESSING_SCOPE_INVALID", "Restriction conditions must be a fixed object", record)
            return
        blocks.append({"card_id": card_id, "claim_id": claim_id, "reason": "shared_pending_review", "details": row.get("reason", "Unresolved shared processing fact"),
                       "record_digest": record["digest"], "record_id": record.get("record_id", record["operation_id"]), "conditions": conditions})

    validated_ids = {id(record) for record in _validated_records}
    for record in records:
        try:
            # Only reuse this call's exact in-memory objects after the caller's
            # stronger validation. No saved report or request flag is accepted.
            if id(record) not in validated_ids:
                validate_ingest_record(record, rules=rules)
            parents = record.get("prior_record_digests", [])
            if not isinstance(parents, list) or len(parents) != len(set(parents)) or any(not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item) for item in parents):
                raise ContractError("PROCESSING_PARENT_INVALID", "Record predecessors need distinct fixed fingerprints")
            by_digest[record["digest"]] = record
        except (ContractError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            gap("PROCESSING_RECORD_INVALID", exc, record if isinstance(record, dict) else None)
    for record in by_digest.values():
        for parent in record.get("prior_record_digests", []):
            if parent not in by_digest:
                gap("PROCESSING_PARENT_UNAVAILABLE", "A declared shared predecessor is unavailable", record)
        pending = record.get("pending", [])
        maintenance = record.get("maintenance_dispositions", [])
        if not isinstance(pending, list) or not isinstance(maintenance, list):
            gap("PROCESSING_FACTS_INVALID", "Pending and maintenance facts must be lists", record)
            continue
        for row in pending:
            # Machine target fields only: never infer an identity from prose.
            if not isinstance(row, dict):
                gap("PROCESSING_FACTS_INVALID", "Pending facts must be explicit objects", record)
            elif "card_id" in row or "claim_id" in row:
                if row.get("outcome", row.get("status")) in unresolved:
                    add(record, row["card_id"], row["claim_id"], row)
                else:
                    gap("PROCESSING_OUTCOME_UNAVAILABLE", "An explicit pending target has no unresolved outcome", record)
        for row in maintenance:
            target = (row["card_id"], row["claim_id"])
            if any(not isinstance(value, str) or not value for value in target):
                gap("PROCESSING_TARGET_UNAVAILABLE", "Maintenance facts need fixed Card/Claim identities", record)
                continue
            if row["outcome"] in unresolved:
                add(record, *target, row)
            elif row["outcome"] in {"content", "skip"}:
                # The disposition is business data, not proof that a predecessor
                # passed. Exact card/Claim bindings are checked independently.
                resolutions.append((record["digest"], target))
        for row in record["dispositions"]:
            status = row["progress"].get("status") if isinstance(row["progress"], dict) else row["progress"]
            if status not in {"pending", "blocked", "partial"} or row["action"] not in {"defer", "failed", "uncovered"}:
                continue
            for ref in row.get("claim_refs", []):
                if isinstance(ref, dict):
                    card_id, claim_id = ref.get("card_id"), ref.get("claim_id")
                else:
                    card_id, claim_id = ref.rsplit("#", 1)
                if isinstance(card_id, str) and "/" in card_id:
                    card_id = paths.get(card_id)
                add(record, card_id, claim_id, row)

    bad_lineage = set()
    def ancestors(identity, trail=()):
        if identity in trail:
            bad_lineage.add(identity)
            gap("PROCESSING_PARENT_CYCLE", "Shared processing predecessors contain a cycle", by_digest[identity])
            return set()
        result = set()
        for parent in by_digest[identity].get("prior_record_digests", []):
            if parent in by_digest:
                result.add(parent)
                result.update(ancestors(parent, (*trail, identity)))
                if parent in bad_lineage:
                    bad_lineage.add(identity)
            else:
                bad_lineage.add(identity)
        return result
    closure = {identity: ancestors(identity) for identity, _ in resolutions}
    unique = {}
    for block in blocks:
        if any(identity not in bad_lineage and block["record_digest"] in closure[identity] and (block["card_id"], block["claim_id"]) == target for identity, target in resolutions):
            continue
        key = (block["record_digest"], block["card_id"], block["claim_id"], str(block["conditions"]))
        unique[key] = block
    return {"complete": not gaps, "blocked_claims": sorted(unique.values(), key=lambda row: (row["card_id"], row["claim_id"], row["record_digest"])), "gaps": gaps}


def validate_record_shape(record, rules):
    return validate_shape("record", record, rules)


def validate_record_binding(record, expected):
    return verify(record, expected)


def validate_scan_manifest(record, rules=None):
    """Validate observed input, without treating an observation as adoption."""
    verify(record)
    if record.get("record_kind") != "source_inventory":
        raise ContractError("RECORD_KIND_MISMATCH", "Expected source_inventory")
    required = ("operation_id", "scope", "full_scan", "complete", "units")
    if any(key not in record for key in required) or not isinstance(record["units"], list):
        raise ContractError("INVALID_SCAN", "A fixed scan with units is required")
    identities = [unit.get("unit_id") for unit in record["units"]]
    if any(not item for item in identities) or len(set(identities)) != len(identities):
        raise ContractError("INVALID_SCAN", "Distinct unit identities are required")
    if rules:
        validate_shape("source_inventory", record, rules)
    return record


validate_scan = validate_scan_manifest


def validate_ingest_record(record, scan=None, view=None, rules=None, *, version_resolver=None, require_final=False):
    """Validate per-unit dispositions and their exact reviewed content bindings."""
    verify(record)
    if record.get("record_kind") != "ingest_record":
        raise ContractError("RECORD_KIND_MISMATCH", "Expected ingest_record")
    required = ("operation_id", "scan_ref", "scan_digest", "dispositions")
    if any(key not in record for key in required) or not isinstance(record["dispositions"], list):
        raise ContractError("INVALID_INGEST_RECORD", "A fixed scan and dispositions are required")
    pending = record.get("pending", [])
    if not isinstance(pending, list) or any(not isinstance(item, dict) for item in pending):
        raise ContractError("INVALID_PENDING", "Pending facts must be a list of structured objects")
    for item in pending:
        if "card_id" in item or "claim_id" in item:
            if not all(isinstance(item.get(key), str) and item[key] for key in ("card_id", "claim_id")) or item.get("outcome", item.get("status")) not in {"defer", "failed", "uncovered", "pending", "blocked", "partial"}:
                raise ContractError("INVALID_PENDING", "Pending Card/Claim targets must be paired with an unresolved outcome")
    stage = record.get("progress", {}).get("apply", {}) if isinstance(record.get("progress"), dict) else {}
    if isinstance(stage, dict) and stage.get("view_digest") is not None and record.get("content_view_digest") is not None and stage["view_digest"] != record["content_view_digest"]:
        raise ContractError("RECORD_VIEW_MISMATCH", "Recorded application and content view fingerprints differ")
    if require_final:
        expected = "recorded" if record.get("batch_kind") == "record_only" else "applied"
        stage = record.get("progress", {}).get("apply", {}) if isinstance(record.get("progress"), dict) else {}
        if not isinstance(stage, dict) or record.get("batch_kind") not in {"record_only", "content"} or record.get("status") != expected or stage.get("status") != expected or stage.get("operation_id") != record["operation_id"]:
            raise ContractError("RECORD_NOT_FINAL", "Formal processing records must contain the final P7 application fact")
        if record["batch_kind"] == "content" and (not record.get("content_view_digest") or stage.get("view_digest") != record["content_view_digest"]):
            raise ContractError("RECORD_NOT_FINAL", "The applied content view must match the formal record")
    ids = [item.get("unit_id") for item in record["dispositions"]]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise ContractError("UNIT_COVERAGE_INVALID", "Disposition coverage contains duplicate units")
    if scan is None and not isinstance(record.get("inventory"), dict):
        raise ContractError("SCAN_INPUT_UNAVAILABLE", "A shared processing record requires its self-contained fixed scan inventory")
    scan = scan if scan is not None else record.get("inventory")
    units = {}
    cards = {}
    source_versions = {item["snapshot_id"]: item for item in (rules or {}).get("source_lock", {}).get("snapshots", [])} if (rules or {}).get("source_lock") else {}
    if view is not None:
        import base64
        from pathlib import PurePosixPath
        from .knowledge import decode_card
        from .validation import load_yaml, safe_path
        if isinstance(view, dict) and "writes" in view:
            # A FinalView is an overlay, including for record-only batches.
            # Unrelated malformed cards must not prevent recording failure facts.
            if rules is not None:
                import os
                from pathlib import Path
                def read(path):
                    text = str(Path(path).absolute())
                    if os.name == "nt" and not text.startswith("\\\\?\\"):
                        text = "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
                    return Path(text).read_bytes()
                root = Path(rules["knowledge_root"])
                replaced = {item["path"] for item in view.get("writes", []) + view.get("deletes", [])}
                try:
                    lock = load_yaml(read(safe_path(root, "governance/sources.lock.yaml")))
                    source_versions.update({item["snapshot_id"]: item for item in lock["snapshots"]})
                except (ContractError, OSError, ValueError, KeyError, TypeError):
                    pass
                directory = safe_path(root, "knowledge")
                if directory.exists():
                    for path in directory.rglob("*.md"):
                        relative = path.relative_to(root).as_posix()
                        if relative in replaced or path.name in {"index.md", "AGENTS.md", "README.md"}:
                            continue
                        try:
                            card = decode_card(read(safe_path(root, relative)), relative, rules)
                        except (ContractError, OSError, ValueError, KeyError, TypeError):
                            continue
                        cards[card["metadata"]["id"]] = card
                        cards[relative] = card
            for write in view["writes"]:
                path = write["path"]
                raw = base64.b64decode(write["bytes_b64"], validate=True)
                if path == "governance/sources.lock.yaml":
                    source_versions = {item["snapshot_id"]: item for item in load_yaml(raw)["snapshots"]}
                elif path.startswith("knowledge/") and path.endswith(".md") and PurePosixPath(path).name not in {"index.md", "AGENTS.md"}:
                    if rules is None:
                        raise ContractError("CARD_INPUT_UNAVAILABLE", "Card validation requires the pinned rules")
                    card = decode_card(raw, path, rules)
                    cards[card["metadata"]["id"]] = card
                    cards[path] = card
        else:
            values = view.values() if isinstance(view, dict) else view
            for card in values:
                if isinstance(card, dict) and "metadata" in card:
                    cards[card["metadata"]["id"]] = card
                    cards[card["path"]] = card
    if scan is not None:
        validate_scan_manifest(scan, rules)
        if record["scan_digest"] != scan["digest"]:
            raise ContractError("SCAN_BINDING_MISMATCH", "Ingest record differs from its exact scan")
        origin = record.get("origin_scan_operation_id")
        if origin is not None and origin != scan["operation_id"]:
            raise ContractError("SCAN_BINDING_MISMATCH", "Origin differs from the actual original inventory")
        if record["operation_id"] != scan["operation_id"]:
            links = ("semantic_plan_ref", "material_ref", "view_ref", "previous_view_ref", "revision_reason")
            digests = ("semantic_plan_digest", "material_digest", "previous_view_digest", "content_view_digest")
            if (origin != scan["operation_id"] or any(not isinstance(record.get(key), str) or not record[key].strip() for key in links)
                    or record["view_ref"] == record["previous_view_ref"]
                    or any(not isinstance(record.get(key), str) or len(record[key]) != 64
                           or any(char not in "0123456789abcdef" for char in record[key]) for key in digests)):
                raise ContractError("SCAN_ADOPTION_REQUIRED", "A new operation needs the exact semantic, material and previous-view adoption")
            if view is not None:
                verify(view)
                expected = {"record_kind": "final_view", "operation_id": record["operation_id"], "digest": record["content_view_digest"],
                            "scan_ref": record["scan_ref"],
                            "origin_scan_operation_id": origin,
                            **{key: record[key] for key in ("semantic_plan_ref", "semantic_plan_digest", "material_ref", "material_digest",
                                                          "previous_view_ref", "previous_view_digest", "revision_reason")}}
                if any(view.get(key) != value for key, value in expected.items()):
                    raise ContractError("SCAN_ADOPTION_MISMATCH", "New operation record differs from the actual adopted candidate")
        units = {item["unit_id"]: item for item in scan["units"]}
        if set(ids) != set(units):
            raise ContractError("UNIT_COVERAGE_INVALID", "Disposition coverage must match the fixed scan units exactly")
    record_cards = {}
    record_card_versions = {}

    def resolve_version(reference, item):
        directed = getattr(version_resolver, "resolve_disposition", None)
        return directed(reference, record, item) if callable(directed) else version_resolver(reference, record)

    def remember(card):
        metadata = card.get("metadata", card)
        identity = metadata["id"]
        version = (card.get("sha256"), card.get("path"))
        if not all(version):
            version += (digest_payload({"metadata": metadata}),)
        previous = record_card_versions.get(identity)
        if previous is not None and previous != version:
            raise ContractError("CARD_VERSION_MISMATCH", "A record must use one exact card body for all its dispositions and Claims", str(identity))
        record_card_versions[identity] = version
        record_cards[identity] = card

    for item in record["dispositions"]:
        required_item = ("unit_id", "action", "reason", "observed_fingerprint", "adopted_fingerprint", "progress", "card_refs", "claim_refs")
        if any(key not in item for key in required_item) or not item.get("reason"):
            raise ContractError("INVALID_DISPOSITION", "A reason, fingerprints, progress and explicit card/Claim references are required")
        progress = item["progress"]
        progress = progress.get("status") if isinstance(progress, dict) else progress
        if progress not in {"pending", "blocked", "partial", "completed", "skipped", "withdrawn"}:
            raise ContractError("INVALID_PROGRESS", "Unknown processing progress")
        if item["action"] not in {"create", "update", "merge", "split", "deprecate", "defer", "skip", "failed", "uncovered"}:
            raise ContractError("INVALID_DISPOSITION", "Unknown disposition action")
        unit = units.get(item["unit_id"])
        if unit and item["observed_fingerprint"] != unit.get("observed_fingerprint"):
            raise ContractError("OBSERVATION_MISMATCH", "Disposition must bind the exact observed version")
        if unit and (unit.get("read_error") or unit.get("change") == "read_failed") and progress in {"completed", "skipped", "withdrawn"}:
            raise ContractError("INCOMPLETE_SOURCE_DISPOSITION", "Unreadable input must remain pending, blocked or partial")
        if progress == "completed":
            if not item["adopted_fingerprint"] or item["adopted_fingerprint"] != item["observed_fingerprint"]:
                raise ContractError("ADOPTION_REQUIRED", "Completed content requires the exact adopted version")
            if unit and unit.get("read_error"):
                raise ContractError("ADOPTION_REQUIRED", "Unreadable input cannot be adopted")
            if not item["card_refs"] and not item.get("document_scope_reviewed"):
                raise ContractError("ADOPTION_REQUIRED", "Completed adoption needs associated cards or explicit reviewed document scope")
        if item["action"] in {"failed", "defer", "uncovered"} and progress == "completed":
            raise ContractError("ADOPTION_REQUIRED", "Unresolved work cannot be adopted")
        if item.get("kind") == "scan_unchanged" and unit and unit.get("change") != "unchanged":
            raise ContractError("SKIP_SAMPLE_REQUIRED", "Only an unchanged observation can be a scan-only skip")
        resolved_cards = []
        disposition_cards = {}
        for reference in item["card_refs"]:
            identity = reference.get("card_id", reference.get("path")) if isinstance(reference, dict) else reference
            card = resolve_version(reference, item) if version_resolver is not None else cards.get(identity)
            if (view is not None or version_resolver is not None) and not card:
                raise ContractError("DANGLING_CARD_RECORD", "Processing record references an unavailable card", str(identity))
            if card:
                meta = card.get("metadata", card)
                if isinstance(reference, dict) and reference.get("sha256") and card.get("sha256") != reference["sha256"]:
                    raise ContractError("CARD_VERSION_MISMATCH", "Processing record card fingerprint differs", str(identity))
                resolved_cards.append(card)
                disposition_cards.setdefault(meta["id"], card)
                if card.get("path"):
                    disposition_cards.setdefault(card["path"], card)
                remember(card)
                cards.setdefault(meta["id"], card)
        for reference in item["claim_refs"]:
            if isinstance(reference, dict):
                card_id, claim_id = reference.get("card_id"), reference.get("claim_id")
            elif isinstance(reference, str) and "#" in reference:
                card_id, claim_id = reference.rsplit("#", 1)
            else:
                raise ContractError("INVALID_CLAIM_RECORD", "Claim reference needs card_id and claim_id")
            card = disposition_cards.get(card_id, record_cards.get(card_id))
            if card is None:
                card = resolve_version({"card_id": card_id, "claim_id": claim_id}, item) if version_resolver is not None else cards.get(card_id)
            if (view is not None or version_resolver is not None) and (not card or claim_id not in {claim["id"] for claim in card.get("metadata", card)["claims"]}):
                raise ContractError("DANGLING_CLAIM_RECORD", "Processing record Claim does not exist", str(claim_id))
            if card:
                remember(card)
        if progress == "completed" and unit and resolved_cards:
            matching = [source for card in resolved_cards for source in card.get("metadata", card)["sources"] if source["source_id"] == unit["source_id"]]
            if not matching:
                raise ContractError("ADOPTION_SOURCE_MISMATCH", "Adopted source is not associated with the recorded cards")
            if source_versions and not any(source_versions.get(source["snapshot_id"], {}).get("source_id") == unit["source_id"]
                                           and source_versions.get(source["snapshot_id"], {}).get("sha256") == item["adopted_fingerprint"] for source in matching):
                raise ContractError("ADOPTION_SOURCE_MISMATCH", "Adopted source version differs from the exact cards")
    expected_maintenance = {(item.get("card_id"), item.get("claim_id")) for item in (scan or {}).get("current_context", {}).get("affected_claims", [])}
    maintenance = record.get("maintenance_dispositions", [])
    actual_maintenance = [(item.get("card_id"), item.get("claim_id")) for item in maintenance]
    if len(set(actual_maintenance)) != len(actual_maintenance) or set(actual_maintenance) != expected_maintenance:
        raise ContractError("MAINTENANCE_COVERAGE_INVALID", "Maintenance dispositions must cover the fixed affected Card/Claim set")
    for item in maintenance:
        expected_id = "maintenance:" + str(item["card_id"]) + "#" + str(item["claim_id"])
        if item.get("unit_id") != expected_id or item.get("outcome") not in {"content", "skip", "defer", "failed", "uncovered"} or not item.get("reason"):
            raise ContractError("MAINTENANCE_DISPOSITION_INVALID", "Maintenance needs one fixed identity, outcome and reason")
        if item["outcome"] == "content":
            if record.get("batch_kind") == "record_only":
                raise ContractError("MAINTENANCE_CONTENT_VIEW_REQUIRED", "Maintenance content cannot be adopted by a record-only batch")
            if view is not None and item["card_id"] not in cards:
                raise ContractError("MAINTENANCE_CONTENT_VIEW_REQUIRED", "Maintenance content needs a card in the exact view")
    acceptance = record.get("acceptance")
    if acceptance is not None:
        import re
        digest_pattern = r"[0-9a-f]{64}"
        if not isinstance(acceptance, dict) or acceptance.get("content_view_digest") != record.get("content_view_digest") or acceptance.get("rules_digest") != record.get("rules_digest"):
            raise ContractError("ACCEPTANCE_BINDING_MISMATCH", "Acceptance summary differs from its record")
        proofs = acceptance.get("proof_digests", [])
        if not isinstance(acceptance.get("cards"), list) or not isinstance(proofs, list) or any(not isinstance(value, str) or not re.fullmatch(digest_pattern, value) for value in proofs):
            raise ContractError("INVALID_ACCEPTANCE", "Acceptance requires exact cards and valid optional proof fingerprints")
        seen = set()
        for summary in acceptance["cards"]:
            required_summary = ("path", "card_id", "sha256", "review_mode", "claim_ids", "review_result")
            if any(key not in summary for key in required_summary) or summary["card_id"] in seen or not re.fullmatch(digest_pattern, summary["sha256"]):
                raise ContractError("INVALID_ACCEPTANCE", "Acceptance card summary is incomplete or duplicate")
            seen.add(summary["card_id"])
            expected = "supported" if summary["review_mode"] in {"manual_document", "code_gate"} else None
            if summary["review_result"] not in {expected, "retired"} or expected is None or not summary["claim_ids"] or len(set(summary["claim_ids"])) != len(summary["claim_ids"]):
                raise ContractError("INVALID_ACCEPTANCE", "Acceptance Claim identities or review result differ")
            card = record_cards.get(summary["card_id"], cards.get(summary["card_id"]))
            if card and (card["sha256"] != summary["sha256"] or card["path"] != summary["path"] or set(summary["claim_ids"]) != {claim["id"] for claim in card["metadata"]["claims"]} or card["metadata"]["review_mode"] != summary["review_mode"]):
                raise ContractError("ACCEPTANCE_CARD_MISMATCH", "Acceptance summary differs from exact card/Claim bytes")
    if rules:
        validate_shape("ingest_record", record, rules)
    return record
