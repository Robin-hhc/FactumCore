"""Scripted governance observations, ingest handoff, and successful-baseline CAS.

Git is a candidate-path accelerator, never the success ledger. Only completion
after real source dispositions, current restrictions and retrieval can advance
the baseline. Git-MM adaptation belongs to patrol_git; no mm subcommand is
inferred here. Indirect semantic dependencies are intentionally outside scope.
"""
from __future__ import annotations

import copy

from .runtime import NodeError, canonical, digest, fixed_bytes, fork_context, read_json, safe, sha, write_bytes
from . import maintenance, patrol_git, patrol_index, publication, reference_audit, source_inventory


PROTOCOL = "1.0"
STATE_REF = ".build/runtime/patrol-state.json"


def _base(ctx):
    # P7 owns and removes producer-private files. Governance observations must
    # survive that cleanup so completion can verify the original handoff.
    return "logs/patrol/" + ctx.operation


def _state(ctx):
    if not safe(ctx.root, STATE_REF).exists():
        return None
    value = read_json(safe(ctx.root, STATE_REF))
    ctx.modules["records"].verify(value)
    if value.get("purpose") != "patrol_success_baseline" or value.get("protocol_version") != PROTOCOL:
        raise NodeError("PATROL_STATE_INVALID", "Successful patrol baseline has an unsupported identity")
    return value


def _formal(ctx):
    view, _ = reference_audit.formal_snapshot(ctx)
    rows = {ref: sha(raw) for ref, raw in view["files"].items()}
    state = "logs/events/state.json"
    if safe(ctx.root, state).is_file():
        rows[state] = sha(fixed_bytes(ctx.root, state))
    # Published old originals are durable inputs, not an expendable local
    # cache. Losing one must invalidate the successful fast path as surely as
    # changing a formal card or source-lock entry does.
    evidence = safe(ctx.root, "logs/evidence/published")
    if evidence.exists():
        for path in sorted(evidence.rglob("*")):
            if path.is_file():
                ref = path.relative_to(ctx.root).as_posix()
                rows[ref] = sha(fixed_bytes(ctx.root, ref, ["logs/evidence/published"]))
    return rows


def _raw(ctx, scope):
    found, errors, complete = source_inventory.observe(ctx, scope)
    return {"files": found, "errors": errors, "complete": complete}


def _metadata(ctx, formal, config):
    return digest({"rules_digest": ctx.args.rules_digest, "config_digest": config["sha256"],
        "formal": {ref: value for ref, value in formal.items() if not ref.startswith("logs/ingest/")}})


def _pending_publications(ctx):
    """Inspect formal publications only; never discover abandoned private stages."""
    pending, gaps = [], []
    root = safe(ctx.root, "logs/publications")
    if root.exists():
        for path in sorted(root.glob("*/manifest.json")):
            ref = path.relative_to(ctx.root).as_posix()
            try:
                manifest = publication.read_manifest(ctx, ref)
                completion = publication.read_completion(ctx, manifest)
                if not completion or not completion["batch_complete"]:
                    operation = manifest["operation_id"]
                    pending.append({"operation_id": operation, "publication_ref": ref,
                        "completion_ref": publication.completion_ref(operation),
                        "resume_request": {"operation_id": operation}, "resume_action": "batch"})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                gaps.append(reference_audit.issue("PATROL_PUBLICATION_UNAVAILABLE", exc, path=ref))
    return pending, gaps


def _read_plan(ctx):
    ref = ctx.request.get("plan_ref", ctx.request.get("patrol_plan_ref"))
    if not ref:
        raise NodeError("PATROL_PLAN_REQUIRED", "Supply the exact patrol plan_ref")
    value = ctx.record(ref, "artifact_manifest")
    if (value.get("purpose") != "patrol_plan" or value.get("protocol_version") != PROTOCOL
            or ref != "logs/patrol/" + value["operation_id"] + "/plan.json"):
        raise NodeError("PATROL_PLAN_INVALID", "This is not the fixed governance plan", ref)
    if ctx.request.get("plan_digest", value["digest"]) != value["digest"]:
        raise NodeError("PATROL_PLAN_CHANGED", "Requested governance plan digest differs", ref)
    return ref, value


def _config(ctx):
    # Even an empty code list uses real workspace configuration: a missing or
    # malformed configuration is an explicit environment gap, not health.
    return reference_audit.configuration(ctx)


def _code_rows(ctx, cards, lock):
    resources = {row["source_id"]: row for row in lock["resources"]}
    rows = []
    for card in cards:
        for source in card["metadata"]["sources"]:
            resource = resources.get(source["source_id"])
            if resource is None:
                raise NodeError("PATROL_SOURCE_UNREGISTERED", "Formal card references an unregistered source", source["source_id"])
            if resource.get("kind") == "code":
                locator = source["locator"]
                rows.append((card, source, {**resource,
                    "repo_id": locator.get("repo_id") or resource["repo_id"],
                    "path": locator.get("path") or resource["path"]}))
    return rows


