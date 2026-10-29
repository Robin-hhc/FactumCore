"""One source entry: fixed current observation, then exact reading material."""

from scan import scan, scopes


def _checked_inventory(context, reference, *, own_operation=False):
    inventory = context.record(reference, "source_inventory")
    context.modules["records"].validate_scan_manifest(inventory, context.rules)
    if own_operation and inventory["operation_id"] != context.operation:
        raise context.modules["runtime"].NodeError(
            "RUN_SCAN_OPERATION_MISMATCH", "run's fixed inventory belongs to another operation; adopt it with prepare",
            reference,
        )
    return inventory


def _scan_data(inventory, reference):
    current = inventory.get("current_context", {})
    return {
        "scan_ref": reference, "scan_digest": inventory["digest"], "complete": inventory["complete"],
        "affected_claims": current.get("affected_claims", []), "context_gaps": current.get("gaps", []),
        "finalization_pending": [], "historical_finalization_unknown": [],
        "execution_history": {"status": "not_inspected"},
        "actionable_unit_ids": [unit["unit_id"] for unit in inventory["units"] if unit["change"] != "unchanged"],
        "unchanged_unit_ids": [unit["unit_id"] for unit in inventory["units"] if unit["change"] == "unchanged"],
    }


def _needs_material(context, inventory):
    if any(context.request.get(key) for key in (
        "targets", "candidate_card_ids", "topics", "code_bundle_refs", "unit_ids",
        "existing_material_ref", "previous_view_ref",
    )):
        return True
    current = inventory.get("current_context")
    if (inventory.get("complete") is not True or not isinstance(current, dict)
            or current.get("complete") is not True or current.get("affected_claims") or current.get("gaps")):
        return True
    state = current.get("state", {})
    if state.get("pending_event_ids") or state.get("pending_events"):
        return True
    return any(unit.get("change") != "unchanged" for unit in inventory["units"])


def _material_request(context, inventory, reference):
    request = {**context.request, "scan_ref": reference}
    if "unit_ids" in request or not request.get("candidate_card_ids"):
        return request
    if request.get("source") is not None:
        request["unit_ids"] = [unit["unit_id"] for unit in inventory["units"]]
        return request
    cards = {card["metadata"]["id"]: card for card in context.modules["source_materials"].domain_cards(context)}
    selected, unmatched = set(), []
    for identity in request["candidate_card_ids"]:
        source_ids = {source["source_id"] for source in cards.get(identity, {}).get("metadata", {}).get("sources", [])}
        matches = {unit["unit_id"] for unit in inventory["units"] if unit["source_id"] in source_ids}
        if not matches:
            unmatched.append(identity)
        selected.update(matches)
    if unmatched:
        raise context.modules["runtime"].NodeError(
            "REVISION_SOURCE_REQUIRED", "Requested cards have no matching observed raw unit; supply an explicit source or use prepare",
            ",".join(sorted(set(unmatched))), blocked=True,
            data={"needs_explicit_source": True, "candidate_card_ids": sorted(set(unmatched))},
        )
    request["unit_ids"] = [unit["unit_id"] for unit in inventory["units"] if unit["unit_id"] in selected]
    return request


def _check_retry_sources(context, inventory, request):
    """A frozen retry detects drift before an existing capture slot can conflict."""
    selected = set(request["unit_ids"]) if "unit_ids" in request else None
    for unit in inventory["units"]:
        if ((selected is not None and unit["unit_id"] not in selected)
                or (selected is None and unit["change"] == "unchanged")
                or unit["change"] in {"missing", "read_failed"} or not unit.get("observed_fingerprint")):
            continue
        try:
            member = context.modules["source_operations"].raw_member(context, unit["path"])
        except (OSError, ValueError) as exc:
            if not isinstance(exc, OSError) and getattr(exc, "code", None) not in {
                    "SOURCE_MISSING", "SOURCE_CHANGED", "INPUT_CHANGED"}:
                raise
            member = None
        if member is None or context.modules["runtime"].sha(member["data"]) != unit["observed_fingerprint"]:
            raise context.modules["runtime"].NodeError(
                "SOURCE_CHANGED", "Selected source differs from the saved observation; refresh the affected input",
                unit["path"], blocked=True, data={"needs_scan": True, "affected_scope": [unit["path"]]},
            )


def _run(context):
    runtime = context.modules["runtime"]
    reference = context.base + "/source-inventory.json"
    stage, saved_reference = "scan", None
    try:
        supplied = context.request.get("scan_ref")
        if supplied is not None and supplied != reference:
            raise runtime.NodeError(
                "RUN_SCAN_REF_SCOPE", "run uses this operation's fixed inventory; adopt external scans with prepare",
                supplied,
            )
        saved = runtime.safe(context.root, reference).is_file()
        if saved:
            saved_reference = reference
            inventory = _checked_inventory(context, reference, own_operation=True)
            expected_scope, full_scan = scopes(context.request)
            if inventory["scope"] != expected_scope or inventory["full_scan"] != full_scan:
                raise runtime.NodeError(
                    "RUN_SCOPE_CHANGED", "A retry cannot replace its original source scope; use a new operation",
                    reference,
                )
        else:
            scan_context = runtime.fork_context(context, action="scan")
            scan(scan_context)
            saved_reference = reference
            inventory = _checked_inventory(context, reference, own_operation=True)
        observed = _scan_data(inventory, reference)
        if not _needs_material(context, inventory):
            if saved:
                raise runtime.NodeError(
                    "FRESH_OBSERVATION_REQUIRED", "An old no-op inventory cannot assert current state; run a new operation",
                    reference, blocked=True, data={"needs_scan": True, "affected_scope": inventory["scope"]},
                )
            return observed, "unchanged"
        stage = "prepare"
        material_request = _material_request(context, inventory, reference)
        if saved:
            _check_retry_sources(context, inventory, material_request)
        prepared_context = runtime.fork_context(
            context, request=material_request, action="prepare",
        )
        data, phase = context.modules["source_materials"].execute(prepared_context)
        return {**observed, **data}, phase
    except Exception as exc:
        if saved_reference is None and runtime.safe(context.root, reference).is_file():
            saved_reference = reference
        exc.data = {**dict(getattr(exc, "data", {}) or {}), "stopped_stage": stage,
                    **({"scan_ref": saved_reference} if saved_reference else {})}
        raise


def execute(context):
    action = context.args.action or "run"
    if action == "run":
        return _run(context)
    if action == "scan":
        return scan(context)
    if action == "prepare":
        if context.request.get("scan_ref"):
            try:
                _checked_inventory(context, context.request["scan_ref"])
            except ValueError as exc:
                if getattr(exc, "code", None) != "STALE_RULES":
                    raise
                # The public material engine preserves its original rules-drift
                # diagnosis. Other invalid inventories are never delegated.
        return context.modules["source_materials"].execute(context)
    if action == "record":
        from record import record
        return record(context)
    if action == "status":
        from status import status
        return status(context)
    if action in {"capture", "resolve", "resolve-source"}:
        return context.modules["source_operations"].execute(context)
    raise context.modules["runtime"].NodeError(
        "UNKNOWN_ACTION", "Expected run, scan, prepare, capture, resolve, resolve-source, record or status", action,
    )
