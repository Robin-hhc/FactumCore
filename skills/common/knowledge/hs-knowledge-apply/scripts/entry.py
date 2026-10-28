"""Keep legacy apply semantics and route new P7 actions to shared functions."""

from pathlib import Path

from support import Blocked, Invalid
from transaction import execute as transaction_execute


NEW_ACTIONS = {"batch", "index-build", "index-verify", "index-activate", "regression",
               "regression-verify", "prepare-submission", "verify-submission"}


class _BatchTransactionContext:
    """Use the new public operation-ID contract without changing legacy run."""

    def __init__(self, original, runtime):
        self.original, self.runtime = original, runtime

    def __getattr__(self, name):
        return getattr(self.original, name)

    def operation(self, request):
        return self.runtime.identifier(request.get("operation_id"))


def execute(ctx, request, action="run"):
    if action not in NEW_ACTIONS:
        if action in {"inspect", "resume", "rollback", "verify-result"} and getattr(ctx, "modules", None):
            return transaction_execute(_BatchTransactionContext(ctx, ctx.modules["runtime"]), request, action)
        return transaction_execute(ctx, request, action)
    if ctx.domain is None:
        raise Blocked("P7 actions require the versioned domain implementation")
    modules = ctx.modules
    runtime = modules["runtime"]
    if action == "batch" and not request.get("view_ref") and request.get("ingest_record_ref"):
        from transaction_v3 import record_only_view
        request = record_only_view(_BatchTransactionContext(ctx, runtime), request)
    shared = runtime.OperationContext(ctx.root, request, modules=modules, rules=ctx.rules,
                                      tool=ctx.identity, rules_digest=ctx.rules_digest,
                                      action=action, package=Path(__file__).resolve().parents[1],
                                      catalog=ctx.catalog_path)

    def transact(mode):
        # This keyword is chosen by the new action, never from request JSON.
        return transaction_execute(_BatchTransactionContext(ctx, runtime), request, mode, safety_only=True)

    try:
        data, phase = modules["ingest_execution"].execute(shared, transact=transact if action == "batch" else None)
    except runtime.NodeError as exc:
        error = Blocked(str(exc)) if exc.blocked else Invalid(str(exc))
        error.code = exc.code
        raise error from exc
    return {**data, "phase": phase}