def _structure(rows):
    return [{"code": "CODE_REF_REQUIRED", "card_id": card["metadata"]["id"],
             "evidence_ref": source["evidence_ref"], "path": card["path"],
             "reason": "An active code metadata reference needs an explicit symbolic code_ref"}
            for card, source, _ in rows
            if card["metadata"]["lifecycle"] != "deprecated" and "code_ref" not in source]


def _processing_context(ctx, cards):
    """Use shared per-Claim lineage, including code-only records with no raw units."""
    records, _ = source_inventory.histories(ctx)
    result = ctx.modules["records"].rebuild_restrictions(records, rules=ctx.rules, cards=cards)
    result["gaps"].extend(reference_audit.issue("PATROL_PROCESSING_NOT_APPLIED", "A formal processing record has no actual applied terminal", record_id=record["record_id"])
                          for record in records if not source_inventory.record_applied(record))
    existing = {(card["metadata"]["id"], claim["id"]) for card in cards for claim in card["metadata"]["claims"]}
    result["gaps"].extend(reference_audit.issue("PATROL_PENDING_TARGET_UNAVAILABLE", "Unresolved processing facts name an absent Card or Claim", card_id=row["card_id"], claim_id=row["claim_id"])
                          for row in result["blocked_claims"] if (row["card_id"], row["claim_id"]) not in existing)
    return result


def _retired_context(ctx, inspection, cards):
    """Retirement drops current navigation duties, never old-evidence/debt duties."""
    retired = {card["metadata"]["id"]: card for card in cards if card["metadata"]["lifecycle"] == "deprecated"}
    result, recoveries = [], {}
    for row in inspection.get("affected_claims", []):
        reason = row.get("reason", "")
        if row["card_id"] not in retired or not (reason in {"source_changed", "code_changed", "code_source_changed"}
                                                  or reason.startswith("code_navigation_")):
            result.append(row)
            continue
        card = retired[row["card_id"]]
        claims = [claim for claim in card["metadata"]["claims"] if claim["id"] == row["claim_id"]]
        evidence = {value for claim in claims for value in claim["source_refs"]}
        sources = [source for source in card["metadata"]["sources"] if source["evidence_ref"] in evidence
                   and (not row.get("source_id") or source["source_id"] == row["source_id"])]
        for source in sources:
            key = digest(source)
            if key not in recoveries:
                try:
                    observed = ctx.modules["source_operations"].resolve_source(ctx, source)
                    recoveries[key] = observed.get("text") is not None
                except (OSError, ValueError, KeyError, TypeError):
                    recoveries[key] = False
        if not sources or not all(recoveries[digest(source)] for source in sources):
            result.append(row)
    return {**inspection, "affected_claims": result}


def _retired_reference(ctx, card, source, row, observed):
    if card["metadata"]["lifecycle"] != "deprecated":
        return row
    try:
        original = ctx.modules["source_operations"].resolve_source(ctx, source)
        if original.get("text") is None:
            return row
    except (OSError, ValueError, KeyError, TypeError):
        return row
    current_codes = {gap["code"] for gap in [observed.get("gap")] if gap}
    navigation = row.get("code_navigation", {})
    if navigation.get("status") == "unavailable":
        current_codes.add(navigation.get("code"))
    row["ignored_current_gaps"] = [gap for gap in row["gaps"] if gap["code"] in current_codes]
    row["gaps"] = [gap for gap in row["gaps"] if gap["code"] not in current_codes]
    row["effect"] = "historical_reference"
    row["suggestion"] = "Retired card: old evidence was actually recovered; current navigation is no longer an active obligation."
    return row


def _verify_candidates(ctx, planned, cards, config):
    """Claims alone do not cover metadata-only references or absent code_ref."""
    identities = set(planned["candidate_card_ids"])
    lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
    rows = [row for row in _code_rows(ctx, cards, lock)
            if row[0]["metadata"]["id"] in identities and row[0]["metadata"]["lifecycle"] != "deprecated"]
    if _structure(rows):
        raise NodeError("PATROL_METADATA_PENDING", "An active repair candidate still has code metadata without code_ref")
    observed = {}
    for card, source, resource in rows:
        key = resource["repo_id"], resource["path"]
        if key not in observed:
            observed[key] = reference_audit.current_source(ctx, config, resource)
        row = reference_audit.reference_row(ctx, card, source, resource, lock, config, observed[key])
        if row["gaps"] or row["effect"].endswith("needs_review"):
            raise NodeError("PATROL_REFERENCE_PENDING", "A candidate's current metadata/code reference remains unresolved", card["path"])
    return [{"repo_id": key[0], "path": key[1], "observation": value["observation"], "sha256": value["current_sha256"]}
            for key, value in observed.items()]


