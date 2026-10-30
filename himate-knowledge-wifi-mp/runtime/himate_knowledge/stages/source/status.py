"""Read saved stages and derived recovery hints without advancing work."""

from .support import NodeError, identifier, safe
from .progress import adopted_successor, batch_finalization, catalog, catalog_gap, finalization, material_refs, observation_only, paths, read_saved

STAGES = (
    ("scan", ".build/operations/{op}/source-inventory.json"),
    ("materials", ".build/operations/{op}/material.json"),
    ("semantic_plan", ".build/operations/{op}/semantic-plan.json"),
    ("plan", ".build/operations/{op}/plan.json"),
    ("view", ".build/operations/{op}/final-view.json"),
    ("record_prepared", ".build/operations/{op}/ingest-record.yaml"),
    ("record_formal", "logs/ingest/{op}.yaml"),
    ("transaction", ".build/operations/{op}/transaction/journal.json"),
    ("apply", ".build/operations/{op}/transaction/apply-result.json"),
    ("transaction", "logs/operations/{op}/journal.json"),
    ("apply", "logs/operations/{op}/apply-result.json"),
    ("submission_handoff", "logs/operations/{op}/publish-handoff.json"),
    ("batch_intent", ".build/operations/{op}/batch-intent.json"),
    ("batch_build", ".build/operations/{op}/batch-build.json"),
    ("batch_complete", ".build/operations/{op}/batch-complete.json"),
)
ALL_STAGES = [stage for stage, _ in STAGES] + ["content_review", "local_check", "lint", "index", "regression", "activation"]


