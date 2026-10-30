"""P2 stores authored meaning; P3 owns concrete bytes and P4 owns review."""

from .support import NodeError
from .plan_v3 import author_plan


def execute(context):
    action = context.args.action or "plan"
    if action in {"plan", "run"}:
        if "decisions" in context.request or "card_inputs" in context.request or "plan_ref" in context.request:
            raise NodeError("BYTE_PRODUCTION_MOVED",
                            "Concrete card decisions now go directly to hs-knowledge-view-materialize run; P2 accepts authored semantic plans")
        return author_plan(context, context.request)
    if action in {"verify", "rederive"}:
        raise NodeError("BYTE_PRODUCTION_MOVED", "P2 no longer reproduces byte plans; inspect the P3 candidate or run P4 lint")
    if action == "review":
        raise NodeError("CONTENT_REVIEW_MOVED", "Independent content and skip review belongs to P4 hs-knowledge-lint")
    raise NodeError("INVALID_ACTION", "Choose plan for authored P2 decisions", action)