def _binding(ctx, config, formal, raw, code):
    return {"rules_digest": ctx.args.rules_digest, "config_digest": config["sha256"],
            "formal": formal, "raw": raw, "code": code}


def _repository_gaps(observation, registered):
    gaps = []
    for gap in observation.get("gaps", []):
        if (gap.get("code") == "PATROL_GIT_UNMERGED" and gap.get("repo_id") in registered
                and isinstance(gap.get("path"), str) and gap["path"] not in registered[gap["repo_id"]]):
            # A conflict in a file this library never registered is outside
            # the explicitly agreed direct-file inspection scope.
            continue
        gaps.append(gap)
    if observation.get("complete") is not True and not observation.get("gaps"):
        gaps.append(reference_audit.issue("PATROL_GIT_OBSERVATION_INCOMPLETE", "Repository observation is incomplete without a precise gap"))
    return gaps


def _validate_inputs(ctx, plan, *, publication_manifest=None, allow_repository_gaps=False):
    """Recheck bytes, not mtime or an earlier process's 'passed' summary."""
    before = plan["inputs"]
    config = _config(ctx)
    if before["rules_digest"] != ctx.args.rules_digest or before["config_digest"] != config["sha256"]:
        raise NodeError("PATROL_INPUT_CHANGED", "Rules or workspace configuration changed after planning", blocked=True)
    expected_formal = copy.deepcopy(before["formal"])
    if publication_manifest is not None:
        # Verify every actual installed payload first. Only those exact formal
        # changes are authorized by this real publication closure.
        publication.read_manifest(ctx, publication.manifest_ref(publication_manifest["operation_id"]), verify_files=True)
        for row in publication_manifest["files"]:
            if row["path"] in expected_formal or row["path"].startswith(("knowledge/", "logs/ingest/", "logs/evidence/published/")) or row["path"] == "logs/events/state.json":
                expected_formal[row["path"]] = row["sha256"]
        for row in publication_manifest.get("deletes", []):
            expected_formal.pop(row["path"], None)
    if _formal(ctx) != expected_formal:
        raise NodeError("PATROL_INPUT_CHANGED", "Formal library changed outside the completed publication", blocked=True)
    if _raw(ctx, plan["raw_scope"]) != before["raw"]:
        raise NodeError("PATROL_INPUT_CHANGED", "Raw originals changed after planning", blocked=True)
    repositories = patrol_git.observe_repositories(ctx, config, plan["repositories"]["heads"])
    if _repository_gaps(repositories, plan["registered_code_paths"]) and not allow_repository_gaps:
        raise NodeError("PATROL_GIT_RECHECK_UNAVAILABLE", "Repository observation is incomplete during input revalidation", blocked=True)
    registered = plan["registered_code_paths"]
    observed_repos = {row["repo_id"]: sorted(set(row.get("dirty_paths", [])) & set(registered.get(row["repo_id"], [])))
                      for row in repositories["repositories"]}
    planned_repos = {row["repo_id"]: sorted(set(row.get("dirty_paths", [])) & set(registered.get(row["repo_id"], [])))
                     for row in plan["repositories"]["repositories"]}
    if repositories["heads"] != plan["repositories"]["heads"] or observed_repos != planned_repos:
        raise NodeError("PATROL_INPUT_CHANGED", "Repository HEAD or dirty path set changed after planning", blocked=True)
    for row in before["code"]:
        observed = reference_audit.current_source(ctx, config, {"repo_id": row["repo_id"], "path": row["path"]})
        if (observed["observation"], observed["current_sha256"]) != (row["observation"], row["sha256"]):
            raise NodeError("PATROL_INPUT_CHANGED", "Selected code changed after planning", row["path"], blocked=True)
    return config


def _response(plan, ref):
    return {"plan_ref": ref, "plan_digest": plan["digest"], "report_ref": ref.rsplit("/", 1)[0] + "/report.md", "scan_ref": plan.get("scan_ref"),
            "source_request": plan.get("source_request"), "complete": plan["complete"],
            "gaps": plan["gaps"], "counts": plan.get("counts", {}),
            "pending_publications": plan.get("pending_publications", [])}, plan["phase"]


