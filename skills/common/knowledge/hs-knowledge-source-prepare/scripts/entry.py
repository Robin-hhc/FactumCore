"""Standalone P2 entry; all source algorithms live in pinned public contracts."""


def execute(context):
    action = context.args.action or "prepare"
    if action in {"run", "prepare"}:
        return context.modules["source_materials"].execute(context)
    return context.modules["source_operations"].execute(context)
