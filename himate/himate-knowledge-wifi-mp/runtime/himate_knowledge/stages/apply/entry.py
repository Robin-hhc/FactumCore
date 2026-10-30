"""Keep legacy apply semantics and route new P6 actions to shared functions."""

from pathlib import Path
import base64

from .support import Blocked, Invalid
from .transaction import execute as transaction_execute


NEW_ACTIONS = {"batch", "index-build", "index-verify", "index-activate", "regression",
               "regression-verify", "prepare-submission", "verify-submission"}


class _BatchTransactionContext:
    """Use the new public operation-ID contract without changing legacy run."""

    def __init__(self, original, runtime, *, record_only_batch=False):
        self.original, self.runtime = original, runtime
        self.record_only_batch = record_only_batch

    def __getattr__(self, name):
        return getattr(self.original, name)

    def operation(self, request):
        return self.runtime.identifier(request.get("operation_id"))


def _reject_legacy_external(ctx, request):
    """The legacy full-check writer cannot promise the new directory binding."""
    reference = request.get("view_ref")
    if not reference or not getattr(ctx, "modules", None):
        return
    view = ctx.read(reference)
    prefix = "docs-raw/sources/dbox/"
    if any(path.startswith(prefix) or row.get("kind") == "external_raw"
           for path, row in (view.get("input_snapshot") or {}).get("current_files", {}).items()):
        raise Invalid("EXTERNAL_LEGACY_APPLY_UNSUPPORTED: use apply.batch for external current inputs")
    lock = ctx.modules["source_resources"].read_source_lock(ctx.root)
    sources = {row.get("source_id") for row in view.get("source_refs", [])}
    for row in view.get("writes", []):
        if row["path"] == "governance/sources.lock.yaml":
            lock = ctx.modules["validation"].load_yaml(base64.b64decode(row["bytes_b64"], validate=True))
        elif row["path"].startswith("knowledge/") and Path(row["path"]).name not in {"AGENTS.md", "index.md", "README.md"}:
            card = ctx.modules["knowledge"].decode_card(base64.b64decode(row["bytes_b64"], validate=True), row["path"], ctx.rules)
            sources.update(source["source_id"] for source in card["metadata"]["sources"])
    if any(row.get("source_id") in sources and row.get("path", "").startswith(prefix)
           for row in lock.get("resources", [])):
        raise Invalid("EXTERNAL_LEGACY_APPLY_UNSUPPORTED: use apply.batch for external sources")


def _verify_publication(ctx, shared, request):
    publication = shared.modules["publication"]
    purpose = request.get("purpose", "current")
    if purpose not in {"current", "historical"}:
        raise Invalid("unknown content verification purpose")
    manifest = publication.read_manifest(shared, request.get("publication_ref"), verify_files=purpose == "current")
    if manifest["operation_id"] != shared.operation:
        raise Invalid("publication belongs to another operation")
    if purpose == "current" and manifest["rules_digest"] != shared.args.rules_digest:
        raise shared.modules["runtime"].NodeError("STALE_RULES", "Published content uses a different rules identity")
    view = publication.published_view(manifest)
    if purpose == "current":
        from .transaction_v3 import check_current_code
        check_current_code(ctx, view, request.get("check_inputs"))
        if manifest.get("index_inputs", {}).get("code_contexts"):
            cards = []
            for row in view.get("writes", []):
                if row["path"].startswith("knowledge/") and Path(row["path"]).name not in {"AGENTS.md", "index.md", "README.md"}:
                    cards.append(shared.modules["knowledge"].decode_card(base64.b64decode(row["bytes_b64"]), row["path"], shared.rules))
            shared.modules["index_runtime"].code_contexts(shared, cards, manifest["index_inputs"])
    resources = shared.modules["source_resources"]
    for snapshot in view.get("source_refs", []):
        resources.recover_snapshot(shared.root, snapshot)
    files = [{"path": row["path"], "sha256": row["final_digest"]} for row in view.get("writes", [])
             if row["path"].startswith("knowledge/") and Path(row["path"]).name not in {"AGENTS.md", "index.md", "README.md"}]
    return {"result_verified": True, "verification_scope": "verified_content_integrity", "purpose": purpose,
            "eligible_files": files if purpose == "current" else [],
            "historical_files": files if purpose == "historical" else [],
            "publication_ref": publication.manifest_ref(shared.operation), "content_digest": manifest["content_digest"],
            "write_manifest": manifest["files"], "delete_manifest": [row["path"] for row in manifest["deletes"]],
            "batch_kind": manifest["batch_kind"], "verification_tier": "transaction_bytes_only", "phase": "verified"}


def execute(ctx, request, action="run"):
    if getattr(ctx, "modules", None) and action == "verify-result":
        runtime = ctx.modules["runtime"]
        op = runtime.identifier(request.get("operation_id"))
        if ctx.path("logs/publications/" + op + "/manifest.json").is_file():
            shared = runtime.OperationContext(ctx.root, request, modules=ctx.modules, rules=ctx.rules,
                tool=ctx.identity, rules_digest=ctx.rules_digest, action=action,
                package=Path(__file__).resolve().parent, catalog=ctx.catalog_path)
            return _verify_publication(ctx, shared, request)
    if action not in NEW_ACTIONS:
        if action == "run":
            _reject_legacy_external(ctx, request)
        if action in {"inspect", "resume", "rollback", "verify-result"} and getattr(ctx, "modules", None):
            return transaction_execute(_BatchTransactionContext(ctx, ctx.modules["runtime"]), request, action)
        return transaction_execute(ctx, request, action)
    if ctx.domain is None:
        raise Blocked("P6 actions require the versioned domain implementation")
    modules = ctx.modules
    runtime = modules["runtime"]
    published = ctx.path("logs/publications/" + runtime.identifier(request.get("operation_id")) + "/manifest.json").is_file()
    if action == "batch" and not published and not request.get("view_ref") and request.get("ingest_record_ref"):
        from .transaction_v3 import record_only_view
        request = record_only_view(_BatchTransactionContext(ctx, runtime), request)
    shared = runtime.OperationContext(ctx.root, request, modules=modules, rules=ctx.rules,
                                      tool=ctx.identity, rules_digest=ctx.rules_digest,
                                      action=action, package=Path(__file__).resolve().parent,
                                      catalog=ctx.catalog_path)

    def transact(mode):
        # This keyword is chosen by the new action, never from request JSON.
        return transaction_execute(_BatchTransactionContext(ctx, runtime, record_only_batch=True), request, mode, safety_only=True)

    try:
        data, phase = modules["ingest_execution"].execute(shared, transact=transact if action == "batch" else None)
    except runtime.NodeError as exc:
        error = Blocked(str(exc)) if exc.blocked else Invalid(str(exc))
        error.code = exc.code
        raise error from exc
    return {**data, "phase": phase}