def _write_report(ctx, plan, ref):
    counts = plan["counts"]
    lines = ["# 知识库治理巡检", "", "状态：" + plan["phase"], "", "固定观察：`" + ref + "`。", "",
        "| 指标 | 数值 |", "|---|---:|", *["| " + key + " | " + str(counts[key]) + " |" for key in sorted(counts)], "",
        "完整观察：" + str(plan["complete"]) + "；首次或登记/规则/配置变化全查：" + str(plan["force_full"]) + "。", "",
        "本轮仅直接登记文件及显式卡间依赖；精确字节相同不证明业务结论成立。", "", "## 仓观察", ""]
    for repo in plan["repositories"]["repositories"]:
        lines.append("- `" + repo["repo_id"] + "`：HEAD `" + str(repo.get("head")) + "`；全hash回退="
                     + str(repo.get("full_scan")) + "；原因=" + str(repo.get("fallback_reason")) + "。")
    lines += ["", "## 引用处置", ""]
    for row in plan["references"]:
        position = (row.get("code_navigation") or {}).get("range")
        lines.append("- `" + row["card_id"] + "` / `" + row["evidence_ref"] + "`：" + row["effect"]
                     + "；`" + row["repo_id"] + ":" + row["path"] + "`；当前位置=" + canonical(position).decode() + "。")
    lines += ["", "## 欠账及恢复", ""]
    lines += ["- `" + gap["code"] + "`：" + gap["reason"].replace("\n", " ") for gap in plan["gaps"]]
    lines += ["- `" + gap["code"] + "` `" + gap["card_id"] + "`：" + gap["reason"]
              for gap in plan.get("structural_findings", [])]
    for pending in plan["pending_publications"]:
        lines.append("- 精确续办 `" + pending["operation_id"] + "`：apply `batch`，请求 `"
                     + canonical(pending["resume_request"]).decode() + "`；依据 `" + pending["publication_ref"] + "`。")
    write_bytes(ctx.root, ref.rsplit("/", 1)[0] + "/report.md", "\n".join(lines).encode("utf-8"), immutable=True)


