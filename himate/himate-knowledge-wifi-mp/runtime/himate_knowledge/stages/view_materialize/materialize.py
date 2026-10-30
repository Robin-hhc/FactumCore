"""P3 directly assembles, revises and describes its owned candidate bytes."""

from .support import NodeError


def execute(context):
    production = context.modules["production"]
    action = context.args.action or "run"
    if action == "run":
        return production.assemble(context)
    if action == "revise":
        return production.revise(context)
    if action in {"describe", "inspect"}:
        return production.describe(context)
    raise NodeError("INVALID_ACTION", "Choose run, revise or describe", action)