def publication_details(ctx, op):
    """Observe a selected formal closure without reopening producer stage paths."""
    publication = ctx.modules["publication"]
    manifest_ref = publication.manifest_ref(op)
    completion_ref = publication.completion_ref(op)
    if not any(safe(ctx.root, ref).exists() for ref in (manifest_ref, completion_ref)):
        return None
    facts, gaps, stage_status = [], [], {stage: "unknown" for stage in ALL_STAGES}
    completion = {"status": "unknown", "next_action": "inspect_finalization",
                  "verification": "saved_facts_only", "index_health": "not_examined"}
    stage, ref = "publication", manifest_ref
    try:
        manifest = publication.read_manifest(ctx, operation_id=op)
        current = manifest.get("rules_digest") == ctx.args.rules_digest
        facts.append({"stage": stage, "ref": ref, "digest": manifest["digest"],
                      "published": True, "batch_kind": manifest["batch_kind"], "rules_current": current})
        stage_status[stage] = "saved" if current else "historical_rules"
        completion.update(published=True, content_applied=True, batch_complete=False,
                          publication_ref=ref, content_digest=manifest["content_digest"],
                          scope=manifest["batch_kind"])
        stage, ref = "publication_completion", completion_ref
        saved = publication.read_completion(ctx, manifest)
        if saved is None:
            completion.update(status="pending", next_action="resume_batch")
        else:
            terminal = saved.get("batch_complete") is True
            if terminal and (saved.get("published") is not True
                             or saved.get("retrieval", {}).get("complete") is not True
                             or saved.get("cleanup", {}).get("status") != "done"
                             or saved.get("phase") != ("recorded" if manifest["batch_kind"] == "record_only" else "completed")):
                raise NodeError("INVALID_PUBLICATION_COMPLETION", "Terminal completion lacks retrieval/cleanup facts", ref)
            facts.append({"stage": stage, "ref": ref, "digest": saved["digest"],
                          "phase": saved["phase"], "rules_current": saved.get("rules_digest") == ctx.args.rules_digest})
            stage_status[stage] = "saved" if saved.get("rules_digest") == ctx.args.rules_digest else "historical_rules"
            cleanup_pending = saved.get("retrieval", {}).get("complete") is True
            completion.update(status="complete" if terminal else "pending", batch_complete=terminal,
                              next_action=None if terminal else ("cleanup" if cleanup_pending else "resume_batch"),
                              completion_ref=ref, cleanup=saved.get("cleanup"), retrieval=saved.get("retrieval"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        gaps.append({"stage": stage, "ref": ref, "reason": str(exc)})
    return {"operation_id": op, "facts": facts, "gaps": gaps, "stage_status": stage_status,
            "completion": completion, "git_submission": "not_verified", "ci": "not_verified", "merge": "not_verified"}


def operation_details(ctx, op, *, global_history=False):
    published = publication_details(ctx, op)
    if published is not None and not global_history:
        return published
    facts, gaps, values = [], [], {}
    stage_status = {stage: "unknown" for stage in ALL_STAGES}

    def add(stage, ref):
        if any(fact["stage"] == stage and fact["ref"] == ref for fact in facts):
            return
        if not safe(ctx.root, ref).is_file():
            return
        try:
            if stage in {"transaction", "apply"} and stage in values:
                raise NodeError("TRANSACTION_PATH_CONFLICT", "Both new and legacy transaction slots are present", ref)
            value = read_saved(ctx, ref)
            if stage not in {"index", "regression", "activation", "lint"} and value.get("operation_id") != op:
                raise NodeError("RECORD_BINDING_MISMATCH", "Saved stage belongs to another operation", ref)
            values[stage] = value
            current = value.get("rules_digest") == ctx.args.rules_digest
            stage_status[stage] = "saved" if current else "historical_rules"
            facts.append({"stage": stage, "ref": ref, "digest": value["digest"],
                          "status": value.get("status"), "phase": value.get("phase"),
                          "progress": value.get("progress"),
                          "batch_kind": value.get("batch_kind", "content") if stage in {"transaction", "apply"} else value.get("batch_kind"),
                          "rules_current": current,
                          **{key: value[key] for key in ("view_ref", "view_digest", "plan_ref", "semantic_plan_ref",
                                                        "generation_ref", "expected_active", "passed", "index_verified",
                                                        "active_digest", "manifest_digest") if key in value}})
        except (OSError, ValueError, KeyError) as exc:
            gaps.append({"stage": stage, "ref": ref, "reason": str(exc)})

    for stage, pattern in STAGES:
        add(stage, pattern.format(op=op))
    for ref in material_refs(ctx, op):
        add("materials", ref)
    if global_history and "record_formal" not in values:
        for pattern in ("logs/ingest/*.yaml", "logs/ingest/*.yml", "logs/ingest/*.json"):
            for ref in paths(ctx, pattern):
                try:
                    value = read_saved(ctx, ref)
                    if value.get("operation_id") == op:
                        add("record_formal", ref)
                except (OSError, ValueError, KeyError) as exc:
                    catalog_gap(ctx, ref, exc)
    for stage, pattern in (("content_review", f".build/operations/{op}/content-review/*.json"),
                           ("local_check", f"logs/operations/{op}/local-check-*.json"),
                           ("lint", f".build/operations/{op}/*lint*.json")):
        for ref in paths(ctx, pattern):
            if not ref.endswith("-input.json"):
                add(stage, ref)
    if global_history:
        for stage, key in (("index", "generations"), ("regression", "regressions"), ("activation", "activations")):
            for ref, value in catalog(ctx)[key]:
                if value.get("operation_id") == op:
                    add(stage, ref)
    journal = values.get("transaction")
    if any(stage in values for stage in ("batch_intent", "batch_build", "batch_complete")):
        if journal and journal.get("view_ref") and "view" not in values:
            add("view", journal["view_ref"])
        if any(gap["stage"] in {"transaction", "apply"} for gap in gaps):
            completion = {"status": "unknown", "next_action": "recover_transaction", "verification": "saved_facts_only",
                          "reason": "The actual local writer journal cannot be read; a saved summary cannot override it"}
        else:
            completion = batch_finalization(ctx, values)
        for stage, key in (("index", "generation_ref"), ("regression", "report_ref"), ("activation", "activation_observation_ref")):
            if completion.get(key):
                add(stage, completion[key])
    elif any(gap["stage"].startswith("batch_") for gap in gaps):
        completion = {"status": "unknown", "next_action": "inspect_finalization", "verification": "saved_facts_only",
                      "reason": "A durable local batch substep cannot be read; inspect it before resuming"}
    elif journal and not any(gap["stage"] in {"transaction", "apply"} for gap in gaps):
        for stage, key in (("view", "view_ref"), ("lint", "lint_report_ref")):
            if journal.get(key) and stage not in values:
                add(stage, journal[key])
        completion = finalization(ctx, journal, values.get("view"), inspect_catalog=global_history)
        for stage, key in (("index", "generation_ref"), ("regression", "regression_ref"), ("activation", "activation_ref")):
            if completion.get(key):
                add(stage, completion[key])
    elif any(gap["stage"] in {"transaction", "apply"} for gap in gaps):
        completion = {"status": "unknown", "next_action": "recover_transaction",
                      "reason": "Local transaction journal exists but cannot be verified; inspect it before further work"}
    elif values.get("record_formal"):
        completion = {"status": "unknown", "next_action": "check_local_index",
                      "reason": "Portable processing history does not prove this machine's index state"}
    elif values.get("view"):
        completion = {"status": "pending", "next_action": "review_content", "view_ref": next(
            fact["ref"] for fact in facts if fact["stage"] == "view")}
    elif any(stage in values for stage in ("index", "regression", "activation")):
        completion = {"status": "unknown", "next_action": "inspect_finalization", "scope": "supporting_stage",
                      "reason": "Saved supporting-stage results alone do not identify a complete ingest batch"}
    elif values.get("scan") and observation_only(values["scan"]) and not any(
            stage in values for stage in ("materials", "plan", "semantic_plan")):
        completion = {"status": "not_applicable", "next_action": None, "scope": "observation_only"}
    else:
        completion = {"status": "unknown", "next_action": "prepare_material"}
    if global_history and not journal:
        old_view = values.get("view")
        old_view_ref = next((fact["ref"] for fact in facts if fact["stage"] == "view"), None)
        successor = adopted_successor(ctx, op, old_view_ref, (old_view or {}).get("digest"), values.get("scan", {}).get("digest"))
        if successor:
            completion = {"status": "not_applicable", "scope": "adopted_by_new_round", "next_action": None,
                          "verification": "saved_facts_only", "adopted_by": successor}
    if published is not None:
        # Global overview also diagnoses obsolete private history, while the
        # formal closure remains authoritative for this operation's completion.
        facts = published["facts"] + facts
        gaps = published["gaps"] + gaps
        stage_status.update({key: value for key, value in published["stage_status"].items()
                             if key.startswith("publication")})
        completion = published["completion"]
    return {"operation_id": op, "facts": facts, "gaps": gaps, "stage_status": stage_status,
            "completion": completion, "git_submission": "not_verified", "ci": "not_verified", "merge": "not_verified"}


def status(context):
    target = context.request.get("target_operation_id")
    operations = {identifier(target)} if target else set()
    if not target:
        for directory in (".build/operations", "logs/operations", "logs/publications"):
            root = safe(context.root, directory)
            if root.exists():
                operations.update(identifier(p.name) for p in root.iterdir() if p.is_dir())
        for pattern in ("logs/ingest/*.yaml", "logs/ingest/*.yml", "logs/ingest/*.json"):
            for ref in paths(context, pattern):
                try:
                    value = read_saved(context, ref)
                    operations.add(identifier(value["operation_id"]))
                except (OSError, ValueError, KeyError) as exc:
                    catalog_gap(context, ref, exc)
    result = [operation_details(context, op, global_history=not target) for op in sorted(operations)]
    gaps = catalog(context)["gaps"] if not target else []
    return {"operations": result, "knowledge_root": str(context.root), "catalog_gaps": gaps,
            "complete": not gaps and not any(row["gaps"] for row in result)}, "status"