def plan(ctx):
    ref = _base(ctx) + "/plan.json"
    if safe(ctx.root, ref).exists():
        previous = ctx.record(ref, "artifact_manifest")
        if previous.get("purpose") != "patrol_plan":
            raise NodeError("PATROL_PLAN_INVALID", "Operation already owns another artifact", ref)
        if previous.get("inputs") is None:
            raise NodeError("PATROL_REPLAN_REQUIRED", "The original environment was unavailable; repair it and observe under a new operation", ref, blocked=True)
        _validate_inputs(ctx, previous)
        current = _state(ctx)
        if ((current["digest"] if current else None) != previous["baseline_digest"]
                and (current or {}).get("plan_digest") != previous["digest"]):
            raise NodeError("PATROL_BASELINE_CHANGED", "Success baseline changed since this immutable plan", blocked=True)
        _write_report(ctx, previous, ref)
        return _response(previous, ref)
    gaps, code_observations, references = [], {}, []
    config = _config(ctx)
    before_state = _state(ctx)
    formal = _formal(ctx)
    cards = ctx.modules["source_materials"].domain_cards(ctx)
    lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
    ctx.modules["validation"].validate_shape("sources", lock, ctx.rules)
    code_refs = _code_rows(ctx, cards, lock)
    structural_findings = _structure(code_refs)
    metadata = _metadata(ctx, formal, config)
    force_full = before_state is None or before_state.get("metadata_digest") != metadata
    repositories = patrol_git.observe_repositories(ctx, config, (before_state or {}).get("heads", {}))
    # Git gaps are visible degraded observations. Full-file hashing can safely
    # replace unavailable history, but authorization/read/parser gaps cannot.
    repository_rows = {row["repo_id"]: row for row in repositories["repositories"]}
    selected_ids = {row["source_id"] for row in lock["resources"] if row.get("kind") != "code"}
    # Existing source-specific freshness events may legitimately exempt a
    # navigable guidance or recoverable historical Claim. Recheck that rare
    # exception rather than losing it merely because Git had no new paths.
    exception_ids = set()
    for block in maintenance.state(ctx).get("blocked_claims", []):
        if block.get("reason") in {"source_changed", "code_changed", "code_source_changed"}:
            if block.get("source_id"):
                exception_ids.add(block["source_id"])
            exception_ids.update(row["source_id"] for row in lock["snapshots"]
                                 if row["snapshot_id"] in block.get("old_snapshot_ids", []))
    selected_ids.update(exception_ids)
    checked_keys = set()
    fingerprint_keys = set()
    fingerprints = copy.deepcopy((before_state or {}).get("code_fingerprints", {}))
    registered = {identity: set() for identity in repository_rows}
    for _, _, resource in code_refs:
        registered.setdefault(resource["repo_id"], set()).add(resource["path"])
    gaps.extend(_repository_gaps(repositories, registered))
    for card, source, resource in code_refs:
        key = resource["repo_id"], resource["path"]
        repo = repository_rows.get(key[0])
        selected = force_full or source["source_id"] in exception_ids or repo is None or repo.get("full_scan") or key[1] in set(
            (repo or {}).get("changed_paths", []) + (repo or {}).get("dirty_paths", []))
        if not selected:
            continue
        if key not in code_observations:
            code_observations[key] = reference_audit.current_source(ctx, config, resource)
        observed = code_observations[key]
        fingerprint_key = digest(list(key))
        fingerprint = {"repo_id": key[0], "path": key[1], "observation": observed["observation"], "sha256": observed["current_sha256"]}
        fingerprint_keys.add(key)
        fingerprints[fingerprint_key] = fingerprint
        if (not force_full and source["source_id"] not in exception_ids
                and fingerprint == (before_state or {}).get("code_fingerprints", {}).get(fingerprint_key)):
            continue
        selected_ids.add(source["source_id"])
        checked_keys.add(key)
        row = reference_audit.reference_row(ctx, card, source, resource, lock, config, observed)
        row = _retired_reference(ctx, card, source, row, observed)
        references.append(row)
        gaps.extend({**gap, "card_id": row["card_id"], "path": row["path"]} for gap in row["gaps"])
    inspection, _ = maintenance.inspect_context(fork_context(ctx, request={"operation_id": ctx.operation}, action="inspect-context"),
                                               source_ids=selected_ids)
    inspection = _retired_context(ctx, inspection, cards)
    processing = _processing_context(ctx, cards)
    inspection["affected_claims"].extend(processing["blocked_claims"])
    gaps.extend(processing["gaps"])
    metadata_cards = {row["card_id"] for row in structural_findings}
    metadata_cards.update(row["card_id"] for row in references
                          if not row["claims"] and row["effect"].endswith("needs_review"))
    # The existing P3 contract authors maintenance work by actual Claim ID.
    # Metadata defects are review tasks for that card's real Claims, without
    # inventing a raw document or asserting that its guidance text is false.
    for card in cards:
        if card["metadata"]["id"] in metadata_cards:
            inspection["affected_claims"].extend({"card_id": card["metadata"]["id"], "claim_id": claim["id"],
                "reason": "code_metadata_needs_review"} for claim in card["metadata"]["claims"])
    gaps.extend(inspection.get("gaps", []))
    scan_ctx = fork_context(ctx, request={"operation_id": ctx.operation}, action="scan")
    scan_ctx.base = _base(ctx)
    scanned, _ = source_inventory.scan(scan_ctx, current_context=inspection)
    inventory = ctx.record(scanned["scan_ref"], "source_inventory")
    candidate_ids = {row["card_id"] for row in inspection.get("affected_claims", [])}
    candidate_ids.update(row["card_id"] for row in references if row["effect"].endswith("needs_review"))
    candidate_ids.update(row["card_id"] for row in structural_findings)
    candidate_sources = {source["source_id"] for card in cards if card["metadata"]["id"] in candidate_ids
                         for source in card["metadata"]["sources"]}
    units = [unit for unit in inventory["units"] if unit["change"] != "unchanged" or unit["source_id"] in candidate_sources]
    targets = {}
    # Capture direct current code material for repair candidates, including code
    # alongside raw evidence. Missing files remain explicit audit debt.
    for card, source, resource in code_refs:
        if card["metadata"]["id"] not in candidate_ids:
            continue
        key = resource["repo_id"], resource["path"]
        if key not in code_observations:
            code_observations[key] = reference_audit.current_source(ctx, config, resource)
        observed = code_observations[key]
        if observed["observation"] == "available":
            target = {"kind": "code", "repo_id": key[0], "relative_path": key[1],
                      "expected_fingerprint": observed["current_sha256"]}
            snapshot = next(row for row in lock["snapshots"] if row["source_id"] == source["source_id"]
                            and row["snapshot_id"] == source["snapshot_id"])
            extractor = (snapshot.get("extraction") or {}).get("extractor")
            if extractor in {"code-utf8:1", "code-gb18030:1"}:
                target["text_encoding"] = "gb18030" if extractor == "code-gb18030:1" else "utf-8"
            # Identity stays on the original path. A rename is a new target
            # chosen by ingest, never a migration of a source_id here.
            original_resource = next(row for row in lock["resources"] if row["source_id"] == source["source_id"])
            if (resource["path"], resource["repo_id"]) == (original_resource["path"], original_resource["repo_id"]):
                target["source_id"] = source["source_id"]
            targets[key] = target
    pending, publication_gaps = _pending_publications(ctx)
    gaps.extend(publication_gaps)
    if pending:
        gaps.append(reference_audit.issue("PATROL_P7_RESUME_REQUIRED", "Finish the exact published operation before a new ingest batch"))
    raw_observation = _raw(ctx, inventory["scope"])
    if not inventory["complete"] or not raw_observation["complete"]:
        # Keep readable raw units actionable; unreadable units stay in the
        # handoff and cannot later satisfy successful completion.
        raw_gaps = [{"code": "PATROL_RAW_UNREADABLE", "path": path, "reason": reason}
                    for path, reason in raw_observation["errors"].items()]
    else:
        raw_gaps = []
    inputs = _binding(ctx, config, formal, raw_observation, [
        {"repo_id": key[0], "path": key[1], "observation": row["observation"], "sha256": row["current_sha256"]}
        for key, row in sorted(code_observations.items())])
    source_request = {"operation_id": ctx.operation, "scan_ref": scanned["scan_ref"],
        "unit_ids": sorted(unit["unit_id"] for unit in units), "candidate_card_ids": sorted(candidate_ids),
        "targets": [targets[key] for key in sorted(targets)], "tolerate_source_errors": True,
        "collect_local_attachments": True, "patrol_plan_ref": ref}
    has_ingest = bool(units or candidate_ids)
    index_gap = None
    index_reusable = not force_full and patrol_index.unchanged_closure(ctx, (before_state or {}).get("index_closure"))
    if not index_reusable:
        try:
            patrol_index.current(ctx)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            index_gap = reference_audit.issue("PATROL_INDEX_REBUILD_REQUIRED", exc)
    phase = "blocked" if gaps else "needs_ingest" if has_ingest else "needs_index" if index_gap else "unchanged"
    payload = ctx.seal({"purpose": "patrol_plan", "protocol_version": PROTOCOL, "phase": phase,
        "baseline_digest": before_state["digest"] if before_state else None,
        "metadata_digest": metadata, "force_full": force_full, "inputs": inputs,
        "raw_scope": inventory["scope"], "scan_ref": scanned["scan_ref"], "scan_digest": scanned["scan_digest"],
        "source_request": source_request, "required_units": units, "candidate_card_ids": sorted(candidate_ids),
        "selected_source_ids": sorted(selected_ids),
        "registered_code_paths": {identity: sorted(paths) for identity, paths in registered.items()},
        "code_fingerprints": fingerprints, "index_reusable": index_reusable,
        "references": references, "repositories": repositories, "pending_publications": pending,
        "structural_findings": structural_findings,
        "index_gap": index_gap, "gaps": gaps + raw_gaps, "complete": not gaps and not raw_gaps,
        "counts": {"code_files_checked": len(fingerprint_keys), "code_files_deep_checked": len(checked_keys), "code_references_checked": len(references),
                   "raw_units": len(units), "candidate_cards": len(candidate_ids)}}, "artifact_manifest")
    # Recheck the exact pre-publication binding before saving a fixed plan.
    _validate_inputs(ctx, payload, allow_repository_gaps=phase == "blocked")
    ctx.save(ref, payload)
    _write_report(ctx, payload, ref)
    return _response(payload, ref)


def reindex(ctx):
    ref, planned = _read_plan(ctx)
    if planned["phase"] not in {"needs_index", "unchanged"}:
        raise NodeError("PATROL_INGEST_REQUIRED", "Index-only maintenance cannot discharge content or environment debt")
    _validate_inputs(ctx, planned)
    result = patrol_index.check_queries(ctx, ctx.modules["source_materials"].domain_cards(ctx), build=True,
                                        inputs=ctx.request.get("index_inputs"))
    return {**result, "plan_ref": ref, "plan_digest": planned["digest"]}, "indexed"


def _completion_publication(ctx, planned):
    ref = ctx.request.get("publication_ref")
    operation = ctx.request.get("batch_operation_id")
    supplied_completion = ctx.request.get("completion_ref")
    if supplied_completion:
        # The stable path identifies the producer; never accept a supplied
        # object's batch_complete or passed booleans as evidence.
        parts = supplied_completion.split("/")
        if len(parts) != 4 or parts[:2] != ["logs", "publications"] or parts[-1] != "completion.json":
            raise NodeError("PATROL_COMPLETION_INVALID", "Expected a formal P7 completion_ref")
        if operation and operation != parts[2]:
            raise NodeError("PATROL_COMPLETION_INVALID", "Completion and producer operation disagree")
        operation = parts[2]
    if not ref and operation:
        ref = publication.manifest_ref(operation)
    if not ref:
        ref = publication.manifest_ref(planned["operation_id"])
    manifest = publication.read_manifest(ctx, ref, verify_files=True)
    completion = publication.read_completion(ctx, manifest)
    if not completion or completion.get("batch_complete") is not True:
        raise NodeError("PATROL_P7_INCOMPLETE", "Real P7 retrieval/cleanup has not completed", ref)
    if manifest["rules_digest"] != ctx.args.rules_digest:
        raise NodeError("PATROL_P7_RULES_CHANGED", "Publication uses another rules identity")
    return manifest, completion


def complete(ctx):
    ref, planned = _read_plan(ctx)
    reasons, manifest = [], None
    try:
        if planned["phase"] == "blocked" or not planned["complete"]:
            raise NodeError("PATROL_PLAN_INCOMPLETE", "The planned environment or raw observation contains gaps")
        if planned["phase"] == "needs_ingest":
            manifest, closure = _completion_publication(ctx, planned)
            processing = manifest.get("processing_record")
            if not processing:
                raise NodeError("PATROL_PROCESSING_RECORD_REQUIRED", "Patrol ingest needs formal per-unit processing facts")
            record = read_json(safe(ctx.root, processing["path"], ["logs/ingest"]))
            ctx.modules["records"].validate_ingest_record(record, rules=ctx.rules)
            if (record.get("scan_digest") != planned["scan_digest"]
                    or record.get("scan_ref") != planned["scan_ref"]):
                raise NodeError("PATROL_SCAN_NOT_COVERED", "P7 processing record belongs to another source inventory")
            dispositions = {row["unit_id"]: row for row in record.get("dispositions", [])}
            if record.get("pending") or any(row.get("outcome") in {"defer", "failed", "uncovered"}
                                             for row in record.get("maintenance_dispositions", [])):
                raise NodeError("PATROL_MAINTENANCE_PENDING", "Formal processing facts retain deferred or incomplete maintenance work")
            for unit in planned["required_units"]:
                row = dispositions.get(unit["unit_id"], {})
                progress = row.get("progress")
                progress = progress.get("status") if isinstance(progress, dict) else progress
                if progress not in {"completed", "skipped", "withdrawn"} or row.get("action") in {"defer", "failed", "uncovered"}:
                    raise NodeError("PATROL_UNIT_PENDING", "A required raw unit has no real terminal disposition", unit["path"])
                if row.get("observed_fingerprint") != unit.get("observed_fingerprint"):
                    raise NodeError("PATROL_UNIT_CHANGED", "Processing facts describe another raw observation", unit["path"])
        config = _validate_inputs(ctx, planned, publication_manifest=manifest)
        pending, gaps = _pending_publications(ctx)
        if pending or gaps:
            raise NodeError("PATROL_P7_PENDING", "A formal publication still needs exact-operation recovery")
        inspected, _ = maintenance.inspect_context(fork_context(ctx, request={"operation_id": ctx.operation}, action="inspect-context"),
            source_ids=None if manifest else set(planned["selected_source_ids"]))
        inspected = _retired_context(ctx, inspected, ctx.modules["source_materials"].domain_cards(ctx))
        if not inspected["complete"] or inspected.get("affected_claims") or inspected.get("state", {}).get("pending_event_ids"):
            raise NodeError("PATROL_RESTRICTIONS_REMAIN", "Current inspection still contains unavailable or restricted Claims")
        # A fresh full inventory must have no new work, even if a producer
        # provided a superficially complete record for a subset of inputs.
        scan_ctx = fork_context(ctx, request={"operation_id": ctx.operation}, action="scan")
        scan_ctx.base = _base(ctx) + "/completion-observations/" + digest(_formal(ctx))[:24]
        observed, _ = source_inventory.scan(scan_ctx, current_context=inspected)
        fresh = ctx.record(observed["scan_ref"], "source_inventory")
        if not fresh["complete"] or any(row["change"] != "unchanged" for row in fresh["units"]):
            raise NodeError("PATROL_RAW_DEBT_REMAINS", "Fresh inventory still contains new, changed or unfinished raw originals")
        cards = ctx.modules["source_materials"].domain_cards(ctx)
        processing = _processing_context(ctx, cards)
        if processing["gaps"] or processing["blocked_claims"]:
            raise NodeError("PATROL_PROCESSING_DEBT_REMAINS", "Formal per-Claim processing facts still contain unresolved work")
        candidate_observations = _verify_candidates(ctx, planned, cards, config) if manifest else []
        previous = _state(ctx)
        reuse = (manifest is None and planned["index_reusable"] and not planned["counts"]["code_files_deep_checked"]
                 and previous is not None and patrol_index.unchanged_closure(ctx, previous.get("index_closure")))
        if reuse:
            retrieval, index_closure = previous["retrieval"], previous["index_closure"]
        else:
            build = False
            try:
                patrol_index.current(ctx)
            except NodeError as exc:
                if exc.code not in {"PATROL_INDEX_MISSING", "PATROL_INDEX_STALE"}:
                    raise
                build = True
            except FileNotFoundError:
                build = True
            retrieval = patrol_index.check_queries(ctx, cards, build=build, inputs=ctx.request.get("index_inputs"))
            index_closure = patrol_index.closure(ctx, retrieval)
        _validate_inputs(ctx, planned, publication_manifest=manifest)
        for row in candidate_observations:
            observed_code = reference_audit.current_source(ctx, config, {"repo_id": row["repo_id"], "path": row["path"]})
            if (observed_code["observation"], observed_code["current_sha256"]) != (row["observation"], row["sha256"]):
                raise NodeError("PATROL_INPUT_CHANGED", "A repaired metadata source changed before completion", row["path"], blocked=True)
        # HEAD may have moved while ingest ran even with identical file bytes.
        # Preserve the planned HEAD: the next patrol conservatively examines
        # that range again rather than swallowing an unobserved commit.
        baseline = ctx.seal({"purpose": "patrol_success_baseline", "protocol_version": PROTOCOL,
            "plan_ref": ref, "plan_digest": planned["digest"],
            "heads": planned["repositories"]["heads"], "metadata_digest": _metadata(ctx, _formal(ctx), config),
            "code_fingerprints": planned["code_fingerprints"], "index_closure": index_closure,
            "retrieval": retrieval, "publication_ref": publication.manifest_ref(manifest["operation_id"]) if manifest else None},
            "artifact_manifest")
        with maintenance.writer_lock(ctx):
            actual = _state(ctx)
            if actual and actual.get("plan_digest") == planned["digest"]:
                return {"plan_ref": ref, "baseline_ref": STATE_REF, "baseline_digest": actual["digest"], "retrieval": retrieval}, "completed"
            if (actual["digest"] if actual else None) != planned["baseline_digest"]:
                raise NodeError("PATROL_BASELINE_CHANGED", "Another patrol completed before this baseline CAS", blocked=True)
            _validate_inputs(ctx, planned, publication_manifest=manifest)
            for row in candidate_observations:
                observed_code = reference_audit.current_source(ctx, config, {"repo_id": row["repo_id"], "path": row["path"]})
                if (observed_code["observation"], observed_code["current_sha256"]) != (row["observation"], row["sha256"]):
                    raise NodeError("PATROL_INPUT_CHANGED", "Repaired code changed while waiting for baseline CAS", row["path"], blocked=True)
            if not patrol_index.unchanged_closure(ctx, index_closure):
                raise NodeError("PATROL_INDEX_CHANGED", "Verified index closure changed before successful-baseline CAS", blocked=True)
            write_bytes(ctx.root, STATE_REF, canonical(baseline), immutable=False)
            if read_json(safe(ctx.root, STATE_REF)) != baseline:
                raise NodeError("PATROL_STATE_WRITE_FAILED", "Successful baseline read-back differs", blocked=True)
        return {"plan_ref": ref, "baseline_ref": STATE_REF, "baseline_digest": baseline["digest"], "retrieval": retrieval}, "completed"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        reasons.append(reference_audit.issue(getattr(exc, "code", "PATROL_COMPLETION_UNAVAILABLE"), exc))
    report = ctx.seal({"purpose": "patrol_pending", "protocol_version": PROTOCOL, "plan_ref": ref,
                       "plan_digest": planned["digest"], "reasons": reasons}, "artifact_manifest")
    report_ref = _base(ctx) + "/pending/" + report["digest"] + ".json"
    ctx.save(report_ref, report)
    return {"plan_ref": ref, "report_ref": report_ref, "complete": False, "reasons": reasons}, "pending"


def execute(ctx):
    action = ctx.args.action
    if action == "patrol-plan":
        try:
            return plan(ctx)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            ref = _base(ctx) + "/plan.json"
            # An existing immutable observation must never be replaced by a
            # catch-all report when its input revalidation fails.
            if safe(ctx.root, ref).exists():
                raise
            payload = ctx.seal({"purpose": "patrol_plan", "protocol_version": PROTOCOL,
                "phase": "blocked", "complete": False, "baseline_digest": None, "force_full": True,
                "gaps": [reference_audit.issue(getattr(exc, "code", "PATROL_ENVIRONMENT_UNAVAILABLE"), exc)],
                "counts": {}, "repositories": {"repositories": [], "heads": {}}, "references": [],
                "pending_publications": [], "inputs": None}, "artifact_manifest")
            ctx.save(ref, payload)
            _write_report(ctx, payload, ref)
            return _response(payload, ref)
    if action == "patrol-reindex":
        return reindex(ctx)
    if action == "patrol-complete":
        return complete(ctx)
    raise NodeError("INVALID_ACTION", action)
